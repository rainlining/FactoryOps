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
            for statement in migration_sql.split(";"):
                if statement.strip():
                    connection.exec_driver_sql(statement)
            connection.execute(
                text("INSERT INTO agent_schema_history(version) VALUES (:version)"),
                {"version": version},
            )
