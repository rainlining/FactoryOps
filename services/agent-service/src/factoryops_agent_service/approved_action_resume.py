from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError

from factoryops_agent_service.human_approval import (
    HumanApprovalSaveOutcome,
    HumanApprovalService,
)
from factoryops_agent_service.run_lifecycle.service import AgentRunLifecycleService


class ApprovedActionResumeRejected(ValueError):
    pass


class ApprovedActionResumeIntegrityError(RuntimeError):
    pass


class BusinessActionUnavailable(RuntimeError):
    pass


class ResumeOutcome(str, Enum):
    APPLIED = "applied"
    DUPLICATE_IDENTICAL = "duplicate-identical"


@dataclass(frozen=True)
class ApprovedActionResumeResult:
    outcome: ResumeOutcome
    approval: Mapping[str, object]
    receipt: Mapping[str, object]
    run: Mapping[str, object]


class BusinessActionPort(Protocol):
    def execute(self, approval_key: str) -> Mapping[str, object]: ...


class BusinessActionHttpClient:
    def __init__(
        self,
        base_url: str,
        service_token: str,
        *,
        timeout_seconds: float = 5.0,
    ) -> None:
        if not base_url.strip() or not service_token.strip():
            raise ValueError("base_url and service_token are required")
        if timeout_seconds <= 0 or timeout_seconds > 30:
            raise ValueError("timeout_seconds must be in (0,30]")
        self._base_url = base_url.rstrip("/")
        self._service_token = service_token
        self._timeout_seconds = timeout_seconds

    def execute(self, approval_key: str) -> Mapping[str, object]:
        encoded = urllib.parse.quote(approval_key, safe="")
        request = urllib.request.Request(
            self._base_url + "/internal/api/v1/approvals/" + encoded + "/execute",
            data=b"{}",
            headers={
                "Content-Type": "application/json",
                "X-FactoryOps-Service-Token": self._service_token,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self._timeout_seconds
            ) as response:
                if response.status < 200 or response.status >= 300:
                    raise BusinessActionUnavailable(
                        f"Business API returned HTTP {response.status}"
                    )
                body = response.read()
        except urllib.error.HTTPError as error:
            raise BusinessActionUnavailable(
                f"Business API returned HTTP {error.code}"
            ) from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise BusinessActionUnavailable("Business API is unavailable") from error
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise BusinessActionUnavailable(
                "Business API returned malformed JSON"
            ) from error
        if not isinstance(payload, Mapping):
            raise BusinessActionUnavailable(
                "Business API returned a non-object response"
            )
        return payload


class ApprovedActionResumeService:
    def __init__(
        self,
        engine: Engine,
        business_client: BusinessActionPort,
        *,
        after_business_hook: Callable[[], None] | None = None,
    ) -> None:
        self._engine = engine
        self._business = business_client
        self._after_business_hook = after_business_hook or (lambda: None)

    def resume(
        self, terminal_approval: Mapping[str, object]
    ) -> ApprovedActionResumeResult:
        saved = HumanApprovalService(self._engine).save(terminal_approval)
        if saved.outcome is HumanApprovalSaveOutcome.DUPLICATE_CONFLICTING:
            raise ApprovedActionResumeRejected("terminal Approval conflicts")
        approval = saved.approval
        identity, request, state = (
            approval["identity"],
            approval["request"],
            approval["state"],
        )
        assert (
            isinstance(identity, Mapping)
            and isinstance(request, Mapping)
            and isinstance(state, Mapping)
        )
        if (
            approval["contract_version"] != "1.1.0"
            or state["revision"] != 2
            or state["status"] != "APPROVED"
        ):
            raise ApprovedActionResumeRejected(
                "revision 2 APPROVED v1.1 Approval is required"
            )
        if request["proposed_action"] != "HOLD_BATCH":
            raise ApprovedActionResumeRejected("only approved HOLD_BATCH can resume")

        try:
            outcome, receipt = self._execute_and_resume(
                approval,
                str(identity["approval_id"]),
                str(identity["approval_key"]),
                str(identity["run_id"]),
            )
        except (ApprovedActionResumeRejected, BusinessActionUnavailable):
            raise
        except Exception as error:
            raise ApprovedActionResumeIntegrityError(
                "Run resume transaction failed"
            ) from error
        verified = HumanApprovalService(self._engine).get_by_key(
            str(identity["approval_key"])
        )
        run = AgentRunLifecycleService(self._engine).get_run(str(identity["run_id"]))
        if verified != approval or run is None:
            raise ApprovedActionResumeIntegrityError(
                "resumed Approval or Run could not be verified"
            )
        return ApprovedActionResumeResult(outcome, approval, receipt, run)

    def _execute_and_resume(
        self,
        approval: Mapping[str, object],
        approval_id: str,
        approval_key: str,
        run_id: str,
    ) -> tuple[ResumeOutcome, Mapping[str, object]]:
        wait_transition_id, wait_request_id = HumanApprovalService._wait_transition_ids(
            approval_id
        )
        resume_transition_id, resume_request_id = self._resume_transition_ids(
            approval_id
        )
        try:
            with self._engine.begin() as connection:
                run = (
                    connection.execute(
                        text("SELECT * FROM agent_runs WHERE run_id=:run FOR UPDATE"),
                        {"run": run_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if run is None:
                    raise ApprovedActionResumeIntegrityError("source Run is missing")
                wait_rows = (
                    connection.execute(
                        text(
                            "SELECT * FROM agent_run_transitions "
                            "WHERE transition_id=:transition OR "
                            "transition_request_id=:request FOR UPDATE"
                        ),
                        {
                            "transition": wait_transition_id,
                            "request": wait_request_id,
                        },
                    )
                    .mappings()
                    .all()
                )
                if len(wait_rows) != 1:
                    raise ApprovedActionResumeIntegrityError(
                        "Approval wait transition is missing or split"
                    )
                wait = wait_rows[0]
                if (
                    wait["transition_id"] != wait_transition_id
                    or wait["transition_request_id"] != wait_request_id
                    or wait["run_id"] != run_id
                    or wait["from_status"] != "RUNNING"
                    or wait["to_status"] != "WAITING_FOR_APPROVAL"
                    or wait["to_revision"] != wait["from_revision"] + 1
                    or wait["reason_code"] != "HUMAN_APPROVAL_REQUIRED"
                    or wait["reason_message"] != approval_key
                ):
                    raise ApprovedActionResumeIntegrityError(
                        "Approval wait transition is inconsistent"
                    )
                resume_rows = (
                    connection.execute(
                        text(
                            "SELECT * FROM agent_run_transitions "
                            "WHERE transition_id=:transition OR "
                            "transition_request_id=:request FOR UPDATE"
                        ),
                        {
                            "transition": resume_transition_id,
                            "request": resume_request_id,
                        },
                    )
                    .mappings()
                    .all()
                )
                if len(resume_rows) > 1:
                    raise ApprovedActionResumeIntegrityError(
                        "Approval resume transition identity is split"
                    )
                receipt = self._validate_receipt(
                    self._business.execute(approval_key), approval
                )
                if resume_rows:
                    self._validate_resume_replay(
                        resume_rows[0],
                        run,
                        resume_transition_id,
                        resume_request_id,
                        approval_key,
                        wait,
                    )
                    return ResumeOutcome.DUPLICATE_IDENTICAL, receipt
                if (
                    run["status"] != "WAITING_FOR_APPROVAL"
                    or run["revision"] != wait["to_revision"]
                ):
                    raise ApprovedActionResumeRejected(
                        "source Run is not at the Approval wait revision"
                    )
                self._after_business_hook()
                occurred_at = connection.scalar(text("SELECT CURRENT_TIMESTAMP(6)"))
                updated = connection.execute(
                    text(
                        "UPDATE agent_runs SET status='RUNNING',revision=:revision,"
                        "updated_at=:occurred,status_reason_code='APPROVED_ACTION_EXECUTED',"
                        "status_reason_message=:approval_key "
                        "WHERE run_id=:run AND status='WAITING_FOR_APPROVAL' "
                        "AND revision=:expected"
                    ),
                    {
                        "revision": int(wait["to_revision"]) + 1,
                        "occurred": occurred_at,
                        "approval_key": approval_key,
                        "run": run_id,
                        "expected": wait["to_revision"],
                    },
                )
                if updated.rowcount != 1:
                    raise ApprovedActionResumeIntegrityError(
                        "Run resume compare-and-set failed"
                    )
                connection.execute(
                    text(
                        "INSERT INTO agent_run_transitions "
                        "(transition_id,transition_request_id,run_id,from_status,to_status,"
                        "from_revision,to_revision,actor_kind,actor_id,reason_code,"
                        "reason_message,checkpoint_id,occurred_at) VALUES "
                        "(:transition,:request,:run,'WAITING_FOR_APPROVAL','RUNNING',"
                        ":from_revision,:to_revision,'COORDINATOR',"
                        "'approved-action-resume-service','APPROVED_ACTION_EXECUTED',"
                        ":approval_key,NULL,:occurred)"
                    ),
                    {
                        "transition": resume_transition_id,
                        "request": resume_request_id,
                        "run": run_id,
                        "from_revision": wait["to_revision"],
                        "to_revision": int(wait["to_revision"]) + 1,
                        "approval_key": approval_key,
                        "occurred": occurred_at,
                    },
                )
                return ResumeOutcome.APPLIED, receipt
        except DBAPIError as error:
            raise ApprovedActionResumeIntegrityError(
                "Run resume database transaction failed"
            ) from error

    @staticmethod
    def _validate_resume_replay(
        resume: Mapping[str, object],
        run: Mapping[str, object],
        transition_id: str,
        request_id: str,
        approval_key: str,
        wait: Mapping[str, object],
    ) -> None:
        if (
            resume["transition_id"] != transition_id
            or resume["transition_request_id"] != request_id
            or resume["run_id"] != run["run_id"]
            or resume["from_status"] != "WAITING_FOR_APPROVAL"
            or resume["to_status"] != "RUNNING"
            or resume["from_revision"] != wait["to_revision"]
            or resume["to_revision"] != int(wait["to_revision"]) + 1
            or resume["actor_kind"] != "COORDINATOR"
            or resume["actor_id"] != "approved-action-resume-service"
            or resume["reason_code"] != "APPROVED_ACTION_EXECUTED"
            or resume["reason_message"] != approval_key
            or resume["checkpoint_id"] is not None
            or run["status"] != "RUNNING"
            or run["revision"] != resume["to_revision"]
            or run["status_reason_code"] != resume["reason_code"]
            or run["status_reason_message"] != resume["reason_message"]
            or HumanApprovalService._utc(run["updated_at"])
            != HumanApprovalService._utc(resume["occurred_at"])
        ):
            raise ApprovedActionResumeIntegrityError(
                "Approval resume replay is inconsistent"
            )

    @staticmethod
    def _validate_receipt(
        value: Mapping[str, object], approval: Mapping[str, object]
    ) -> Mapping[str, object]:
        expected_fields = {
            "approval_key",
            "action",
            "incident_id",
            "batch_id",
            "status",
            "executed_at",
            "replayed",
        }
        identity = approval["identity"]
        request = approval["request"]
        assert isinstance(identity, Mapping) and isinstance(request, Mapping)
        try:
            valid_time = datetime.fromisoformat(
                str(value["executed_at"]).replace("Z", "+00:00")
            )
        except (KeyError, ValueError):
            valid_time = None
        if (
            set(value) != expected_fields
            or value.get("approval_key") != identity["approval_key"]
            or value.get("action") != request["proposed_action"]
            or value.get("incident_id") != identity["incident_id"]
            or not isinstance(value.get("batch_id"), str)
            or not str(value.get("batch_id")).strip()
            or value.get("status") != "EXECUTED"
            or valid_time is None
            or valid_time.tzinfo is None
            or not isinstance(value.get("replayed"), bool)
        ):
            raise ApprovedActionResumeRejected(
                "Business action receipt is invalid or mismatched"
            )
        return dict(value)

    @staticmethod
    def _resume_transition_ids(approval_id: str) -> tuple[str, str]:
        digest = (
            hashlib.sha256(("approved-action-resume-v1\n" + approval_id).encode())
            .hexdigest()
            .upper()[:32]
        )
        return "TRN-" + digest, "TRQ-" + digest
