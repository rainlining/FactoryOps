from __future__ import annotations

from importlib.resources import files

from sqlalchemy import Connection, Engine, text

MIGRATION_VERSIONS = (
    "001_create_agent_event_inbox",
    "002_create_agent_run_lifecycle",
    "003_create_agent_task_lifecycle",
    "004_create_agent_execution_lifecycle",
    "005_create_coordinator_start_requests",
    "006_create_agent_task_leases",
    "007_create_worker_task_execution_requests",
    "008_create_worker_task_completion_requests",
    "009_create_worker_task_retry_requests",
    "010_create_specialist_recommendations",
    "011_create_risk_decisions",
    "012_create_coordinator_fusions",
    "013_extend_risk_decision_subject",
    "014_create_human_approvals",
    "015_bind_human_approval_incident",
)


def _preflight_execution_references(connection: Connection) -> None:
    count = connection.scalar(
        text(
            """
            SELECT COUNT(*) FROM (
              SELECT coordinator_execution_id AS execution_id FROM agent_runs
                WHERE coordinator_execution_id IS NOT NULL
              UNION ALL
              SELECT created_by_execution_id FROM agent_tasks
                WHERE created_by_execution_id IS NOT NULL
              UNION ALL
              SELECT current_execution_id FROM agent_tasks
                WHERE current_execution_id IS NOT NULL
              UNION ALL
              SELECT completion_execution_id FROM agent_tasks
                WHERE completion_execution_id IS NOT NULL
              UNION ALL
              SELECT failure_execution_id FROM agent_tasks
                WHERE failure_execution_id IS NOT NULL
            ) existing_execution_references
            """
        )
    )
    if count:
        raise RuntimeError(
            "migration 004 requires existing Run/Task execution references "
            "to be audited and cleared before agent_executions is created"
        )


def _apply_risk_decision_subject_migration(
    connection: Connection, statements: list[str]
) -> None:
    expected_columns = {
        "subject_type",
        "fusion_id",
        "fusion_key",
        "coordinator_execution_id",
        "fusion_round",
    }
    existing_columns = set(
        connection.scalars(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=DATABASE() AND table_name='risk_decisions' "
                "AND column_name IN "
                "('subject_type','fusion_id','fusion_key',"
                "'coordinator_execution_id','fusion_round')"
            )
        )
    )
    if not existing_columns:
        connection.exec_driver_sql(statements[0])
    elif existing_columns != expected_columns:
        raise RuntimeError(
            "migration 013 found a partial column set; audit risk_decisions before retry"
        )
    connection.exec_driver_sql(statements[1])
    expected_constraints = {
        "fk_risk_decision_fusion",
        "fk_risk_decision_coordinator_execution",
        "uk_risk_decision_fusion",
        "chk_risk_decision_subject",
    }
    existing_constraints = set(
        connection.scalars(
            text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_schema=DATABASE() AND table_name='risk_decisions' "
                "AND constraint_name IN "
                "('fk_risk_decision_fusion',"
                "'fk_risk_decision_coordinator_execution',"
                "'uk_risk_decision_fusion','chk_risk_decision_subject')"
            )
        )
    )
    if not existing_constraints:
        connection.exec_driver_sql(statements[2])
    elif existing_constraints != expected_constraints:
        raise RuntimeError(
            "migration 013 found a partial constraint set; audit risk_decisions before retry"
        )


def _validate_table_shape(
    connection: Connection,
    table: str,
    expected_columns: set[str],
    expected_constraints: set[str],
) -> None:
    columns = set(
        connection.scalars(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=DATABASE() AND table_name=:table"
            ),
            {"table": table},
        )
    )
    constraints = set(
        connection.scalars(
            text(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_schema=DATABASE() AND table_name=:table"
            ),
            {"table": table},
        )
    )
    allowed_columns = {frozenset(expected_columns)}
    if table == "human_approvals":
        allowed_columns.add(frozenset(expected_columns | {"incident_id"}))
    if frozenset(columns) not in allowed_columns or constraints != expected_constraints:
        raise RuntimeError(
            f"migration 014 found unexpected {table} structure; audit before retry"
        )


def _apply_human_approval_incident_migration(
    connection: Connection, statements: list[str]
) -> None:
    column = connection.execute(
        text(
            "SELECT data_type AS data_type,"
            "character_maximum_length AS character_maximum_length,"
            "is_nullable AS is_nullable "
            "FROM information_schema.columns WHERE table_schema=DATABASE() "
            "AND table_name='human_approvals' AND column_name='incident_id'"
        )
    ).one_or_none()
    if column is None:
        connection.exec_driver_sql(statements[0])
        return
    if column[0] != "varchar" or int(column[1]) != 67 or column[2] != "YES":
        raise RuntimeError(
            "migration 015 found unexpected incident_id structure; audit before retry"
        )


def _apply_human_approval_migration(
    connection: Connection, statements: list[str]
) -> None:
    tables = set(
        connection.scalars(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema=DATABASE() AND table_name IN "
                "('human_approvals','human_approval_history')"
            )
        )
    )
    current_columns = {
        "approval_id",
        "approval_key",
        "decision_id",
        "decision_key",
        "fusion_id",
        "fusion_key",
        "run_id",
        "coordinator_execution_id",
        "fusion_round",
        "revision",
        "status",
        "canonical_sha256",
        "payload_json",
        "requested_at",
        "expires_at",
        "updated_at",
        "created_at",
    }
    history_columns = {
        "approval_id",
        "revision",
        "status",
        "canonical_sha256",
        "payload_json",
        "recorded_at",
    }
    current_constraints = {
        "PRIMARY",
        "approval_key",
        "decision_id",
        "decision_key",
        "fk_human_approval_decision",
        "fk_human_approval_fusion",
        "fk_human_approval_run",
        "fk_human_approval_coordinator",
        "chk_human_approval_status",
        "chk_human_approval_revision",
        "chk_human_approval_payload",
    }
    history_constraints = {
        "PRIMARY",
        "fk_human_approval_history_current",
        "chk_human_approval_history_status",
        "chk_human_approval_history_payload",
    }
    if "human_approval_history" in tables and "human_approvals" not in tables:
        raise RuntimeError(
            "migration 014 found history without current table; audit before retry"
        )
    if "human_approvals" not in tables:
        connection.exec_driver_sql(statements[0])
    else:
        _validate_table_shape(
            connection, "human_approvals", current_columns, current_constraints
        )
    if "human_approval_history" not in tables:
        connection.exec_driver_sql(statements[1])
    else:
        _validate_table_shape(
            connection,
            "human_approval_history",
            history_columns,
            history_constraints,
        )
    _validate_table_shape(
        connection, "human_approvals", current_columns, current_constraints
    )
    _validate_table_shape(
        connection, "human_approval_history", history_columns, history_constraints
    )


def migrate(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS agent_schema_history (
                  version VARCHAR(100) PRIMARY KEY,
                  applied_at TIMESTAMP(6) NOT NULL
                    DEFAULT CURRENT_TIMESTAMP(6)
                ) ENGINE=InnoDB
                """
            )
        )
        for version in MIGRATION_VERSIONS:
            applied = connection.execute(
                text("SELECT 1 FROM agent_schema_history WHERE version=:version"),
                {"version": version},
            ).first()
            if applied:
                continue
            if version == "004_create_agent_execution_lifecycle":
                _preflight_execution_references(connection)
            migration_sql = (
                files("factoryops_agent_service.event_ingress.migrations")
                .joinpath(f"{version}.sql")
                .read_text(encoding="utf-8")
            )
            statements = [
                statement for statement in migration_sql.split(";") if statement.strip()
            ]
            if version == "013_extend_risk_decision_subject":
                _apply_risk_decision_subject_migration(connection, statements)
            elif version == "014_create_human_approvals":
                _apply_human_approval_migration(connection, statements)
            elif version == "015_bind_human_approval_incident":
                _apply_human_approval_incident_migration(connection, statements)
            else:
                for statement in statements:
                    connection.exec_driver_sql(statement)
            connection.execute(
                text("INSERT INTO agent_schema_history(version) VALUES (:version)"),
                {"version": version},
            )
