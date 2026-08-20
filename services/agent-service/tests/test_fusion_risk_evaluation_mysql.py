from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from factoryops_agent_service.coordinator_fusion import (
    CoordinatorFusionService,
    FusionPersistenceIntegrityError,
)
from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.fusion_risk_evaluation import (
    FusionRiskEvaluationCommand,
    FusionRiskEvaluationRejected,
    FusionRiskEvaluationService,
    evaluate_fusion_policy,
)
from factoryops_agent_service.risk_decision import (
    RiskDecisionSaveOutcome,
    RiskDecisionService,
)
from sqlalchemy import Engine, create_engine, text
from test_coordinator_fusion_mysql import _fusion, _parents
from testcontainers.community.mysql import MySqlContainer

GENERATED_AT = "2026-08-20T08:00:00Z"


@pytest.fixture(scope="module")
def mysql_engine() -> Engine:
    with MySqlContainer("mysql:8.4") as mysql:
        engine = create_engine(
            mysql.get_connection_url().replace("mysql://", "mysql+pymysql://", 1)
        )
        migrate(engine)
        yield engine
        engine.dispose()


@pytest.mark.parametrize(
    ("action", "conflict", "decision", "risk"),
    (
        ("PASS", False, "ALLOW", "LOW"),
        ("RECHECK", True, "ALLOW", "LOW"),
        ("REJECT_ITEM", False, "ALLOW", "MEDIUM"),
        ("HOLD_BATCH", True, "REQUIRE_APPROVAL", "MEDIUM"),
        ("STOP_LINE", False, "REQUIRE_APPROVAL", "HIGH"),
        ("ESCALATE", True, "ALLOW", "LOW"),
    ),
)
def test_policy_matrix(action: str, conflict: bool, decision: str, risk: str):
    fusion = {
        "fusion": {
            "proposed_action": action,
            "has_conflict": conflict,
            "candidates": [{"action": action, "rank": 1, "score": 0.75}],
        }
    }

    gate = evaluate_fusion_policy(fusion)

    assert gate["decision"] == decision
    assert gate["risk_level"] == risk
    assert gate["approval_required"] is (decision == "REQUIRE_APPROVAL")
    assert gate["confidence"] == 0.75


def test_evaluate_persists_medium_conflict_and_replays(mysql_engine: Engine):
    run_id, coordinator_id, sources = _parents(mysql_engine, "4")
    fusion = _fusion(run_id, coordinator_id, sources, "4")
    CoordinatorFusionService(mysql_engine).save(fusion)
    command = FusionRiskEvaluationCommand(
        fusion_key=str(fusion["identity"]["fusion_key"]), generated_at=GENERATED_AT
    )
    service = FusionRiskEvaluationService(mysql_engine)

    first = service.evaluate(command)
    replay = service.evaluate(command)
    conflicting = service.evaluate(
        FusionRiskEvaluationCommand(
            fusion_key=command.fusion_key, generated_at="2026-08-20T08:00:01Z"
        )
    )

    assert first.outcome is RiskDecisionSaveOutcome.APPLIED
    assert replay.outcome is RiskDecisionSaveOutcome.DUPLICATE_IDENTICAL
    assert conflicting.outcome is RiskDecisionSaveOutcome.DUPLICATE_CONFLICTING
    assert first.decision["identity"]["subject_type"] == "FUSION"
    assert first.decision["gate"]["decision"] == "REQUIRE_APPROVAL"
    with mysql_engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM risk_decisions")) == 1
        assert (
            connection.scalar(
                text(
                    "SELECT status FROM agent_executions "
                    "WHERE execution_id=:execution_id"
                ),
                {"execution_id": coordinator_id},
            )
            == "RUNNING"
        )


def test_concurrent_identical_evaluation_keeps_one_decision(mysql_engine: Engine):
    run_id, coordinator_id, sources = _parents(mysql_engine, "5")
    fusion = _fusion(run_id, coordinator_id, sources, "5")
    CoordinatorFusionService(mysql_engine).save(fusion)
    command = FusionRiskEvaluationCommand(
        fusion_key=str(fusion["identity"]["fusion_key"]), generated_at=GENERATED_AT
    )
    service = FusionRiskEvaluationService(mysql_engine)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.evaluate, (command, command)))

    assert {result.outcome for result in results} == {
        RiskDecisionSaveOutcome.APPLIED,
        RiskDecisionSaveOutcome.DUPLICATE_IDENTICAL,
    }


def test_missing_or_corrupt_fusion_is_rejected_without_decision(mysql_engine: Engine):
    service = FusionRiskEvaluationService(mysql_engine)
    with mysql_engine.connect() as connection:
        before = connection.scalar(text("SELECT COUNT(*) FROM risk_decisions"))
    with pytest.raises(FusionRiskEvaluationRejected, match="does not exist"):
        service.evaluate(
            FusionRiskEvaluationCommand(
                fusion_key="FUK-" + "0" * 64, generated_at=GENERATED_AT
            )
        )

    run_id, coordinator_id, sources = _parents(mysql_engine, "6")
    fusion = _fusion(run_id, coordinator_id, sources, "6")
    CoordinatorFusionService(mysql_engine).save(fusion)
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE coordinator_fusions SET canonical_sha256=:hash "
                "WHERE fusion_id=:fusion_id"
            ),
            {"hash": "0" * 64, "fusion_id": fusion["identity"]["fusion_id"]},
        )
    with pytest.raises(FusionPersistenceIntegrityError, match="hash"):
        service.evaluate(
            FusionRiskEvaluationCommand(
                fusion_key=str(fusion["identity"]["fusion_key"]),
                generated_at=GENERATED_AT,
            )
        )
    with mysql_engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM risk_decisions")) == before


def test_save_locks_complete_fusion_provenance_until_decision_commits(
    mysql_engine: Engine, monkeypatch: pytest.MonkeyPatch
):
    run_id, coordinator_id, sources = _parents(mysql_engine, "7")
    fusion = _fusion(run_id, coordinator_id, sources, "7")
    CoordinatorFusionService(mysql_engine).save(fusion)
    command = FusionRiskEvaluationCommand(
        fusion_key=str(fusion["identity"]["fusion_key"]), generated_at=GENERATED_AT
    )
    source_id = sources[0]["identity"]["recommendation_id"]
    validated = threading.Event()
    mutation_started = threading.Event()
    release_save = threading.Event()
    commit_order: list[str] = []
    original = RiskDecisionService._decode_fusion

    def pause_after_locked_validation(
        service: RiskDecisionService, connection, row, *, for_update: bool = False
    ):
        payload = original(service, connection, row, for_update=for_update)
        if for_update:
            validated.set()
            assert release_save.wait(5)
        return payload

    monkeypatch.setattr(
        RiskDecisionService, "_decode_fusion", pause_after_locked_validation
    )

    def evaluate():
        result = FusionRiskEvaluationService(mysql_engine).evaluate(command)
        commit_order.append("decision")
        return result

    def corrupt_source():
        with mysql_engine.begin() as connection:
            mutation_started.set()
            connection.execute(
                text(
                    "UPDATE specialist_recommendations SET canonical_sha256=:hash "
                    "WHERE recommendation_id=:recommendation_id"
                ),
                {"hash": "0" * 64, "recommendation_id": source_id},
            )
        commit_order.append("corruption")

    with ThreadPoolExecutor(max_workers=2) as pool:
        decision_future = pool.submit(evaluate)
        assert validated.wait(5)
        mutation_future = pool.submit(corrupt_source)
        assert mutation_started.wait(5)
        time.sleep(0.25)
        assert not mutation_future.done()
        release_save.set()
        assert decision_future.result().outcome is RiskDecisionSaveOutcome.APPLIED
        mutation_future.result()

    assert commit_order == ["decision", "corruption"]
