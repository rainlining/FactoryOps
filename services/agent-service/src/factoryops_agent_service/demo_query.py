from __future__ import annotations

import json
from collections.abc import Mapping

from sqlalchemy import Engine, text


class WorkflowSnapshotNotFound(LookupError):
    pass


class WorkflowSnapshotIntegrityError(RuntimeError):
    pass


class WorkflowSnapshotQueryService:
    """Read-only, run-scoped projection for the local demo."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, run_id: str) -> dict[str, object]:
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("run_id is required")
        with self._engine.connect() as connection:
            run = self._one(
                connection, "SELECT * FROM agent_runs WHERE run_id=:run", run_id
            )
            if run is None:
                raise WorkflowSnapshotNotFound(run_id)
            tasks = self._many(
                connection,
                "SELECT * FROM agent_tasks WHERE run_id=:run ORDER BY task_id",
                run_id,
            )
            task_ids = {row["task_id"] for row in tasks}
            executions = self._many(
                connection,
                "SELECT * FROM agent_executions WHERE run_id=:run ORDER BY execution_id",
                run_id,
            )
            for execution in executions:
                if execution["run_id"] != run_id or (
                    execution["task_id"] is not None
                    and execution["task_id"] not in task_ids
                ):
                    raise WorkflowSnapshotIntegrityError(
                        "execution is outside run snapshot"
                    )
            coordinator = next(
                (
                    row
                    for row in executions
                    if row["execution_id"] == run["coordinator_execution_id"]
                ),
                None,
            )
            if run["coordinator_execution_id"] is not None and (
                coordinator is None
                or coordinator["agent_role"] != "coordinator"
                or coordinator["task_id"] is not None
                or coordinator["run_id"] != run_id
            ):
                raise WorkflowSnapshotIntegrityError(
                    "coordinator execution binding is inconsistent"
                )
            fusion = self._one(
                connection,
                "SELECT fusion_id, fusion_key, coordinator_execution_id, proposed_action, has_conflict, fusion_round, run_id FROM coordinator_fusions WHERE run_id=:run ORDER BY fusion_round DESC LIMIT 1",
                run_id,
            )
            risk = self._one(
                connection,
                "SELECT decision_id, decision_key, fusion_id, fusion_key, coordinator_execution_id, task_id, run_id, decision, risk_level, approval_required, proposed_action FROM risk_decisions WHERE run_id=:run ORDER BY created_at DESC LIMIT 1",
                run_id,
            )
            approval = self._one(
                connection,
                "SELECT approval_key, decision_id, decision_key, fusion_id, fusion_key, coordinator_execution_id, run_id, status, revision, requested_at, expires_at, updated_at FROM human_approvals WHERE run_id=:run ORDER BY created_at DESC LIMIT 1",
                run_id,
            )
            if fusion is not None and (
                fusion["run_id"] != run_id
                or coordinator is None
                or fusion["coordinator_execution_id"] != coordinator["execution_id"]
            ):
                raise WorkflowSnapshotIntegrityError(
                    "fusion provenance is inconsistent"
                )
            if risk is not None and (
                risk["run_id"] != run_id
                or risk["fusion_id"] != (fusion or {}).get("fusion_id")
                or risk["fusion_key"] != (fusion or {}).get("fusion_key")
                or risk["coordinator_execution_id"]
                != (fusion or {}).get("coordinator_execution_id")
                or (risk["task_id"] is not None and risk["task_id"] not in task_ids)
            ):
                raise WorkflowSnapshotIntegrityError("risk provenance is inconsistent")
            if approval is not None and (
                approval["run_id"] != run_id
                or approval["decision_id"] != (risk or {}).get("decision_id")
                or approval["decision_key"] != (risk or {}).get("decision_key")
                or approval["fusion_id"] != (fusion or {}).get("fusion_id")
                or approval["fusion_key"] != (fusion or {}).get("fusion_key")
                or approval["coordinator_execution_id"]
                != (fusion or {}).get("coordinator_execution_id")
            ):
                raise WorkflowSnapshotIntegrityError(
                    "approval provenance is inconsistent"
                )
            return {
                "run": self._project(
                    run,
                    (
                        "run_id",
                        "run_kind",
                        "incident_id",
                        "status",
                        "revision",
                        "created_at",
                        "updated_at",
                        "started_at",
                        "ended_at",
                        "status_reason_code",
                        "status_reason_message",
                        "task_count",
                        "completed_task_count",
                    ),
                ),
                "coordinator": self._project(
                    coordinator,
                    (
                        "execution_id",
                        "status",
                        "revision",
                        "agent_role",
                        "attempt",
                        "output_artifact_refs",
                        "decision_id",
                    ),
                ),
                "tasks": [
                    self._project(
                        task,
                        (
                            "task_id",
                            "task_key",
                            "target_agent_role",
                            "status",
                            "revision",
                            "attempt_count",
                            "current_execution_id",
                            "completion_execution_id",
                        ),
                    )
                    for task in tasks
                ],
                "executions": [
                    self._project(
                        execution,
                        (
                            "execution_id",
                            "agent_role",
                            "task_id",
                            "status",
                            "revision",
                            "attempt",
                        ),
                    )
                    for execution in executions
                ],
                "fusion": self._project(
                    fusion,
                    ("fusion_key", "proposed_action", "has_conflict", "fusion_round"),
                ),
                "risk": self._project(
                    risk,
                    (
                        "decision_key",
                        "decision",
                        "risk_level",
                        "approval_required",
                        "proposed_action",
                    ),
                ),
                "approval": self._project(
                    approval,
                    (
                        "approval_key",
                        "status",
                        "revision",
                        "requested_at",
                        "expires_at",
                        "updated_at",
                    ),
                ),
            }

    @staticmethod
    def _one(connection, statement: str, run_id: str) -> Mapping[str, object] | None:
        return (
            connection.execute(text(statement), {"run": run_id})
            .mappings()
            .one_or_none()
        )

    @staticmethod
    def _many(connection, statement: str, run_id: str) -> list[Mapping[str, object]]:
        return list(
            connection.execute(text(statement), {"run": run_id}).mappings().all()
        )

    @staticmethod
    def _project(
        row: Mapping[str, object] | None, fields: tuple[str, ...]
    ) -> dict[str, object] | None:
        if row is None:
            return None
        result: dict[str, object] = {}
        for field in fields:
            value = row.get(field)
            if isinstance(value, (dict, list)):
                result[field] = value
            elif field == "output_artifact_refs" and isinstance(value, str):
                result[field] = json.loads(value)
            else:
                result[field] = value
        return result
