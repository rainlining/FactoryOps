from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import Engine, create_engine, text
from testcontainers.community.mysql import MySqlContainer

from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.run_lifecycle.model import (
    OperationOutcome,
    OriginalRunCommand,
    ReplayRunCommand,
    RunProvenance,
)
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

    assert count == 2


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

    assert first.outcome is OperationOutcome.APPLIED
    assert identical.outcome is OperationOutcome.DUPLICATE_IDENTICAL
    assert conflicting.outcome is OperationOutcome.DUPLICATE_CONFLICTING
    assert identical.run == first.run
    assert conflicting.run == first.run


def test_original_requires_persisted_inbox_event(mysql_engine: Engine) -> None:
    with pytest.raises(RunCreationRejected, match="Inbox"):
        _service(mysql_engine).create_original_run(
            OriginalRunCommand(_event_id("3"), _provenance("3"))
        )


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

    with pytest.raises(RunCreationRejected, match="same Incident"):
        service.create_replay_run(
            ReplayRunCommand(
                replay_request_id="RPR-" + "5" * 32,
                original_run_id=original_run_id,
                replayed_from_run_id=original_run_id,
                provenance=_provenance("5"),
            )
        )
