from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from sqlalchemy import Engine, create_engine, text
from test_worker_task_completion_mysql import _running
from testcontainers.community.mysql import MySqlContainer

from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.worker_task_execution import (
    CompleteWorkerExecutionCommand,
    RetryWorkerExecutionCommand,
    WorkerExecutionOutcome,
    WorkerExecutionRejected,
    WorkerTaskExecutionService,
)


@pytest.fixture(scope="module")
def mysql_engine() -> Engine:
    with MySqlContainer("mysql:8.4") as mysql:
        engine = create_engine(
            mysql.get_connection_url().replace("mysql://", "mysql+pymysql://", 1)
        )
        migrate(engine)
        yield engine
        engine.dispose()


def _retry(task_id: str, execution_id: str, owner: str, token: str, marker: str):
    return RetryWorkerExecutionCommand(
        request_id="WRR-" + marker.upper() * 32,
        task_id=task_id,
        execution_id=execution_id,
        owner_id=owner,
        lease_token=token,
        failure={
            "code": "MODEL_TIMEOUT",
            "message": "model did not answer before deadline",
            "recoverability": "retryable",
            "failed_dependency_ref": None,
        },
        max_attempts=3,
        runtime_version="runtime-v2",
        prompt_version="prompt-v2",
        model_policy_version="model-v2",
        tool_policy_version="tool-v2",
        context_policy_version="context-v2",
        code_revision="b" * 40,
    )


def test_retry_atomically_replaces_attempt_and_keeps_lease(mysql_engine: Engine):
    task_id, lease, old_execution_id = _running(mysql_engine, "a")
    command = _retry(task_id, old_execution_id, lease.owner_id, lease.lease_token, "1")

    result = WorkerTaskExecutionService(mysql_engine).retry(command)

    assert result.outcome is WorkerExecutionOutcome.APPLIED
    assert result.execution_id != old_execution_id
    with mysql_engine.connect() as connection:
        task = (
            connection.execute(
                text("SELECT * FROM agent_tasks WHERE task_id=:id"), {"id": task_id}
            )
            .mappings()
            .one()
        )
        old_execution = (
            connection.execute(
                text("SELECT * FROM agent_executions WHERE execution_id=:id"),
                {"id": old_execution_id},
            )
            .mappings()
            .one()
        )
        new_execution = (
            connection.execute(
                text("SELECT * FROM agent_executions WHERE execution_id=:id"),
                {"id": result.execution_id},
            )
            .mappings()
            .one()
        )
        assert (task["status"], task["revision"], task["attempt_count"]) == (
            "RUNNING",
            2,
            2,
        )
        assert task["current_execution_id"] == result.execution_id
        assert (old_execution["status"], old_execution["failure_recoverability"]) == (
            "FAILED",
            "retryable",
        )
        assert (new_execution["status"], new_execution["attempt"]) == ("RUNNING", 2)
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM agent_task_leases WHERE task_id=:id"),
                {"id": task_id},
            )
            == 1
        )


def test_retry_replay_is_identical_or_conflicting(mysql_engine: Engine):
    task_id, lease, execution_id = _running(mysql_engine, "b")
    command = _retry(task_id, execution_id, lease.owner_id, lease.lease_token, "2")
    service = WorkerTaskExecutionService(mysql_engine)

    first = service.retry(command)
    same = service.retry(command)
    conflict = service.retry(replace(command, runtime_version="runtime-v3"))

    assert first.outcome is WorkerExecutionOutcome.APPLIED
    assert same.outcome is WorkerExecutionOutcome.DUPLICATE_IDENTICAL
    assert conflict.outcome is WorkerExecutionOutcome.DUPLICATE_CONFLICTING
    assert first.execution_id == same.execution_id == conflict.execution_id


def test_retry_rejects_unsafe_failure_and_exhausted_budget(mysql_engine: Engine):
    task_id, lease, execution_id = _running(mysql_engine, "c")
    command = _retry(task_id, execution_id, lease.owner_id, lease.lease_token, "3")
    service = WorkerTaskExecutionService(mysql_engine)

    with pytest.raises(WorkerExecutionRejected, match="safely retryable"):
        service.retry(
            replace(command, failure={**command.failure, "code": "INVALID_INPUT"})
        )
    with pytest.raises(WorkerExecutionRejected, match="lease"):
        service.retry(replace(command, owner_id="wrong-worker"))
    first_retry = service.retry(replace(command, max_attempts=2))
    exhausted = replace(
        command,
        request_id="WRR-" + "6" * 32,
        execution_id=str(first_retry.execution_id),
        max_attempts=2,
    )
    with pytest.raises(WorkerExecutionRejected, match="budget"):
        service.retry(exhausted)

    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT status FROM agent_executions WHERE execution_id=:id"),
                {"id": first_retry.execution_id},
            )
            == "RUNNING"
        )


def test_retry_accepts_worker_sandbox_unavailable(mysql_engine: Engine):
    task_id, lease, execution_id = _running(mysql_engine, "2")
    command = _retry(task_id, execution_id, lease.owner_id, lease.lease_token, "b")
    command = replace(
        command,
        failure={
            **command.failure,
            "code": "WORKER_SANDBOX_UNAVAILABLE",
            "message": "worker sandbox could not be allocated",
        },
    )

    result = WorkerTaskExecutionService(mysql_engine).retry(command)

    assert result.outcome is WorkerExecutionOutcome.APPLIED
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT failure_code FROM agent_executions WHERE execution_id=:id"
                ),
                {"id": execution_id},
            )
            == "WORKER_SANDBOX_UNAVAILABLE"
        )
        assert (
            connection.scalar(
                text("SELECT status FROM agent_executions WHERE execution_id=:id"),
                {"id": result.execution_id},
            )
            == "RUNNING"
        )


def test_concurrent_request_across_tasks_has_one_winner(mysql_engine: Engine):
    first_task, first_lease, first_execution = _running(mysql_engine, "d")
    second_task, second_lease, second_execution = _running(mysql_engine, "e")
    request_id = "WRR-" + "9" * 32
    commands = (
        replace(
            _retry(
                first_task,
                first_execution,
                first_lease.owner_id,
                first_lease.lease_token,
                "4",
            ),
            request_id=request_id,
        ),
        replace(
            _retry(
                second_task,
                second_execution,
                second_lease.owner_id,
                second_lease.lease_token,
                "5",
            ),
            request_id=request_id,
        ),
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(
            pool.map(WorkerTaskExecutionService(mysql_engine).retry, commands)
        )

    assert {result.outcome for result in results} == {
        WorkerExecutionOutcome.APPLIED,
        WorkerExecutionOutcome.DUPLICATE_CONFLICTING,
    }
    loser = (
        second_task
        if results[0].outcome is WorkerExecutionOutcome.APPLIED
        else first_task
    )
    with mysql_engine.connect() as connection:
        task = (
            connection.execute(
                text(
                    "SELECT status,revision,attempt_count FROM agent_tasks WHERE task_id=:id"
                ),
                {"id": loser},
            )
            .mappings()
            .one()
        )
        assert (task["status"], task["revision"], task["attempt_count"]) == (
            "RUNNING",
            1,
            1,
        )
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM worker_task_execution_retry_requests WHERE request_id=:id"
                ),
                {"id": request_id},
            )
            == 1
        )


def test_new_attempt_failure_rolls_back_old_attempt_task_and_request(
    mysql_engine: Engine, monkeypatch: pytest.MonkeyPatch
):
    task_id, lease, execution_id = _running(mysql_engine, "f")
    service = WorkerTaskExecutionService(mysql_engine)
    monkeypatch.setattr(
        service,
        "_insert_running_execution",
        lambda *args: (_ for _ in ()).throw(
            RuntimeError("injected new execution history failure")
        ),
    )

    with pytest.raises(RuntimeError, match="injected new execution history failure"):
        service.retry(
            _retry(task_id, execution_id, lease.owner_id, lease.lease_token, "7")
        )

    with mysql_engine.connect() as connection:
        task = (
            connection.execute(
                text(
                    "SELECT status,revision,attempt_count FROM agent_tasks WHERE task_id=:id"
                ),
                {"id": task_id},
            )
            .mappings()
            .one()
        )
        assert (task["status"], task["revision"], task["attempt_count"]) == (
            "RUNNING",
            1,
            1,
        )
        assert (
            connection.scalar(
                text("SELECT status FROM agent_executions WHERE execution_id=:id"),
                {"id": execution_id},
            )
            == "RUNNING"
        )
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM agent_task_leases WHERE task_id=:id"),
                {"id": task_id},
            )
            == 1
        )
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM worker_task_execution_retry_requests WHERE task_id=:id"
                ),
                {"id": task_id},
            )
            == 0
        )


def test_concurrent_identical_retry_creates_one_new_attempt(mysql_engine: Engine):
    task_id, lease, execution_id = _running(mysql_engine, "0")
    command = _retry(task_id, execution_id, lease.owner_id, lease.lease_token, "8")
    service = WorkerTaskExecutionService(mysql_engine)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.retry, (command, command)))

    assert {result.outcome for result in results} == {
        WorkerExecutionOutcome.APPLIED,
        WorkerExecutionOutcome.DUPLICATE_IDENTICAL,
    }
    assert results[0].execution_id == results[1].execution_id
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM agent_executions WHERE task_id=:id"),
                {"id": task_id},
            )
            == 2
        )


def test_retried_attempt_can_complete_task(mysql_engine: Engine):
    task_id, lease, execution_id = _running(mysql_engine, "1")
    service = WorkerTaskExecutionService(mysql_engine)
    retry_result = service.retry(
        _retry(task_id, execution_id, lease.owner_id, lease.lease_token, "a")
    )

    completed = service.complete(
        CompleteWorkerExecutionCommand(
            request_id="WCR-" + "A" * 32,
            task_id=task_id,
            execution_id=str(retry_result.execution_id),
            owner_id=lease.owner_id,
            lease_token=lease.lease_token,
            final_status="SUCCEEDED",
            result={
                "output_artifact_refs": ["artifact:retry-success"],
                "decision_id": None,
                "evidence_refs": [],
            },
        )
    )

    assert completed.outcome is WorkerExecutionOutcome.APPLIED
    with mysql_engine.connect() as connection:
        task = (
            connection.execute(
                text(
                    "SELECT status,revision,attempt_count FROM agent_tasks WHERE task_id=:id"
                ),
                {"id": task_id},
            )
            .mappings()
            .one()
        )
        assert (task["status"], task["revision"], task["attempt_count"]) == (
            "SUCCEEDED",
            3,
            2,
        )
