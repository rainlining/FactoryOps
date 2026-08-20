from __future__ import annotations

import copy
import hashlib
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
    HumanApprovalSaveOutcome,
    HumanApprovalService,
)
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


def _facts(engine: Engine, marker: str):
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
        "contract_version": "1.0.0",
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
    return approval


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
