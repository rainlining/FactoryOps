from __future__ import annotations

import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from factoryops_agent_service.approved_action_resume import (
    ApprovedActionResumeIntegrityError,
    ApprovedActionResumeRejected,
    ApprovedActionResumeService,
    BusinessActionUnavailable,
    ResumeOutcome,
)
from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.human_approval import HumanApprovalService
from factoryops_agent_service.run_lifecycle.model import (
    ActorKind,
    OperationOutcome,
    RunStatus,
    TransitionCommand,
)
from factoryops_agent_service.run_lifecycle.service import AgentRunLifecycleService
from sqlalchemy import Engine, create_engine, text
from test_human_approval_mysql import _approved, _facts
from testcontainers.community.mysql import MySqlContainer


@pytest.fixture(scope="module")
def mysql_engine() -> Engine:
    with MySqlContainer("mysql:8.4") as mysql:
        engine = create_engine(
            mysql.get_connection_url().replace("mysql://", "mysql+pymysql://", 1)
        )
        migrate(engine)
        yield engine
        engine.dispose()


class RecordingBusinessClient:
    def __init__(self, approval: dict[str, object]) -> None:
        identity = approval["identity"]
        self.receipt = {
            "approval_key": identity["approval_key"],
            "action": approval["request"]["proposed_action"],
            "incident_id": identity["incident_id"],
            "batch_id": "BATCH-DEMO",
            "status": "EXECUTED",
            "executed_at": "2026-08-21T02:00:00Z",
            "replayed": False,
        }
        self.calls = 0
        self._lock = threading.Lock()

    def execute(self, approval_key: str):
        with self._lock:
            replayed = self.calls > 0
            self.calls += 1
        return {**self.receipt, "replayed": replayed}


def _terminal(engine: Engine, marker: str):
    pending = _facts(engine, marker, "1.1.0")
    HumanApprovalService(engine).save(pending)
    return _approved(pending)


def test_approved_receipt_resumes_waiting_run(mysql_engine: Engine):
    terminal = _terminal(mysql_engine, "1")
    client = RecordingBusinessClient(terminal)
    result = ApprovedActionResumeService(mysql_engine, client).resume(terminal)
    assert result.outcome is ResumeOutcome.APPLIED
    assert result.receipt["batch_id"] == "BATCH-DEMO"
    with mysql_engine.connect() as connection:
        assert connection.execute(
            text("SELECT status,revision FROM agent_runs WHERE run_id=:run"),
            {"run": terminal["identity"]["run_id"]},
        ).one() == ("RUNNING", 3)
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM agent_run_transitions "
                    "WHERE run_id=:run AND reason_code='APPROVED_ACTION_EXECUTED'"
                ),
                {"run": terminal["identity"]["run_id"]},
            )
            == 1
        )
    assert (
        HumanApprovalService(mysql_engine).get_by_key(
            str(terminal["identity"]["approval_key"])
        )["state"]["status"]
        == "APPROVED"
    )


def test_identical_resume_replays_business_and_transition(mysql_engine: Engine):
    terminal = _terminal(mysql_engine, "2")
    client = RecordingBusinessClient(terminal)
    service = ApprovedActionResumeService(mysql_engine, client)
    assert service.resume(terminal).outcome is ResumeOutcome.APPLIED
    replay = service.resume(terminal)
    assert replay.outcome is ResumeOutcome.DUPLICATE_IDENTICAL
    assert replay.receipt["replayed"] is True
    assert client.calls == 2
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM agent_run_transitions "
                    "WHERE run_id=:run AND reason_code='APPROVED_ACTION_EXECUTED'"
                ),
                {"run": terminal["identity"]["run_id"]},
            )
            == 1
        )


def test_receipt_mismatch_keeps_run_waiting(mysql_engine: Engine):
    terminal = _terminal(mysql_engine, "3")
    client = RecordingBusinessClient(terminal)
    client.receipt["incident_id"] = "QI-" + "F" * 64
    with pytest.raises(ApprovedActionResumeRejected, match="receipt"):
        ApprovedActionResumeService(mysql_engine, client).resume(terminal)
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT status FROM agent_runs WHERE run_id=:run"),
                {"run": terminal["identity"]["run_id"]},
            )
            == "WAITING_FOR_APPROVAL"
        )


def test_business_failure_keeps_terminal_approval_and_wait(mysql_engine: Engine):
    terminal = _terminal(mysql_engine, "4")

    class FailedClient:
        def execute(self, approval_key: str):
            raise BusinessActionUnavailable("timeout")

    with pytest.raises(BusinessActionUnavailable):
        ApprovedActionResumeService(mysql_engine, FailedClient()).resume(terminal)
    assert (
        HumanApprovalService(mysql_engine).get_by_key(
            str(terminal["identity"]["approval_key"])
        )["state"]["status"]
        == "APPROVED"
    )
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT status FROM agent_runs WHERE run_id=:run"),
                {"run": terminal["identity"]["run_id"]},
            )
            == "WAITING_FOR_APPROVAL"
        )


def test_java_success_then_resume_failure_is_recoverable(mysql_engine: Engine):
    terminal = _terminal(mysql_engine, "5")
    client = RecordingBusinessClient(terminal)

    def fail_after_business():
        raise RuntimeError("injected resume failure")

    with pytest.raises(ApprovedActionResumeIntegrityError, match="transaction"):
        ApprovedActionResumeService(
            mysql_engine, client, after_business_hook=fail_after_business
        ).resume(terminal)
    recovered = ApprovedActionResumeService(mysql_engine, client).resume(terminal)
    assert recovered.outcome is ResumeOutcome.APPLIED
    assert recovered.receipt["replayed"] is True
    assert client.calls == 2


def test_concurrent_identical_resume_has_one_run_transition(mysql_engine: Engine):
    terminal = _terminal(mysql_engine, "6")
    client = RecordingBusinessClient(terminal)
    service = ApprovedActionResumeService(mysql_engine, client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.resume, (terminal, copy.deepcopy(terminal))))
    assert {result.outcome for result in results} == {
        ResumeOutcome.APPLIED,
        ResumeOutcome.DUPLICATE_IDENTICAL,
    }
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM agent_run_transitions "
                    "WHERE run_id=:run AND reason_code='APPROVED_ACTION_EXECUTED'"
                ),
                {"run": terminal["identity"]["run_id"]},
            )
            == 1
        )


def test_business_call_holds_run_fence_until_resume_commit(mysql_engine: Engine):
    terminal = _terminal(mysql_engine, "a")
    entered = threading.Event()
    release = threading.Event()

    class PausingClient(RecordingBusinessClient):
        def execute(self, approval_key: str):
            entered.set()
            assert release.wait(5)
            return super().execute(approval_key)

    client = PausingClient(terminal)
    with ThreadPoolExecutor(max_workers=2) as pool:
        resume = pool.submit(
            ApprovedActionResumeService(mysql_engine, client).resume, terminal
        )
        assert entered.wait(5)
        cancel = pool.submit(
            AgentRunLifecycleService(mysql_engine).transition_run,
            TransitionCommand(
                transition_request_id="TRQ-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA1",
                run_id=str(terminal["identity"]["run_id"]),
                expected_status=RunStatus.WAITING_FOR_APPROVAL,
                expected_revision=2,
                to_status=RunStatus.CANCELLED,
                actor_kind=ActorKind.OPERATOR,
                actor_id="concurrent-operator",
                reason_code="OPERATOR_CANCELLED",
            ),
        )
        assert not cancel.done()
        release.set()
        assert resume.result().outcome is ResumeOutcome.APPLIED
        assert cancel.result().outcome is OperationOutcome.CONCURRENCY_CONFLICT


def test_business_call_fences_approval_history_until_resume_commit(
    mysql_engine: Engine,
):
    terminal = _terminal(mysql_engine, "d")
    entered = threading.Event()
    release = threading.Event()

    class PausingClient(RecordingBusinessClient):
        def execute(self, approval_key: str):
            entered.set()
            assert release.wait(5)
            return super().execute(approval_key)

    def corrupt_history():
        with mysql_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE human_approval_history SET canonical_sha256='late-corruption' "
                    "WHERE approval_id=:id AND revision=1"
                ),
                {"id": terminal["identity"]["approval_id"]},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        resume = pool.submit(
            ApprovedActionResumeService(mysql_engine, PausingClient(terminal)).resume,
            terminal,
        )
        assert entered.wait(5)
        corruption = pool.submit(corrupt_history)
        assert not corruption.done()
        release.set()
        assert resume.result().outcome is ResumeOutcome.APPLIED
        corruption.result()


def test_rejects_non_approved_or_malformed_receipt(mysql_engine: Engine):
    terminal = _terminal(mysql_engine, "7")
    rejected = copy.deepcopy(terminal)
    rejected["state"]["status"] = "REJECTED"
    rejected["state"]["outcome"]["reason_code"] = "OWNER_REJECTED"
    client = RecordingBusinessClient(terminal)
    with pytest.raises(ApprovedActionResumeRejected, match="APPROVED"):
        ApprovedActionResumeService(mysql_engine, client).resume(rejected)
    assert client.calls == 0
    assert (
        HumanApprovalService(mysql_engine).get_by_key(
            str(terminal["identity"]["approval_key"])
        )["state"]["status"]
        == "PENDING"
    )

    terminal2 = _terminal(mysql_engine, "8")
    client2 = RecordingBusinessClient(terminal2)
    client2.receipt["executed_at"] = "not-a-time"
    with pytest.raises(ApprovedActionResumeRejected, match="receipt"):
        ApprovedActionResumeService(mysql_engine, client2).resume(terminal2)


def test_corrupt_approval_before_business_call_fails_closed(mysql_engine: Engine):
    terminal = _terminal(mysql_engine, "b")
    client = RecordingBusinessClient(terminal)
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE human_approval_history SET canonical_sha256='broken' "
                "WHERE approval_id=:id AND revision=1"
            ),
            {"id": terminal["identity"]["approval_id"]},
        )
    with pytest.raises(ApprovedActionResumeIntegrityError):
        ApprovedActionResumeService(mysql_engine, client).resume(terminal)
    assert client.calls == 0


def test_existing_resume_requires_replayed_business_receipt(mysql_engine: Engine):
    terminal = _terminal(mysql_engine, "c")
    first = RecordingBusinessClient(terminal)
    assert (
        ApprovedActionResumeService(mysql_engine, first).resume(terminal).outcome
        is ResumeOutcome.APPLIED
    )
    lost_receipt = RecordingBusinessClient(terminal)
    with pytest.raises(ApprovedActionResumeIntegrityError, match="replay"):
        ApprovedActionResumeService(mysql_engine, lost_receipt).resume(terminal)


def test_receipt_time_is_parseable(mysql_engine: Engine):
    terminal = _terminal(mysql_engine, "9")
    result = ApprovedActionResumeService(
        mysql_engine, RecordingBusinessClient(terminal)
    ).resume(terminal)
    assert datetime.fromisoformat(
        str(result.receipt["executed_at"]).replace("Z", "+00:00")
    )
