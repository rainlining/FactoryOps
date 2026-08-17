from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from importlib.resources import files

import pytest
from sqlalchemy import Engine, create_engine, event, text
from testcontainers.community.mysql import MySqlContainer

from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.run_lifecycle.model import (
    ActorKind,
    OperationOutcome,
    OriginalRunCommand,
    ReplayRunCommand,
    RunProvenance,
    RunStatus,
    TransitionCommand,
)
from factoryops_agent_service.run_lifecycle.rules import LifecycleRuleViolation
from factoryops_agent_service.run_lifecycle.service import (
    AgentRunLifecycleService,
    RunCreationRejected,
)

FIXED_TIME = datetime(2026, 8, 15, 5, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def mysql_engine() -> Engine:
    with MySqlContainer("mysql:8.4") as mysql:
        database_url = mysql.get_connection_url().replace(
            "mysql://",
            "mysql+pymysql://",
            1,
        )
        engine = create_engine(database_url)
        migrate(engine)
        yield engine
        engine.dispose()


def test_migrations_create_run_lifecycle_schema(mysql_engine: Engine) -> None:
    with mysql_engine.connect() as connection:
        versions = connection.scalars(
            text("SELECT version FROM agent_schema_history ORDER BY version")
        ).all()
        tables = set(
            connection.scalars(
                text(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = DATABASE()
                    """
                )
            ).all()
        )
        run_indexes = set(
            connection.scalars(
                text(
                    """
                    SELECT DISTINCT index_name
                    FROM information_schema.statistics
                    WHERE table_schema = DATABASE()
                      AND table_name = 'agent_runs'
                    """
                )
            ).all()
        )
        transition_indexes = set(
            connection.scalars(
                text(
                    """
                    SELECT DISTINCT index_name
                    FROM information_schema.statistics
                    WHERE table_schema = DATABASE()
                      AND table_name = 'agent_run_transitions'
                    """
                )
            ).all()
        )
        delete_rules = set(
            connection.scalars(
                text(
                    """
                    SELECT delete_rule
                    FROM information_schema.referential_constraints
                    WHERE constraint_schema = DATABASE()
                      AND table_name IN (
                        'agent_runs',
                        'agent_run_transitions'
                      )
                    """
                )
            ).all()
        )
        check_names = set(
            connection.scalars(
                text(
                    """
                    SELECT constraint_name
                    FROM information_schema.table_constraints
                    WHERE constraint_schema = DATABASE()
                      AND constraint_type = 'CHECK'
                      AND table_name IN (
                        'agent_runs',
                        'agent_run_transitions'
                      )
                    """
                )
            ).all()
        )

    assert versions == [
        "001_create_agent_event_inbox",
        "002_create_agent_run_lifecycle",
        "003_create_agent_task_lifecycle",
        "004_create_agent_execution_lifecycle",
        "005_create_coordinator_start_requests",
        "006_create_agent_task_leases",
    ]
    assert {"agent_runs", "agent_run_transitions"} <= tables
    assert {
        "PRIMARY",
        "uk_agent_runs_trigger_event",
        "uk_agent_runs_replay_request",
        "idx_agent_runs_incident_created",
        "idx_agent_runs_original_created",
        "idx_agent_runs_status_updated",
    } <= run_indexes
    assert {
        "PRIMARY",
        "uk_run_transitions_request",
        "uk_run_transitions_run_revision",
    } <= transition_indexes
    assert delete_rules == {"RESTRICT"}
    assert {
        "chk_agent_runs_identity",
        "chk_agent_runs_lifecycle",
        "chk_agent_runs_reason",
        "chk_agent_runs_progress",
        "chk_run_transitions_revision",
        "chk_run_transitions_suspended",
    } <= check_names


def test_migration_runner_is_idempotent(mysql_engine: Engine) -> None:
    migrate(mysql_engine)

    with mysql_engine.connect() as connection:
        count = connection.scalar(text("SELECT COUNT(*) FROM agent_schema_history"))

    assert count == 6


def test_migration_runner_upgrades_database_that_only_has_001() -> None:
    mysql = MySqlContainer("mysql:8.4")
    mysql.start()
    upgrade_engine = None
    try:
        database_url = mysql.get_connection_url().replace(
            "mysql://",
            "mysql+pymysql://",
            1,
        )
        upgrade_engine = create_engine(database_url)
        migration_001 = (
            files("factoryops_agent_service.event_ingress.migrations")
            .joinpath("001_create_agent_event_inbox.sql")
            .read_text(encoding="utf-8")
        )
        with upgrade_engine.begin() as connection:
            connection.exec_driver_sql(
                """
                CREATE TABLE agent_schema_history (
                  version VARCHAR(100) PRIMARY KEY,
                  applied_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                ) ENGINE=InnoDB
                """
            )
            for statement in migration_001.split(";"):
                if statement.strip():
                    connection.exec_driver_sql(statement)
            connection.execute(
                text("INSERT INTO agent_schema_history(version) VALUES (:version)"),
                {"version": "001_create_agent_event_inbox"},
            )

        migrate(upgrade_engine)

        with upgrade_engine.connect() as connection:
            versions = connection.scalars(
                text("SELECT version FROM agent_schema_history ORDER BY version")
            ).all()
            run_table = connection.scalar(
                text(
                    """
                    SELECT COUNT(*)
                    FROM information_schema.tables
                    WHERE table_schema = DATABASE()
                      AND table_name = 'agent_runs'
                    """
                )
            )
        assert versions == [
            "001_create_agent_event_inbox",
            "002_create_agent_run_lifecycle",
            "003_create_agent_task_lifecycle",
            "004_create_agent_execution_lifecycle",
            "005_create_coordinator_start_requests",
            "006_create_agent_task_leases",
        ]
        assert run_table == 1
    finally:
        if upgrade_engine is not None:
            upgrade_engine.dispose()
        mysql.stop()


def _event_id(marker: str) -> str:
    return "EVT-" + marker * 64


def _incident_id(marker: str) -> str:
    return "QI-" + marker * 64


def _seed_inbox(engine: Engine, marker: str) -> str:
    event_id = _event_id(marker)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO agent_event_inbox (
                  event_id, event_type, contract_version, topic,
                  kafka_partition, kafka_offset, message_key,
                  raw_payload, canonical_sha256, received_at)
                VALUES (
                  :event_id, 'quality.incident.opened', '1.0',
                  'factoryops.quality.incident.v1', 0, :offset,
                  :message_key, '{}', UNHEX(REPEAT(:marker, 64)), :received_at)
                """
            ),
            {
                "event_id": event_id,
                "offset": int(marker, 16),
                "message_key": _incident_id(marker),
                "marker": marker,
                "received_at": FIXED_TIME,
            },
        )
    return event_id


def _provenance(marker: str, *, prompt: str = "prompts:1.0.0") -> RunProvenance:
    return RunProvenance(
        incident_id=_incident_id(marker),
        runtime_version="runtime:1.0.0",
        workflow_version="workflow:1.0.0",
        prompt_set_version=prompt,
        model_policy_version="model-policy:1.0.0",
        tool_policy_version="tool-policy:1.0.0",
        context_policy_version="context-policy:1.0.0",
        code_revision="a" * 40,
    )


def _service(engine: Engine) -> AgentRunLifecycleService:
    return AgentRunLifecycleService(engine, clock=lambda: FIXED_TIME)


def test_original_creation_is_atomic_and_rebuilds_contract(
    mysql_engine: Engine,
) -> None:
    event_id = _seed_inbox(mysql_engine, "1")
    result = _service(mysql_engine).create_original_run(
        OriginalRunCommand(event_id, _provenance("1"))
    )

    assert result.outcome is OperationOutcome.APPLIED
    assert result.run is not None
    identity = result.run["identity"]
    lifecycle = result.run["lifecycle"]
    provenance = result.run["provenance"]
    assert isinstance(identity, dict)
    assert isinstance(lifecycle, dict)
    assert isinstance(provenance, dict)
    assert identity["run_id"] == identity["original_run_id"]
    assert identity["trigger_event_id"] == event_id
    assert lifecycle == {
        "status": "PENDING",
        "revision": 0,
        "updated_at": "2026-08-15T05:00:00.000000Z",
        "status_reason": None,
    }
    assert provenance["created_at"] == "2026-08-15T05:00:00.000000Z"

    with mysql_engine.connect() as connection:
        run_id = identity["run_id"]
        history = (
            connection.execute(
                text(
                    """
                SELECT from_status, to_status, from_revision, to_revision,
                       actor_kind, actor_id, reason_code, occurred_at
                FROM agent_run_transitions
                WHERE run_id=:run_id
                """
                ),
                {"run_id": run_id},
            )
            .mappings()
            .one()
        )
    assert history["from_status"] is None
    assert history["to_status"] == "PENDING"
    assert history["from_revision"] is None
    assert history["to_revision"] == 0
    assert history["actor_kind"] == "SYSTEM"
    assert history["actor_id"] == "agent-run-lifecycle"
    assert history["reason_code"] == "RUN_CREATED"
    assert history["occurred_at"] == FIXED_TIME.replace(tzinfo=None)


def test_original_retry_is_identical_or_conflicting(mysql_engine: Engine) -> None:
    event_id = _seed_inbox(mysql_engine, "2")
    service = _service(mysql_engine)
    command = OriginalRunCommand(event_id, _provenance("2"))

    first = service.create_original_run(command)
    identical = service.create_original_run(command)
    conflicting = service.create_original_run(
        OriginalRunCommand(
            event_id,
            _provenance("2", prompt="prompts:2.0.0"),
        )
    )
    conflicting_invalid_contract = service.create_original_run(
        OriginalRunCommand(
            event_id,
            _provenance("2", prompt="invalid version with spaces"),
        )
    )

    assert first.outcome is OperationOutcome.APPLIED
    assert identical.outcome is OperationOutcome.DUPLICATE_IDENTICAL
    assert conflicting.outcome is OperationOutcome.DUPLICATE_CONFLICTING
    assert (
        conflicting_invalid_contract.outcome is OperationOutcome.DUPLICATE_CONFLICTING
    )
    assert identical.run == first.run
    assert conflicting.run == first.run
    assert conflicting_invalid_contract.run == first.run


def test_original_retry_rechecks_key_after_initial_miss(mysql_engine: Engine) -> None:
    event_id = _seed_inbox(mysql_engine, "E")
    winner_service = _service(mysql_engine)
    retry_service = _service(mysql_engine)
    original_lookup = retry_service._repository.find_run_by_trigger_event
    winner: dict[str, object] = {}

    def stale_first_lookup(candidate_event_id: str) -> object:
        if not winner:
            assert original_lookup(candidate_event_id) is None
            winner["result"] = winner_service.create_original_run(
                OriginalRunCommand(event_id, _provenance("E"))
            )
            return None
        return original_lookup(candidate_event_id)

    retry_service._repository.find_run_by_trigger_event = stale_first_lookup
    result = retry_service.create_original_run(
        OriginalRunCommand(
            event_id,
            _provenance("E", prompt="invalid version with spaces"),
        )
    )

    assert result.outcome is OperationOutcome.DUPLICATE_CONFLICTING
    assert result.run == winner["result"].run


def test_original_requires_persisted_inbox_event(mysql_engine: Engine) -> None:
    with pytest.raises(RunCreationRejected, match="Inbox"):
        _service(mysql_engine).create_original_run(
            OriginalRunCommand(_event_id("3"), _provenance("3"))
        )


def test_invalid_creation_contract_is_rejected_before_insert(
    mysql_engine: Engine,
) -> None:
    event_id = _seed_inbox(mysql_engine, "C")

    with pytest.raises(RunCreationRejected, match="Contract"):
        _service(mysql_engine).create_original_run(
            OriginalRunCommand(
                event_id,
                _provenance("C", prompt="invalid version with spaces"),
            )
        )

    with mysql_engine.connect() as connection:
        count = connection.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM agent_runs
                WHERE trigger_event_id=:event_id
                """
            ),
            {"event_id": event_id},
        )
    assert count == 0


def test_initial_history_failure_rolls_back_run(mysql_engine: Engine) -> None:
    event_id = _seed_inbox(mysql_engine, "D")
    service = _service(mysql_engine)

    def fail_initial_transition(
        _connection: object,
        _cursor: object,
        statement: str,
        parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if "INSERT INTO agent_run_transitions" not in statement:
            return
        if isinstance(parameters, dict) and parameters.get("to_revision") == 0:
            raise RuntimeError("injected initial history failure")

    event.listen(mysql_engine, "before_cursor_execute", fail_initial_transition)
    try:
        with pytest.raises(RuntimeError, match="initial history failure"):
            service.create_original_run(OriginalRunCommand(event_id, _provenance("D")))
    finally:
        event.remove(mysql_engine, "before_cursor_execute", fail_initial_transition)

    with mysql_engine.connect() as connection:
        count = connection.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM agent_runs
                WHERE trigger_event_id=:event_id
                """
            ),
            {"event_id": event_id},
        )
    assert count == 0


def test_replay_creation_validates_lineage_and_is_idempotent(
    mysql_engine: Engine,
) -> None:
    original_event = _seed_inbox(mysql_engine, "4")
    _seed_inbox(mysql_engine, "5")
    service = _service(mysql_engine)
    original = service.create_original_run(
        OriginalRunCommand(original_event, _provenance("4"))
    ).run
    assert original is not None
    original_identity = original["identity"]
    assert isinstance(original_identity, dict)
    original_run_id = original_identity["run_id"]
    assert isinstance(original_run_id, str)
    replay_command = ReplayRunCommand(
        replay_request_id="RPR-" + "4" * 32,
        original_run_id=original_run_id,
        replayed_from_run_id=original_run_id,
        provenance=_provenance("4", prompt="prompts:2.0.0"),
    )

    applied = service.create_replay_run(replay_command)
    duplicate = service.create_replay_run(replay_command)

    assert applied.outcome is OperationOutcome.APPLIED
    assert duplicate.outcome is OperationOutcome.DUPLICATE_IDENTICAL
    assert applied.run == duplicate.run

    conflicting_retry = service.create_replay_run(
        ReplayRunCommand(
            replay_request_id=replay_command.replay_request_id,
            original_run_id=original_run_id,
            replayed_from_run_id=original_run_id,
            provenance=_provenance("5"),
        )
    )
    assert conflicting_retry.outcome is OperationOutcome.DUPLICATE_CONFLICTING
    assert conflicting_retry.run == applied.run

    with pytest.raises(RunCreationRejected, match="same Incident"):
        service.create_replay_run(
            ReplayRunCommand(
                replay_request_id="RPR-" + "5" * 32,
                original_run_id=original_run_id,
                replayed_from_run_id=original_run_id,
                provenance=_provenance("5"),
            )
        )


def test_replay_retry_rechecks_key_after_initial_miss(mysql_engine: Engine) -> None:
    event_id = _seed_inbox(mysql_engine, "F")
    setup_service = _service(mysql_engine)
    original = setup_service.create_original_run(
        OriginalRunCommand(event_id, _provenance("F"))
    ).run
    assert original is not None
    identity = original["identity"]
    assert isinstance(identity, dict)
    original_run_id = identity["run_id"]
    assert isinstance(original_run_id, str)
    request_id = "RPR-" + "F" * 32
    winner_service = _service(mysql_engine)
    retry_service = _service(mysql_engine)
    original_lookup = retry_service._repository.find_run_by_replay_request
    winner: dict[str, object] = {}

    def stale_first_lookup(candidate_request_id: str) -> object:
        if not winner:
            assert original_lookup(candidate_request_id) is None
            winner["result"] = winner_service.create_replay_run(
                ReplayRunCommand(
                    request_id,
                    original_run_id,
                    original_run_id,
                    _provenance("F", prompt="prompts:2.0.0"),
                )
            )
            return None
        return original_lookup(candidate_request_id)

    retry_service._repository.find_run_by_replay_request = stale_first_lookup
    result = retry_service.create_replay_run(
        ReplayRunCommand(
            request_id,
            original_run_id,
            original_run_id,
            _provenance("E"),
        )
    )

    assert result.outcome is OperationOutcome.DUPLICATE_CONFLICTING
    assert result.run == winner["result"].run


def _create_original(
    engine: Engine,
    marker: str,
) -> tuple[AgentRunLifecycleService, str]:
    event_id = _seed_inbox(engine, marker)
    service = _service(engine)
    result = service.create_original_run(
        OriginalRunCommand(event_id, _provenance(marker))
    )
    assert result.run is not None
    identity = result.run["identity"]
    assert isinstance(identity, dict)
    run_id = identity["run_id"]
    assert isinstance(run_id, str)
    return service, run_id


def _transition_command(
    run_id: str,
    request_marker: str,
    expected_status: RunStatus,
    expected_revision: int,
    to_status: RunStatus,
    *,
    reason_code: str = "TEST_TRANSITION",
    checkpoint_id: str | None = None,
) -> TransitionCommand:
    return TransitionCommand(
        transition_request_id="TRQ-" + request_marker * 32,
        run_id=run_id,
        expected_status=expected_status,
        expected_revision=expected_revision,
        to_status=to_status,
        actor_kind=ActorKind.COORDINATOR,
        actor_id="coordinator-execution-1",
        reason_code=reason_code,
        reason_message="A persisted lifecycle transition.",
        checkpoint_id=checkpoint_id,
    )


def test_transition_updates_snapshot_and_appends_history(
    mysql_engine: Engine,
) -> None:
    service, run_id = _create_original(mysql_engine, "6")
    result = service.transition_run(
        _transition_command(
            run_id,
            "6",
            RunStatus.PENDING,
            0,
            RunStatus.RUNNING,
            reason_code="WORKFLOW_STARTED",
        )
    )

    assert result.outcome is OperationOutcome.APPLIED
    assert result.run is not None
    lifecycle = result.run["lifecycle"]
    assert isinstance(lifecycle, dict)
    assert lifecycle["status"] == "RUNNING"
    assert lifecycle["revision"] == 1
    assert lifecycle["started_at"] == "2026-08-15T05:00:00.000000Z"
    assert "ended_at" not in lifecycle
    assert lifecycle["status_reason"] == {
        "code": "WORKFLOW_STARTED",
        "message": "A persisted lifecycle transition.",
    }

    with mysql_engine.connect() as connection:
        transitions = connection.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM agent_run_transitions
                WHERE run_id=:run_id
                """
            ),
            {"run_id": run_id},
        )
    assert transitions == 2


def test_transition_retry_conflict_and_stale_revision_are_distinct(
    mysql_engine: Engine,
) -> None:
    service, run_id = _create_original(mysql_engine, "7")
    transition = _transition_command(
        run_id,
        "7",
        RunStatus.PENDING,
        0,
        RunStatus.RUNNING,
    )

    applied = service.transition_run(transition)
    identical = service.transition_run(transition)
    conflicting = service.transition_run(
        _transition_command(
            run_id,
            "7",
            RunStatus.PENDING,
            0,
            RunStatus.RUNNING,
            reason_code="DIFFERENT_REASON",
        )
    )
    conflicting_missing_run = service.transition_run(
        _transition_command(
            "RUN-" + "F" * 32,
            "7",
            RunStatus.PENDING,
            0,
            RunStatus.RUNNING,
        )
    )
    conflicting_illegal_transition = service.transition_run(
        _transition_command(
            run_id,
            "7",
            RunStatus.RUNNING,
            1,
            RunStatus.PENDING,
        )
    )
    stale = service.transition_run(
        _transition_command(
            run_id,
            "8",
            RunStatus.PENDING,
            0,
            RunStatus.CANCELLED,
        )
    )

    assert applied.outcome is OperationOutcome.APPLIED
    assert identical.outcome is OperationOutcome.DUPLICATE_IDENTICAL
    assert conflicting.outcome is OperationOutcome.DUPLICATE_CONFLICTING
    assert conflicting_missing_run.outcome is OperationOutcome.DUPLICATE_CONFLICTING
    assert (
        conflicting_illegal_transition.outcome is OperationOutcome.DUPLICATE_CONFLICTING
    )
    assert conflicting_missing_run.run == applied.run
    assert conflicting_illegal_transition.run == applied.run
    assert stale.outcome is OperationOutcome.CONCURRENCY_CONFLICT
    assert stale.run is not None
    stale_lifecycle = stale.run["lifecycle"]
    assert isinstance(stale_lifecycle, dict)
    assert stale_lifecycle["status"] == "RUNNING"
    assert stale_lifecycle["revision"] == 1


def test_transition_retry_rechecks_key_after_initial_miss(mysql_engine: Engine) -> None:
    winner_service, run_id = _create_original(mysql_engine, "0")
    retry_service = _service(mysql_engine)
    request_marker = "Z"
    winner_command = _transition_command(
        run_id,
        request_marker,
        RunStatus.PENDING,
        0,
        RunStatus.RUNNING,
    )
    original_lookup = retry_service._repository.find_transition_by_request
    winner: dict[str, object] = {}

    def stale_first_lookup(candidate_request_id: str) -> object:
        if not winner:
            assert original_lookup(candidate_request_id) is None
            winner["result"] = winner_service.transition_run(winner_command)
            return None
        return original_lookup(candidate_request_id)

    retry_service._repository.find_transition_by_request = stale_first_lookup
    result = retry_service.transition_run(
        _transition_command(
            "RUN-" + "E" * 32,
            request_marker,
            RunStatus.RUNNING,
            1,
            RunStatus.PENDING,
        )
    )

    assert result.outcome is OperationOutcome.DUPLICATE_CONFLICTING
    assert result.run == winner["result"].run


def test_cancel_before_start_has_no_started_at(mysql_engine: Engine) -> None:
    service, run_id = _create_original(mysql_engine, "8")

    result = service.transition_run(
        _transition_command(
            run_id,
            "9",
            RunStatus.PENDING,
            0,
            RunStatus.CANCELLED,
            reason_code="CANCELLED_BEFORE_START",
        )
    )

    assert result.run is not None
    lifecycle = result.run["lifecycle"]
    assert isinstance(lifecycle, dict)
    assert lifecycle["status"] == "CANCELLED"
    assert "started_at" not in lifecycle
    assert lifecycle["ended_at"] == "2026-08-15T05:00:00.000000Z"

    with pytest.raises(LifecycleRuleViolation, match="illegal transition"):
        service.transition_run(
            _transition_command(
                run_id,
                "A",
                RunStatus.CANCELLED,
                1,
                RunStatus.RUNNING,
            )
        )


def test_clock_rollback_cannot_commit_terminal_state(mysql_engine: Engine) -> None:
    event_id = _seed_inbox(mysql_engine, "3")
    times = iter(
        (
            FIXED_TIME,
            FIXED_TIME + timedelta(minutes=10),
            FIXED_TIME + timedelta(minutes=5),
        )
    )
    service = AgentRunLifecycleService(mysql_engine, clock=lambda: next(times))
    created = service.create_original_run(
        OriginalRunCommand(event_id, _provenance("3"))
    )
    assert created.run is not None
    identity = created.run["identity"]
    assert isinstance(identity, dict)
    run_id = identity["run_id"]
    assert isinstance(run_id, str)
    service.transition_run(
        _transition_command(
            run_id,
            "Y",
            RunStatus.PENDING,
            0,
            RunStatus.RUNNING,
        )
    )

    with pytest.raises(LifecycleRuleViolation, match="Run Contract"):
        service.transition_run(
            _transition_command(
                run_id,
                "S",
                RunStatus.RUNNING,
                1,
                RunStatus.SUCCEEDED,
            )
        )

    with mysql_engine.connect() as connection:
        snapshot = (
            connection.execute(
                text(
                    """
                SELECT status, revision, ended_at
                FROM agent_runs
                WHERE run_id=:run_id
                """
                ),
                {"run_id": run_id},
            )
            .mappings()
            .one()
        )
        transition_count = connection.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM agent_run_transitions
                WHERE run_id=:run_id
                """
            ),
            {"run_id": run_id},
        )

    assert snapshot == {"status": "RUNNING", "revision": 1, "ended_at": None}
    assert transition_count == 2


def test_suspended_persists_checkpoint_reference(mysql_engine: Engine) -> None:
    service, run_id = _create_original(mysql_engine, "9")
    service.transition_run(
        _transition_command(
            run_id,
            "B",
            RunStatus.PENDING,
            0,
            RunStatus.RUNNING,
        )
    )

    with pytest.raises(LifecycleRuleViolation, match="checkpoint"):
        service.transition_run(
            _transition_command(
                run_id,
                "C",
                RunStatus.RUNNING,
                1,
                RunStatus.SUSPENDED,
            )
        )

    suspended = service.transition_run(
        _transition_command(
            run_id,
            "D",
            RunStatus.RUNNING,
            1,
            RunStatus.SUSPENDED,
            reason_code="TOOL_TEMPORARILY_UNAVAILABLE",
            checkpoint_id="checkpoint-9",
        )
    )

    assert suspended.outcome is OperationOutcome.APPLIED
    assert suspended.run is not None
    refs = suspended.run["execution_refs"]
    assert isinstance(refs, dict)
    assert refs["latest_checkpoint_id"] == "checkpoint-9"


def test_concurrent_transitions_allow_only_one_winner(mysql_engine: Engine) -> None:
    service, run_id = _create_original(mysql_engine, "A")
    commands = (
        _transition_command(
            run_id,
            "E",
            RunStatus.PENDING,
            0,
            RunStatus.RUNNING,
        ),
        _transition_command(
            run_id,
            "F",
            RunStatus.PENDING,
            0,
            RunStatus.CANCELLED,
        ),
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(service.transition_run, commands))

    assert {result.outcome for result in results} == {
        OperationOutcome.APPLIED,
        OperationOutcome.CONCURRENCY_CONFLICT,
    }
    stored = service.get_run(run_id)
    assert stored is not None
    lifecycle = stored["lifecycle"]
    assert isinstance(lifecycle, dict)
    assert lifecycle["revision"] == 1
    with mysql_engine.connect() as connection:
        count = connection.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM agent_run_transitions
                WHERE run_id=:run_id
                """
            ),
            {"run_id": run_id},
        )
    assert count == 2


def test_transition_insert_failure_rolls_back_snapshot(mysql_engine: Engine) -> None:
    service, run_id = _create_original(mysql_engine, "B")

    def fail_transition_insert(
        _connection: object,
        _cursor: object,
        statement: str,
        parameters: object,
        _context: object,
        _executemany: bool,
    ) -> None:
        if "INSERT INTO agent_run_transitions" not in statement:
            return
        if isinstance(parameters, dict) and parameters.get("to_revision") == 1:
            raise RuntimeError("injected transition history failure")

    event.listen(mysql_engine, "before_cursor_execute", fail_transition_insert)
    try:
        with pytest.raises(RuntimeError, match="history failure"):
            service.transition_run(
                _transition_command(
                    run_id,
                    "A",
                    RunStatus.PENDING,
                    0,
                    RunStatus.RUNNING,
                )
            )
    finally:
        event.remove(mysql_engine, "before_cursor_execute", fail_transition_insert)

    stored = service.get_run(run_id)
    assert stored is not None
    lifecycle = stored["lifecycle"]
    assert isinstance(lifecycle, dict)
    assert lifecycle["status"] == "PENDING"
    assert lifecycle["revision"] == 0
    with mysql_engine.connect() as connection:
        count = connection.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM agent_run_transitions
                WHERE run_id=:run_id
                """
            ),
            {"run_id": run_id},
        )
    assert count == 1
