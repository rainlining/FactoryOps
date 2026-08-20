from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import ClassVar

from sqlalchemy import Connection, Engine, text

from contracts.agent_execution.validator import compute_execution_key


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


@dataclass(frozen=True)
class CompleteWorkerExecutionCommand:
    request_id: str
    task_id: str
    execution_id: str
    owner_id: str
    lease_token: str
    final_status: str
    result: Mapping[str, object] | None = None
    failure: Mapping[str, object] | None = None


@dataclass(frozen=True)
class RetryWorkerExecutionCommand:
    request_id: str
    task_id: str
    execution_id: str
    owner_id: str
    lease_token: str
    failure: Mapping[str, object]
    max_attempts: int
    runtime_version: str
    prompt_version: str
    model_policy_version: str
    tool_policy_version: str
    context_policy_version: str
    code_revision: str


def _new_id(prefix: str) -> str:
    return prefix + uuid.uuid4().hex.upper()


class WorkerTaskExecutionService:
    SAFE_RETRY_CODES: ClassVar[frozenset[str]] = frozenset(
        {
            "MODEL_TIMEOUT",
            "TOOL_TIMEOUT",
            "TRANSIENT_UPSTREAM",
            "RATE_LIMITED",
            "WORKER_SANDBOX_UNAVAILABLE",
        }
    )

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
        lock_name = (
            "worker-start:"
            + hashlib.sha256(command.request_id.encode()).hexdigest()[:51]
        )
        with self._engine.connect() as connection:
            acquired = connection.scalar(
                text("SELECT GET_LOCK(:name, 10)"), {"name": lock_name}
            )
            connection.commit()
            if acquired != 1:
                raise WorkerExecutionRejected("request admission lock timed out")
            try:
                with connection.begin():
                    replay = self._find_start_request(connection, command.request_id)
                    if replay is not None:
                        return self._classify(replay, command_hash)

                    task = self._lock_task(connection, command.task_id)
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
                        raise WorkerExecutionRejected(
                            "lease is missing, stale, or expired"
                        )
                    if connection.scalar(
                        text(
                            """SELECT COUNT(*) FROM agent_task_dependencies d
                            JOIN agent_tasks dependency ON dependency.task_id=d.dependency_task_id
                            WHERE d.task_id=:task AND dependency.status<>'SUCCEEDED'"""
                        ),
                        {"task": command.task_id},
                    ):
                        raise WorkerExecutionRejected(
                            "Task dependencies are not satisfied"
                        )

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
                    self._insert_running_execution(
                        connection, execution, command.owner_id
                    )
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
            finally:
                connection.execute(
                    text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name}
                )
                connection.commit()
        return WorkerExecutionResult(
            WorkerExecutionOutcome.APPLIED, command.task_id, execution_id
        )

    def complete(
        self, command: CompleteWorkerExecutionCommand
    ) -> WorkerExecutionResult:
        self._validate_completion(command)
        now = self._now()
        command_hash = self._completion_hash(command)
        lock_name = (
            "worker-complete:"
            + hashlib.sha256(command.request_id.encode()).hexdigest()[:48]
        )
        with self._engine.connect() as connection:
            acquired = connection.scalar(
                text("SELECT GET_LOCK(:name, 10)"), {"name": lock_name}
            )
            connection.commit()
            if acquired != 1:
                raise WorkerExecutionRejected("request admission lock timed out")
            try:
                with connection.begin():
                    replay = self._find_completion_request(
                        connection, command.request_id
                    )
                    if replay is not None:
                        return self._classify(replay, command_hash)
                    task = self._lock_task(connection, command.task_id)
                    lease = self._lock_lease(connection, command.task_id)
                    execution = (
                        connection.execute(
                            text(
                                "SELECT * FROM agent_executions WHERE execution_id=:execution FOR UPDATE"
                            ),
                            {"execution": command.execution_id},
                        )
                        .mappings()
                        .one_or_none()
                    )
                    if task is None or execution is None:
                        raise WorkerExecutionRejected(
                            "Task or Execution does not exist"
                        )
                    if (
                        task["status"] != "RUNNING"
                        or task["current_execution_id"] != command.execution_id
                        or execution["status"] != "RUNNING"
                        or execution["task_id"] != command.task_id
                        or execution["run_id"] != task["run_id"]
                    ):
                        raise WorkerExecutionRejected(
                            "Task and Execution are not current RUNNING pair"
                        )
                    if (
                        lease is None
                        or lease["owner_id"] != command.owner_id
                        or lease["lease_token"] != command.lease_token
                        or self._utc(lease["expires_at"]) <= now
                    ):
                        raise WorkerExecutionRejected(
                            "lease is missing, stale, or expired"
                        )

                    self._finish_execution(connection, execution, command, now)
                    self._finish_task(connection, task, command, now)
                    deleted = connection.execute(
                        text(
                            """DELETE FROM agent_task_leases WHERE task_id=:task AND owner_id=:owner
                            AND lease_token=:token AND expires_at>:now"""
                        ),
                        {
                            "task": command.task_id,
                            "owner": command.owner_id,
                            "token": command.lease_token,
                            "now": now,
                        },
                    )
                    if deleted.rowcount != 1:
                        raise WorkerExecutionRejected("lease changed concurrently")
                    connection.execute(
                        text(
                            """INSERT INTO worker_task_execution_completion_requests
                            (request_id,command_hash,task_id,execution_id,final_status,created_at)
                            VALUES (:request,:hash,:task,:execution,:status,:now)"""
                        ),
                        {
                            "request": command.request_id,
                            "hash": command_hash,
                            "task": command.task_id,
                            "execution": command.execution_id,
                            "status": command.final_status,
                            "now": now,
                        },
                    )
            finally:
                connection.execute(
                    text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name}
                )
                connection.commit()
        return WorkerExecutionResult(
            WorkerExecutionOutcome.APPLIED, command.task_id, command.execution_id
        )

    def retry(self, command: RetryWorkerExecutionCommand) -> WorkerExecutionResult:
        self._validate_retry(command)
        now = self._now()
        command_hash = self._retry_hash(command)
        lock_name = (
            "worker-retry:"
            + hashlib.sha256(command.request_id.encode()).hexdigest()[:51]
        )
        with self._engine.connect() as connection:
            acquired = connection.scalar(
                text("SELECT GET_LOCK(:name, 10)"), {"name": lock_name}
            )
            connection.commit()
            if acquired != 1:
                raise WorkerExecutionRejected("request admission lock timed out")
            try:
                with connection.begin():
                    replay = self._find_retry_request(connection, command.request_id)
                    if replay is not None:
                        return self._classify_retry(replay, command_hash)
                    task = self._lock_task(connection, command.task_id)
                    lease = self._lock_lease(connection, command.task_id)
                    execution = (
                        connection.execute(
                            text(
                                "SELECT * FROM agent_executions WHERE execution_id=:execution FOR UPDATE"
                            ),
                            {"execution": command.execution_id},
                        )
                        .mappings()
                        .one_or_none()
                    )
                    if task is None or execution is None:
                        raise WorkerExecutionRejected(
                            "Task or Execution does not exist"
                        )
                    if (
                        task["status"] != "RUNNING"
                        or task["current_execution_id"] != command.execution_id
                        or execution["status"] != "RUNNING"
                        or execution["task_id"] != command.task_id
                        or execution["run_id"] != task["run_id"]
                    ):
                        raise WorkerExecutionRejected(
                            "Task and Execution are not current RUNNING pair"
                        )
                    if (
                        lease is None
                        or lease["owner_id"] != command.owner_id
                        or lease["lease_token"] != command.lease_token
                        or self._utc(lease["expires_at"]) <= now
                    ):
                        raise WorkerExecutionRejected(
                            "lease is missing, stale, or expired"
                        )
                    attempt = int(execution["attempt"])
                    if attempt >= command.max_attempts:
                        raise WorkerExecutionRejected(
                            "retry attempt budget is exhausted"
                        )

                    self._fail_retryable_execution(connection, execution, command, now)
                    new_execution_id = self._execution_id_factory()
                    new_attempt = attempt + 1
                    new_execution = {
                        "execution_id": new_execution_id,
                        "execution_key": compute_execution_key(
                            str(task["run_id"]),
                            str(task["target_agent_role"]),
                            command.task_id,
                            new_attempt,
                        ),
                        "run_id": task["run_id"],
                        "agent_role": task["target_agent_role"],
                        "attempt": new_attempt,
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
                    self._insert_running_execution(
                        connection, new_execution, command.owner_id
                    )
                    self._retry_task(
                        connection,
                        task,
                        new_execution_id,
                        new_attempt,
                        command.owner_id,
                        now,
                    )
                    connection.execute(
                        text(
                            """INSERT INTO worker_task_execution_retry_requests
                            (request_id,command_hash,task_id,failed_execution_id,new_execution_id,created_at)
                            VALUES (:request,:hash,:task,:failed,:new,:now)"""
                        ),
                        {
                            "request": command.request_id,
                            "hash": command_hash,
                            "task": command.task_id,
                            "failed": command.execution_id,
                            "new": new_execution_id,
                            "now": now,
                        },
                    )
            finally:
                connection.execute(
                    text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name}
                )
                connection.commit()
        return WorkerExecutionResult(
            WorkerExecutionOutcome.APPLIED, command.task_id, new_execution_id
        )

    def _fail_retryable_execution(
        self,
        connection: Connection,
        execution: Mapping[str, object],
        command: RetryWorkerExecutionCommand,
        now: datetime,
    ) -> None:
        failure = command.failure
        updated = connection.execute(
            text(
                """UPDATE agent_executions SET status='FAILED',revision=2,updated_at=:now,ended_at=:now,
                status_reason_code='WORKER_RETRY',status_reason_message='Worker execution retried',
                failure_code=:code,failure_message=:message,
                failure_recoverability='retryable',failed_dependency_ref=:dependency
                WHERE execution_id=:execution AND status='RUNNING' AND revision=1"""
            ),
            {
                "now": now,
                "code": failure["code"],
                "message": failure["message"],
                "dependency": failure["failed_dependency_ref"],
                "execution": command.execution_id,
            },
        )
        if updated.rowcount != 1:
            raise WorkerExecutionRejected("Execution changed concurrently")
        connection.execute(
            text(
                """INSERT INTO agent_execution_transitions(transition_id,transition_request_id,execution_id,from_status,
                to_status,from_revision,to_revision,actor_kind,actor_id,reason_code,reason_message,result_json,failure_json,occurred_at)
                VALUES (:transition,:request,:execution,'RUNNING','FAILED',1,2,'WORKER',:owner,
                'WORKER_RETRY','Worker execution retried',NULL,:failure,:now)"""
            ),
            {
                "transition": self._transition_id_factory(),
                "request": _new_id("ERQ-"),
                "execution": command.execution_id,
                "owner": command.owner_id,
                "failure": json.dumps(command.failure, sort_keys=True),
                "now": now,
            },
        )

    def _retry_task(
        self,
        connection: Connection,
        task: Mapping[str, object],
        execution_id: str,
        attempt: int,
        owner_id: str,
        now: datetime,
    ) -> None:
        from_revision = int(task["revision"])
        updated = connection.execute(
            text(
                """UPDATE agent_tasks SET revision=:revision,updated_at=:now,status_reason_code='WORKER_RETRY',
                status_reason_message='Worker execution retried',current_execution_id=:execution,attempt_count=:attempt
                WHERE task_id=:task AND status='RUNNING' AND revision=:from_revision"""
            ),
            {
                "revision": from_revision + 1,
                "now": now,
                "execution": execution_id,
                "attempt": attempt,
                "task": task["task_id"],
                "from_revision": from_revision,
            },
        )
        if updated.rowcount != 1:
            raise WorkerExecutionRejected("Task changed concurrently")
        connection.execute(
            text(
                """INSERT INTO agent_task_transitions(transition_id,transition_request_id,task_id,from_status,to_status,
                from_revision,to_revision,actor_kind,actor_id,reason_code,reason_message,execution_id,attempt_count,
                completion_execution_id,failure_code,failure_message,failure_recoverability,occurred_at)
                VALUES (:transition,:request,:task,'RUNNING','RUNNING',:from_revision,:to_revision,'WORKER',:owner,
                'WORKER_RETRY','Worker execution retried',:execution,:attempt,NULL,NULL,NULL,NULL,:now)"""
            ),
            {
                "transition": self._transition_id_factory(),
                "request": _new_id("TRQ-"),
                "task": task["task_id"],
                "from_revision": from_revision,
                "to_revision": from_revision + 1,
                "owner": owner_id,
                "execution": execution_id,
                "attempt": attempt,
                "now": now,
            },
        )

    def _finish_execution(
        self,
        connection: Connection,
        execution: Mapping[str, object],
        command: CompleteWorkerExecutionCommand,
        now: datetime,
    ) -> None:
        result = command.result
        failure = command.failure
        updated = connection.execute(
            text(
                """UPDATE agent_executions SET status=:status,revision=2,updated_at=:now,ended_at=:now,
                status_reason_code=:reason,status_reason_message=:reason_message,output_artifact_refs=:artifacts,
                decision_id=:decision,result_evidence_refs=:evidence,failure_code=:failure_code,
                failure_message=:failure_message,failure_recoverability=:recoverability,
                failed_dependency_ref=:dependency WHERE execution_id=:execution AND status='RUNNING' AND revision=1"""
            ),
            {
                "status": command.final_status,
                "now": now,
                "reason": "WORKER_COMPLETED" if result else "WORKER_FAILED",
                "reason_message": "Worker execution completed"
                if result
                else "Worker execution failed",
                "artifacts": json.dumps(result["output_artifact_refs"])
                if result
                else None,
                "decision": result.get("decision_id") if result else None,
                "evidence": json.dumps(result["evidence_refs"]) if result else None,
                "failure_code": failure["code"] if failure else None,
                "failure_message": failure["message"] if failure else None,
                "recoverability": failure["recoverability"] if failure else None,
                "dependency": failure.get("failed_dependency_ref") if failure else None,
                "execution": command.execution_id,
            },
        )
        if updated.rowcount != 1:
            raise WorkerExecutionRejected("Execution changed concurrently")
        self._insert_completion_history(connection, execution, command, now)

    def _insert_completion_history(
        self,
        connection: Connection,
        execution: Mapping[str, object],
        command: CompleteWorkerExecutionCommand,
        now: datetime,
    ) -> None:
        connection.execute(
            text(
                """INSERT INTO agent_execution_transitions(transition_id,transition_request_id,execution_id,from_status,
                to_status,from_revision,to_revision,actor_kind,actor_id,reason_code,reason_message,result_json,failure_json,occurred_at)
                VALUES (:transition,:request,:execution,'RUNNING',:status,1,2,'WORKER',:owner,
                :reason,:reason_message,:result,:failure,:now)"""
            ),
            {
                "transition": self._transition_id_factory(),
                "request": _new_id("ERQ-"),
                "execution": execution["execution_id"],
                "status": command.final_status,
                "owner": command.owner_id,
                "reason": "WORKER_COMPLETED" if command.result else "WORKER_FAILED",
                "reason_message": "Worker execution completed"
                if command.result
                else "Worker execution failed",
                "result": json.dumps(command.result, sort_keys=True)
                if command.result
                else None,
                "failure": json.dumps(command.failure, sort_keys=True)
                if command.failure
                else None,
                "now": now,
            },
        )

    def _finish_task(
        self,
        connection: Connection,
        task: Mapping[str, object],
        command: CompleteWorkerExecutionCommand,
        now: datetime,
    ) -> None:
        failure = command.failure
        from_revision = int(task["revision"])
        updated = connection.execute(
            text(
                """UPDATE agent_tasks SET status=:status,revision=:to_revision,updated_at=:now,ended_at=:now,
                status_reason_code=:reason,status_reason_message=:reason_message,completion_execution_id=:completion,
                failure_execution_id=:failure_execution,failure_code=:failure_code,failure_message=:failure_message,
                failure_recoverability=:recoverability WHERE task_id=:task AND status='RUNNING' AND revision=:from_revision
                AND current_execution_id=:execution"""
            ),
            {
                "status": command.final_status,
                "from_revision": from_revision,
                "to_revision": from_revision + 1,
                "now": now,
                "reason": "WORKER_COMPLETED" if command.result else "WORKER_FAILED",
                "reason_message": "Worker task completed"
                if command.result
                else "Worker task failed",
                "completion": command.execution_id if command.result else None,
                "failure_execution": command.execution_id if failure else None,
                "failure_code": failure["code"] if failure else None,
                "failure_message": failure["message"] if failure else None,
                "recoverability": failure["recoverability"] if failure else None,
                "task": command.task_id,
                "execution": command.execution_id,
            },
        )
        if updated.rowcount != 1:
            raise WorkerExecutionRejected("Task changed concurrently")
        connection.execute(
            text(
                """INSERT INTO agent_task_transitions(transition_id,transition_request_id,task_id,from_status,to_status,
                from_revision,to_revision,actor_kind,actor_id,reason_code,reason_message,execution_id,attempt_count,
                completion_execution_id,failure_code,failure_message,failure_recoverability,occurred_at)
                VALUES (:transition,:request,:task,'RUNNING',:status,:from_revision,:to_revision,'WORKER',:owner,
                :reason,:reason_message,:execution,
                :attempt,:completion,:failure_code,:failure_message,:recoverability,:now)"""
            ),
            {
                "transition": self._transition_id_factory(),
                "request": _new_id("TRQ-"),
                "task": command.task_id,
                "status": command.final_status,
                "from_revision": from_revision,
                "to_revision": from_revision + 1,
                "owner": command.owner_id,
                "reason": "WORKER_COMPLETED" if command.result else "WORKER_FAILED",
                "reason_message": "Worker task completed"
                if command.result
                else "Worker task failed",
                "execution": command.execution_id,
                "attempt": task["attempt_count"],
                "completion": command.execution_id if command.result else None,
                "failure_code": failure["code"] if failure else None,
                "failure_message": failure["message"] if failure else None,
                "recoverability": failure["recoverability"] if failure else None,
                "now": now,
            },
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
                :code_revision,:context_snapshot_id,:input_evidence_refs,'RUNNING',1,:now,:now,:now,NULL,'WORKER_STARTED','Worker execution started',
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
                'WORKER_STARTED','Worker execution started',NULL,NULL,:now)"""
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
                status_reason_code='WORKER_STARTED',status_reason_message='Worker execution started',current_execution_id=:execution,
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
                VALUES (:transition,:request,:task,'PENDING','RUNNING',0,1,'WORKER',:owner,'WORKER_STARTED','Worker execution started',
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
    def _find_completion_request(
        connection: Connection, request_id: str
    ) -> Mapping[str, object] | None:
        return (
            connection.execute(
                text(
                    "SELECT * FROM worker_task_execution_completion_requests WHERE request_id=:request FOR UPDATE"
                ),
                {"request": request_id},
            )
            .mappings()
            .one_or_none()
        )

    @staticmethod
    def _find_retry_request(
        connection: Connection, request_id: str
    ) -> Mapping[str, object] | None:
        return (
            connection.execute(
                text(
                    "SELECT * FROM worker_task_execution_retry_requests WHERE request_id=:request FOR UPDATE"
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
    def _classify_retry(
        row: Mapping[str, object], command_hash: str
    ) -> WorkerExecutionResult:
        return WorkerExecutionResult(
            WorkerExecutionOutcome.DUPLICATE_IDENTICAL
            if row["command_hash"] == command_hash
            else WorkerExecutionOutcome.DUPLICATE_CONFLICTING,
            str(row["task_id"]),
            str(row["new_execution_id"]),
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
        version_pattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
        versions = (
            command.runtime_version,
            command.prompt_version,
            command.model_policy_version,
            command.tool_policy_version,
            command.context_policy_version,
        )
        if any(version_pattern.fullmatch(value) is None for value in versions):
            raise WorkerExecutionRejected("version fields violate Execution Contract")
        if re.fullmatch(r"[0-9a-f]{7,64}", command.code_revision) is None:
            raise WorkerExecutionRejected("code revision violates Execution Contract")

    @staticmethod
    def _completion_hash(command: CompleteWorkerExecutionCommand) -> str:
        payload = json.dumps(asdict(command), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _retry_hash(command: RetryWorkerExecutionCommand) -> str:
        payload = json.dumps(asdict(command), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    @classmethod
    def _validate_retry(cls, command: RetryWorkerExecutionCommand) -> None:
        required = (
            command.request_id,
            command.task_id,
            command.execution_id,
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
        if not 2 <= command.max_attempts <= 10:
            raise WorkerExecutionRejected("max attempts must be between 2 and 10")
        if set(command.failure) != {
            "code",
            "message",
            "recoverability",
            "failed_dependency_ref",
        }:
            raise WorkerExecutionRejected("failure fields violate Execution Contract")
        if (
            command.failure["code"] not in cls.SAFE_RETRY_CODES
            or command.failure["recoverability"] != "retryable"
            or not 1 <= len(str(command.failure["message"])) <= 600
        ):
            raise WorkerExecutionRejected("failure is not safely retryable")
        dependency = command.failure["failed_dependency_ref"]
        if dependency is not None and not cls._valid_refs((dependency,)):
            raise WorkerExecutionRejected(
                "failure reference violates Execution Contract"
            )
        version_pattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
        versions = (
            command.runtime_version,
            command.prompt_version,
            command.model_policy_version,
            command.tool_policy_version,
            command.context_policy_version,
        )
        if any(version_pattern.fullmatch(value) is None for value in versions):
            raise WorkerExecutionRejected("version fields violate Execution Contract")
        if re.fullmatch(r"[0-9a-f]{7,64}", command.code_revision) is None:
            raise WorkerExecutionRejected("code revision violates Execution Contract")

    @staticmethod
    def _validate_completion(command: CompleteWorkerExecutionCommand) -> None:
        required = (
            command.request_id,
            command.task_id,
            command.execution_id,
            command.owner_id,
            command.lease_token,
        )
        if any(not value or value != value.strip() for value in required):
            raise WorkerExecutionRejected("command fields must be non-blank")
        if command.final_status == "SUCCEEDED":
            if command.result is None or command.failure is not None:
                raise WorkerExecutionRejected("SUCCEEDED requires only result")
            if set(command.result) != {
                "output_artifact_refs",
                "decision_id",
                "evidence_refs",
            }:
                raise WorkerExecutionRejected(
                    "result fields violate Execution Contract"
                )
            artifacts = command.result["output_artifact_refs"]
            evidence = command.result["evidence_refs"]
            if (
                not isinstance(artifacts, (list, tuple))
                or not 1 <= len(artifacts) <= 64
            ):
                raise WorkerExecutionRejected(
                    "result artifacts violate Execution Contract"
                )
            if not isinstance(evidence, (list, tuple)) or len(evidence) > 64:
                raise WorkerExecutionRejected(
                    "result evidence violates Execution Contract"
                )
            if not WorkerTaskExecutionService._valid_refs((*artifacts, *evidence)):
                raise WorkerExecutionRejected(
                    "result references violate Execution Contract"
                )
            decision = command.result["decision_id"]
            if (
                decision is not None
                and re.fullmatch(r"DEC-[0-9A-F]{32}", str(decision)) is None
            ):
                raise WorkerExecutionRejected("decision ID violates Execution Contract")
        elif command.final_status == "FAILED":
            if command.failure is None or command.result is not None:
                raise WorkerExecutionRejected("FAILED requires only failure")
            if set(command.failure) != {
                "code",
                "message",
                "recoverability",
                "failed_dependency_ref",
            }:
                raise WorkerExecutionRejected(
                    "failure fields violate Execution Contract"
                )
            if (
                re.fullmatch(
                    r"[A-Z][A-Z0-9_]{2,127}",
                    str(command.failure.get("code", "")),
                )
                is None
                or not 1 <= len(str(command.failure.get("message", ""))) <= 600
                or command.failure.get("recoverability") != "non_retryable"
            ):
                raise WorkerExecutionRejected("Task failure must be non_retryable")
            dependency = command.failure["failed_dependency_ref"]
            if dependency is not None and not WorkerTaskExecutionService._valid_refs(
                (dependency,)
            ):
                raise WorkerExecutionRejected(
                    "failure reference violates Execution Contract"
                )
        else:
            raise WorkerExecutionRejected("final status must be SUCCEEDED or FAILED")

    @staticmethod
    def _valid_refs(refs: tuple[object, ...]) -> bool:
        pattern = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$")
        values = tuple(str(ref) for ref in refs)
        return len(values) == len(set(values)) and all(
            isinstance(ref, str) and pattern.fullmatch(ref) is not None for ref in refs
        )

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
