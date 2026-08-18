from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from contracts.agent_task.validator import compute_task_key
from sqlalchemy import Engine, create_engine, event, text
from testcontainers.community.mysql import MySqlContainer

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
from factoryops_agent_service.task_lifecycle.model import (
    CreateTaskCommand,
    OperationOutcome,
    TaskStatus,
    TransitionCommand,
)
from factoryops_agent_service.task_lifecycle.rules import LifecycleRuleViolation
from factoryops_agent_service.task_lifecycle.service import (
    AgentTaskLifecycleService,
    PersistenceIntegrityError,
    TaskCreationRejected,
)

NOW = datetime(2026, 8, 16, 8, 0, tzinfo=timezone.utc)
RUN_CREATORS: dict[str, str] = {}


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
    event_id = "EVT-" + marker * 64
    with engine.begin() as connection:
        connection.execute(
            text("""INSERT INTO agent_event_inbox
          (event_id,event_type,contract_version,topic,kafka_partition,kafka_offset,message_key,raw_payload,canonical_sha256,received_at)
          VALUES (:e,'quality.incident.opened','1.0','factoryops.quality.incident.v1',0,:o,:k,'{}',UNHEX(REPEAT(:m,64)),:t)"""),
            {
                "e": event_id,
                "o": int(marker, 16),
                "k": "QI-" + marker * 64,
                "m": marker,
                "t": NOW,
            },
        )
    result = AgentRunLifecycleService(engine, clock=lambda: NOW).create_original_run(
        OriginalRunCommand(
            event_id,
            RunProvenance(
                "QI-" + marker * 64,
                "runtime:1",
                "workflow:1",
                "prompts:1",
                "model:1",
                "tool:1",
                "context:1",
                "a" * 40,
            ),
        )
    )
    run_id = str(result.run["identity"]["run_id"])
    execution = (
        AgentExecutionLifecycleService(engine, clock=lambda: NOW)
        .create_execution(
            CreateExecutionCommand(
                run_id,
                "coordinator",
                1,
                None,
                "runtime:1",
                "coordinator:1",
                "model:1",
                "tool:1",
                "context:1",
                "a" * 40,
                "CTX-" + marker * 32,
                (),
            )
        )
        .execution
    )
    RUN_CREATORS[run_id] = str(execution["identity"]["execution_id"])
    return run_id


def _create(
    run_id: str, marker: str, dependencies: tuple[str, ...] = ()
) -> CreateTaskCommand:
    return CreateTaskCommand(
        "TQR-" + marker * 32,
        run_id,
        "QUALITY_ANALYSIS",
        "quality",
        RUN_CREATORS[run_id],
        50,
        "CTX-" + marker * 32,
        ("inspection:731",),
        dependencies,
    )


def _service(engine: Engine) -> AgentTaskLifecycleService:
    return AgentTaskLifecycleService(engine, clock=lambda: NOW)


def _seed_specialist_execution(
    engine: Engine, task_id: str, execution_id: str, attempt: int
) -> None:
    with engine.connect() as connection:
        task = (
            connection.execute(
                text(
                    "SELECT run_id,target_agent_role,context_snapshot_id FROM agent_tasks WHERE task_id=:id"
                ),
                {"id": task_id},
            )
            .mappings()
            .one()
        )
    AgentExecutionLifecycleService(
        engine, clock=lambda: NOW, execution_id_factory=lambda: execution_id
    ).create_execution(
        CreateExecutionCommand(
            str(task["run_id"]),
            str(task["target_agent_role"]),
            attempt,
            task_id,
            "runtime:1",
            "specialist:1",
            "model:1",
            "tool:1",
            "context:1",
            "a" * 40,
            str(task["context_snapshot_id"]),
            (),
        )
    )


def test_migration_creates_task_tables(mysql_engine: Engine) -> None:
    with mysql_engine.connect() as c:
        versions = c.scalars(
            text("SELECT version FROM agent_schema_history ORDER BY version")
        ).all()
        tables = set(
            c.scalars(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema=DATABASE()"
                )
            ).all()
        )
    assert versions[-1] == "008_create_worker_task_completion_requests"
    assert "worker_task_execution_start_requests" in tables
    assert "worker_task_execution_completion_requests" in tables
    assert {
        "agent_tasks",
        "agent_task_dependencies",
        "agent_task_transitions",
    } <= tables


def test_create_is_atomic_and_idempotent(mysql_engine: Engine) -> None:
    run_id = _run(mysql_engine, "1")
    service = _service(mysql_engine)
    command = _create(run_id, "1")
    applied = service.create_task(command)
    identical = service.create_task(command)
    conflicting = service.create_task(
        CreateTaskCommand(**{**command.__dict__, "priority": 51})
    )
    assert applied.outcome is OperationOutcome.APPLIED
    assert identical.outcome is OperationOutcome.DUPLICATE_IDENTICAL
    assert conflicting.outcome is OperationOutcome.DUPLICATE_CONFLICTING
    assert applied.task["identity"]["task_key"] == compute_task_key(
        run_id, command.task_request_id
    )
    with mysql_engine.connect() as c:
        assert (
            c.scalar(
                text("SELECT COUNT(*) FROM agent_task_transitions WHERE task_id=:id"),
                {"id": applied.task["identity"]["task_id"]},
            )
            == 1
        )


def test_dependencies_must_exist_and_share_run(mysql_engine: Engine) -> None:
    run_a, run_b = _run(mysql_engine, "2"), _run(mysql_engine, "3")
    dependency = (
        _service(mysql_engine)
        .create_task(_create(run_a, "2"))
        .task["identity"]["task_id"]
    )
    with pytest.raises(TaskCreationRejected, match="same Run"):
        _service(mysql_engine).create_task(_create(run_b, "3", (dependency,)))
    with pytest.raises(TaskCreationRejected, match="does not exist"):
        _service(mysql_engine).create_task(_create(run_a, "4", ("TSK-" + "F" * 32,)))


def test_dependency_is_rebuilt_in_contract_order(mysql_engine: Engine) -> None:
    run_id = _run(mysql_engine, "6")
    dependency = (
        _service(mysql_engine)
        .create_task(_create(run_id, "B"))
        .task["identity"]["task_id"]
    )
    result = _service(mysql_engine).create_task(_create(run_id, "C", (dependency,)))
    assert result.task["input"]["dependency_task_ids"] == [dependency]


def _transition(
    task_id: str,
    request: str,
    source: TaskStatus,
    revision: int,
    target: TaskStatus,
    execution: str | None = None,
    **kwargs: object,
) -> TransitionCommand:
    return TransitionCommand(
        "TRQ-" + request * 32,
        task_id,
        source,
        revision,
        target,
        "COORDINATOR",
        "coordinator",
        str(kwargs.get("reason_code", "TASK_CHANGED")),
        "changed",
        execution,
        kwargs.get("completion_execution_id"),
        kwargs.get("failure_code"),
        kwargs.get("failure_message"),
        kwargs.get("failure_recoverability"),
    )


def test_transition_retry_terminal_and_conflicts(mysql_engine: Engine) -> None:
    run_id = _run(mysql_engine, "4")
    service = _service(mysql_engine)
    task_id = service.create_task(_create(run_id, "5")).task["identity"]["task_id"]
    exe1, exe2 = "EXE-" + "1" * 32, "EXE-" + "2" * 32
    _seed_specialist_execution(mysql_engine, task_id, exe1, 1)
    _seed_specialist_execution(mysql_engine, task_id, exe2, 2)
    first = service.transition_task(
        _transition(task_id, "5", TaskStatus.PENDING, 0, TaskStatus.RUNNING, exe1)
    )
    retry = service.transition_task(
        _transition(task_id, "6", TaskStatus.RUNNING, 1, TaskStatus.RUNNING, exe2)
    )
    same = service.transition_task(
        _transition(task_id, "6", TaskStatus.RUNNING, 1, TaskStatus.RUNNING, exe2)
    )
    stale = service.transition_task(
        _transition(task_id, "7", TaskStatus.RUNNING, 1, TaskStatus.CANCELLED)
    )
    done = service.transition_task(
        _transition(
            task_id,
            "8",
            TaskStatus.RUNNING,
            2,
            TaskStatus.SUCCEEDED,
            exe2,
            completion_execution_id=exe2,
        )
    )
    assert first.task["execution"]["attempt_count"] == 1
    assert retry.task["execution"]["attempt_count"] == 2
    assert same.outcome is OperationOutcome.DUPLICATE_IDENTICAL
    assert stale.outcome is OperationOutcome.CONCURRENCY_CONFLICT
    assert done.task["completion"] == {"successful_execution_id": exe2}
    with pytest.raises(LifecycleRuleViolation, match="illegal transition"):
        service.transition_task(
            _transition(task_id, "9", TaskStatus.SUCCEEDED, 3, TaskStatus.RUNNING, exe1)
        )


def test_failure_message_600_characters_round_trips(mysql_engine: Engine) -> None:
    run_id = _run(mysql_engine, "A")
    service = _service(mysql_engine)
    task_id = service.create_task(_create(run_id, "0")).task["identity"]["task_id"]
    execution_id = "EXE-" + "0" * 32
    _seed_specialist_execution(mysql_engine, task_id, execution_id, 1)
    service.transition_task(
        _transition(
            task_id, "0", TaskStatus.PENDING, 0, TaskStatus.RUNNING, execution_id
        )
    )

    result = service.transition_task(
        _transition(
            task_id,
            "1",
            TaskStatus.RUNNING,
            1,
            TaskStatus.FAILED,
            execution_id,
            failure_code="MODEL_TIMEOUT",
            failure_message="x" * 600,
            failure_recoverability="non_retryable",
        )
    )

    assert result.task["failure"]["message"] == "x" * 600


def test_running_cancellation_retry_is_identical(mysql_engine: Engine) -> None:
    run_id = _run(mysql_engine, "C")
    service = _service(mysql_engine)
    task_id = service.create_task(_create(run_id, "7")).task["identity"]["task_id"]
    execution = "EXE-" + "7" * 32
    _seed_specialist_execution(mysql_engine, task_id, execution, 1)
    service.transition_task(
        _transition(task_id, "B", TaskStatus.PENDING, 0, TaskStatus.RUNNING, execution)
    )
    command = _transition(task_id, "C", TaskStatus.RUNNING, 1, TaskStatus.CANCELLED)
    assert service.transition_task(command).outcome is OperationOutcome.APPLIED
    assert (
        service.transition_task(command).outcome is OperationOutcome.DUPLICATE_IDENTICAL
    )


def test_transition_history_failure_rolls_back_snapshot(mysql_engine: Engine) -> None:
    run_id = _run(mysql_engine, "5")
    service = _service(mysql_engine)
    task_id = service.create_task(_create(run_id, "A")).task["identity"]["task_id"]
    _seed_specialist_execution(mysql_engine, task_id, "EXE-" + "3" * 32, 1)

    def fail(
        _c: object,
        _cursor: object,
        statement: str,
        params: object,
        _ctx: object,
        _many: bool,
    ) -> None:
        if (
            "INSERT INTO agent_task_transitions" in statement
            and isinstance(params, dict)
            and params.get("to_revision") == 1
        ):
            raise RuntimeError("injected task history failure")

    event.listen(mysql_engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="history failure"):
            service.transition_task(
                _transition(
                    task_id,
                    "A",
                    TaskStatus.PENDING,
                    0,
                    TaskStatus.RUNNING,
                    "EXE-" + "3" * 32,
                )
            )
    finally:
        event.remove(mysql_engine, "before_cursor_execute", fail)
    assert service.get_task(task_id)["lifecycle"]["revision"] == 0


def test_initial_history_failure_rolls_back_task(mysql_engine: Engine) -> None:
    run_id = _run(mysql_engine, "7")
    service = _service(mysql_engine)

    def fail(
        _c: object,
        _cursor: object,
        statement: str,
        _params: object,
        _ctx: object,
        _many: bool,
    ) -> None:
        if "INSERT INTO agent_task_transitions" in statement:
            raise RuntimeError("injected initial history failure")

    event.listen(mysql_engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="initial history failure"):
            service.create_task(_create(run_id, "D"))
    finally:
        event.remove(mysql_engine, "before_cursor_execute", fail)
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM agent_tasks WHERE task_request_id=:id"),
                {"id": "TQR-" + "D" * 32},
            )
            == 0
        )


def test_concurrent_transitions_allow_one_winner(mysql_engine: Engine) -> None:
    run_id = _run(mysql_engine, "8")
    service = _service(mysql_engine)
    task_id = service.create_task(_create(run_id, "E")).task["identity"]["task_id"]
    _seed_specialist_execution(mysql_engine, task_id, "EXE-" + "E" * 32, 1)
    commands = (
        _transition(
            task_id, "E", TaskStatus.PENDING, 0, TaskStatus.RUNNING, "EXE-" + "E" * 32
        ),
        _transition(task_id, "F", TaskStatus.PENDING, 0, TaskStatus.CANCELLED),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(service.transition_task, commands))
    assert {result.outcome for result in results} == {
        OperationOutcome.APPLIED,
        OperationOutcome.CONCURRENCY_CONFLICT,
    }


def test_clock_rollback_and_corrupt_snapshot_are_rejected(mysql_engine: Engine) -> None:
    run_id = _run(mysql_engine, "9")
    service = _service(mysql_engine)
    task_id = service.create_task(_create(run_id, "F")).task["identity"]["task_id"]
    rollback_service = AgentTaskLifecycleService(
        mysql_engine, clock=lambda: NOW - timedelta(seconds=1)
    )
    with pytest.raises(LifecycleRuleViolation, match="Contract"):
        rollback_service.transition_task(
            _transition(
                task_id,
                "G",
                TaskStatus.PENDING,
                0,
                TaskStatus.RUNNING,
                "EXE-" + "9" * 32,
            )
        )
    assert service.get_task(task_id)["lifecycle"]["revision"] == 0

    with mysql_engine.begin() as connection:
        connection.execute(
            text("UPDATE agent_tasks SET target_agent_role='risk' WHERE task_id=:id"),
            {"id": task_id},
        )
    with pytest.raises(PersistenceIntegrityError, match="stored Task"):
        service.get_task(task_id)
