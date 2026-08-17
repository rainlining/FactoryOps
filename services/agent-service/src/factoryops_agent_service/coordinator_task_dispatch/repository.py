from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy import Connection, Engine, text


class CoordinatorExecutionRejected(ValueError):
    pass


class MySqlCoordinatorTaskDispatchRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def find_by_request(self, request_id: str) -> Mapping[str, object] | None:
        with self._engine.connect() as c:
            row = (
                c.execute(
                    text("SELECT * FROM agent_tasks WHERE task_request_id=:id"),
                    {"id": request_id},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            result = dict(row)
            result["dependency_task_ids"] = tuple(
                c.scalars(
                    text(
                        "SELECT dependency_task_id FROM agent_task_dependencies WHERE task_id=:id ORDER BY ordinal"
                    ),
                    {"id": row["task_id"]},
                ).all()
            )
            return result

    def dispatch(
        self,
        task: Mapping[str, object],
        dependencies: Sequence[str],
        history: Mapping[str, object],
        execution_history: Mapping[str, object],
    ) -> None:
        with self._engine.begin() as c:
            owner = (
                c.execute(
                    text(
                        "SELECT run_id, agent_role, status FROM agent_executions WHERE execution_id=:id FOR UPDATE"
                    ),
                    {"id": task["created_by_execution_id"]},
                )
                .mappings()
                .one_or_none()
            )
            if (
                owner is None
                or owner["agent_role"] != "coordinator"
                or owner["status"] not in {"PENDING", "RUNNING"}
                or owner["run_id"] != task["run_id"]
            ):
                raise CoordinatorExecutionRejected(
                    "Coordinator execution must be RUNNING and share Run"
                )
            if (
                c.scalar(
                    text("SELECT 1 FROM agent_runs WHERE run_id=:id FOR UPDATE"),
                    {"id": task["run_id"]},
                )
                is None
            ):
                raise CoordinatorExecutionRejected("parent Run does not exist")
            if owner["status"] == "PENDING":
                updated = c.execute(
                    text("""
                  UPDATE agent_executions SET status='RUNNING', revision=1, updated_at=:at,
                    started_at=:at, status_reason_code='COORDINATOR_EXECUTION_STARTED',
                    status_reason_message='Coordinator execution started'
                  WHERE execution_id=:id AND status='PENDING' AND revision=0
                """),
                    {
                        "at": execution_history["occurred_at"],
                        "id": task["created_by_execution_id"],
                    },
                )
                if updated.rowcount != 1:
                    raise CoordinatorExecutionRejected(
                        "Coordinator execution changed concurrently"
                    )
                self._insert_execution_history(c, execution_history)
            self._insert_task(c, task)
            for ordinal, dependency in enumerate(dependencies):
                run_id = c.scalar(
                    text("SELECT run_id FROM agent_tasks WHERE task_id=:id FOR SHARE"),
                    {"id": dependency},
                )
                if run_id is None or run_id != task["run_id"]:
                    raise CoordinatorExecutionRejected(
                        "dependency Task must exist in same Run"
                    )
                c.execute(
                    text(
                        "INSERT INTO agent_task_dependencies(task_id,dependency_task_id,ordinal) VALUES (:task,:dependency,:ordinal)"
                    ),
                    {
                        "task": task["task_id"],
                        "dependency": dependency,
                        "ordinal": ordinal,
                    },
                )
            self._insert_history(c, history)

    @staticmethod
    def _insert_execution_history(c: Connection, h: Mapping[str, object]) -> None:
        c.execute(
            text("""
          INSERT INTO agent_execution_transitions(transition_id,transition_request_id,execution_id,from_status,to_status,
          from_revision,to_revision,actor_kind,actor_id,reason_code,reason_message,result_json,failure_json,occurred_at)
          VALUES (:transition_id,:transition_request_id,:execution_id,:from_status,:to_status,:from_revision,:to_revision,
          :actor_kind,:actor_id,:reason_code,:reason_message,:result_json,:failure_json,:occurred_at)
        """),
            h,
        )

    @staticmethod
    def _insert_task(c: Connection, t: Mapping[str, object]) -> None:
        c.execute(
            text("""
          INSERT INTO agent_tasks(task_id,task_request_id,task_key,contract_version,run_id,task_type,target_agent_role,
          created_by_execution_id,priority,context_snapshot_id,evidence_refs,status,revision,created_at,updated_at,
          started_at,ended_at,status_reason_code,status_reason_message,current_execution_id,attempt_count,
          completion_execution_id,failure_execution_id,failure_code,failure_message,failure_recoverability)
          VALUES (:task_id,:task_request_id,:task_key,:contract_version,:run_id,:task_type,:target_agent_role,
          :created_by_execution_id,:priority,:context_snapshot_id,:evidence_refs,:status,:revision,:created_at,:updated_at,
          :started_at,:ended_at,:status_reason_code,:status_reason_message,:current_execution_id,:attempt_count,
          :completion_execution_id,:failure_execution_id,:failure_code,:failure_message,:failure_recoverability)
        """),
            t,
        )

    @staticmethod
    def _insert_history(c: Connection, h: Mapping[str, object]) -> None:
        c.execute(
            text("""
          INSERT INTO agent_task_transitions(transition_id,transition_request_id,task_id,from_status,to_status,
          from_revision,to_revision,actor_kind,actor_id,reason_code,reason_message,execution_id,attempt_count,
          completion_execution_id,failure_code,failure_message,failure_recoverability,occurred_at)
          VALUES (:transition_id,:transition_request_id,:task_id,:from_status,:to_status,:from_revision,:to_revision,
          :actor_kind,:actor_id,:reason_code,:reason_message,:execution_id,:attempt_count,:completion_execution_id,
          :failure_code,:failure_message,:failure_recoverability,:occurred_at)
        """),
            h,
        )
