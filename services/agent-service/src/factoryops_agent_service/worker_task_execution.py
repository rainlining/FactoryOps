from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum

from contracts.agent_execution.validator import compute_execution_key
from sqlalchemy import Connection, Engine, text


class WorkerExecutionRejected(ValueError):
    pass


class WorkerExecutionOutcome(str, Enum):
    APPLIED = "applied"
    DUPLICATE_IDENTICAL = "duplicate-identical"
    DUPLICATE_CONFLICTING = "duplicate-conflicting"


@dataclass(frozen=True)
class StartWorkerExecutionCommand:
    request_id: str
    task_id: str
    owner_id: str
    lease_token: str
    runtime_version: str
    prompt_version: str
    model_policy_version: str
    tool_policy_version: str
    context_policy_version: str
    code_revision: str


@dataclass(frozen=True)
class WorkerExecutionResult:
    outcome: WorkerExecutionOutcome
    task_id: str | None
    execution_id: str | None


def _new_id(prefix: str) -> str:
    return prefix + uuid.uuid4().hex.upper()


class WorkerTaskExecutionService:
    def __init__(
        self,
        engine: Engine,
        *,
        clock: Callable[[], datetime] | None = None,
        execution_id_factory: Callable[[], str] | None = None,
        transition_id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._engine = engine
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._execution_id_factory = execution_id_factory or (lambda: _new_id("EXE-"))
        self._transition_id_factory = transition_id_factory or (lambda: _new_id("WTR-"))

    def start(self, command: StartWorkerExecutionCommand) -> WorkerExecutionResult:
        self._validate_command(command)
        now = self._now()
        command_hash = self._hash(command)
        with self._engine.begin() as connection:
            replay = self._find_start_request(connection, command.request_id)
            if replay is not None:
                return self._classify(replay, command_hash)

            task = self._lock_task(connection, command.task_id)
            replay = self._find_start_request(connection, command.request_id)
            if replay is not None:
                return self._classify(replay, command_hash)
            lease = self._lock_lease(connection, command.task_id)
            if task is None:
                raise WorkerExecutionRejected("Task does not exist")
            if task["status"] != "PENDING" or task["revision"] != 0:
                raise WorkerExecutionRejected("Task is not PENDING")
            if (
                lease is None
                or lease["owner_id"] != command.owner_id
                or lease["lease_token"] != command.lease_token
                or self._utc(lease["expires_at"]) <= now
            ):
                raise WorkerExecutionRejected("lease is missing, stale, or expired")
            if connection.scalar(
                text(
                    """SELECT COUNT(*) FROM agent_task_dependencies d
                    JOIN agent_tasks dependency ON dependency.task_id=d.dependency_task_id
                    WHERE d.task_id=:task AND dependency.status<>'SUCCEEDED'"""
                ),
                {"task": command.task_id},
            ):
                raise WorkerExecutionRejected("Task dependencies are not satisfied")

            execution_id = self._execution_id_factory()
            attempt = int(task["attempt_count"]) + 1
            execution = {
                "execution_id": execution_id,
                "execution_key": compute_execution_key(
                    str(task["run_id"]),
                    str(task["target_agent_role"]),
                    command.task_id,
                    attempt,
                ),
                "run_id": task["run_id"],
                "agent_role": task["target_agent_role"],
                "attempt": attempt,
                "task_id": command.task_id,
                "runtime_version": command.runtime_version,
                "prompt_version": command.prompt_version,
                "model_policy_version": command.model_policy_version,
                "tool_policy_version": command.tool_policy_version,
                "context_policy_version": command.context_policy_version,
                "code_revision": command.code_revision,
                "context_snapshot_id": task["context_snapshot_id"],
                "input_evidence_refs": task["evidence_refs"],
                "now": now,
            }
            self._insert_running_execution(connection, execution, command.owner_id)
            self._start_task(
                connection, task, execution_id, attempt, command.owner_id, now
            )
            connection.execute(
                text(
                    """INSERT INTO worker_task_execution_start_requests
                    (request_id,command_hash,task_id,execution_id,created_at)
                    VALUES (:request,:hash,:task,:execution,:now)"""
                ),
                {
                    "request": command.request_id,
                    "hash": command_hash,
                    "task": command.task_id,
                    "execution": execution_id,
                    "now": now,
                },
            )
        return WorkerExecutionResult(
            WorkerExecutionOutcome.APPLIED, command.task_id, execution_id
        )

    def _insert_running_execution(
        self, connection: Connection, execution: Mapping[str, object], owner_id: str
    ) -> None:
        connection.execute(
            text(
                """INSERT INTO agent_executions(execution_id,execution_key,contract_version,run_id,agent_role,attempt,task_id,
                runtime_version,prompt_version,model_policy_version,tool_policy_version,context_policy_version,code_revision,
                context_snapshot_id,input_evidence_refs,status,revision,created_at,updated_at,started_at,ended_at,status_reason_code,
                status_reason_message,output_artifact_refs,decision_id,result_evidence_refs,failure_code,failure_message,
                failure_recoverability,failed_dependency_ref) VALUES (:execution_id,:execution_key,'1.0.0',:run_id,:agent_role,
                :attempt,:task_id,:runtime_version,:prompt_version,:model_policy_version,:tool_policy_version,:context_policy_version,
                :code_revision,:context_snapshot_id,:input_evidence_refs,'RUNNING',1,:now,:now,:now,NULL,'WORKER_STARTED',NULL,
                NULL,NULL,NULL,NULL,NULL,NULL,NULL)"""
            ),
            execution,
        )
        self._insert_execution_history(connection, execution, owner_id)

    def _insert_execution_history(
        self, connection: Connection, execution: Mapping[str, object], owner_id: str
    ) -> None:
        base = {
            "execution": execution["execution_id"],
            "owner": owner_id,
            "now": execution["now"],
        }
        connection.execute(
            text(
                """INSERT INTO agent_execution_transitions(transition_id,transition_request_id,execution_id,from_status,
                to_status,from_revision,to_revision,actor_kind,actor_id,reason_code,reason_message,result_json,failure_json,occurred_at)
                VALUES (:transition_id,:request,:execution,NULL,'PENDING',NULL,0,'SYSTEM','worker-task-execution',
                'EXECUTION_CREATED',NULL,NULL,NULL,:now)"""
            ),
            {
                **base,
                "transition_id": self._transition_id_factory(),
                "request": _new_id("ERQ-"),
            },
        )
        connection.execute(
            text(
                """INSERT INTO agent_execution_transitions(transition_id,transition_request_id,execution_id,from_status,
                to_status,from_revision,to_revision,actor_kind,actor_id,reason_code,reason_message,result_json,failure_json,occurred_at)
                VALUES (:transition_id,:request,:execution,'PENDING','RUNNING',0,1,'WORKER',:owner,
                'WORKER_STARTED',NULL,NULL,NULL,:now)"""
            ),
            {
                **base,
                "transition_id": self._transition_id_factory(),
                "request": _new_id("ERQ-"),
            },
        )

    def _start_task(
        self,
        connection: Connection,
        task: Mapping[str, object],
        execution_id: str,
        attempt: int,
        owner_id: str,
        now: datetime,
    ) -> None:
        result = connection.execute(
            text(
                """UPDATE agent_tasks SET status='RUNNING',revision=1,updated_at=:now,started_at=:now,
                status_reason_code='WORKER_STARTED',status_reason_message=NULL,current_execution_id=:execution,
                attempt_count=:attempt WHERE task_id=:task AND status='PENDING' AND revision=0"""
            ),
            {
                "now": now,
                "execution": execution_id,
                "attempt": attempt,
                "task": task["task_id"],
            },
        )
        if result.rowcount != 1:
            raise WorkerExecutionRejected("Task changed concurrently")
        connection.execute(
            text(
                """INSERT INTO agent_task_transitions(transition_id,transition_request_id,task_id,from_status,to_status,
                from_revision,to_revision,actor_kind,actor_id,reason_code,reason_message,execution_id,attempt_count,
                completion_execution_id,failure_code,failure_message,failure_recoverability,occurred_at)
                VALUES (:transition,:request,:task,'PENDING','RUNNING',0,1,'WORKER',:owner,'WORKER_STARTED',NULL,
                :execution,:attempt,NULL,NULL,NULL,NULL,:now)"""
            ),
            {
                "transition": self._transition_id_factory(),
                "request": _new_id("TRQ-"),
                "task": task["task_id"],
                "owner": owner_id,
                "execution": execution_id,
                "attempt": attempt,
                "now": now,
            },
        )

    @staticmethod
    def _lock_task(connection: Connection, task_id: str) -> Mapping[str, object] | None:
        return (
            connection.execute(
                text("SELECT * FROM agent_tasks WHERE task_id=:task FOR UPDATE"),
                {"task": task_id},
            )
            .mappings()
            .one_or_none()
        )

    @staticmethod
    def _lock_lease(
        connection: Connection, task_id: str
    ) -> Mapping[str, object] | None:
        return (
            connection.execute(
                text("SELECT * FROM agent_task_leases WHERE task_id=:task FOR UPDATE"),
                {"task": task_id},
            )
            .mappings()
            .one_or_none()
        )

    @staticmethod
    def _find_start_request(
        connection: Connection, request_id: str
    ) -> Mapping[str, object] | None:
        return (
            connection.execute(
                text(
                    "SELECT * FROM worker_task_execution_start_requests WHERE request_id=:request FOR UPDATE"
                ),
                {"request": request_id},
            )
            .mappings()
            .one_or_none()
        )

    @staticmethod
    def _classify(
        row: Mapping[str, object], command_hash: str
    ) -> WorkerExecutionResult:
        return WorkerExecutionResult(
            WorkerExecutionOutcome.DUPLICATE_IDENTICAL
            if row["command_hash"] == command_hash
            else WorkerExecutionOutcome.DUPLICATE_CONFLICTING,
            str(row["task_id"]),
            str(row["execution_id"]),
        )

    @staticmethod
    def _hash(command: StartWorkerExecutionCommand) -> str:
        payload = json.dumps(asdict(command), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _validate_command(command: StartWorkerExecutionCommand) -> None:
        required = (
            command.request_id,
            command.task_id,
            command.owner_id,
            command.lease_token,
            command.runtime_version,
            command.prompt_version,
            command.model_policy_version,
            command.tool_policy_version,
            command.context_policy_version,
            command.code_revision,
        )
        if any(not value or value != value.strip() for value in required):
            raise WorkerExecutionRejected("command fields must be non-blank")

    def _now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            raise ValueError("clock must be timezone-aware")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _utc(value: datetime) -> datetime:
        return (
            value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        ).astimezone(timezone.utc)
