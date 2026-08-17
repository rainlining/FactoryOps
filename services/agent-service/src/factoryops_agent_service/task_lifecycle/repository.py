from __future__ import annotations

from collections.abc import Mapping, Sequence

from sqlalchemy import Connection, Engine, text


class ConditionalUpdateMiss(RuntimeError):
    pass


class MySqlAgentTaskRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def find_task(self, task_id: str) -> Mapping[str, object] | None:
        return self._find("task_id", task_id)

    def find_by_request(self, request_id: str) -> Mapping[str, object] | None:
        return self._find("task_request_id", request_id)

    def _find(self, column: str, value: str) -> Mapping[str, object] | None:
        if column not in {"task_id", "task_request_id"}:
            raise ValueError("unsupported task lookup")
        with self._engine.connect() as c:
            row = (
                c.execute(
                    text(f"SELECT * FROM agent_tasks WHERE {column}=:value"),
                    {"value": value},
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

    def find_transition(self, request_id: str) -> Mapping[str, object] | None:
        with self._engine.connect() as c:
            return (
                c.execute(
                    text(
                        "SELECT * FROM agent_task_transitions WHERE transition_request_id=:id"
                    ),
                    {"id": request_id},
                )
                .mappings()
                .one_or_none()
            )

    def create(
        self,
        task: Mapping[str, object],
        dependencies: Sequence[str],
        transition: Mapping[str, object],
    ) -> None:
        with self._engine.begin() as c:
            if (
                c.scalar(
                    text("SELECT 1 FROM agent_runs WHERE run_id=:id FOR SHARE"),
                    {"id": task["run_id"]},
                )
                is None
            ):
                raise ParentRunMissing
            for dependency in dependencies:
                run_id = c.scalar(
                    text("SELECT run_id FROM agent_tasks WHERE task_id=:id FOR SHARE"),
                    {"id": dependency},
                )
                if run_id is None:
                    raise DependencyMissing(dependency)
                if run_id != task["run_id"]:
                    raise CrossRunDependency(dependency)
            self._insert_task(c, task)
            for ordinal, dependency in enumerate(dependencies):
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
            self._insert_transition(c, transition)

    def apply_transition(
        self, update: Mapping[str, object], transition: Mapping[str, object]
    ) -> None:
        with self._engine.begin() as c:
            result = c.execute(
                text("""UPDATE agent_tasks SET status=:to_status,revision=:to_revision,updated_at=:occurred_at,
              started_at=:started_at,ended_at=:ended_at,status_reason_code=:reason_code,status_reason_message=:reason_message,
              current_execution_id=:execution_id,attempt_count=:attempt_count,completion_execution_id=:completion_execution_id,
              failure_execution_id=:failure_execution_id,failure_code=:failure_code,failure_message=:failure_message,
              failure_recoverability=:failure_recoverability
              WHERE task_id=:task_id AND status=:expected_status AND revision=:expected_revision"""),
                update,
            )
            if result.rowcount != 1:
                raise ConditionalUpdateMiss
            self._insert_transition(c, transition)

    def _insert_task(self, c: Connection, task: Mapping[str, object]) -> None:
        c.execute(
            text("""INSERT INTO agent_tasks(task_id,task_request_id,task_key,contract_version,run_id,task_type,target_agent_role,
          created_by_execution_id,priority,context_snapshot_id,evidence_refs,status,revision,created_at,updated_at,started_at,ended_at,
          status_reason_code,status_reason_message,current_execution_id,attempt_count,completion_execution_id,failure_execution_id,
          failure_code,failure_message,failure_recoverability)
          VALUES (:task_id,:task_request_id,:task_key,:contract_version,:run_id,:task_type,:target_agent_role,
          :created_by_execution_id,:priority,:context_snapshot_id,:evidence_refs,:status,:revision,:created_at,:updated_at,:started_at,:ended_at,
          :status_reason_code,:status_reason_message,:current_execution_id,:attempt_count,:completion_execution_id,:failure_execution_id,
          :failure_code,:failure_message,:failure_recoverability)"""),
            task,
        )

    def _insert_transition(
        self, c: Connection, transition: Mapping[str, object]
    ) -> None:
        c.execute(
            text("""INSERT INTO agent_task_transitions(transition_id,transition_request_id,task_id,from_status,to_status,
          from_revision,to_revision,actor_kind,actor_id,reason_code,reason_message,execution_id,attempt_count,
          completion_execution_id,failure_code,failure_message,failure_recoverability,occurred_at)
          VALUES (:transition_id,:transition_request_id,:task_id,:from_status,:to_status,:from_revision,:to_revision,:actor_kind,
          :actor_id,:reason_code,:reason_message,:execution_id,:attempt_count,:completion_execution_id,:failure_code,:failure_message,
          :failure_recoverability,:occurred_at)"""),
            transition,
        )


class ParentRunMissing(RuntimeError):
    pass


class DependencyMissing(RuntimeError):
    pass


class CrossRunDependency(RuntimeError):
    pass
