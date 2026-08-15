from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timezone

from contracts.agent_run.validator import AgentRunValidationError, validate_run
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError

from .model import (
    OperationOutcome,
    OriginalRunCommand,
    ReplayRunCommand,
    RunKind,
    RunOperationResult,
    RunProvenance,
    RunStatus,
    TransitionCommand,
    TransitionOperationResult,
)
from .repository import ConditionalUpdateMiss, MySqlAgentRunRepository
from .rules import plan_transition


class RunCreationRejected(ValueError):
    pass


class PersistenceIntegrityError(RuntimeError):
    pass


class RunNotFound(LookupError):
    pass


def _new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex.upper()}"


class AgentRunLifecycleService:
    def __init__(
        self,
        engine: Engine,
        *,
        clock: Callable[[], datetime] | None = None,
        run_id_factory: Callable[[], str] | None = None,
        transition_id_factory: Callable[[], str] | None = None,
        transition_request_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repository = MySqlAgentRunRepository(engine)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._run_id_factory = run_id_factory or (lambda: _new_id("RUN-"))
        self._transition_id_factory = transition_id_factory or (lambda: _new_id("TRN-"))
        self._transition_request_id_factory = transition_request_id_factory or (
            lambda: _new_id("TRQ-")
        )

    def create_original_run(
        self,
        command: OriginalRunCommand,
    ) -> RunOperationResult:
        if not self._repository.inbox_event_exists(command.trigger_event_id):
            raise RunCreationRejected("Inbox event does not exist")
        created_at = self._now()
        run_id = self._run_id_factory()
        run = self._initial_run(
            run_id=run_id,
            kind=RunKind.ORIGINAL,
            provenance=command.provenance,
            created_at=created_at,
            original_run_id=run_id,
            trigger_event_id=command.trigger_event_id,
        )
        return self._create_or_classify(
            run,
            self._initial_transition(run_id, created_at),
            lambda: self._repository.find_run_by_trigger_event(
                command.trigger_event_id
            ),
            self._original_matches,
            command,
        )

    def create_replay_run(
        self,
        command: ReplayRunCommand,
    ) -> RunOperationResult:
        original = self._repository.find_run(command.original_run_id)
        source = self._repository.find_run(command.replayed_from_run_id)
        self._validate_replay_lineage(command, original, source)
        created_at = self._now()
        run_id = self._run_id_factory()
        run = self._initial_run(
            run_id=run_id,
            kind=RunKind.REPLAY,
            provenance=command.provenance,
            created_at=created_at,
            original_run_id=command.original_run_id,
            replayed_from_run_id=command.replayed_from_run_id,
            replay_request_id=command.replay_request_id,
        )
        return self._create_or_classify(
            run,
            self._initial_transition(run_id, created_at),
            lambda: self._repository.find_run_by_replay_request(
                command.replay_request_id
            ),
            self._replay_matches,
            command,
        )

    def get_run(self, run_id: str) -> Mapping[str, object] | None:
        row = self._repository.find_run(run_id)
        return None if row is None else self._to_contract(row)

    def transition_run(
        self,
        command: TransitionCommand,
    ) -> TransitionOperationResult:
        current = self._repository.find_run(command.run_id)
        if current is None:
            raise RunNotFound(f"Run does not exist: {command.run_id}")
        if (
            current["status"] != command.expected_status.value
            or current["revision"] != command.expected_revision
        ):
            return self._classify_failed_transition(command)

        occurred_at = self._now()
        current_started_at = current["started_at"]
        assert current_started_at is None or isinstance(
            current_started_at,
            datetime,
        )
        plan = plan_transition(
            command,
            current_started_at=current_started_at,
            occurred_at=occurred_at,
        )
        transition = {
            "transition_id": self._transition_id_factory(),
            "transition_request_id": command.transition_request_id,
            "run_id": command.run_id,
            "from_status": command.expected_status.value,
            "to_status": command.to_status.value,
            "from_revision": command.expected_revision,
            "to_revision": plan.to_revision,
            "actor_kind": command.actor_kind.value,
            "actor_id": command.actor_id,
            "reason_code": command.reason_code,
            "reason_message": command.reason_message,
            "checkpoint_id": command.checkpoint_id,
            "occurred_at": occurred_at,
        }
        update = {
            **transition,
            "expected_status": command.expected_status.value,
            "expected_revision": command.expected_revision,
            "started_at": plan.started_at,
            "ended_at": plan.ended_at,
            "status_reason_message": command.reason_message or command.reason_code,
        }
        try:
            self._repository.apply_transition(update, transition)
        except ConditionalUpdateMiss:
            return self._classify_failed_transition(command)
        except IntegrityError as error:
            classified = self._classify_failed_transition(command)
            if classified.outcome is OperationOutcome.CONCURRENCY_CONFLICT:
                raise PersistenceIntegrityError(
                    "transition history insert violated database constraints"
                ) from error
            return classified

        stored = self.get_run(command.run_id)
        if stored is None:
            raise PersistenceIntegrityError("transitioned Run could not be reloaded")
        return TransitionOperationResult(OperationOutcome.APPLIED, stored)

    def _classify_failed_transition(
        self,
        command: TransitionCommand,
    ) -> TransitionOperationResult:
        existing = self._repository.find_transition_by_request(
            command.transition_request_id
        )
        if existing is None:
            outcome = OperationOutcome.CONCURRENCY_CONFLICT
        elif self._transition_matches(existing, command):
            outcome = OperationOutcome.DUPLICATE_IDENTICAL
        else:
            outcome = OperationOutcome.DUPLICATE_CONFLICTING
        return TransitionOperationResult(outcome, self.get_run(command.run_id))

    def _transition_matches(
        self,
        existing: Mapping[str, object],
        command: TransitionCommand,
    ) -> bool:
        expected = {
            "run_id": command.run_id,
            "from_status": command.expected_status.value,
            "to_status": command.to_status.value,
            "from_revision": command.expected_revision,
            "to_revision": command.expected_revision + 1,
            "actor_kind": command.actor_kind.value,
            "actor_id": command.actor_id,
            "reason_code": command.reason_code,
            "reason_message": command.reason_message,
            "checkpoint_id": command.checkpoint_id,
        }
        return all(existing[column] == value for column, value in expected.items())

    def _create_or_classify(
        self,
        run: Mapping[str, object],
        transition: Mapping[str, object],
        find_existing: Callable[[], Mapping[str, object] | None],
        matches: Callable[[Mapping[str, object], object], bool],
        command: object,
    ) -> RunOperationResult:
        try:
            self._to_contract(run)
        except PersistenceIntegrityError as error:
            raise RunCreationRejected(f"Run Contract is invalid: {error}") from error
        try:
            self._repository.insert_run_with_initial_transition(run, transition)
        except IntegrityError as error:
            existing = find_existing()
            if existing is None:
                raise RunCreationRejected(
                    "Run creation violated database constraints"
                ) from error
            outcome = (
                OperationOutcome.DUPLICATE_IDENTICAL
                if matches(existing, command)
                else OperationOutcome.DUPLICATE_CONFLICTING
            )
            return RunOperationResult(outcome, self._to_contract(existing))
        created = self._repository.find_run(str(run["run_id"]))
        if created is None:
            raise PersistenceIntegrityError("created Run could not be reloaded")
        return RunOperationResult(
            OperationOutcome.APPLIED,
            self._to_contract(created),
        )

    def _initial_run(
        self,
        *,
        run_id: str,
        kind: RunKind,
        provenance: RunProvenance,
        created_at: datetime,
        original_run_id: str,
        trigger_event_id: str | None = None,
        replayed_from_run_id: str | None = None,
        replay_request_id: str | None = None,
    ) -> Mapping[str, object]:
        return {
            "run_id": run_id,
            "contract_version": "1.0.0",
            "run_kind": kind.value,
            "original_run_id": original_run_id,
            "trigger_event_id": trigger_event_id,
            "replayed_from_run_id": replayed_from_run_id,
            "replay_request_id": replay_request_id,
            **self._provenance_parameters(provenance),
            "status": RunStatus.PENDING.value,
            "revision": 0,
            "created_at": created_at,
            "updated_at": created_at,
            "started_at": None,
            "ended_at": None,
            "status_reason_code": None,
            "status_reason_message": None,
            "coordinator_execution_id": None,
            "latest_checkpoint_id": None,
            "agent_execution_count": 0,
            "task_count": 0,
            "completed_task_count": 0,
        }

    def _initial_transition(
        self,
        run_id: str,
        occurred_at: datetime,
    ) -> Mapping[str, object]:
        return {
            "transition_id": self._transition_id_factory(),
            "transition_request_id": self._transition_request_id_factory(),
            "run_id": run_id,
            "from_status": None,
            "to_status": RunStatus.PENDING.value,
            "from_revision": None,
            "to_revision": 0,
            "actor_kind": "SYSTEM",
            "actor_id": "agent-run-lifecycle",
            "reason_code": "RUN_CREATED",
            "reason_message": None,
            "checkpoint_id": None,
            "occurred_at": occurred_at,
        }

    def _validate_replay_lineage(
        self,
        command: ReplayRunCommand,
        original: Mapping[str, object] | None,
        source: Mapping[str, object] | None,
    ) -> None:
        if original is None or source is None:
            raise RunCreationRejected("replay lineage Run does not exist")
        if original["run_kind"] != RunKind.ORIGINAL.value:
            raise RunCreationRejected("original_run_id must identify an original Run")
        if source["original_run_id"] != command.original_run_id:
            raise RunCreationRejected("replay source has a different original Run")
        incidents = {
            original["incident_id"],
            source["incident_id"],
            command.provenance.incident_id,
        }
        if len(incidents) != 1:
            raise RunCreationRejected("replay lineage must belong to the same Incident")

    def _original_matches(
        self,
        existing: Mapping[str, object],
        command: object,
    ) -> bool:
        assert isinstance(command, OriginalRunCommand)
        return (
            existing["run_kind"] == RunKind.ORIGINAL.value
            and existing["trigger_event_id"] == command.trigger_event_id
            and self._provenance_matches(existing, command.provenance)
        )

    def _replay_matches(
        self,
        existing: Mapping[str, object],
        command: object,
    ) -> bool:
        assert isinstance(command, ReplayRunCommand)
        return (
            existing["run_kind"] == RunKind.REPLAY.value
            and existing["original_run_id"] == command.original_run_id
            and existing["replayed_from_run_id"] == command.replayed_from_run_id
            and existing["replay_request_id"] == command.replay_request_id
            and self._provenance_matches(existing, command.provenance)
        )

    def _provenance_matches(
        self,
        existing: Mapping[str, object],
        provenance: RunProvenance,
    ) -> bool:
        return all(
            existing[column] == expected
            for column, expected in self._provenance_parameters(provenance).items()
        )

    def _provenance_parameters(
        self,
        provenance: RunProvenance,
    ) -> Mapping[str, str]:
        return {
            "incident_id": provenance.incident_id,
            "runtime_version": provenance.runtime_version,
            "workflow_version": provenance.workflow_version,
            "prompt_set_version": provenance.prompt_set_version,
            "model_policy_version": provenance.model_policy_version,
            "tool_policy_version": provenance.tool_policy_version,
            "context_policy_version": provenance.context_policy_version,
            "code_revision": provenance.code_revision,
        }

    def _to_contract(self, row: Mapping[str, object]) -> Mapping[str, object]:
        identity: dict[str, object] = {
            "run_id": row["run_id"],
            "run_kind": row["run_kind"],
            "original_run_id": row["original_run_id"],
        }
        if row["run_kind"] == RunKind.ORIGINAL.value:
            identity["trigger_event_id"] = row["trigger_event_id"]
        else:
            identity["replayed_from_run_id"] = row["replayed_from_run_id"]
            identity["replay_request_id"] = row["replay_request_id"]

        lifecycle: dict[str, object] = {
            "status": row["status"],
            "revision": row["revision"],
            "updated_at": self._format_timestamp(row["updated_at"]),
            "status_reason": None,
        }
        if row["started_at"] is not None:
            lifecycle["started_at"] = self._format_timestamp(row["started_at"])
        if row["ended_at"] is not None:
            lifecycle["ended_at"] = self._format_timestamp(row["ended_at"])
        if row["status_reason_code"] is not None:
            lifecycle["status_reason"] = {
                "code": row["status_reason_code"],
                "message": row["status_reason_message"] or row["status_reason_code"],
            }

        contract = {
            "contract_version": row["contract_version"],
            "identity": identity,
            "provenance": {
                "incident_id": row["incident_id"],
                "runtime_version": row["runtime_version"],
                "workflow_version": row["workflow_version"],
                "prompt_set_version": row["prompt_set_version"],
                "model_policy_version": row["model_policy_version"],
                "tool_policy_version": row["tool_policy_version"],
                "context_policy_version": row["context_policy_version"],
                "code_revision": row["code_revision"],
                "created_at": self._format_timestamp(row["created_at"]),
            },
            "lifecycle": lifecycle,
            "execution_refs": {
                "coordinator_execution_id": row["coordinator_execution_id"],
                "latest_checkpoint_id": row["latest_checkpoint_id"],
            },
            "progress": {
                "agent_execution_count": row["agent_execution_count"],
                "task_count": row["task_count"],
                "completed_task_count": row["completed_task_count"],
            },
        }
        try:
            validate_run(contract)
        except AgentRunValidationError as error:
            raise PersistenceIntegrityError(
                f"stored Run violates Contract: {error}"
            ) from error
        return contract

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware UTC datetime")
        return value.astimezone(timezone.utc)

    def _format_timestamp(self, value: object) -> str:
        assert isinstance(value, datetime)
        aware = (
            value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        )
        return (
            aware.astimezone(timezone.utc)
            .isoformat(timespec="microseconds")
            .replace("+00:00", "Z")
        )
