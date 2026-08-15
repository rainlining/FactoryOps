from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import Connection, Engine, text


class MySqlAgentRunRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def inbox_event_exists(self, event_id: str) -> bool:
        with self._engine.connect() as connection:
            return (
                connection.scalar(
                    text(
                        """
                        SELECT 1
                        FROM agent_event_inbox
                        WHERE event_id=:event_id
                        """
                    ),
                    {"event_id": event_id},
                )
                is not None
            )

    def insert_run_with_initial_transition(
        self,
        run: Mapping[str, object],
        transition: Mapping[str, object],
    ) -> None:
        with self._engine.begin() as connection:
            self._insert_run(connection, run)
            self._insert_transition(connection, transition)

    def find_run(self, run_id: str) -> Mapping[str, object] | None:
        return self._find_run("run_id", run_id)

    def find_run_by_trigger_event(
        self,
        trigger_event_id: str,
    ) -> Mapping[str, object] | None:
        return self._find_run("trigger_event_id", trigger_event_id)

    def find_run_by_replay_request(
        self,
        replay_request_id: str,
    ) -> Mapping[str, object] | None:
        return self._find_run("replay_request_id", replay_request_id)

    def find_transition_by_request(
        self,
        transition_request_id: str,
    ) -> Mapping[str, object] | None:
        with self._engine.connect() as connection:
            return (
                connection.execute(
                    text(
                        """
                        SELECT *
                        FROM agent_run_transitions
                        WHERE transition_request_id=:transition_request_id
                        """
                    ),
                    {"transition_request_id": transition_request_id},
                )
                .mappings()
                .one_or_none()
            )

    def apply_transition(
        self,
        update: Mapping[str, object],
        transition: Mapping[str, object],
    ) -> None:
        with self._engine.begin() as connection:
            updated = connection.execute(
                text(
                    """
                    UPDATE agent_runs
                    SET status=:to_status,
                        revision=:to_revision,
                        updated_at=:occurred_at,
                        started_at=:started_at,
                        ended_at=:ended_at,
                        status_reason_code=:reason_code,
                        status_reason_message=:status_reason_message,
                        latest_checkpoint_id=CASE
                          WHEN :to_status='SUSPENDED' THEN :checkpoint_id
                          ELSE latest_checkpoint_id
                        END
                    WHERE run_id=:run_id
                      AND status=:expected_status
                      AND revision=:expected_revision
                    """
                ),
                update,
            )
            if updated.rowcount != 1:
                raise ConditionalUpdateMiss
            self._insert_transition(connection, transition)

    def _find_run(
        self,
        column: str,
        value: str,
    ) -> Mapping[str, object] | None:
        allowed_columns = {"run_id", "trigger_event_id", "replay_request_id"}
        if column not in allowed_columns:
            raise ValueError(f"unsupported lookup column: {column}")
        with self._engine.connect() as connection:
            return (
                connection.execute(
                    text(f"SELECT * FROM agent_runs WHERE {column}=:value"),
                    {"value": value},
                )
                .mappings()
                .one_or_none()
            )

    def _insert_run(
        self,
        connection: Connection,
        run: Mapping[str, object],
    ) -> None:
        connection.execute(
            text(
                """
                INSERT INTO agent_runs (
                  run_id, contract_version, run_kind, original_run_id,
                  trigger_event_id, replayed_from_run_id, replay_request_id,
                  incident_id, runtime_version, workflow_version,
                  prompt_set_version, model_policy_version,
                  tool_policy_version, context_policy_version, code_revision,
                  status, revision, created_at, updated_at,
                  started_at, ended_at,
                  status_reason_code, status_reason_message,
                  coordinator_execution_id, latest_checkpoint_id,
                  agent_execution_count, task_count, completed_task_count)
                VALUES (
                  :run_id, :contract_version, :run_kind, :original_run_id,
                  :trigger_event_id, :replayed_from_run_id, :replay_request_id,
                  :incident_id, :runtime_version, :workflow_version,
                  :prompt_set_version, :model_policy_version,
                  :tool_policy_version, :context_policy_version, :code_revision,
                  :status, :revision, :created_at, :updated_at,
                  :started_at, :ended_at,
                  :status_reason_code, :status_reason_message,
                  :coordinator_execution_id, :latest_checkpoint_id,
                  :agent_execution_count, :task_count, :completed_task_count)
                """
            ),
            run,
        )

    def _insert_transition(
        self,
        connection: Connection,
        transition: Mapping[str, object],
    ) -> None:
        connection.execute(
            text(
                """
                INSERT INTO agent_run_transitions (
                  transition_id, transition_request_id, run_id,
                  from_status, to_status, from_revision, to_revision,
                  actor_kind, actor_id, reason_code, reason_message,
                  checkpoint_id, occurred_at)
                VALUES (
                  :transition_id, :transition_request_id, :run_id,
                  :from_status, :to_status, :from_revision, :to_revision,
                  :actor_kind, :actor_id, :reason_code, :reason_message,
                  :checkpoint_id, :occurred_at)
                """
            ),
            transition,
        )


class ConditionalUpdateMiss(RuntimeError):
    pass
