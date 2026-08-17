from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from sqlalchemy import Engine, create_engine, event, text
from testcontainers.community.mysql import MySqlContainer

from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.execution_lifecycle.model import (
    CreateExecutionCommand,
    ExecutionStatus,
    OperationOutcome,
    TransitionCommand,
)
from factoryops_agent_service.execution_lifecycle.service import (
    AgentExecutionLifecycleService,
    ExecutionCreationRejected,
)
from factoryops_agent_service.run_lifecycle.model import (
    OriginalRunCommand,
    RunProvenance,
)
from factoryops_agent_service.run_lifecycle.service import AgentRunLifecycleService

NOW = datetime(2026, 8, 17, 1, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def mysql_engine() -> Engine:
    with MySqlContainer("mysql:8.4") as mysql:
        engine = create_engine(
            mysql.get_connection_url().replace("mysql://", "mysql+pymysql://", 1)
        )
        migrate(engine)
        yield engine
        engine.dispose()


def run(engine: Engine, marker: str) -> str:
    event = "EVT-" + marker * 64
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO agent_event_inbox(event_id,event_type,contract_version,topic,kafka_partition,kafka_offset,message_key,raw_payload,canonical_sha256,received_at) VALUES (:e,'quality.incident.opened','1.0','t',0,:o,:k,'{}',UNHEX(REPEAT(:m,64)),:t)"
            ),
            {
                "e": event,
                "o": int(marker, 16),
                "k": "QI-" + marker * 64,
                "m": marker,
                "t": NOW,
            },
        )
    result = AgentRunLifecycleService(engine, clock=lambda: NOW).create_original_run(
        OriginalRunCommand(
            event,
            RunProvenance(
                "QI-" + marker * 64,
                "runtime:1",
                "workflow:1",
                "prompt:1",
                "model:1",
                "tool:1",
                "context:1",
                "a" * 40,
            ),
        )
    )
    return str(result.run["identity"]["run_id"])


def create(
    run_id: str, role: str = "coordinator", task_id: str | None = None, attempt: int = 1
) -> CreateExecutionCommand:
    return CreateExecutionCommand(
        run_id,
        role,
        attempt,
        task_id,
        "runtime:1",
        "prompt:1",
        "model:1",
        "tool:1",
        "context:1",
        "a" * 40,
        "CTX-" + "1" * 32,
        ("incident:1",),
    )


def transition(
    eid: str,
    request: str,
    source: ExecutionStatus,
    revision: int,
    target: ExecutionStatus,
    **kw: object,
) -> TransitionCommand:
    return TransitionCommand(
        "ERQ-" + request * 32,
        eid,
        source,
        revision,
        target,
        "WORKER",
        "worker",
        "STATE_CHANGED",
        "changed",
        kw.get("result"),
        kw.get("failure"),
    )


def test_schema_and_creation_idempotency(mysql_engine: Engine) -> None:
    with mysql_engine.connect() as c:
        assert c.scalar(text("SELECT COUNT(*) FROM agent_schema_history")) == 5
    run_id = run(mysql_engine, "1")
    service = AgentExecutionLifecycleService(mysql_engine, clock=lambda: NOW)
    command = create(run_id)
    applied = service.create_execution(command)
    same = service.create_execution(command)
    conflicting = service.create_execution(
        CreateExecutionCommand(**{**command.__dict__, "prompt_version": "prompt:2"})
    )
    assert applied.outcome is OperationOutcome.APPLIED
    assert same.outcome is OperationOutcome.DUPLICATE_IDENTICAL
    assert conflicting.outcome is OperationOutcome.DUPLICATE_CONFLICTING


def test_missing_run_and_task_are_rejected(mysql_engine: Engine) -> None:
    service = AgentExecutionLifecycleService(mysql_engine, clock=lambda: NOW)
    with pytest.raises(ExecutionCreationRejected, match="Run"):
        service.create_execution(create("RUN-" + "F" * 32))
    run_id = run(mysql_engine, "2")
    with pytest.raises(ExecutionCreationRejected, match="Task"):
        service.create_execution(create(run_id, "quality", "TSK-" + "F" * 32))


def test_transition_result_retry_and_concurrency(mysql_engine: Engine) -> None:
    run_id = run(mysql_engine, "3")
    service = AgentExecutionLifecycleService(mysql_engine, clock=lambda: NOW)
    eid = str(
        service.create_execution(create(run_id)).execution["identity"]["execution_id"]
    )
    assert (
        service.transition_execution(
            transition(eid, "1", ExecutionStatus.PENDING, 0, ExecutionStatus.RUNNING)
        ).outcome
        is OperationOutcome.APPLIED
    )
    commands = (
        transition(
            eid,
            "2",
            ExecutionStatus.RUNNING,
            1,
            ExecutionStatus.SUCCEEDED,
            result={
                "output_artifact_refs": ["artifact:1"],
                "decision_id": None,
                "evidence_refs": [],
            },
        ),
        transition(eid, "3", ExecutionStatus.RUNNING, 1, ExecutionStatus.CANCELLED),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(service.transition_execution, commands))
    assert {r.outcome for r in results} == {
        OperationOutcome.APPLIED,
        OperationOutcome.CONCURRENCY_CONFLICT,
    }
    winner = next(r for r in results if r.outcome is OperationOutcome.APPLIED)
    same = service.transition_execution(
        commands[0]
        if winner.execution["lifecycle"]["status"] == "SUCCEEDED"
        else commands[1]
    )
    assert same.outcome is OperationOutcome.DUPLICATE_IDENTICAL


def test_history_failure_rolls_back(mysql_engine: Engine) -> None:
    run_id = run(mysql_engine, "4")
    service = AgentExecutionLifecycleService(mysql_engine, clock=lambda: NOW)
    eid = str(
        service.create_execution(create(run_id)).execution["identity"]["execution_id"]
    )

    def fail(
        _c: object,
        _cur: object,
        statement: str,
        params: object,
        _ctx: object,
        _many: bool,
    ) -> None:
        if (
            "INSERT INTO agent_execution_transitions" in statement
            and isinstance(params, dict)
            and params.get("to_revision") == 1
        ):
            raise RuntimeError("history failure")

    event.listen(mysql_engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="history failure"):
            service.transition_execution(
                transition(
                    eid, "4", ExecutionStatus.PENDING, 0, ExecutionStatus.RUNNING
                )
            )
    finally:
        event.remove(mysql_engine, "before_cursor_execute", fail)
    assert service.get_execution(eid)["lifecycle"]["revision"] == 0


def test_initial_history_failure_rolls_back(mysql_engine: Engine) -> None:
    run_id = run(mysql_engine, "5")
    service = AgentExecutionLifecycleService(mysql_engine, clock=lambda: NOW)

    def fail(
        _c: object,
        _cur: object,
        statement: str,
        _params: object,
        _ctx: object,
        _many: bool,
    ) -> None:
        if "INSERT INTO agent_execution_transitions" in statement:
            raise RuntimeError("initial history failure")

    event.listen(mysql_engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="initial history failure"):
            service.create_execution(create(run_id))
    finally:
        event.remove(mysql_engine, "before_cursor_execute", fail)
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM agent_executions WHERE run_id=:run"),
                {"run": run_id},
            )
            == 0
        )


def test_failed_execution_round_trips(mysql_engine: Engine) -> None:
    run_id = run(mysql_engine, "6")
    service = AgentExecutionLifecycleService(mysql_engine, clock=lambda: NOW)
    eid = str(
        service.create_execution(create(run_id)).execution["identity"]["execution_id"]
    )
    service.transition_execution(
        transition(eid, "5", ExecutionStatus.PENDING, 0, ExecutionStatus.RUNNING)
    )
    failure = {
        "code": "MODEL_TIMEOUT",
        "message": "x" * 600,
        "recoverability": "retryable",
        "failed_dependency_ref": "model:primary",
    }
    result = service.transition_execution(
        transition(
            eid,
            "6",
            ExecutionStatus.RUNNING,
            1,
            ExecutionStatus.FAILED,
            failure=failure,
        )
    )
    assert result.execution["failure"] == failure
