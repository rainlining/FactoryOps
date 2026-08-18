from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import Engine, create_engine, text
from test_coordinator_start_mysql import _command as coordinator_command
from test_coordinator_start_mysql import _run
from test_coordinator_start_mysql import _service as coordinator_service
from test_coordinator_task_dispatch_mysql import _dispatch
from testcontainers.community.mysql import MySqlContainer

from factoryops_agent_service.coordinator_task_dispatch.model import DispatchCommand
from factoryops_agent_service.coordinator_task_dispatch.service import (
    CoordinatorTaskDispatchService,
)
from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.task_lease import AgentTaskLeaseService
from factoryops_agent_service.worker_task_execution import (
    StartWorkerExecutionCommand,
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


def _task(engine: Engine, marker: str, dependencies: tuple[str, ...] = ()) -> str:
    run_id = _run(engine, marker)
    coordinator = coordinator_service(engine).start(coordinator_command(run_id, marker))
    execution_id = str(coordinator.execution["identity"]["execution_id"])
    command: DispatchCommand = _dispatch(run_id, execution_id, marker)
    command = replace(command, dependency_task_ids=dependencies)
    task = CoordinatorTaskDispatchService(engine).dispatch(command).task
    return str(task["identity"]["task_id"])


def _start_command(
    task_id: str, owner: str, token: str, marker: str
) -> StartWorkerExecutionCommand:
    return StartWorkerExecutionCommand(
        request_id="WSR-" + marker.upper() * 32,
        task_id=task_id,
        owner_id=owner,
        lease_token=token,
        runtime_version="runtime-v1",
        prompt_version="prompt-v1",
        model_policy_version="model-v1",
        tool_policy_version="tool-v1",
        context_policy_version="context-v1",
        code_revision="a" * 40,
    )


def test_valid_lease_starts_task_and_execution_atomically(mysql_engine: Engine) -> None:
    task_id = _task(mysql_engine, "7")
    lease = AgentTaskLeaseService(mysql_engine).claim(task_id, "worker-1", 60)
    result = WorkerTaskExecutionService(mysql_engine).start(
        _start_command(task_id, lease.owner_id, lease.lease_token, "7")
    )

    assert result.outcome is WorkerExecutionOutcome.APPLIED
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
                {"id": result.execution_id},
            )
            .mappings()
            .one()
        )
        assert (task["status"], task["revision"], task["current_execution_id"]) == (
            "RUNNING",
            1,
            result.execution_id,
        )
        assert (execution["status"], execution["revision"], execution["attempt"]) == (
            "RUNNING",
            1,
            1,
        )
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM agent_execution_transitions WHERE execution_id=:id"
                ),
                {"id": result.execution_id},
            )
            == 2
        )


def test_start_replay_is_classified_without_duplicate_rows(
    mysql_engine: Engine,
) -> None:
    task_id = _task(mysql_engine, "8")
    lease = AgentTaskLeaseService(mysql_engine).claim(task_id, "worker-2", 60)
    command = _start_command(task_id, lease.owner_id, lease.lease_token, "8")
    service = WorkerTaskExecutionService(mysql_engine)

    first = service.start(command)
    same = service.start(command)
    conflict = service.start(replace(command, runtime_version="runtime-v2"))

    assert first.outcome is WorkerExecutionOutcome.APPLIED
    assert same.outcome is WorkerExecutionOutcome.DUPLICATE_IDENTICAL
    assert conflict.outcome is WorkerExecutionOutcome.DUPLICATE_CONFLICTING
    assert first.execution_id == same.execution_id == conflict.execution_id


def test_missing_expired_or_wrong_lease_is_rejected(mysql_engine: Engine) -> None:
    task_id = _task(mysql_engine, "9")
    now = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
    lease = AgentTaskLeaseService(mysql_engine).claim(task_id, "worker-3", 30, now=now)
    service = WorkerTaskExecutionService(
        mysql_engine, clock=lambda: now + timedelta(seconds=31)
    )

    with pytest.raises(WorkerExecutionRejected, match="lease"):
        service.start(_start_command(task_id, lease.owner_id, lease.lease_token, "9"))
    with pytest.raises(WorkerExecutionRejected, match="lease"):
        WorkerTaskExecutionService(mysql_engine, clock=lambda: now).start(
            _start_command(task_id, "wrong-worker", lease.lease_token, "a")
        )
    with pytest.raises(WorkerExecutionRejected, match="non-blank"):
        WorkerTaskExecutionService(mysql_engine, clock=lambda: now).start(
            replace(
                _start_command(task_id, lease.owner_id, lease.lease_token, "d"),
                runtime_version="",
            )
        )


def test_unsatisfied_dependency_and_history_failure_leave_no_partial_start(
    mysql_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    dependency_id = _task(mysql_engine, "a")
    with mysql_engine.connect() as connection:
        parent = (
            connection.execute(
                text(
                    "SELECT run_id,created_by_execution_id FROM agent_tasks WHERE task_id=:id"
                ),
                {"id": dependency_id},
            )
            .mappings()
            .one()
        )
    dependent_command = replace(
        _dispatch(str(parent["run_id"]), str(parent["created_by_execution_id"]), "b"),
        dependency_task_ids=(dependency_id,),
    )
    dependent = (
        CoordinatorTaskDispatchService(mysql_engine).dispatch(dependent_command).task
    )
    task_id = str(dependent["identity"]["task_id"])
    lease = AgentTaskLeaseService(mysql_engine).claim(task_id, "worker-4", 60)
    with pytest.raises(WorkerExecutionRejected, match="dependencies"):
        WorkerTaskExecutionService(mysql_engine).start(
            _start_command(task_id, lease.owner_id, lease.lease_token, "b")
        )

    rollback_task_id = _task(mysql_engine, "c")
    rollback_lease = AgentTaskLeaseService(mysql_engine).claim(
        rollback_task_id, "worker-5", 60
    )
    service = WorkerTaskExecutionService(mysql_engine)
    monkeypatch.setattr(
        service,
        "_insert_execution_history",
        lambda *args: (_ for _ in ()).throw(RuntimeError("injected history failure")),
    )
    with pytest.raises(RuntimeError, match="injected history failure"):
        service.start(
            _start_command(
                rollback_task_id,
                rollback_lease.owner_id,
                rollback_lease.lease_token,
                "c",
            )
        )
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT status FROM agent_tasks WHERE task_id=:id"),
                {"id": rollback_task_id},
            )
            == "PENDING"
        )
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM agent_executions WHERE task_id=:id"),
                {"id": rollback_task_id},
            )
            == 0
        )
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM worker_task_execution_start_requests WHERE task_id=:id"
                ),
                {"id": rollback_task_id},
            )
            == 0
        )
