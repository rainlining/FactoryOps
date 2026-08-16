from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timezone

from contracts.agent_task.validator import (
    AgentTaskValidationError,
    compute_task_key,
    validate_task,
)
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError

from .model import (
    CreateTaskCommand,
    OperationOutcome,
    OperationResult,
    TaskStatus,
    TransitionCommand,
)
from .repository import (
    ConditionalUpdateMiss,
    CrossRunDependency,
    DependencyMissing,
    MySqlAgentTaskRepository,
    ParentRunMissing,
)
from .rules import LifecycleRuleViolation, plan_transition


class TaskCreationRejected(ValueError):
    pass


class TaskNotFound(LookupError):
    pass


class PersistenceIntegrityError(RuntimeError):
    pass


def _id(prefix: str) -> str:
    return prefix + uuid.uuid4().hex.upper()


class AgentTaskLifecycleService:
    def __init__(
        self,
        engine: Engine,
        *,
        clock: Callable[[], datetime] | None = None,
        task_id_factory: Callable[[], str] | None = None,
        transition_id_factory: Callable[[], str] | None = None,
        transition_request_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repository = MySqlAgentTaskRepository(engine)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._task_id_factory = task_id_factory or (lambda: _id("TSK-"))
        self._transition_id_factory = transition_id_factory or (lambda: _id("TTR-"))
        self._transition_request_id_factory = transition_request_id_factory or (
            lambda: _id("TRQ-")
        )

    def create_task(self, command: CreateTaskCommand) -> OperationResult:
        existing = self._repository.find_by_request(command.task_request_id)
        if existing is not None:
            return self._classify_creation(existing, command)
        now, task_id = self._now(), self._task_id_factory()
        if task_id in command.dependency_task_ids:
            raise TaskCreationRejected("Task cannot depend on itself")
        task = {
            "task_id": task_id,
            "task_request_id": command.task_request_id,
            "task_key": compute_task_key(command.run_id, command.task_request_id),
            "contract_version": "1.0.0",
            "run_id": command.run_id,
            "task_type": command.task_type,
            "target_agent_role": command.target_agent_role,
            "created_by_execution_id": command.created_by_execution_id,
            "priority": command.priority,
            "context_snapshot_id": command.context_snapshot_id,
            "evidence_refs": json.dumps(command.evidence_refs),
            "dependency_task_ids": command.dependency_task_ids,
            "status": "PENDING",
            "revision": 0,
            "created_at": now,
            "updated_at": now,
            "started_at": None,
            "ended_at": None,
            "status_reason_code": None,
            "status_reason_message": None,
            "current_execution_id": None,
            "attempt_count": 0,
            "completion_execution_id": None,
            "failure_execution_id": None,
            "failure_code": None,
            "failure_message": None,
            "failure_recoverability": None,
        }
        self._validate(task, TaskCreationRejected)
        transition = self._transition_row(
            self._transition_request_id_factory(),
            task_id,
            None,
            "PENDING",
            None,
            0,
            "SYSTEM",
            "agent-task-lifecycle",
            "TASK_CREATED",
            None,
            None,
            0,
            None,
            None,
            None,
            None,
            now,
        )
        try:
            self._repository.create(task, command.dependency_task_ids, transition)
        except ParentRunMissing as error:
            raise TaskCreationRejected("parent Run does not exist") from error
        except DependencyMissing as error:
            raise TaskCreationRejected("dependency Task does not exist") from error
        except CrossRunDependency as error:
            raise TaskCreationRejected(
                "dependency Task must belong to same Run"
            ) from error
        except IntegrityError as error:
            existing = self._repository.find_by_request(command.task_request_id)
            if existing is None:
                raise TaskCreationRejected(
                    "Task creation violated database constraints"
                ) from error
            return self._classify_creation(existing, command)
        return OperationResult(OperationOutcome.APPLIED, self.get_task(task_id))

    def get_task(self, task_id: str) -> Mapping[str, object] | None:
        row = self._repository.find_task(task_id)
        return None if row is None else self._to_contract(row)

    def transition_task(self, command: TransitionCommand) -> OperationResult:
        existing = self._repository.find_transition(command.transition_request_id)
        if existing is not None:
            return self._classify_transition(existing, command)
        current = self._repository.find_task(command.task_id)
        if current is None:
            existing = self._repository.find_transition(command.transition_request_id)
            if existing is not None:
                return self._classify_transition(existing, command)
            raise TaskNotFound(command.task_id)
        if (
            current["status"] != command.expected_status.value
            or current["revision"] != command.expected_revision
        ):
            existing = self._repository.find_transition(command.transition_request_id)
            if existing is not None:
                return self._classify_transition(existing, command)
            return OperationResult(
                OperationOutcome.CONCURRENCY_CONFLICT, self._to_contract(current)
            )
        now = self._now()
        try:
            plan = plan_transition(
                command,
                current_started_at=current["started_at"],
                current_execution_id=current["current_execution_id"],
                current_attempt_count=int(current["attempt_count"]),
                occurred_at=now,
            )
        except LifecycleRuleViolation:
            existing = self._repository.find_transition(command.transition_request_id)
            if existing is not None:
                return self._classify_transition(existing, command)
            raise
        failure_execution = (
            plan.current_execution_id
            if command.to_status is TaskStatus.FAILED
            else None
        )
        candidate = {
            **current,
            "status": command.to_status.value,
            "revision": plan.to_revision,
            "updated_at": now,
            "started_at": plan.started_at,
            "ended_at": plan.ended_at,
            "status_reason_code": command.reason_code,
            "status_reason_message": command.reason_message,
            "current_execution_id": plan.current_execution_id,
            "attempt_count": plan.attempt_count,
            "completion_execution_id": command.completion_execution_id,
            "failure_execution_id": failure_execution,
            "failure_code": command.failure_code,
            "failure_message": command.failure_message,
            "failure_recoverability": command.failure_recoverability,
        }
        self._validate(candidate, LifecycleRuleViolation)
        transition = self._transition_row(
            command.transition_request_id,
            command.task_id,
            command.expected_status.value,
            command.to_status.value,
            command.expected_revision,
            plan.to_revision,
            command.actor_kind,
            command.actor_id,
            command.reason_code,
            command.reason_message,
            plan.current_execution_id,
            plan.attempt_count,
            command.completion_execution_id,
            command.failure_code,
            command.failure_message,
            command.failure_recoverability,
            now,
        )
        update = {
            **transition,
            "expected_status": command.expected_status.value,
            "expected_revision": command.expected_revision,
            "started_at": plan.started_at,
            "ended_at": plan.ended_at,
            "failure_execution_id": failure_execution,
        }
        try:
            self._repository.apply_transition(update, transition)
        except ConditionalUpdateMiss:
            existing = self._repository.find_transition(command.transition_request_id)
            return (
                self._classify_transition(existing, command)
                if existing
                else OperationResult(
                    OperationOutcome.CONCURRENCY_CONFLICT,
                    self.get_task(command.task_id),
                )
            )
        except IntegrityError:
            existing = self._repository.find_transition(command.transition_request_id)
            if existing:
                return self._classify_transition(existing, command)
            raise
        return OperationResult(OperationOutcome.APPLIED, self.get_task(command.task_id))

    def _classify_creation(
        self, row: Mapping[str, object], command: CreateTaskCommand
    ) -> OperationResult:
        same = (
            row["run_id"],
            row["task_type"],
            row["target_agent_role"],
            row["created_by_execution_id"],
            row["priority"],
            row["context_snapshot_id"],
            tuple(json.loads(row["evidence_refs"])),
            tuple(row["dependency_task_ids"]),
        ) == (
            command.run_id,
            command.task_type,
            command.target_agent_role,
            command.created_by_execution_id,
            command.priority,
            command.context_snapshot_id,
            command.evidence_refs,
            command.dependency_task_ids,
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
        fields = (
            "task_id",
            "from_status",
            "to_status",
            "from_revision",
            "actor_kind",
            "actor_id",
            "reason_code",
            "reason_message",
            "completion_execution_id",
            "failure_code",
            "failure_message",
            "failure_recoverability",
        )
        values = (
            command.task_id,
            command.expected_status.value,
            command.to_status.value,
            command.expected_revision,
            command.actor_kind,
            command.actor_id,
            command.reason_code,
            command.reason_message,
            command.completion_execution_id,
            command.failure_code,
            command.failure_message,
            command.failure_recoverability,
        )
        same = all(row[key] == value for key, value in zip(fields, values))
        if command.to_status in {
            TaskStatus.RUNNING,
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
        }:
            same = same and row["execution_id"] == command.execution_id
        return OperationResult(
            OperationOutcome.DUPLICATE_IDENTICAL
            if same
            else OperationOutcome.DUPLICATE_CONFLICTING,
            self.get_task(str(row["task_id"])),
        )

    def _to_contract(self, row: Mapping[str, object]) -> Mapping[str, object]:
        lifecycle = {
            "status": row["status"],
            "revision": row["revision"],
            "created_at": self._time(row["created_at"]),
            "updated_at": self._time(row["updated_at"]),
            "status_reason": None,
        }
        for key in ("started_at", "ended_at"):
            if row[key] is not None:
                lifecycle[key] = self._time(row[key])
        if row["status_reason_code"] is not None:
            lifecycle["status_reason"] = {
                "code": row["status_reason_code"],
                "message": row["status_reason_message"],
            }
        evidence = row["evidence_refs"]
        if isinstance(evidence, str):
            evidence = json.loads(evidence)
        contract = {
            "contract_version": row["contract_version"],
            "identity": {
                "task_id": row["task_id"],
                "task_request_id": row["task_request_id"],
                "task_key": row["task_key"],
                "run_id": row["run_id"],
            },
            "assignment": {
                "task_type": row["task_type"],
                "target_agent_role": row["target_agent_role"],
                "created_by_execution_id": row["created_by_execution_id"],
                "priority": row["priority"],
            },
            "input": {
                "context_snapshot_id": row["context_snapshot_id"],
                "evidence_refs": list(evidence),
                "dependency_task_ids": list(row["dependency_task_ids"]),
            },
            "lifecycle": lifecycle,
            "execution": {
                "current_execution_id": row["current_execution_id"],
                "attempt_count": row["attempt_count"],
            },
            "completion": None,
            "failure": None,
        }
        if row["completion_execution_id"]:
            contract["completion"] = {
                "successful_execution_id": row["completion_execution_id"]
            }
        if row["failure_execution_id"]:
            contract["failure"] = {
                "failed_execution_id": row["failure_execution_id"],
                "code": row["failure_code"],
                "message": row["failure_message"],
                "recoverability": row["failure_recoverability"],
            }
        result_fields = (
            row["failure_code"],
            row["failure_message"],
            row["failure_recoverability"],
        )
        if row["failure_execution_id"] is None and any(
            value is not None for value in result_fields
        ):
            raise PersistenceIntegrityError(
                "stored Task has failure details without a failure execution"
            )
        try:
            validate_task(contract)
        except AgentTaskValidationError as error:
            raise PersistenceIntegrityError(
                f"stored Task violates Contract: {error}"
            ) from error
        return contract

    def _validate(
        self, row: Mapping[str, object], error_type: type[ValueError]
    ) -> None:
        try:
            self._to_contract(row)
        except PersistenceIntegrityError as error:
            raise error_type(f"Task Contract is invalid: {error}") from error

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

    def _transition_row(
        self,
        request: str,
        task: str,
        source: str | None,
        target: str,
        from_rev: int | None,
        to_rev: int,
        actor_kind: str,
        actor_id: str,
        reason: str,
        message: str | None,
        execution: str | None,
        attempts: int,
        completion: str | None,
        failure_code: str | None,
        failure_message: str | None,
        recoverability: str | None,
        occurred: datetime,
    ) -> dict[str, object]:
        return {
            "transition_id": self._transition_id_factory(),
            "transition_request_id": request,
            "task_id": task,
            "from_status": source,
            "to_status": target,
            "from_revision": from_rev,
            "to_revision": to_rev,
            "actor_kind": actor_kind,
            "actor_id": actor_id,
            "reason_code": reason,
            "reason_message": message,
            "execution_id": execution,
            "attempt_count": attempts,
            "completion_execution_id": completion,
            "failure_code": failure_code,
            "failure_message": failure_message,
            "failure_recoverability": recoverability,
            "occurred_at": occurred,
        }
