from __future__ import annotations

import pytest
from sqlalchemy import Engine, create_engine, text
from test_coordinator_start_mysql import _command, _run, _service
from testcontainers.community.mysql import MySqlContainer

from factoryops_agent_service.coordinator_task_dispatch.model import DispatchCommand
from factoryops_agent_service.coordinator_task_dispatch.service import (
    CoordinatorTaskDispatchService,
    DispatchOutcome,
)
from factoryops_agent_service.event_ingress.migration import migrate


@pytest.fixture(scope="module")
def mysql_engine() -> Engine:
    with MySqlContainer("mysql:8.4") as mysql:
        engine = create_engine(
            mysql.get_connection_url().replace("mysql://", "mysql+pymysql://", 1)
        )
        migrate(engine)
        yield engine
        engine.dispose()


def _started(engine: Engine, marker: str) -> tuple[str, str]:
    run_id = _run(engine, marker)
    started = _service(engine).start(_command(run_id, marker))
    return run_id, str(started.execution["identity"]["execution_id"])


def _dispatch(run_id: str, execution_id: str, marker: str = "1") -> DispatchCommand:
    return DispatchCommand(
        task_request_id="TQR-" + marker.upper() * 32,
        run_id=run_id,
        coordinator_execution_id=execution_id,
        task_type="QUALITY_ANALYSIS",
        target_agent_role="quality",
        priority=50,
        context_snapshot_id="CTX-" + marker.upper() * 32,
        evidence_refs=("inspection:" + marker,),
        dependency_task_ids=(),
    )


def test_dispatch_creates_pending_task_and_history(mysql_engine: Engine) -> None:
    run_id, execution_id = _started(mysql_engine, "c")
    result = CoordinatorTaskDispatchService(mysql_engine).dispatch(
        _dispatch(run_id, execution_id, "c")
    )
    assert result.outcome is DispatchOutcome.APPLIED
    assert result.task["lifecycle"]["status"] == "PENDING"
    assert result.task["assignment"]["created_by_execution_id"] == execution_id


def test_dispatch_replay_is_idempotent(mysql_engine: Engine) -> None:
    run_id, execution_id = _started(mysql_engine, "d")
    command = _dispatch(run_id, execution_id, "d")
    first = CoordinatorTaskDispatchService(mysql_engine).dispatch(command)
    same = CoordinatorTaskDispatchService(mysql_engine).dispatch(command)
    conflict = CoordinatorTaskDispatchService(mysql_engine).dispatch(
        _dispatch(run_id, execution_id, "d")
    )
    assert first.outcome is DispatchOutcome.APPLIED
    assert same.outcome is DispatchOutcome.DUPLICATE_IDENTICAL
    assert conflict.outcome is DispatchOutcome.DUPLICATE_IDENTICAL


def test_non_running_or_wrong_owner_is_rejected(mysql_engine: Engine) -> None:
    run_id = _run(mysql_engine, "e")
    with pytest.raises(ValueError, match="Coordinator execution"):
        CoordinatorTaskDispatchService(mysql_engine).dispatch(
            _dispatch(run_id, "EXE-" + "E" * 32, "e")
        )


def test_history_failure_rolls_back_task(
    mysql_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id, execution_id = _started(mysql_engine, "f")
    service = CoordinatorTaskDispatchService(mysql_engine)
    monkeypatch.setattr(
        service._repository,
        "_insert_history",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("injected")),
    )
    with pytest.raises(RuntimeError, match="injected"):
        service.dispatch(_dispatch(run_id, execution_id, "f"))
    with mysql_engine.connect() as c:
        assert (
            c.scalar(
                text("SELECT COUNT(*) FROM agent_tasks WHERE run_id=:id"),
                {"id": run_id},
            )
            == 0
        )
