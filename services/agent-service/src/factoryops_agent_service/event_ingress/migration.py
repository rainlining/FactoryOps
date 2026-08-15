from __future__ import annotations

from importlib.resources import files

from sqlalchemy import Engine, text

MIGRATION_VERSION = "001_create_agent_event_inbox"


def migrate(engine: Engine) -> None:
    migration_sql = (
        files("factoryops_agent_service.event_ingress.migrations")
        .joinpath(f"{MIGRATION_VERSION}.sql")
        .read_text(encoding="utf-8")
    )
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
        applied = connection.execute(
            text("SELECT 1 FROM agent_schema_history WHERE version=:version"),
            {"version": MIGRATION_VERSION},
        ).first()
        if applied:
            return
        for statement in migration_sql.split(";"):
            if statement.strip():
                connection.exec_driver_sql(statement)
        connection.execute(
            text("INSERT INTO agent_schema_history(version) VALUES (:version)"),
            {"version": MIGRATION_VERSION},
        )
