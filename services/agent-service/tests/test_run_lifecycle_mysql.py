from __future__ import annotations

import pytest
from sqlalchemy import Engine, create_engine, text
from testcontainers.community.mysql import MySqlContainer

from factoryops_agent_service.event_ingress.migration import migrate


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
