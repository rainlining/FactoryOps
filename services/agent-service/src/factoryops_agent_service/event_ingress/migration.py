from __future__ import annotations

from importlib.resources import files

from sqlalchemy import Engine, text

MIGRATION_VERSIONS = (
    "001_create_agent_event_inbox",
    "002_create_agent_run_lifecycle",
    "003_create_agent_task_lifecycle",
    "004_create_agent_execution_lifecycle",
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
