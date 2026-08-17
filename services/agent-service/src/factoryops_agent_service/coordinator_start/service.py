from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable, Mapping
from datetime import datetime, timezone

from contracts.agent_execution.validator import compute_execution_key
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError

from factoryops_agent_service.execution_lifecycle.service import (
    AgentExecutionLifecycleService,
)
from factoryops_agent_service.run_lifecycle.service import AgentRunLifecycleService

from .model import StartCoordinatorCommand, StartOutcome, StartResult
from .repository import MySqlCoordinatorStartRepository, RunMissing, RunNotStartable

__all__ = ["CoordinatorStartService", "StartOutcome"]


def _id(prefix: str) -> str:
    return prefix + uuid.uuid4().hex.upper()


class CoordinatorStartService:
    def __init__(
        self,
        engine: Engine,
        *,
        clock: Callable[[], datetime] | None = None,
        execution_id_factory: Callable[[], str] | None = None,
        transition_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._repository = MySqlCoordinatorStartRepository(engine)
        self._runs = AgentRunLifecycleService(engine)
        self._executions = AgentExecutionLifecycleService(engine)
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._execution_id = execution_id_factory or (lambda: _id("EXE-"))
        self._transition_id = transition_id_factory or (lambda: _id("TRN-"))

    def start(self, command: StartCoordinatorCommand) -> StartResult:
        if command.command_version != "1.0.0":
            raise ValueError("unsupported Coordinator start command version")
        if not re.fullmatch(r"SRQ-[0-9A-F]{32}", command.start_request_id):
            raise ValueError("start_request_id must match SRQ-[0-9A-F]{32}")
        digest = self._digest(command)
        existing = self._repository.find_receipt(command.start_request_id)
        if existing is not None:
            return self._from_receipt(existing, digest)
        run = self._repository.find_run(command.run_id)
        if run is None:
            raise RunMissing(command.run_id)
        now = self._now()
        execution_id = self._execution_id()
        execution = self._execution_row(command, run, execution_id, now)
        self._executions._validate(execution, ValueError)
        run_candidate = {
            **run,
            "status": "RUNNING",
            "revision": 1,
            "updated_at": now,
            "started_at": now,
            "status_reason_code": "COORDINATOR_STARTED",
            "status_reason_message": "Coordinator execution started",
            "coordinator_execution_id": execution_id,
            "agent_execution_count": 1,
        }
        self._runs._to_contract(run_candidate)
        execution_history = {
            "transition_id": self._transition_id(),
            "transition_request_id": _id("ERQ-"),
            "execution_id": execution_id,
            "from_status": None,
            "to_status": "PENDING",
            "from_revision": None,
            "to_revision": 0,
            "actor_kind": "SYSTEM",
            "actor_id": "coordinator-start",
            "reason_code": "EXECUTION_CREATED",
            "reason_message": None,
            "result_json": None,
            "failure_json": None,
            "occurred_at": now,
        }
        run_history = {
            "transition_id": self._transition_id(),
            "transition_request_id": command.start_request_id,
            "run_id": command.run_id,
            "from_status": "PENDING",
            "to_status": "RUNNING",
            "from_revision": 0,
            "to_revision": 1,
            "actor_kind": "SYSTEM",
            "actor_id": "coordinator-start",
            "reason_code": "COORDINATOR_STARTED",
            "reason_message": "Coordinator execution started",
            "checkpoint_id": None,
            "occurred_at": now,
        }
        receipt = {
            "start_request_id": command.start_request_id,
            "run_id": command.run_id,
            "execution_id": execution_id,
            "payload_sha256": digest,
            "created_at": now,
        }
        try:
            self._repository.start(
                run_id=command.run_id,
                execution=execution,
                execution_history=execution_history,
                run_history=run_history,
                receipt=receipt,
            )
        except RunNotStartable:
            existing = self._repository.find_receipt(command.start_request_id)
            return (
                self._from_receipt(existing, digest)
                if existing
                else self._result(
                    StartOutcome.CONCURRENCY_CONFLICT, command.run_id, None
                )
            )
        except IntegrityError:
            existing = self._repository.find_receipt(command.start_request_id)
            if existing is not None:
                return self._from_receipt(existing, digest)
            competing = self._repository.find_execution_by_key(
                str(execution["execution_key"])
            )
            if competing is not None:
                return self._result(
                    StartOutcome.CONCURRENCY_CONFLICT,
                    command.run_id,
                    str(competing["execution_id"]),
                )
            raise
        return self._result(StartOutcome.APPLIED, command.run_id, execution_id)

    def _from_receipt(
        self, receipt: Mapping[str, object], digest: bytes
    ) -> StartResult:
        outcome = (
            StartOutcome.DUPLICATE_IDENTICAL
            if receipt["payload_sha256"] == digest
            else StartOutcome.DUPLICATE_CONFLICTING
        )
        return self._result(
            outcome, str(receipt["run_id"]), str(receipt["execution_id"])
        )

    def _result(
        self, outcome: StartOutcome, run_id: str, execution_id: str | None
    ) -> StartResult:
        run = self._runs.get_run(run_id)
        if execution_id is None and run is not None:
            execution_id = run["execution_refs"]["coordinator_execution_id"]
        execution = (
            self._executions.get_execution(execution_id) if execution_id else None
        )
        return StartResult(outcome, run, execution)

    @staticmethod
    def _digest(command: StartCoordinatorCommand) -> bytes:
        payload = {
            "command_version": command.command_version,
            "run_id": command.run_id,
            "prompt_version": command.prompt_version,
            "context_snapshot_id": command.context_snapshot_id,
            "evidence_refs": list(command.evidence_refs),
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).digest()

    @staticmethod
    def _execution_row(
        command: StartCoordinatorCommand,
        run: Mapping[str, object],
        execution_id: str,
        now: datetime,
    ) -> dict[str, object]:
        return {
            "execution_id": execution_id,
            "execution_key": compute_execution_key(
                command.run_id, "coordinator", None, 1
            ),
            "contract_version": "1.0.0",
            "run_id": command.run_id,
            "agent_role": "coordinator",
            "attempt": 1,
            "task_id": None,
            "runtime_version": run["runtime_version"],
            "prompt_version": command.prompt_version,
            "model_policy_version": run["model_policy_version"],
            "tool_policy_version": run["tool_policy_version"],
            "context_policy_version": run["context_policy_version"],
            "code_revision": run["code_revision"],
            "context_snapshot_id": command.context_snapshot_id,
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

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("clock must be timezone-aware")
        return value.astimezone(timezone.utc)
