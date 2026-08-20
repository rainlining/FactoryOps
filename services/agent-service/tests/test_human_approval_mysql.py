from __future__ import annotations

import copy
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from factoryops_agent_service.coordinator_fusion import CoordinatorFusionService
from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.fusion_risk_evaluation import (
    FusionRiskEvaluationCommand,
    FusionRiskEvaluationService,
)
from factoryops_agent_service.human_approval import (
    HumanApprovalPersistenceIntegrityError,
    HumanApprovalPersistenceRejected,
    HumanApprovalSaveOutcome,
    HumanApprovalService,
)
from factoryops_agent_service.risk_decision import (
    RiskDecisionSaveOutcome,
    RiskDecisionService,
)
from factoryops_agent_service.run_lifecycle.model import (
    ActorKind,
    RunStatus,
    TransitionCommand,
)
from factoryops_agent_service.run_lifecycle.service import AgentRunLifecycleService
from sqlalchemy import Engine, create_engine, text
from test_coordinator_fusion_mysql import _fusion, _parents
from testcontainers.community.mysql import MySqlContainer

from contracts.human_approval.validator import (
    canonicalize_human_approval,
    compute_approval_id,
    compute_approval_key,
)


@pytest.fixture(scope="module")
def mysql_engine() -> Engine:
    with MySqlContainer("mysql:8.4") as mysql:
        engine = create_engine(
            mysql.get_connection_url().replace("mysql://", "mysql+pymysql://", 1)
        )
        migrate(engine)
        yield engine
        engine.dispose()


def _facts(engine: Engine, marker: str, version: str = "1.0.0"):
    run_id, coordinator_id, sources = _parents(engine, marker)
    fusion = _fusion(run_id, coordinator_id, sources, marker)
    CoordinatorFusionService(engine).save(fusion)
    risk = (
        FusionRiskEvaluationService(engine)
        .evaluate(
            FusionRiskEvaluationCommand(
                str(fusion["identity"]["fusion_key"]), "2026-08-20T08:00:00Z"
            )
        )
        .decision
    )
    decision_key = str(risk["identity"]["decision_key"])
    requested = datetime(2026, 8, 20, 9, tzinfo=timezone.utc)
    approval = {
        "contract_version": version,
        "identity": {
            "approval_id": compute_approval_id(decision_key),
            "approval_key": compute_approval_key(decision_key),
            **{
                field: risk["identity"][field]
                for field in (
                    "decision_id",
                    "decision_key",
                    "fusion_id",
                    "fusion_key",
                    "run_id",
                    "coordinator_execution_id",
                    "round",
                )
            },
        },
        "request": {
            **{
                field: risk["gate"][field]
                for field in (
                    "proposed_action",
                    "risk_level",
                    "policy_refs",
                    "reason_codes",
                )
            },
            "requested_at": requested.isoformat().replace("+00:00", "Z"),
            "expires_at": (requested + timedelta(hours=1))
            .isoformat()
            .replace("+00:00", "Z"),
        },
        "state": {"revision": 1, "status": "PENDING"},
    }
    if version == "1.1.0":
        with engine.connect() as connection:
            approval["identity"]["incident_id"] = connection.scalar(
                text("SELECT incident_id FROM agent_runs WHERE run_id=:run"),
                {"run": run_id},
            )
    return approval


def test_v11_persists_incident_binding(mysql_engine: Engine):
    pending = _facts(mysql_engine, "8", "1.1.0")
    service = HumanApprovalService(mysql_engine)
    assert service.save(pending).outcome is HumanApprovalSaveOutcome.APPLIED
    assert service.get_by_key(str(pending["identity"]["approval_key"])) == pending
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT incident_id FROM human_approvals WHERE approval_id=:id"),
                {"id": pending["identity"]["approval_id"]},
            )
            == pending["identity"]["incident_id"]
        )


def test_pending_approval_atomically_pauses_source_run(mysql_engine: Engine):
    pending = _facts(mysql_engine, "c", "1.1.0")
    service = HumanApprovalService(mysql_engine)
    result = service.save(pending)
    assert result.outcome is HumanApprovalSaveOutcome.APPLIED
    request_id = (
        "TRQ-"
        + hashlib.sha256(
            ("approval-wait-v1\n" + str(pending["identity"]["approval_id"])).encode()
        )
        .hexdigest()
        .upper()[:32]
    )
    with mysql_engine.connect() as connection:
        run = (
            connection.execute(
                text("SELECT status,revision FROM agent_runs WHERE run_id=:run"),
                {"run": pending["identity"]["run_id"]},
            )
            .mappings()
            .one()
        )
        transition = (
            connection.execute(
                text(
                    "SELECT * FROM agent_run_transitions WHERE transition_request_id=:request"
                ),
                {"request": request_id},
            )
            .mappings()
            .one()
        )
        assert (run["status"], run["revision"]) == ("WAITING_FOR_APPROVAL", 2)
        assert transition["from_status"] == "RUNNING"
        assert transition["to_status"] == "WAITING_FOR_APPROVAL"
        assert transition["reason_code"] == "HUMAN_APPROVAL_REQUIRED"
        assert transition["reason_message"] == pending["identity"]["approval_key"]
    AgentRunLifecycleService(mysql_engine).transition_run(
        TransitionCommand(
            transition_request_id="TRQ-CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
            run_id=str(pending["identity"]["run_id"]),
            expected_status=RunStatus.WAITING_FOR_APPROVAL,
            expected_revision=2,
            to_status=RunStatus.RUNNING,
            actor_kind=ActorKind.COORDINATOR,
            actor_id="approval-resume-test",
            reason_code="APPROVAL_RESOLVED",
        )
    )
    assert service.get_by_key(str(pending["identity"]["approval_key"])) == pending


def test_pending_approval_replay_requires_intact_wait_transition(mysql_engine: Engine):
    pending = _facts(mysql_engine, "f", "1.1.0")
    service = HumanApprovalService(mysql_engine)
    assert service.save(pending).outcome is HumanApprovalSaveOutcome.APPLIED
    assert service.save(pending).outcome is HumanApprovalSaveOutcome.DUPLICATE_IDENTICAL
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE agent_runs SET status_reason_code='CORRUPT_REASON' "
                "WHERE run_id=:run"
            ),
            {"run": pending["identity"]["run_id"]},
        )
    with pytest.raises(HumanApprovalPersistenceIntegrityError, match="wait transition"):
        service.get_by_key(str(pending["identity"]["approval_key"]))
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE agent_runs SET status_reason_code='HUMAN_APPROVAL_REQUIRED' "
                "WHERE run_id=:run"
            ),
            {"run": pending["identity"]["run_id"]},
        )
        connection.execute(
            text(
                "UPDATE agent_run_transitions SET reason_message='corrupt' "
                "WHERE run_id=:run AND reason_code='HUMAN_APPROVAL_REQUIRED'"
            ),
            {"run": pending["identity"]["run_id"]},
        )
    with pytest.raises(HumanApprovalPersistenceIntegrityError, match="wait transition"):
        service.get_by_key(str(pending["identity"]["approval_key"]))


def test_wait_transition_failure_rolls_back_approval_and_run(mysql_engine: Engine):
    pending = _facts(mysql_engine, "0", "1.1.0")
    transition_id = (
        "TRN-"
        + hashlib.sha256(
            ("approval-wait-v1\n" + str(pending["identity"]["approval_id"])).encode()
        )
        .hexdigest()
        .upper()[:32]
    )
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE agent_run_transitions ADD CONSTRAINT "
                f"chk_injected_wait_failure CHECK (transition_id<>'{transition_id}')"
            )
        )
    try:
        with pytest.raises(HumanApprovalPersistenceIntegrityError):
            HumanApprovalService(mysql_engine).save(pending)
    finally:
        with mysql_engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE agent_run_transitions DROP CHECK chk_injected_wait_failure"
                )
            )
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM human_approvals WHERE approval_id=:id"),
                {"id": pending["identity"]["approval_id"]},
            )
            == 0
        )
        assert connection.execute(
            text("SELECT status,revision FROM agent_runs WHERE run_id=:run"),
            {"run": pending["identity"]["run_id"]},
        ).one() == ("RUNNING", 1)


def test_v11_rejects_wrong_run_incident_without_rows(mysql_engine: Engine):
    pending = _facts(mysql_engine, "9", "1.1.0")
    valid = copy.deepcopy(pending)
    pending["identity"]["incident_id"] = "QI-" + "F" * 64
    with pytest.raises(ValueError, match="incident"):
        HumanApprovalService(mysql_engine).save(pending)
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM human_approvals WHERE approval_id=:id"),
                {"id": pending["identity"]["approval_id"]},
            )
            == 0
        )
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE agent_runs SET status='SUSPENDED',"
                "latest_checkpoint_id='CHK-99999999999999999999999999999999' "
                "WHERE run_id=:run"
            ),
            {"run": valid["identity"]["run_id"]},
        )
    with pytest.raises(HumanApprovalPersistenceRejected, match="RUNNING"):
        HumanApprovalService(mysql_engine).save(valid)


def test_v11_rejects_typed_incident_corruption(mysql_engine: Engine):
    pending = _facts(mysql_engine, "a", "1.1.0")
    service = HumanApprovalService(mysql_engine)
    service.save(pending)
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE human_approvals SET incident_id=:incident WHERE approval_id=:id"
            ),
            {"incident": "QI-" + "F" * 64, "id": pending["identity"]["approval_id"]},
        )
    with pytest.raises(HumanApprovalPersistenceIntegrityError):
        service.get_by_key(str(pending["identity"]["approval_key"]))


def test_v11_run_incident_update_waits_for_approval_commit(
    mysql_engine: Engine, monkeypatch: pytest.MonkeyPatch
):
    pending = _facts(mysql_engine, "b", "1.1.0")
    service = HumanApprovalService(mysql_engine)
    run_locked = threading.Event()
    release_approval = threading.Event()
    update_started = threading.Event()
    original = HumanApprovalService._read_source_run

    def pause_after_run_lock(instance, connection, run_id, *, for_update=False):
        source = original(instance, connection, run_id, for_update=for_update)
        if for_update and not run_locked.is_set():
            run_locked.set()
            assert release_approval.wait(5)
        return source

    monkeypatch.setattr(HumanApprovalService, "_read_source_run", pause_after_run_lock)

    def drift_incident():
        update_started.set()
        with mysql_engine.begin() as connection:
            connection.execute(
                text("UPDATE agent_runs SET incident_id=:incident WHERE run_id=:run"),
                {"incident": "QI-" + "F" * 64, "run": pending["identity"]["run_id"]},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        approval_future = pool.submit(service.save, pending)
        assert run_locked.wait(5)
        drift_future = pool.submit(drift_incident)
        assert update_started.wait(5)
        assert not drift_future.done()
        release_approval.set()
        assert approval_future.result().outcome is HumanApprovalSaveOutcome.APPLIED
        drift_future.result()

    with pytest.raises(HumanApprovalPersistenceIntegrityError):
        service.get_by_key(str(pending["identity"]["approval_key"]))
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM human_approval_history WHERE approval_id=:id"
                ),
                {"id": pending["identity"]["approval_id"]},
            )
            == 1
        )


def _approved(pending):
    terminal = copy.deepcopy(pending)
    terminal["state"] = {
        "revision": 2,
        "status": "APPROVED",
        "outcome": {
            "actor_type": "HUMAN",
            "actor_id": "user:owner",
            "decided_at": "2026-08-20T09:30:00Z",
            "reason_code": "OWNER_APPROVED",
        },
    }
    return terminal


def test_pending_and_terminal_preserve_history(mysql_engine: Engine):
    pending = _facts(mysql_engine, "d")
    service = HumanApprovalService(mysql_engine)
    assert service.save(pending).outcome is HumanApprovalSaveOutcome.APPLIED
    assert service.save(pending).outcome is HumanApprovalSaveOutcome.DUPLICATE_IDENTICAL
    terminal = _approved(pending)
    assert service.save(terminal).outcome is HumanApprovalSaveOutcome.APPLIED
    assert service.get_by_key(str(pending["identity"]["approval_key"])) == terminal
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM human_approval_history WHERE approval_id=:id"
                ),
                {"id": pending["identity"]["approval_id"]},
            )
            == 2
        )


def test_conflicting_terminal_does_not_overwrite(mysql_engine: Engine):
    pending = _facts(mysql_engine, "e")
    service = HumanApprovalService(mysql_engine)
    service.save(pending)
    service.save(_approved(pending))
    rejected = _approved(pending)
    rejected["state"]["status"] = "REJECTED"
    assert (
        service.save(rejected).outcome is HumanApprovalSaveOutcome.DUPLICATE_CONFLICTING
    )
    assert (
        service.get_by_key(str(pending["identity"]["approval_key"]))["state"]["status"]
        == "APPROVED"
    )


def test_concurrent_identical_pending_keeps_one_fact(mysql_engine: Engine):
    pending = _facts(mysql_engine, "1")
    service = HumanApprovalService(mysql_engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.save, (pending, pending)))
    assert {result.outcome for result in results} == {
        HumanApprovalSaveOutcome.APPLIED,
        HumanApprovalSaveOutcome.DUPLICATE_IDENTICAL,
    }
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM human_approvals WHERE approval_id=:id"),
                {"id": pending["identity"]["approval_id"]},
            )
            == 1
        )
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM human_approval_history WHERE approval_id=:id"
                ),
                {"id": pending["identity"]["approval_id"]},
            )
            == 1
        )
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM agent_run_transitions "
                    "WHERE run_id=:run AND reason_code='HUMAN_APPROVAL_REQUIRED'"
                ),
                {"run": pending["identity"]["run_id"]},
            )
            == 1
        )
        assert connection.execute(
            text("SELECT status,revision FROM agent_runs WHERE run_id=:run"),
            {"run": pending["identity"]["run_id"]},
        ).one() == ("WAITING_FOR_APPROVAL", 2)


def test_concurrent_opposite_terminal_has_one_winner(mysql_engine: Engine):
    pending = _facts(mysql_engine, "2")
    service = HumanApprovalService(mysql_engine)
    service.save(pending)
    approved = _approved(pending)
    rejected = copy.deepcopy(approved)
    rejected["state"]["status"] = "REJECTED"
    rejected["state"]["outcome"]["reason_code"] = "OWNER_REJECTED"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.save, (approved, rejected)))
    assert {result.outcome for result in results} == {
        HumanApprovalSaveOutcome.APPLIED,
        HumanApprovalSaveOutcome.DUPLICATE_CONFLICTING,
    }
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM human_approval_history WHERE approval_id=:id"
                ),
                {"id": pending["identity"]["approval_id"]},
            )
            == 2
        )


@pytest.mark.parametrize("table", ["human_approvals", "human_approval_history"])
def test_corrupt_current_or_history_is_rejected(mysql_engine: Engine, table: str):
    pending = _facts(mysql_engine, "3" if table == "human_approvals" else "4")
    service = HumanApprovalService(mysql_engine)
    service.save(pending)
    with mysql_engine.begin() as connection:
        connection.execute(
            text(f"UPDATE {table} SET canonical_sha256=:hash WHERE approval_id=:id"),
            {"hash": "0" * 64, "id": pending["identity"]["approval_id"]},
        )
    with pytest.raises(HumanApprovalPersistenceIntegrityError, match="hash|history"):
        service.get_by_key(str(pending["identity"]["approval_key"]))


def test_corrupt_risk_provenance_rejects_without_approval(mysql_engine: Engine):
    pending = _facts(mysql_engine, "5")
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE risk_decisions SET canonical_sha256=:hash WHERE decision_id=:id"
            ),
            {"hash": "0" * 64, "id": pending["identity"]["decision_id"]},
        )
    with pytest.raises(HumanApprovalPersistenceIntegrityError, match="Risk Decision"):
        HumanApprovalService(mysql_engine).save(pending)
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM human_approvals WHERE approval_id=:id"),
                {"id": pending["identity"]["approval_id"]},
            )
            == 0
        )


def test_canonical_but_rebound_history_is_rejected(mysql_engine: Engine):
    pending = _facts(mysql_engine, "6")
    service = HumanApprovalService(mysql_engine)
    service.save(pending)
    rebound = copy.deepcopy(pending)
    rebound["identity"]["run_id"] = "RUN-" + "F" * 32
    canonical = canonicalize_human_approval(rebound)
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE human_approval_history SET payload_json=:payload,canonical_sha256=:hash "
                "WHERE approval_id=:id AND revision=1"
            ),
            {
                "payload": canonical.decode(),
                "hash": hashlib.sha256(canonical).hexdigest(),
                "id": pending["identity"]["approval_id"],
            },
        )
    with pytest.raises(HumanApprovalPersistenceIntegrityError, match="history"):
        service.get_by_key(str(pending["identity"]["approval_key"]))


def test_risk_replay_and_approval_share_provenance_first_lock_order(
    mysql_engine: Engine, monkeypatch: pytest.MonkeyPatch
):
    pending = _facts(mysql_engine, "7")
    risk_service = RiskDecisionService(mysql_engine)
    risk = risk_service.get_by_key(str(pending["identity"]["decision_key"]))
    assert risk is not None
    locked = threading.Event()
    approval_reached_risk = threading.Event()
    release = threading.Event()
    original = RiskDecisionService._decode_fusion
    original_read = RiskDecisionService._read_row_by_identity

    def pause_first_locked_decode(service, connection, row, *, for_update=False):
        result = original(service, connection, row, for_update=for_update)
        if for_update and not locked.is_set():
            locked.set()
            assert release.wait(5)
        return result

    monkeypatch.setattr(
        RiskDecisionService, "_decode_fusion", pause_first_locked_decode
    )

    def observe_risk_lock(connection, key, decision_id, *, for_update=False):
        result = original_read(connection, key, decision_id, for_update=for_update)
        if threading.current_thread().name == "approval-save" and for_update:
            approval_reached_risk.set()
        return result

    monkeypatch.setattr(
        RiskDecisionService, "_read_row_by_identity", staticmethod(observe_risk_lock)
    )

    def save_approval():
        threading.current_thread().name = "approval-save"
        return HumanApprovalService(mysql_engine).save(pending)

    with ThreadPoolExecutor(max_workers=2) as pool:
        risk_future = pool.submit(risk_service.save, risk)
        assert locked.wait(5)
        approval_future = pool.submit(save_approval)
        assert not approval_reached_risk.wait(0.5)
        release.set()
        assert (
            risk_future.result().outcome is RiskDecisionSaveOutcome.DUPLICATE_IDENTICAL
        )
        assert approval_future.result().outcome is HumanApprovalSaveOutcome.APPLIED


def test_migration_recovers_current_only_partial_state(mysql_engine: Engine):
    with mysql_engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE human_approval_history")
        connection.execute(
            text(
                "DELETE FROM agent_schema_history WHERE version='014_create_human_approvals'"
            )
        )
    migrate(mysql_engine)
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() "
                    "AND table_name IN ('human_approvals','human_approval_history')"
                )
            )
            == 2
        )


def test_migration_015_recovers_after_ddl_without_history(mysql_engine: Engine):
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                "DELETE FROM agent_schema_history "
                "WHERE version='015_bind_human_approval_incident'"
            )
        )
    migrate(mysql_engine)
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM agent_schema_history "
                    "WHERE version='015_bind_human_approval_incident'"
                )
            )
            == 1
        )
