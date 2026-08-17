from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import Connection, Engine, text


class RunMissing(LookupError):
    pass


class RunNotStartable(RuntimeError):
    pass


class MySqlCoordinatorStartRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def find_receipt(self, request_id: str) -> Mapping[str, object] | None:
        with self._engine.connect() as connection:
            return self._find_receipt(connection, request_id)

    def find_run(self, run_id: str) -> Mapping[str, object] | None:
        with self._engine.connect() as connection:
            return (
                connection.execute(
                    text("SELECT * FROM agent_runs WHERE run_id=:id"), {"id": run_id}
                )
                .mappings()
                .one_or_none()
            )

    def find_execution(self, execution_id: str) -> Mapping[str, object] | None:
        with self._engine.connect() as connection:
            return (
                connection.execute(
                    text("SELECT * FROM agent_executions WHERE execution_id=:id"),
                    {"id": execution_id},
                )
                .mappings()
                .one_or_none()
            )

    def find_execution_by_key(self, execution_key: str) -> Mapping[str, object] | None:
        with self._engine.connect() as connection:
            return (
                connection.execute(
                    text("SELECT * FROM agent_executions WHERE execution_key=:key"),
                    {"key": execution_key},
                )
                .mappings()
                .one_or_none()
            )

    def start(
        self,
        *,
        run_id: str,
        execution: Mapping[str, object],
        execution_history: Mapping[str, object],
        run_history: Mapping[str, object],
        receipt: Mapping[str, object],
    ) -> None:
        with self._engine.begin() as connection:
            run = (
                connection.execute(
                    text("SELECT * FROM agent_runs WHERE run_id=:id FOR UPDATE"),
                    {"id": run_id},
                )
                .mappings()
                .one_or_none()
            )
            if run is None:
                raise RunMissing(run_id)
            if not (
                run["status"] == "PENDING"
                and run["revision"] == 0
                and run["coordinator_execution_id"] is None
                and run["agent_execution_count"] == 0
            ):
                raise RunNotStartable(run_id)
            self._insert_execution(connection, execution)
            self._insert_execution_history(connection, execution_history)
            updated = connection.execute(
                text(
                    """
                    UPDATE agent_runs SET
                      status='RUNNING', revision=1, updated_at=:at, started_at=:at,
                      status_reason_code='COORDINATOR_STARTED',
                      status_reason_message='Coordinator execution started',
                      coordinator_execution_id=:execution_id,
                      agent_execution_count=1
                    WHERE run_id=:run_id AND status='PENDING' AND revision=0
                      AND coordinator_execution_id IS NULL AND agent_execution_count=0
                    """
                ),
                {
                    "at": receipt["created_at"],
                    "execution_id": execution["execution_id"],
                    "run_id": run_id,
                },
            )
            if updated.rowcount != 1:
                raise RunNotStartable(run_id)
            self._insert_run_history(connection, run_history)
            connection.execute(
                text(
                    """
                    INSERT INTO coordinator_start_requests (
                      start_request_id, run_id, execution_id, payload_sha256, created_at)
                    VALUES (:start_request_id, :run_id, :execution_id, :payload_sha256, :created_at)
                    """
                ),
                receipt,
            )

    @staticmethod
    def _find_receipt(
        connection: Connection, request_id: str
    ) -> Mapping[str, object] | None:
        return (
            connection.execute(
                text(
                    "SELECT * FROM coordinator_start_requests WHERE start_request_id=:id"
                ),
                {"id": request_id},
            )
            .mappings()
            .one_or_none()
        )

    @staticmethod
    def _insert_execution(connection: Connection, row: Mapping[str, object]) -> None:
        connection.execute(
            text("""
            INSERT INTO agent_executions (
              execution_id, execution_key, contract_version, run_id, agent_role,
              attempt, task_id, runtime_version, prompt_version, model_policy_version,
              tool_policy_version, context_policy_version, code_revision,
              context_snapshot_id, input_evidence_refs, status, revision,
              created_at, updated_at, started_at, ended_at, status_reason_code,
              status_reason_message, output_artifact_refs, decision_id,
              result_evidence_refs, failure_code, failure_message,
              failure_recoverability, failed_dependency_ref)
            VALUES (
              :execution_id, :execution_key, :contract_version, :run_id, :agent_role,
              :attempt, :task_id, :runtime_version, :prompt_version, :model_policy_version,
              :tool_policy_version, :context_policy_version, :code_revision,
              :context_snapshot_id, :input_evidence_refs, :status, :revision,
              :created_at, :updated_at, :started_at, :ended_at, :status_reason_code,
              :status_reason_message, :output_artifact_refs, :decision_id,
              :result_evidence_refs, :failure_code, :failure_message,
              :failure_recoverability, :failed_dependency_ref)
        """),
            row,
        )

    @staticmethod
    def _insert_execution_history(
        connection: Connection, row: Mapping[str, object]
    ) -> None:
        connection.execute(
            text("""
            INSERT INTO agent_execution_transitions (
              transition_id, transition_request_id, execution_id, from_status,
              to_status, from_revision, to_revision, actor_kind, actor_id,
              reason_code, reason_message, result_json, failure_json, occurred_at)
            VALUES (:transition_id, :transition_request_id, :execution_id, :from_status,
              :to_status, :from_revision, :to_revision, :actor_kind, :actor_id,
              :reason_code, :reason_message, :result_json, :failure_json, :occurred_at)
        """),
            row,
        )

    @staticmethod
    def _insert_run_history(connection: Connection, row: Mapping[str, object]) -> None:
        connection.execute(
            text("""
            INSERT INTO agent_run_transitions (
              transition_id, transition_request_id, run_id, from_status, to_status,
              from_revision, to_revision, actor_kind, actor_id, reason_code,
              reason_message, checkpoint_id, occurred_at)
            VALUES (:transition_id, :transition_request_id, :run_id, :from_status, :to_status,
              :from_revision, :to_revision, :actor_kind, :actor_id, :reason_code,
              :reason_message, :checkpoint_id, :occurred_at)
        """),
            row,
        )
