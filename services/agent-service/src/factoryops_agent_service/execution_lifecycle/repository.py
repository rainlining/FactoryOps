from collections.abc import Mapping

from sqlalchemy import Connection, Engine, text


class ConditionalUpdateMiss(RuntimeError):
    pass


class ParentRunMissing(RuntimeError):
    pass


class ParentTaskMissing(RuntimeError):
    pass


class ParentTaskMismatch(RuntimeError):
    pass


class MySqlAgentExecutionRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def find(self, execution_id: str) -> Mapping[str, object] | None:
        return self._find("execution_id", execution_id)

    def find_by_key(self, key: str) -> Mapping[str, object] | None:
        return self._find("execution_key", key)

    def _find(self, column: str, value: str) -> Mapping[str, object] | None:
        if column not in {"execution_id", "execution_key"}:
            raise ValueError("unsupported lookup")
        with self._engine.connect() as c:
            return (
                c.execute(
                    text(f"SELECT * FROM agent_executions WHERE {column}=:value"),
                    {"value": value},
                )
                .mappings()
                .one_or_none()
            )

    def find_transition(self, request_id: str) -> Mapping[str, object] | None:
        with self._engine.connect() as c:
            return (
                c.execute(
                    text(
                        "SELECT * FROM agent_execution_transitions WHERE transition_request_id=:id"
                    ),
                    {"id": request_id},
                )
                .mappings()
                .one_or_none()
            )

    def create(
        self, execution: Mapping[str, object], transition: Mapping[str, object]
    ) -> None:
        with self._engine.begin() as c:
            if (
                c.scalar(
                    text("SELECT 1 FROM agent_runs WHERE run_id=:id FOR SHARE"),
                    {"id": execution["run_id"]},
                )
                is None
            ):
                raise ParentRunMissing
            task_id = execution["task_id"]
            if task_id is not None:
                task = (
                    c.execute(
                        text(
                            "SELECT run_id,target_agent_role FROM agent_tasks WHERE task_id=:id FOR SHARE"
                        ),
                        {"id": task_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if task is None:
                    raise ParentTaskMissing
                if (
                    task["run_id"] != execution["run_id"]
                    or task["target_agent_role"] != execution["agent_role"]
                ):
                    raise ParentTaskMismatch
            self._insert_execution(c, execution)
            self._insert_transition(c, transition)

    def apply(
        self, update: Mapping[str, object], transition: Mapping[str, object]
    ) -> None:
        with self._engine.begin() as c:
            result = c.execute(
                text("""UPDATE agent_executions SET status=:to_status,revision=:to_revision,updated_at=:occurred_at,
              started_at=:started_at,ended_at=:ended_at,status_reason_code=:reason_code,status_reason_message=:reason_message,
              output_artifact_refs=:output_artifact_refs,decision_id=:decision_id,result_evidence_refs=:result_evidence_refs,
              failure_code=:failure_code,failure_message=:failure_message,failure_recoverability=:failure_recoverability,
              failed_dependency_ref=:failed_dependency_ref
              WHERE execution_id=:execution_id AND status=:expected_status AND revision=:expected_revision"""),
                update,
            )
            if result.rowcount != 1:
                raise ConditionalUpdateMiss
            self._insert_transition(c, transition)

    def _insert_execution(self, c: Connection, e: Mapping[str, object]) -> None:
        c.execute(
            text("""INSERT INTO agent_executions(execution_id,execution_key,contract_version,run_id,agent_role,attempt,task_id,
          runtime_version,prompt_version,model_policy_version,tool_policy_version,context_policy_version,code_revision,
          context_snapshot_id,input_evidence_refs,status,revision,created_at,updated_at,started_at,ended_at,status_reason_code,
          status_reason_message,output_artifact_refs,decision_id,result_evidence_refs,failure_code,failure_message,
          failure_recoverability,failed_dependency_ref) VALUES (:execution_id,:execution_key,:contract_version,:run_id,:agent_role,
          :attempt,:task_id,:runtime_version,:prompt_version,:model_policy_version,:tool_policy_version,:context_policy_version,
          :code_revision,:context_snapshot_id,:input_evidence_refs,:status,:revision,:created_at,:updated_at,:started_at,:ended_at,
          :status_reason_code,:status_reason_message,:output_artifact_refs,:decision_id,:result_evidence_refs,:failure_code,
          :failure_message,:failure_recoverability,:failed_dependency_ref)"""),
            e,
        )

    def _insert_transition(self, c: Connection, t: Mapping[str, object]) -> None:
        c.execute(
            text("""INSERT INTO agent_execution_transitions(transition_id,transition_request_id,execution_id,from_status,
          to_status,from_revision,to_revision,actor_kind,actor_id,reason_code,reason_message,result_json,failure_json,occurred_at)
          VALUES (:transition_id,:transition_request_id,:execution_id,:from_status,:to_status,:from_revision,:to_revision,
          :actor_kind,:actor_id,:reason_code,:reason_message,:result_json,:failure_json,:occurred_at)"""),
            t,
        )
