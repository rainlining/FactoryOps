from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum

from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from factoryops_agent_service.approved_action_resume import (
    ApprovedActionResumeIntegrityError,
    ApprovedActionResumeService,
    BusinessActionPort,
    BusinessActionPreconditionIntegrityError,
    BusinessActionPreconditionRejected,
)
from factoryops_agent_service.execution_lifecycle.model import ExecutionStatus
from factoryops_agent_service.execution_lifecycle.rules import LEGAL as EXECUTION_LEGAL
from factoryops_agent_service.execution_lifecycle.service import (
    AgentExecutionLifecycleService,
)
from factoryops_agent_service.human_approval import (
    HumanApprovalPersistenceIntegrityError,
    HumanApprovalService,
)
from factoryops_agent_service.risk_decision import (
    RiskDecisionPersistenceIntegrityError,
    RiskDecisionService,
)
from factoryops_agent_service.run_lifecycle.model import RunStatus
from factoryops_agent_service.run_lifecycle.rules import LEGAL_TRANSITIONS
from factoryops_agent_service.run_lifecycle.service import AgentRunLifecycleService
from factoryops_agent_service.task_lifecycle.model import TaskStatus
from factoryops_agent_service.task_lifecycle.rules import LEGAL as TASK_LEGAL
from factoryops_agent_service.task_lifecycle.service import AgentTaskLifecycleService


class ApprovedWorkflowCompletionRejected(ValueError):
    pass


class ApprovedWorkflowCompletionIntegrityError(RuntimeError):
    pass


class WorkflowCompletionOutcome(str, Enum):
    APPLIED = "applied"
    DUPLICATE_IDENTICAL = "duplicate-identical"


@dataclass(frozen=True)
class ApprovedWorkflowCompletionResult:
    outcome: WorkflowCompletionOutcome
    approval: Mapping[str, object]
    coordinator_execution: Mapping[str, object]
    run: Mapping[str, object]


class ApprovedWorkflowCompletionService:
    def __init__(
        self,
        engine: Engine,
        business_client: BusinessActionPort,
        *,
        after_coordinator_hook: Callable[[], None] | None = None,
        admission_wait_seconds: float = 35,
    ) -> None:
        if admission_wait_seconds <= 0:
            raise ValueError("admission_wait_seconds must be positive")
        self._engine = engine
        self._business = business_client
        self._after_coordinator_hook = after_coordinator_hook or (lambda: None)
        self._admission_wait_seconds = admission_wait_seconds

    def complete(
        self, terminal_approval: Mapping[str, object]
    ) -> ApprovedWorkflowCompletionResult:
        identity = terminal_approval.get("identity")
        if not isinstance(identity, Mapping) or not isinstance(
            identity.get("approval_id"), str
        ):
            raise ApprovedWorkflowCompletionRejected("Approval identity is required")
        lock_name = (
            "workflow-complete:"
            + hashlib.sha256(str(identity["approval_id"]).encode()).hexdigest()[:45]
        )
        with self._engine.connect() as admission:
            while True:
                acquired = admission.scalar(
                    text("SELECT GET_LOCK(:name,:timeout)"),
                    {"name": lock_name, "timeout": self._admission_wait_seconds},
                )
                admission.commit()
                if acquired == 1:
                    break
                if acquired is None:
                    raise ApprovedWorkflowCompletionIntegrityError(
                        "workflow completion admission lock failed"
                    )
            admission.commit()
            try:
                if not self._has_completion(identity):
                    try:
                        ApprovedActionResumeService(
                            self._engine,
                            self._business,
                            before_business_hook=lambda connection: (
                                self._resume_preflight(connection, identity)
                            ),
                        ).resume(terminal_approval)
                    except BusinessActionPreconditionRejected as error:
                        raise ApprovedWorkflowCompletionRejected(str(error)) from error
                    except BusinessActionPreconditionIntegrityError as error:
                        raise ApprovedWorkflowCompletionIntegrityError(
                            str(error)
                        ) from error
                    except ApprovedActionResumeIntegrityError as error:
                        raise ApprovedWorkflowCompletionIntegrityError(
                            "workflow readiness or resume integrity failed"
                        ) from error
                return self._complete_agent(terminal_approval)
            finally:
                admission.rollback()
                admission.execute(
                    text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name}
                )
                admission.commit()

    def _has_completion(self, identity: Mapping[str, object]) -> bool:
        execution_transition, execution_request, run_transition, run_request = (
            self._transition_ids(str(identity["approval_id"]))
        )
        with self._engine.connect() as connection:
            return bool(
                connection.scalar(
                    text(
                        "SELECT EXISTS(SELECT 1 FROM agent_execution_transitions "
                        "WHERE transition_id=:execution OR transition_request_id=:execution_request) OR "
                        "EXISTS(SELECT 1 FROM agent_run_transitions "
                        "WHERE transition_id=:run OR transition_request_id=:run_request)"
                    ),
                    {
                        "execution": execution_transition,
                        "execution_request": execution_request,
                        "run": run_transition,
                        "run_request": run_request,
                    },
                )
            )

    def _complete_agent(
        self, approval: Mapping[str, object]
    ) -> ApprovedWorkflowCompletionResult:
        identity = approval["identity"]
        assert isinstance(identity, Mapping)
        approval_id = str(identity["approval_id"])
        approval_key = str(identity["approval_key"])
        run_id = str(identity["run_id"])
        coordinator_id = str(identity["coordinator_execution_id"])
        (
            execution_transition_id,
            execution_request_id,
            run_transition_id,
            run_request_id,
        ) = self._transition_ids(approval_id)
        result_payload = {
            "output_artifact_refs": ["fusion:" + str(identity["fusion_key"])],
            "decision_id": None,
            "evidence_refs": [
                "approval:" + approval_key,
                "risk:" + str(identity["decision_key"]),
            ],
        }
        try:
            with self._engine.begin() as connection:
                risk_service = RiskDecisionService(self._engine)
                fusion = RiskDecisionService._read_fusion(
                    connection, str(identity["fusion_key"]), for_update=True
                )
                if fusion is None:
                    raise ApprovedWorkflowCompletionIntegrityError(
                        "Fusion provenance is missing"
                    )
                risk_service._decode_fusion(connection, fusion, for_update=True)
                risk = RiskDecisionService._read_row_by_identity(
                    connection,
                    str(identity["decision_key"]),
                    str(identity["decision_id"]),
                    for_update=True,
                )
                if risk is None:
                    raise ApprovedWorkflowCompletionIntegrityError(
                        "Risk Decision is missing"
                    )
                risk_service._decode(connection, risk)
                run = (
                    connection.execute(
                        text("SELECT * FROM agent_runs WHERE run_id=:run FOR UPDATE"),
                        {"run": run_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if run is None:
                    raise ApprovedWorkflowCompletionIntegrityError("Run is missing")
                run_history = self._lock_run_history(connection, run_id)
                self._validate_run_history(run, run_history)
                approval_row = HumanApprovalService._read_by_identity(
                    connection, approval_key, approval_id, for_update=True
                )
                if approval_row is None:
                    raise ApprovedWorkflowCompletionIntegrityError(
                        "Approval is missing"
                    )
                stored_approval = HumanApprovalService(self._engine)._decode(
                    connection, approval_row, for_update=True
                )
                if stored_approval != approval:
                    raise ApprovedWorkflowCompletionIntegrityError(
                        "Approval changed before workflow completion"
                    )
                coordinator = (
                    connection.execute(
                        text(
                            "SELECT * FROM agent_executions "
                            "WHERE execution_id=:execution FOR UPDATE"
                        ),
                        {"execution": coordinator_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if coordinator is None:
                    raise ApprovedWorkflowCompletionIntegrityError(
                        "Coordinator Execution is missing"
                    )
                AgentExecutionLifecycleService(self._engine)._to_contract(coordinator)
                coordinator_history = (
                    connection.execute(
                        text(
                            "SELECT * FROM agent_execution_transitions "
                            "WHERE execution_id=:execution ORDER BY to_revision FOR UPDATE"
                        ),
                        {"execution": coordinator_id},
                    )
                    .mappings()
                    .all()
                )
                self._validate_coordinator_history(coordinator, coordinator_history)
                tasks = self._lock_tasks(connection, run_id)
                self._validate_tasks(connection, tasks, run_id)
                execution_count = int(
                    connection.scalar(
                        text("SELECT COUNT(*) FROM agent_executions WHERE run_id=:run"),
                        {"run": run_id},
                    )
                )
                execution_rows = self._lock_identity(
                    connection,
                    "agent_execution_transitions",
                    execution_transition_id,
                    execution_request_id,
                )
                run_rows = self._lock_identity(
                    connection,
                    "agent_run_transitions",
                    run_transition_id,
                    run_request_id,
                )
                if execution_rows or run_rows:
                    self._validate_replay(
                        execution_rows,
                        run_rows,
                        coordinator,
                        run,
                        coordinator_id,
                        run_id,
                        execution_transition_id,
                        execution_request_id,
                        run_transition_id,
                        run_request_id,
                        approval_key,
                        result_payload,
                        tasks,
                        execution_count,
                    )
                    outcome = WorkflowCompletionOutcome.DUPLICATE_IDENTICAL
                else:
                    self._validate_readiness(
                        run, coordinator, tasks, run_id, coordinator_id, approval_key
                    )
                    task_count = len(tasks)
                    occurred_at = connection.scalar(text("SELECT CURRENT_TIMESTAMP(6)"))
                    execution_revision = int(coordinator["revision"]) + 1
                    run_revision = int(run["revision"]) + 1
                    result_json = json.dumps(result_payload, sort_keys=True)
                    if (
                        connection.execute(
                            text(
                                "UPDATE agent_executions SET status='SUCCEEDED',revision=:revision,"
                                "updated_at=:at,ended_at=:at,status_reason_code='APPROVED_WORKFLOW_COMPLETED',"
                                "status_reason_message=:key,output_artifact_refs=:artifacts,"
                                "decision_id=:decision,result_evidence_refs=:evidence "
                                "WHERE execution_id=:execution AND status='RUNNING' AND revision=:expected"
                            ),
                            {
                                "revision": execution_revision,
                                "at": occurred_at,
                                "key": approval_key,
                                "artifacts": json.dumps(
                                    result_payload["output_artifact_refs"]
                                ),
                                "decision": result_payload["decision_id"],
                                "evidence": json.dumps(result_payload["evidence_refs"]),
                                "execution": coordinator_id,
                                "expected": coordinator["revision"],
                            },
                        ).rowcount
                        != 1
                    ):
                        raise ApprovedWorkflowCompletionIntegrityError(
                            "Coordinator completion compare-and-set failed"
                        )
                    connection.execute(
                        text(
                            "INSERT INTO agent_execution_transitions "
                            "(transition_id,transition_request_id,execution_id,from_status,to_status,"
                            "from_revision,to_revision,actor_kind,actor_id,reason_code,reason_message,"
                            "result_json,failure_json,occurred_at) VALUES "
                            "(:transition,:request,:execution,'RUNNING','SUCCEEDED',:from_revision,"
                            ":to_revision,'COORDINATOR','approved-workflow-completion-service',"
                            "'APPROVED_WORKFLOW_COMPLETED',:key,:result,NULL,:at)"
                        ),
                        {
                            "transition": execution_transition_id,
                            "request": execution_request_id,
                            "execution": coordinator_id,
                            "from_revision": coordinator["revision"],
                            "to_revision": execution_revision,
                            "key": approval_key,
                            "result": result_json,
                            "at": occurred_at,
                        },
                    )
                    self._after_coordinator_hook()
                    if (
                        connection.execute(
                            text(
                                "UPDATE agent_runs SET status='SUCCEEDED',revision=:revision,"
                                "updated_at=:at,ended_at=:at,status_reason_code='APPROVED_WORKFLOW_COMPLETED',"
                                "status_reason_message=:key,task_count=:task_count,"
                                "completed_task_count=:task_count,agent_execution_count=:execution_count "
                                "WHERE run_id=:run "
                                "AND status='RUNNING' AND revision=:expected"
                            ),
                            {
                                "revision": run_revision,
                                "at": occurred_at,
                                "key": approval_key,
                                "task_count": task_count,
                                "execution_count": execution_count,
                                "run": run_id,
                                "expected": run["revision"],
                            },
                        ).rowcount
                        != 1
                    ):
                        raise ApprovedWorkflowCompletionIntegrityError(
                            "Run completion compare-and-set failed"
                        )
                    connection.execute(
                        text(
                            "INSERT INTO agent_run_transitions "
                            "(transition_id,transition_request_id,run_id,from_status,to_status,"
                            "from_revision,to_revision,actor_kind,actor_id,reason_code,reason_message,"
                            "checkpoint_id,occurred_at) VALUES "
                            "(:transition,:request,:run,'RUNNING','SUCCEEDED',:from_revision,"
                            ":to_revision,'COORDINATOR','approved-workflow-completion-service',"
                            "'APPROVED_WORKFLOW_COMPLETED',:key,NULL,:at)"
                        ),
                        {
                            "transition": run_transition_id,
                            "request": run_request_id,
                            "run": run_id,
                            "from_revision": run["revision"],
                            "to_revision": run_revision,
                            "key": approval_key,
                            "at": occurred_at,
                        },
                    )
                    outcome = WorkflowCompletionOutcome.APPLIED
        except (
            DBAPIError,
            RiskDecisionPersistenceIntegrityError,
            HumanApprovalPersistenceIntegrityError,
        ) as error:
            raise ApprovedWorkflowCompletionIntegrityError(
                "approved workflow completion transaction failed"
            ) from error
        except ApprovedWorkflowCompletionIntegrityError:
            raise
        except ApprovedWorkflowCompletionRejected:
            raise
        except Exception as error:
            raise ApprovedWorkflowCompletionIntegrityError(
                "approved workflow completion transaction failed"
            ) from error
        coordinator_contract = AgentExecutionLifecycleService(
            self._engine
        ).get_execution(coordinator_id)
        run_contract = AgentRunLifecycleService(self._engine).get_run(run_id)
        if coordinator_contract is None or run_contract is None:
            raise ApprovedWorkflowCompletionIntegrityError(
                "completed workflow could not be reloaded"
            )
        return ApprovedWorkflowCompletionResult(
            outcome, approval, coordinator_contract, run_contract
        )

    def _preflight(self, connection, identity: Mapping[str, object]) -> None:
        run_id = str(identity["run_id"])
        coordinator_id = str(identity["coordinator_execution_id"])
        coordinator = (
            connection.execute(
                text(
                    "SELECT * FROM agent_executions "
                    "WHERE execution_id=:execution FOR UPDATE"
                ),
                {"execution": coordinator_id},
            )
            .mappings()
            .one_or_none()
        )
        if coordinator is None:
            raise ApprovedWorkflowCompletionIntegrityError(
                "Coordinator Execution is missing during preflight"
            )
        AgentExecutionLifecycleService(self._engine)._to_contract(coordinator)
        if (
            coordinator["run_id"] != run_id
            or coordinator["agent_role"] != "coordinator"
            or coordinator["task_id"] is not None
        ):
            raise ApprovedWorkflowCompletionIntegrityError(
                "Coordinator Execution identity is inconsistent"
            )
        if coordinator["status"] != "RUNNING":
            raise ApprovedWorkflowCompletionRejected(
                "Coordinator Execution must be RUNNING before business execution"
            )
        coordinator_history = (
            connection.execute(
                text(
                    "SELECT * FROM agent_execution_transitions "
                    "WHERE execution_id=:execution ORDER BY to_revision FOR UPDATE"
                ),
                {"execution": coordinator_id},
            )
            .mappings()
            .all()
        )
        self._validate_coordinator_history(coordinator, coordinator_history)
        tasks = self._lock_tasks(connection, run_id)
        self._validate_tasks(connection, tasks, run_id)
        run = (
            connection.execute(
                text("SELECT * FROM agent_runs WHERE run_id=:run FOR UPDATE"),
                {"run": run_id},
            )
            .mappings()
            .one()
        )
        run_history = self._lock_run_history(connection, run_id)
        self._validate_run_history(run, run_history)
        self._validate_pre_business_run_phase(connection, run, identity)

    @staticmethod
    def _validate_pre_business_run_phase(
        connection, run: Mapping[str, object], identity: Mapping[str, object]
    ) -> None:
        approval_id = str(identity["approval_id"])
        approval_key = str(identity["approval_key"])
        wait_id, wait_request = HumanApprovalService._wait_transition_ids(approval_id)
        resume_id, resume_request = ApprovedActionResumeService._resume_transition_ids(
            approval_id
        )
        wait = (
            connection.execute(
                text(
                    "SELECT * FROM agent_run_transitions WHERE transition_id=:transition "
                    "AND transition_request_id=:request FOR UPDATE"
                ),
                {"transition": wait_id, "request": wait_request},
            )
            .mappings()
            .one_or_none()
        )
        resume = (
            connection.execute(
                text(
                    "SELECT * FROM agent_run_transitions WHERE transition_id=:transition "
                    "AND transition_request_id=:request FOR UPDATE"
                ),
                {"transition": resume_id, "request": resume_request},
            )
            .mappings()
            .one_or_none()
        )
        if (
            wait is None
            or wait["run_id"] != run["run_id"]
            or wait["to_status"] != "WAITING_FOR_APPROVAL"
            or wait["reason_code"] != "HUMAN_APPROVAL_REQUIRED"
            or wait["reason_message"] != approval_key
        ):
            raise ApprovedWorkflowCompletionIntegrityError(
                "Approval wait phase is inconsistent"
            )
        if resume is None:
            if (
                run["status"] != "WAITING_FOR_APPROVAL"
                or run["revision"] != wait["to_revision"]
                or run["status_reason_code"] != wait["reason_code"]
                or run["status_reason_message"] != approval_key
            ):
                raise ApprovedWorkflowCompletionRejected(
                    "Run is not ready for approved business execution"
                )
            return
        if (
            resume["run_id"] != run["run_id"]
            or resume["from_status"] != "WAITING_FOR_APPROVAL"
            or resume["to_status"] != "RUNNING"
            or resume["from_revision"] != wait["to_revision"]
            or resume["to_revision"] != int(wait["to_revision"]) + 1
            or resume["reason_code"] != "APPROVED_ACTION_EXECUTED"
            or resume["reason_message"] != approval_key
            or run["status"] != "RUNNING"
            or run["revision"] != resume["to_revision"]
            or run["status_reason_code"] != resume["reason_code"]
            or run["status_reason_message"] != approval_key
        ):
            raise ApprovedWorkflowCompletionIntegrityError(
                "Approval resume phase is inconsistent"
            )

    def _resume_preflight(self, connection, identity: Mapping[str, object]) -> None:
        try:
            self._preflight(connection, identity)
        except ApprovedWorkflowCompletionRejected as error:
            raise BusinessActionPreconditionRejected(str(error)) from error
        except ApprovedWorkflowCompletionIntegrityError as error:
            raise BusinessActionPreconditionIntegrityError(str(error)) from error

    @staticmethod
    def _lock_tasks(connection, run_id: str):
        return (
            connection.execute(
                text(
                    "SELECT t.*,e.status AS execution_status,e.task_id AS execution_task_id,"
                    "e.run_id AS execution_run_id,e.agent_role AS execution_agent_role "
                    "FROM agent_tasks t LEFT JOIN agent_executions e "
                    "ON e.execution_id=t.completion_execution_id "
                    "WHERE t.run_id=:run ORDER BY t.task_id FOR UPDATE"
                ),
                {"run": run_id},
            )
            .mappings()
            .all()
        )

    @staticmethod
    def _validate_task_readiness(tasks, run_id: str) -> None:
        if len(tasks) < 2 or any(task["status"] != "SUCCEEDED" for task in tasks):
            raise ApprovedWorkflowCompletionRejected(
                "all Specialist Tasks must be SUCCEEDED"
            )
        if any(
            task["current_execution_id"] != task["completion_execution_id"]
            or task["execution_status"] != "SUCCEEDED"
            or task["execution_task_id"] != task["task_id"]
            or task["execution_run_id"] != run_id
            or task["execution_agent_role"] != task["target_agent_role"]
            for task in tasks
        ):
            raise ApprovedWorkflowCompletionIntegrityError(
                "Task or completion Execution readiness is inconsistent"
            )

    def _validate_tasks(self, connection, tasks, run_id: str) -> None:
        self._validate_task_readiness(tasks, run_id)
        task_service = AgentTaskLifecycleService(self._engine)
        execution_service = AgentExecutionLifecycleService(self._engine)
        for task in tasks:
            dependencies = (
                connection.execute(
                    text(
                        "SELECT dependency_task_id FROM agent_task_dependencies "
                        "WHERE task_id=:task ORDER BY ordinal"
                    ),
                    {"task": task["task_id"]},
                )
                .scalars()
                .all()
            )
            task_service._to_contract(
                {**task, "dependency_task_ids": tuple(dependencies)}
            )
            history = (
                connection.execute(
                    text(
                        "SELECT * FROM agent_task_transitions WHERE task_id=:task "
                        "ORDER BY to_revision FOR UPDATE"
                    ),
                    {"task": task["task_id"]},
                )
                .mappings()
                .all()
            )
            self._validate_task_history(task, history)
            execution = (
                connection.execute(
                    text(
                        "SELECT * FROM agent_executions "
                        "WHERE execution_id=:execution FOR UPDATE"
                    ),
                    {"execution": task["completion_execution_id"]},
                )
                .mappings()
                .one()
            )
            execution_service._to_contract(execution)
            execution_history = (
                connection.execute(
                    text(
                        "SELECT * FROM agent_execution_transitions "
                        "WHERE execution_id=:execution ORDER BY to_revision FOR UPDATE"
                    ),
                    {"execution": task["completion_execution_id"]},
                )
                .mappings()
                .all()
            )
            self._validate_coordinator_history(execution, execution_history)

    @staticmethod
    def _validate_task_history(task: Mapping[str, object], history) -> None:
        if len(history) != int(task["revision"]) + 1:
            raise ApprovedWorkflowCompletionIntegrityError("Task history is incomplete")
        previous_status: str | None = None
        for expected_revision, transition in enumerate(history):
            if (
                transition["to_revision"] != expected_revision
                or transition["task_id"] != task["task_id"]
                or transition["from_revision"]
                != (None if expected_revision == 0 else expected_revision - 1)
                or transition["from_status"] != previous_status
            ):
                raise ApprovedWorkflowCompletionIntegrityError(
                    "Task history is inconsistent"
                )
            if previous_status is not None:
                try:
                    if (
                        TaskStatus(str(transition["to_status"]))
                        not in TASK_LEGAL[TaskStatus(previous_status)]
                    ):
                        raise ApprovedWorkflowCompletionIntegrityError(
                            "Task history transition is illegal"
                        )
                except ValueError as error:
                    raise ApprovedWorkflowCompletionIntegrityError(
                        "Task history status is invalid"
                    ) from error
            previous_status = str(transition["to_status"])
        tail = history[-1]
        if (
            tail["to_status"] != task["status"]
            or tail["to_revision"] != task["revision"]
            or tail["reason_code"] != task["status_reason_code"]
            or tail["reason_message"] != task["status_reason_message"]
            or tail["execution_id"] != task["current_execution_id"]
            or tail["attempt_count"] != task["attempt_count"]
            or tail["completion_execution_id"] != task["completion_execution_id"]
            or tail["occurred_at"] != task["updated_at"]
        ):
            raise ApprovedWorkflowCompletionIntegrityError(
                "Task current snapshot differs from history"
            )

    @staticmethod
    def _lock_run_history(connection, run_id: str):
        return (
            connection.execute(
                text(
                    "SELECT * FROM agent_run_transitions WHERE run_id=:run "
                    "ORDER BY to_revision FOR UPDATE"
                ),
                {"run": run_id},
            )
            .mappings()
            .all()
        )

    @staticmethod
    def _validate_run_history(run: Mapping[str, object], history) -> None:
        if len(history) != int(run["revision"]) + 1:
            raise ApprovedWorkflowCompletionIntegrityError("Run history is incomplete")
        previous_status: str | None = None
        for expected_revision, transition in enumerate(history):
            if (
                transition["to_revision"] != expected_revision
                or transition["run_id"] != run["run_id"]
                or transition["from_revision"]
                != (None if expected_revision == 0 else expected_revision - 1)
                or transition["from_status"] != previous_status
            ):
                raise ApprovedWorkflowCompletionIntegrityError(
                    "Run history is inconsistent"
                )
            if previous_status is not None:
                try:
                    if (
                        RunStatus(str(transition["to_status"]))
                        not in LEGAL_TRANSITIONS[RunStatus(previous_status)]
                    ):
                        raise ApprovedWorkflowCompletionIntegrityError(
                            "Run history transition is illegal"
                        )
                except ValueError as error:
                    raise ApprovedWorkflowCompletionIntegrityError(
                        "Run history status is invalid"
                    ) from error
            previous_status = str(transition["to_status"])
        tail = history[-1]
        if (
            tail["to_status"] != run["status"]
            or tail["to_revision"] != run["revision"]
            or tail["reason_code"] != run["status_reason_code"]
            or tail["reason_message"] != run["status_reason_message"]
            or tail["occurred_at"] != run["updated_at"]
        ):
            raise ApprovedWorkflowCompletionIntegrityError(
                "Run current snapshot differs from history"
            )

    @staticmethod
    def _validate_readiness(
        run: Mapping[str, object],
        coordinator: Mapping[str, object],
        tasks: list[Mapping[str, object]],
        run_id: str,
        coordinator_id: str,
        approval_key: str,
    ) -> None:
        if (
            run["status"] != "RUNNING"
            or run["status_reason_code"] != "APPROVED_ACTION_EXECUTED"
            or run["status_reason_message"] != approval_key
            or run["coordinator_execution_id"] != coordinator_id
            or coordinator["run_id"] != run_id
            or coordinator["agent_role"] != "coordinator"
            or coordinator["task_id"] is not None
            or coordinator["status"] != "RUNNING"
        ):
            raise ApprovedWorkflowCompletionRejected(
                "Run or Coordinator is not ready for completion"
            )
        if len(tasks) < 2 or any(
            task["status"] != "SUCCEEDED"
            or task["current_execution_id"] != task["completion_execution_id"]
            or task["execution_status"] != "SUCCEEDED"
            for task in tasks
        ):
            raise ApprovedWorkflowCompletionRejected(
                "all Specialist Tasks must be SUCCEEDED"
            )

    @staticmethod
    def _lock_identity(connection, table: str, transition: str, request: str):
        if table not in {"agent_execution_transitions", "agent_run_transitions"}:
            raise AssertionError("unexpected transition table")
        return (
            connection.execute(
                text(
                    f"SELECT * FROM {table} WHERE transition_id=:transition "
                    "OR transition_request_id=:request FOR UPDATE"
                ),
                {"transition": transition, "request": request},
            )
            .mappings()
            .all()
        )

    @staticmethod
    def _validate_replay(
        execution_rows,
        run_rows,
        coordinator,
        run,
        coordinator_id,
        run_id,
        execution_transition_id,
        execution_request_id,
        run_transition_id,
        run_request_id,
        approval_key,
        result_payload,
        tasks,
        execution_count,
    ) -> None:
        if len(execution_rows) != 1 or len(run_rows) != 1:
            raise ApprovedWorkflowCompletionIntegrityError(
                "workflow completion transition identity is split"
            )
        execution = execution_rows[0]
        run_transition = run_rows[0]
        expected_result = json.dumps(result_payload, sort_keys=True)
        if (
            execution["transition_id"] != execution_transition_id
            or execution["transition_request_id"] != execution_request_id
            or execution["execution_id"] != coordinator_id
            or execution["from_status"] != "RUNNING"
            or execution["to_status"] != "SUCCEEDED"
            or execution["to_revision"] != execution["from_revision"] + 1
            or execution["actor_kind"] != "COORDINATOR"
            or execution["actor_id"] != "approved-workflow-completion-service"
            or execution["reason_code"] != "APPROVED_WORKFLOW_COMPLETED"
            or execution["reason_message"] != approval_key
            or json.dumps(json.loads(str(execution["result_json"])), sort_keys=True)
            != expected_result
            or execution["failure_json"] is not None
            or run_transition["transition_id"] != run_transition_id
            or run_transition["transition_request_id"] != run_request_id
            or run_transition["run_id"] != run_id
            or run_transition["from_status"] != "RUNNING"
            or run_transition["to_status"] != "SUCCEEDED"
            or run_transition["to_revision"] != run_transition["from_revision"] + 1
            or run_transition["actor_kind"] != "COORDINATOR"
            or run_transition["actor_id"] != "approved-workflow-completion-service"
            or run_transition["reason_code"] != "APPROVED_WORKFLOW_COMPLETED"
            or run_transition["reason_message"] != approval_key
            or run_transition["checkpoint_id"] is not None
            or coordinator["status"] != "SUCCEEDED"
            or coordinator["run_id"] != run_id
            or coordinator["agent_role"] != "coordinator"
            or coordinator["task_id"] is not None
            or coordinator["revision"] != execution["to_revision"]
            or coordinator["status_reason_code"] != execution["reason_code"]
            or coordinator["status_reason_message"] != execution["reason_message"]
            or json.dumps(
                json.loads(str(coordinator["output_artifact_refs"])), sort_keys=True
            )
            != json.dumps(result_payload["output_artifact_refs"], sort_keys=True)
            or coordinator["decision_id"] is not None
            or json.dumps(
                json.loads(str(coordinator["result_evidence_refs"])), sort_keys=True
            )
            != json.dumps(result_payload["evidence_refs"], sort_keys=True)
            or run["status"] != "SUCCEEDED"
            or run["revision"] != run_transition["to_revision"]
            or run["status_reason_code"] != run_transition["reason_code"]
            or run["status_reason_message"] != run_transition["reason_message"]
            or int(run["task_count"]) != len(tasks)
            or int(run["completed_task_count"]) != len(tasks)
            or int(run["agent_execution_count"]) != execution_count
            or any(
                task["status"] != "SUCCEEDED"
                or task["current_execution_id"] != task["completion_execution_id"]
                or task["execution_status"] != "SUCCEEDED"
                or task["execution_task_id"] != task["task_id"]
                or task["execution_run_id"] != run_id
                or task["execution_agent_role"] != task["target_agent_role"]
                for task in tasks
            )
            or coordinator["ended_at"] != execution["occurred_at"]
            or coordinator["updated_at"] != execution["occurred_at"]
            or run["ended_at"] != run_transition["occurred_at"]
            or run["updated_at"] != run_transition["occurred_at"]
            or execution["occurred_at"] != run_transition["occurred_at"]
        ):
            raise ApprovedWorkflowCompletionIntegrityError(
                "workflow completion replay is inconsistent"
            )

    @staticmethod
    def _validate_coordinator_history(
        coordinator: Mapping[str, object], history: list[Mapping[str, object]]
    ) -> None:
        if len(history) != int(coordinator["revision"]) + 1:
            raise ApprovedWorkflowCompletionIntegrityError(
                "Coordinator Execution history is incomplete"
            )
        previous_status: str | None = None
        for expected_revision, transition in enumerate(history):
            if (
                transition["to_revision"] != expected_revision
                or transition["execution_id"] != coordinator["execution_id"]
                or transition["from_revision"]
                != (None if expected_revision == 0 else expected_revision - 1)
                or transition["from_status"] != previous_status
            ):
                raise ApprovedWorkflowCompletionIntegrityError(
                    "Coordinator Execution history is inconsistent"
                )
            if previous_status is not None:
                try:
                    if (
                        ExecutionStatus(str(transition["to_status"]))
                        not in EXECUTION_LEGAL[ExecutionStatus(previous_status)]
                    ):
                        raise ApprovedWorkflowCompletionIntegrityError(
                            "Coordinator Execution history transition is illegal"
                        )
                except ValueError as error:
                    raise ApprovedWorkflowCompletionIntegrityError(
                        "Coordinator Execution history status is invalid"
                    ) from error
            previous_status = str(transition["to_status"])
        tail = history[-1]
        if (
            tail["to_status"] != coordinator["status"]
            or tail["to_revision"] != coordinator["revision"]
            or tail["reason_code"] != coordinator["status_reason_code"]
            or tail["reason_message"] != coordinator["status_reason_message"]
            or tail["occurred_at"] != coordinator["updated_at"]
        ):
            raise ApprovedWorkflowCompletionIntegrityError(
                "Coordinator Execution current snapshot differs from history"
            )

    @staticmethod
    def _transition_ids(approval_id: str) -> tuple[str, str, str, str]:
        def derive(namespace: str, prefix: str) -> str:
            digest = (
                hashlib.sha256((namespace + "\n" + approval_id).encode())
                .hexdigest()
                .upper()[:32]
            )
            return prefix + digest

        return (
            derive("approved-workflow-execution-v1", "WCT-"),
            derive("approved-workflow-execution-request-v1", "WCQ-"),
            derive("approved-workflow-run-v1", "TRN-"),
            derive("approved-workflow-run-request-v1", "TRQ-"),
        )
