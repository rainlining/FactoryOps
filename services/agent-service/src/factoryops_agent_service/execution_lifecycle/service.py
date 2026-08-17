from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timezone

from contracts.agent_execution.validator import (
    AgentExecutionValidationError,
    compute_execution_key,
    validate_execution,
)
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError

from .model import (
    CreateExecutionCommand,
    OperationOutcome,
    OperationResult,
    TransitionCommand,
)
from .repository import (
    ConditionalUpdateMiss,
    MySqlAgentExecutionRepository,
    ParentRunMissing,
    ParentTaskMismatch,
    ParentTaskMissing,
)
from .rules import LifecycleRuleViolation, plan_transition


class ExecutionCreationRejected(ValueError):
    pass


class ExecutionNotFound(LookupError):
    pass


class PersistenceIntegrityError(RuntimeError):
    pass


def _id(prefix: str) -> str:
    return prefix + uuid.uuid4().hex.upper()


class AgentExecutionLifecycleService:
    def __init__(
        self,
        engine: Engine,
        *,
        clock: Callable[[], datetime] | None = None,
        execution_id_factory: Callable[[], str] | None = None,
        transition_id_factory: Callable[[], str] | None = None,
        transition_request_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repository = MySqlAgentExecutionRepository(engine)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._execution_id_factory = execution_id_factory or (lambda: _id("EXE-"))
        self._transition_id_factory = transition_id_factory or (lambda: _id("ETR-"))
        self._transition_request_id_factory = transition_request_id_factory or (
            lambda: _id("ERQ-")
        )

    def create_execution(self, command: CreateExecutionCommand) -> OperationResult:
        key = compute_execution_key(
            command.run_id, command.agent_role, command.task_id, command.attempt
        )
        existing = self._repository.find_by_key(key)
        if existing:
            return self._classify_creation(existing, command)
        now = self._now()
        row = {
            **command.__dict__,
            "execution_id": self._execution_id_factory(),
            "execution_key": key,
            "contract_version": "1.0.0",
            "input_evidence_refs": json.dumps(command.evidence_refs),
            "status": "PENDING",
            "revision": 0,
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "ended_at": None,
            "status_reason_code": None,
            "status_reason_message": None,
            "output_artifact_refs": None,
            "decision_id": None,
            "result_evidence_refs": None,
            "failure_code": None,
            "failure_message": None,
            "failure_recoverability": None,
            "failed_dependency_ref": None,
        }
        row.pop("evidence_refs")
        self._validate(row, ExecutionCreationRejected)
        transition = self._history(
            self._transition_request_id_factory(),
            row["execution_id"],
            None,
            "PENDING",
            None,
            0,
            "SYSTEM",
            "agent-execution-lifecycle",
            "EXECUTION_CREATED",
            None,
            None,
            None,
            now,
        )
        try:
            self._repository.create(row, transition)
        except ParentRunMissing as error:
            raise ExecutionCreationRejected("parent Run does not exist") from error
        except ParentTaskMissing as error:
            raise ExecutionCreationRejected("parent Task does not exist") from error
        except ParentTaskMismatch as error:
            raise ExecutionCreationRejected(
                "Task must share Run and target role"
            ) from error
        except IntegrityError as error:
            existing = self._repository.find_by_key(key)
            if existing:
                return self._classify_creation(existing, command)
            raise ExecutionCreationRejected(
                "Execution creation violated database constraints"
            ) from error
        return OperationResult(
            OperationOutcome.APPLIED, self.get_execution(str(row["execution_id"]))
        )

    def get_execution(self, execution_id: str) -> Mapping[str, object] | None:
        row = self._repository.find(execution_id)
        return None if row is None else self._to_contract(row)

    def transition_execution(self, command: TransitionCommand) -> OperationResult:
        existing = self._repository.find_transition(command.transition_request_id)
        if existing:
            return self._classify_transition(existing, command)
        current = self._repository.find(command.execution_id)
        if current is None:
            raise ExecutionNotFound(command.execution_id)
        if (
            current["status"] != command.expected_status.value
            or current["revision"] != command.expected_revision
        ):
            existing = self._repository.find_transition(command.transition_request_id)
            return (
                self._classify_transition(existing, command)
                if existing
                else OperationResult(
                    OperationOutcome.CONCURRENCY_CONFLICT, self._to_contract(current)
                )
            )
        now = self._now()
        plan = plan_transition(
            command, started_at=current["started_at"], occurred_at=now
        )
        result, failure = command.result, command.failure
        candidate = {
            **current,
            "status": command.to_status.value,
            "revision": plan.revision,
            "updated_at": now,
            "started_at": plan.started_at,
            "ended_at": plan.ended_at,
            "status_reason_code": command.reason_code,
            "status_reason_message": command.reason_message,
            "output_artifact_refs": json.dumps(result["output_artifact_refs"])
            if result
            else None,
            "decision_id": result["decision_id"] if result else None,
            "result_evidence_refs": json.dumps(result["evidence_refs"])
            if result
            else None,
            "failure_code": failure["code"] if failure else None,
            "failure_message": failure["message"] if failure else None,
            "failure_recoverability": failure["recoverability"] if failure else None,
            "failed_dependency_ref": failure["failed_dependency_ref"]
            if failure
            else None,
        }
        self._validate(candidate, LifecycleRuleViolation)
        history = self._history(
            command.transition_request_id,
            command.execution_id,
            command.expected_status.value,
            command.to_status.value,
            command.expected_revision,
            plan.revision,
            command.actor_kind,
            command.actor_id,
            command.reason_code,
            command.reason_message,
            result,
            failure,
            now,
        )
        update = {
            **candidate,
            **history,
            "expected_status": command.expected_status.value,
            "expected_revision": command.expected_revision,
            "to_revision": plan.revision,
            "occurred_at": now,
        }
        try:
            self._repository.apply(update, history)
        except ConditionalUpdateMiss:
            existing = self._repository.find_transition(command.transition_request_id)
            return (
                self._classify_transition(existing, command)
                if existing
                else OperationResult(
                    OperationOutcome.CONCURRENCY_CONFLICT,
                    self.get_execution(command.execution_id),
                )
            )
        except IntegrityError:
            existing = self._repository.find_transition(command.transition_request_id)
            if existing:
                return self._classify_transition(existing, command)
            raise
        return OperationResult(
            OperationOutcome.APPLIED, self.get_execution(command.execution_id)
        )

    def _classify_creation(
        self, row: Mapping[str, object], command: CreateExecutionCommand
    ) -> OperationResult:
        fields = (
            "run_id",
            "agent_role",
            "attempt",
            "task_id",
            "runtime_version",
            "prompt_version",
            "model_policy_version",
            "tool_policy_version",
            "context_policy_version",
            "code_revision",
            "context_snapshot_id",
        )
        same = (
            all(row[k] == getattr(command, k) for k in fields)
            and tuple(json.loads(row["input_evidence_refs"])) == command.evidence_refs
        )
        return OperationResult(
            OperationOutcome.DUPLICATE_IDENTICAL
            if same
            else OperationOutcome.DUPLICATE_CONFLICTING,
            self._to_contract(row),
        )

    def _classify_transition(
        self, row: Mapping[str, object], command: TransitionCommand
    ) -> OperationResult:
        same = (
            row["execution_id"],
            row["from_status"],
            row["to_status"],
            row["from_revision"],
            row["actor_kind"],
            row["actor_id"],
            row["reason_code"],
            row["reason_message"],
            row["result_json"],
            row["failure_json"],
        ) == (
            command.execution_id,
            command.expected_status.value,
            command.to_status.value,
            command.expected_revision,
            command.actor_kind,
            command.actor_id,
            command.reason_code,
            command.reason_message,
            json.dumps(command.result, sort_keys=True) if command.result else None,
            json.dumps(command.failure, sort_keys=True) if command.failure else None,
        )
        return OperationResult(
            OperationOutcome.DUPLICATE_IDENTICAL
            if same
            else OperationOutcome.DUPLICATE_CONFLICTING,
            self.get_execution(str(row["execution_id"])),
        )

    def _to_contract(self, row: Mapping[str, object]) -> Mapping[str, object]:
        def load(value: object) -> object:
            return json.loads(value) if isinstance(value, str) else value

        lifecycle = {
            "status": row["status"],
            "revision": row["revision"],
            "updated_at": self._time(row["updated_at"]),
            "status_reason": None,
        }
        for k in ("started_at", "ended_at"):
            if row[k] is not None:
                lifecycle[k] = self._time(row[k])
        if row["status_reason_code"]:
            lifecycle["status_reason"] = {
                "code": row["status_reason_code"],
                "message": row["status_reason_message"],
            }
        contract = {
            "contract_version": row["contract_version"],
            "identity": {
                "execution_id": row["execution_id"],
                "execution_key": row["execution_key"],
                "run_id": row["run_id"],
                "agent_role": row["agent_role"],
                "attempt": row["attempt"],
            },
            "provenance": {
                "runtime_version": row["runtime_version"],
                "prompt_version": row["prompt_version"],
                "model_policy_version": row["model_policy_version"],
                "tool_policy_version": row["tool_policy_version"],
                "context_policy_version": row["context_policy_version"],
                "code_revision": row["code_revision"],
                "created_at": self._time(row["created_at"]),
            },
            "input": {
                "task_id": row["task_id"],
                "context_snapshot_id": row["context_snapshot_id"],
                "evidence_refs": load(row["input_evidence_refs"]),
            },
            "lifecycle": lifecycle,
            "result": None,
            "failure": None,
        }
        if row["output_artifact_refs"] is not None:
            contract["result"] = {
                "output_artifact_refs": load(row["output_artifact_refs"]),
                "decision_id": row["decision_id"],
                "evidence_refs": load(row["result_evidence_refs"]),
            }
        if row["failure_code"] is not None:
            contract["failure"] = {
                "code": row["failure_code"],
                "message": row["failure_message"],
                "recoverability": row["failure_recoverability"],
                "failed_dependency_ref": row["failed_dependency_ref"],
            }
        try:
            validate_execution(contract)
        except AgentExecutionValidationError as error:
            raise PersistenceIntegrityError(
                f"stored Execution violates Contract: {error}"
            ) from error
        return contract

    def _validate(
        self, row: Mapping[str, object], error_type: type[ValueError]
    ) -> None:
        try:
            self._to_contract(row)
        except PersistenceIntegrityError as error:
            raise error_type(f"Execution Contract is invalid: {error}") from error

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("clock must be timezone-aware")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _time(value: object) -> str:
        assert isinstance(value, datetime)
        return (
            (value if value.tzinfo else value.replace(tzinfo=timezone.utc))
            .astimezone(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )

    def _history(
        self,
        request: str,
        execution: str,
        source: str | None,
        target: str,
        from_rev: int | None,
        to_rev: int,
        actor_kind: str,
        actor_id: str,
        reason: str,
        message: str | None,
        result: Mapping[str, object] | None,
        failure: Mapping[str, object] | None,
        occurred: datetime,
    ) -> dict[str, object]:
        return {
            "transition_id": self._transition_id_factory(),
            "transition_request_id": request,
            "execution_id": execution,
            "from_status": source,
            "to_status": target,
            "from_revision": from_rev,
            "to_revision": to_rev,
            "actor_kind": actor_kind,
            "actor_id": actor_id,
            "reason_code": reason,
            "reason_message": message,
            "result_json": json.dumps(result, sort_keys=True) if result else None,
            "failure_json": json.dumps(failure, sort_keys=True) if failure else None,
            "occurred_at": occurred,
        }
