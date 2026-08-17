from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from sqlalchemy import Engine, create_engine, text
from testcontainers.community.mysql import MySqlContainer

from factoryops_agent_service.coordinator_start.model import StartCoordinatorCommand
from factoryops_agent_service.coordinator_start.service import (
    CoordinatorStartService,
    StartOutcome,
)
from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.execution_lifecycle.model import CreateExecutionCommand
from factoryops_agent_service.execution_lifecycle.service import (
    AgentExecutionLifecycleService,
)
from factoryops_agent_service.run_lifecycle.model import (
    OriginalRunCommand,
    RunProvenance,
)
from factoryops_agent_service.run_lifecycle.service import AgentRunLifecycleService

NOW = datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def mysql_engine() -> Engine:
    with MySqlContainer("mysql:8.4") as mysql:
        engine = create_engine(
            mysql.get_connection_url().replace("mysql://", "mysql+pymysql://", 1)
        )
        migrate(engine)
        yield engine
        engine.dispose()


def _run(engine: Engine, marker: str) -> str:
    contract_marker = marker.upper()
    event_id = "EVT-" + contract_marker * 64
    incident_id = "QI-" + contract_marker * 64
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO agent_event_inbox (
                  event_id, event_type, contract_version, topic, kafka_partition,
                  kafka_offset, message_key, raw_payload, canonical_sha256, received_at)
                VALUES (:event, 'quality.incident.opened', '1.0', 'topic', 0,
                  :offset, :incident, '{}', UNHEX(REPEAT(:marker, 64)), :now)
                """
            ),
            {
                "event": event_id,
                "incident": incident_id,
                "offset": int(marker, 16),
                "marker": marker,
                "now": NOW,
            },
        )
    result = AgentRunLifecycleService(engine, clock=lambda: NOW).create_original_run(
        OriginalRunCommand(
            event_id,
            RunProvenance(
                incident_id,
                "runtime:v1",
                "workflow:v1",
                "prompts:v1",
                "model:v1",
                "tools:v1",
                "context:v1",
                "a" * 40,
            ),
        )
    )
    return str(result.run["identity"]["run_id"])


def _command(
    run_id: str,
    marker: str = "1",
    *,
    prompt: str = "coordinator/v1",
    evidence_refs: tuple[str, ...] | None = None,
) -> StartCoordinatorCommand:
    contract_marker = marker.upper()
    return StartCoordinatorCommand(
        start_request_id="SRQ-" + contract_marker * 32,
        run_id=run_id,
        prompt_version=prompt,
        context_snapshot_id="CTX-" + contract_marker * 32,
        evidence_refs=evidence_refs
        if evidence_refs is not None
        else ("inspection:" + marker, "incident:" + marker),
    )


def _service(engine: Engine) -> CoordinatorStartService:
    return CoordinatorStartService(engine, clock=lambda: NOW)


def test_start_is_atomic_and_rebuilds_both_contracts(mysql_engine: Engine) -> None:
    run_id = _run(mysql_engine, "5")
    result = _service(mysql_engine).start(_command(run_id, "5"))

    assert result.outcome is StartOutcome.APPLIED
    assert result.run["lifecycle"]["status"] == "RUNNING"
    assert result.run["lifecycle"]["revision"] == 1
    assert result.execution["identity"]["agent_role"] == "coordinator"
    assert result.execution["identity"]["attempt"] == 1
    execution_id = result.execution["identity"]["execution_id"]
    assert result.run["execution_refs"]["coordinator_execution_id"] == execution_id
    assert result.run["progress"]["agent_execution_count"] == 1
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM agent_run_transitions WHERE run_id=:id"),
                {"id": run_id},
            )
            == 2
        )
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM agent_execution_transitions WHERE execution_id=:id"
                ),
                {"id": execution_id},
            )
            == 1
        )


def test_replay_is_identical_or_conflicting(mysql_engine: Engine) -> None:
    run_id = _run(mysql_engine, "6")
    command = _command(run_id, "6")
    first = _service(mysql_engine).start(command)
    same = _service(mysql_engine).start(command)
    conflict = _service(mysql_engine).start(
        _command(run_id, "6", prompt="coordinator/v2")
    )

    assert first.outcome is StartOutcome.APPLIED
    assert same.outcome is StartOutcome.DUPLICATE_IDENTICAL
    assert conflict.outcome is StartOutcome.DUPLICATE_CONFLICTING
    assert same.execution == first.execution


def test_non_empty_evidence_is_persisted_and_changes_request_digest(
    mysql_engine: Engine,
) -> None:
    run_id = _run(mysql_engine, "c")
    command = _command(run_id, "c", evidence_refs=("incident:c",))

    first = _service(mysql_engine).start(command)
    conflict = _service(mysql_engine).start(
        _command(run_id, "c", evidence_refs=("incident:changed",))
    )

    assert first.outcome is StartOutcome.APPLIED
    assert first.execution["input"]["evidence_refs"] == ["incident:c"]
    assert conflict.outcome is StartOutcome.DUPLICATE_CONFLICTING


def test_different_requests_have_one_concurrent_winner(mysql_engine: Engine) -> None:
    run_id = _run(mysql_engine, "7")
    commands = (_command(run_id, "7"), _command(run_id, "8"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda c: _service(mysql_engine).start(c), commands))

    assert [r.outcome for r in results].count(StartOutcome.APPLIED) == 1
    assert [r.outcome for r in results].count(StartOutcome.CONCURRENCY_CONFLICT) == 1
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM agent_executions WHERE run_id=:id"),
                {"id": run_id},
            )
            == 1
        )


def test_invalid_input_does_not_change_run(mysql_engine: Engine) -> None:
    run_id = _run(mysql_engine, "9")
    with pytest.raises(ValueError, match="Execution Contract"):
        _service(mysql_engine).start(
            StartCoordinatorCommand(
                "SRQ-" + "9" * 32, run_id, "coordinator/v1", "bad", ()
            )
        )
    with mysql_engine.connect() as connection:
        row = connection.execute(
            text("SELECT status, revision FROM agent_runs WHERE run_id=:id"),
            {"id": run_id},
        ).one()
    assert row == ("PENDING", 0)


def test_run_history_failure_rolls_back_everything(
    mysql_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = _run(mysql_engine, "a")
    execution_id = "EXE-" + "A" * 32
    service = CoordinatorStartService(
        mysql_engine,
        clock=lambda: NOW,
        execution_id_factory=lambda: execution_id,
    )

    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("injected run history failure")

    monkeypatch.setattr(service._repository, "_insert_run_history", fail)
    with pytest.raises(RuntimeError, match="injected"):
        service.start(_command(run_id, "a"))

    with mysql_engine.connect() as connection:
        run = connection.execute(
            text(
                "SELECT status, revision, coordinator_execution_id FROM agent_runs WHERE run_id=:id"
            ),
            {"id": run_id},
        ).one()
        executions = connection.scalar(
            text("SELECT COUNT(*) FROM agent_executions WHERE run_id=:id"),
            {"id": run_id},
        )
        run_history = connection.scalar(
            text("SELECT COUNT(*) FROM agent_run_transitions WHERE run_id=:id"),
            {"id": run_id},
        )
        execution_history = connection.scalar(
            text(
                "SELECT COUNT(*) FROM agent_execution_transitions WHERE execution_id=:id"
            ),
            {"id": execution_id},
        )
        receipts = connection.scalar(
            text("SELECT COUNT(*) FROM coordinator_start_requests WHERE run_id=:id"),
            {"id": run_id},
        )
    assert run == ("PENDING", 0, None)
    assert executions == 0
    assert run_history == 1
    assert execution_history == 0
    assert receipts == 0


def test_preexisting_coordinator_key_is_a_stable_conflict(mysql_engine: Engine) -> None:
    run_id = _run(mysql_engine, "b")
    created = AgentExecutionLifecycleService(
        mysql_engine, clock=lambda: NOW
    ).create_execution(
        CreateExecutionCommand(
            run_id,
            "coordinator",
            1,
            None,
            "runtime:v1",
            "coordinator/v1",
            "model:v1",
            "tools:v1",
            "context:v1",
            "a" * 40,
            "CTX-" + "B" * 32,
            (),
        )
    )

    result = _service(mysql_engine).start(_command(run_id, "b"))

    assert result.outcome is StartOutcome.CONCURRENCY_CONFLICT
    assert result.execution == created.execution
    assert result.run["lifecycle"]["status"] == "PENDING"
