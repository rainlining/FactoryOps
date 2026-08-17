from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from contracts.agent_task.validator import compute_task_key
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError

from factoryops_agent_service.task_lifecycle.service import AgentTaskLifecycleService

from .model import DispatchCommand, DispatchOutcome, DispatchResult
from .repository import (
    CoordinatorExecutionRejected,
    MySqlCoordinatorTaskDispatchRepository,
)


def _id(prefix: str) -> str:
    return prefix + uuid.uuid4().hex.upper()


class CoordinatorTaskDispatchService:
    def __init__(
        self, engine: Engine, *, clock: Callable[[], datetime] | None = None
    ) -> None:
        self._repository = MySqlCoordinatorTaskDispatchRepository(engine)
        self._tasks = AgentTaskLifecycleService(engine)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def dispatch(self, command: DispatchCommand) -> DispatchResult:
        existing = self._repository.find_by_request(command.task_request_id)
        digest = self._digest(command)
        if existing is not None:
            return self._classify(existing, command, digest)
        now = self._now()
        task_id = _id("TSK-")
        task = {
            "task_id": task_id,
            "task_request_id": command.task_request_id,
            "task_key": compute_task_key(command.run_id, command.task_request_id),
            "contract_version": "1.0.0",
            "run_id": command.run_id,
            "task_type": command.task_type,
            "target_agent_role": command.target_agent_role,
            "created_by_execution_id": command.coordinator_execution_id,
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
        self._tasks._validate(task, ValueError)
        history = {
            "transition_id": _id("TTR-"),
            "transition_request_id": _id("TQR-"),
            "task_id": task_id,
            "from_status": None,
            "to_status": "PENDING",
            "from_revision": None,
            "to_revision": 0,
            "actor_kind": "COORDINATOR",
            "actor_id": command.coordinator_execution_id,
            "reason_code": "TASK_DISPATCHED",
            "reason_message": "Task dispatched by Coordinator",
            "execution_id": None,
            "attempt_count": 0,
            "completion_execution_id": None,
            "failure_code": None,
            "failure_message": None,
            "failure_recoverability": None,
            "occurred_at": now,
        }
        execution_history = {
            "transition_id": _id("ETR-"),
            "transition_request_id": _id("ERQ-"),
            "execution_id": command.coordinator_execution_id,
            "from_status": "PENDING",
            "to_status": "RUNNING",
            "from_revision": 0,
            "to_revision": 1,
            "actor_kind": "COORDINATOR",
            "actor_id": command.coordinator_execution_id,
            "reason_code": "COORDINATOR_EXECUTION_STARTED",
            "reason_message": "Coordinator execution started",
            "result_json": None,
            "failure_json": None,
            "occurred_at": now,
        }
        try:
            self._repository.dispatch(
                task, command.dependency_task_ids, history, execution_history
            )
        except CoordinatorExecutionRejected:
            raise
        except IntegrityError:
            existing = self._repository.find_by_request(command.task_request_id)
            if existing is None:
                raise
            return self._classify(existing, command, digest)
        return DispatchResult(DispatchOutcome.APPLIED, self._tasks.get_task(task_id))

    def _classify(
        self, row: dict[str, object], command: DispatchCommand, digest: bytes
    ) -> DispatchResult:
        stored = self._digest_row(row)
        outcome = (
            DispatchOutcome.DUPLICATE_IDENTICAL
            if stored == digest
            else DispatchOutcome.DUPLICATE_CONFLICTING
        )
        return DispatchResult(outcome, self._tasks.get_task(str(row["task_id"])))

    @staticmethod
    def _digest(command: DispatchCommand) -> bytes:
        payload = {
            "task_request_id": command.task_request_id,
            "run_id": command.run_id,
            "task_type": command.task_type,
            "target_agent_role": command.target_agent_role,
            "created_by_execution_id": command.coordinator_execution_id,
            "priority": command.priority,
            "context_snapshot_id": command.context_snapshot_id,
            "evidence_refs": list(command.evidence_refs),
            "dependency_task_ids": list(command.dependency_task_ids),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).digest()

    @staticmethod
    def _digest_row(row: dict[str, object]) -> bytes:
        payload = {
            k: row[k]
            for k in (
                "task_request_id",
                "run_id",
                "task_type",
                "target_agent_role",
                "created_by_execution_id",
                "priority",
                "context_snapshot_id",
            )
        }
        payload["evidence_refs"] = json.loads(row["evidence_refs"])
        payload["dependency_task_ids"] = list(row.get("dependency_task_ids", ()))
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).digest()

    def _now(self) -> datetime:
        value = self._clock()
        return (
            value.astimezone(timezone.utc)
            if value.tzinfo
            else (_ for _ in ()).throw(ValueError("clock must be timezone-aware"))
        )
