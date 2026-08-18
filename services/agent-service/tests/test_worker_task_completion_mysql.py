from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from sqlalchemy import Engine, create_engine, text
from test_worker_task_execution_mysql import _start_command, _task
from testcontainers.community.mysql import MySqlContainer

from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.task_lease import AgentTaskLeaseService
from factoryops_agent_service.worker_task_execution import (
    CompleteWorkerExecutionCommand,
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


def _running(engine: Engine, marker: str):
    task_id = _task(engine, marker)
    lease = AgentTaskLeaseService(engine).claim(task_id, "worker-" + marker, 120)
    execution = WorkerTaskExecutionService(engine).start(
        _start_command(task_id, lease.owner_id, lease.lease_token, marker)
    )
    return task_id, lease, str(execution.execution_id)


def _success(task_id: str, execution_id: str, owner: str, token: str, marker: str):
    return CompleteWorkerExecutionCommand(
        request_id="WCR-" + marker.upper() * 32,
        task_id=task_id,
        execution_id=execution_id,
        owner_id=owner,
        lease_token=token,
        final_status="SUCCEEDED",
        result={
            "output_artifact_refs": ["artifact:" + marker],
            "decision_id": None,
            "evidence_refs": ["evidence:" + marker],
        },
    )


def test_success_atomically_finishes_pair_and_releases_lease(
    mysql_engine: Engine,
) -> None:
    task_id, lease, execution_id = _running(mysql_engine, "1")
    result = WorkerTaskExecutionService(mysql_engine).complete(
        _success(task_id, execution_id, lease.owner_id, lease.lease_token, "1")
    )
    assert result.outcome is WorkerExecutionOutcome.APPLIED
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT status FROM agent_tasks WHERE task_id=:id"),
                {"id": task_id},
            )
            == "SUCCEEDED"
        )
        assert (
            connection.scalar(
                text("SELECT status FROM agent_executions WHERE execution_id=:id"),
                {"id": execution_id},
            )
            == "SUCCEEDED"
        )
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM agent_task_leases WHERE task_id=:id"),
                {"id": task_id},
            )
            == 0
        )


def test_non_retryable_failure_finishes_task_and_execution(
    mysql_engine: Engine,
) -> None:
    task_id, lease, execution_id = _running(mysql_engine, "2")
    command = CompleteWorkerExecutionCommand(
        request_id="WCR-" + "2" * 32,
        task_id=task_id,
        execution_id=execution_id,
        owner_id=lease.owner_id,
        lease_token=lease.lease_token,
        final_status="FAILED",
        failure={
            "code": "INVALID_EVIDENCE",
            "message": "evidence cannot be processed",
            "recoverability": "non_retryable",
            "failed_dependency_ref": None,
        },
    )
    WorkerTaskExecutionService(mysql_engine).complete(command)
    with mysql_engine.connect() as connection:
        task = (
            connection.execute(
                text("SELECT * FROM agent_tasks WHERE task_id=:id"), {"id": task_id}
            )
            .mappings()
            .one()
        )
        execution = (
            connection.execute(
                text("SELECT * FROM agent_executions WHERE execution_id=:id"),
                {"id": execution_id},
            )
            .mappings()
            .one()
        )
        assert (
            task["status"],
            task["failure_execution_id"],
            task["failure_recoverability"],
        ) == ("FAILED", execution_id, "non_retryable")
        assert (execution["status"], execution["failure_code"]) == (
            "FAILED",
            "INVALID_EVIDENCE",
        )


def test_completion_replay_and_stale_lease_are_classified(mysql_engine: Engine) -> None:
    task_id, lease, execution_id = _running(mysql_engine, "3")
    command = _success(task_id, execution_id, lease.owner_id, lease.lease_token, "3")
    service = WorkerTaskExecutionService(mysql_engine)
    first = service.complete(command)
    same = service.complete(command)
    conflict = service.complete(
        replace(command, result={**command.result, "evidence_refs": ["changed"]})
    )
    assert first.outcome is WorkerExecutionOutcome.APPLIED
    assert same.outcome is WorkerExecutionOutcome.DUPLICATE_IDENTICAL
    assert conflict.outcome is WorkerExecutionOutcome.DUPLICATE_CONFLICTING

    other_task, other_lease, other_execution = _running(mysql_engine, "4")
    with pytest.raises(WorkerExecutionRejected, match="lease"):
        service.complete(
            _success(other_task, other_execution, "wrong", other_lease.lease_token, "4")
        )


def test_concurrent_same_request_different_tasks_is_stably_conflicting(
    mysql_engine: Engine,
) -> None:
    first_task, first_lease, first_execution = _running(mysql_engine, "7")
    second_task, second_lease, second_execution = _running(mysql_engine, "8")
    request_id = "WCR-" + "7" * 32
    commands = (
        replace(
            _success(
                first_task,
                first_execution,
                first_lease.owner_id,
                first_lease.lease_token,
                "7",
            ),
            request_id=request_id,
        ),
        replace(
            _success(
                second_task,
                second_execution,
                second_lease.owner_id,
                second_lease.lease_token,
                "8",
            ),
            request_id=request_id,
        ),
    )
    service = WorkerTaskExecutionService(mysql_engine)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(service.complete, commands))

    assert {result.outcome for result in results} == {
        WorkerExecutionOutcome.APPLIED,
        WorkerExecutionOutcome.DUPLICATE_CONFLICTING,
    }
    winner = next(
        result for result in results if result.outcome is WorkerExecutionOutcome.APPLIED
    )
    loser_task = second_task if winner.task_id == first_task else first_task
    loser_execution = second_execution if loser_task == second_task else first_execution
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM worker_task_execution_completion_requests WHERE request_id=:id"
                ),
                {"id": request_id},
            )
            == 1
        )
        assert (
            connection.scalar(
                text("SELECT status FROM agent_tasks WHERE task_id=:id"),
                {"id": loser_task},
            )
            == "RUNNING"
        )
        assert (
            connection.scalar(
                text("SELECT status FROM agent_executions WHERE execution_id=:id"),
                {"id": loser_execution},
            )
            == "RUNNING"
        )
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM agent_task_leases WHERE task_id=:id"),
                {"id": loser_task},
            )
            == 1
        )


def test_concurrent_identical_completion_writes_one_fact(mysql_engine: Engine) -> None:
    task_id, lease, execution_id = _running(mysql_engine, "9")
    command = _success(task_id, execution_id, lease.owner_id, lease.lease_token, "9")
    service = WorkerTaskExecutionService(mysql_engine)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(service.complete, (command, command)))

    assert {result.outcome for result in results} == {
        WorkerExecutionOutcome.APPLIED,
        WorkerExecutionOutcome.DUPLICATE_IDENTICAL,
    }
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM worker_task_execution_completion_requests WHERE request_id=:id"
                ),
                {"id": command.request_id},
            )
            == 1
        )
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM agent_execution_transitions WHERE execution_id=:id"
                ),
                {"id": execution_id},
            )
            == 3
        )


def test_completion_history_failure_rolls_back_pair_and_lease(
    mysql_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_id, lease, execution_id = _running(mysql_engine, "5")
    service = WorkerTaskExecutionService(mysql_engine)
    monkeypatch.setattr(
        service,
        "_insert_completion_history",
        lambda *args: (_ for _ in ()).throw(
            RuntimeError("injected completion history failure")
        ),
    )
    with pytest.raises(RuntimeError, match="injected completion history failure"):
        service.complete(
            _success(task_id, execution_id, lease.owner_id, lease.lease_token, "5")
        )
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT status FROM agent_tasks WHERE task_id=:id"),
                {"id": task_id},
            )
            == "RUNNING"
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
                text("SELECT owner_id FROM agent_task_leases WHERE task_id=:id"),
                {"id": task_id},
            )
            == lease.owner_id
        )
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM worker_task_execution_completion_requests WHERE task_id=:id"
                ),
                {"id": task_id},
            )
            == 0
        )


def test_completion_rejects_contract_invalid_result(mysql_engine: Engine) -> None:
    task_id, lease, execution_id = _running(mysql_engine, "6")
    invalid = replace(
        _success(task_id, execution_id, lease.owner_id, lease.lease_token, "6"),
        result={
            "output_artifact_refs": [],
            "decision_id": None,
            "evidence_refs": [],
        },
    )
    with pytest.raises(WorkerExecutionRejected, match="artifacts"):
        WorkerTaskExecutionService(mysql_engine).complete(invalid)
