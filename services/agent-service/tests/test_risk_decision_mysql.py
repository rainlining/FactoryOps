from __future__ import annotations

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from factoryops_agent_service.coordinator_fusion import CoordinatorFusionService
from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.risk_decision import (
    RiskDecisionPersistenceIntegrityError,
    RiskDecisionPersistenceRejected,
    RiskDecisionSaveOutcome,
    RiskDecisionService,
)
from factoryops_agent_service.specialist_recommendation import (
    SpecialistRecommendationService,
)
from factoryops_agent_service.worker_task_execution import WorkerTaskExecutionService
from sqlalchemy import Engine, create_engine, text
from test_coordinator_fusion_mysql import _fusion, _parents
from test_specialist_recommendation_mysql import _recommendation
from test_worker_task_completion_mysql import _running, _success
from testcontainers.community.mysql import MySqlContainer

from contracts.risk_decision.validator import compute_decision_key

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "risk_decision"
    / "fixtures"
    / "valid"
    / "stop-line-approval.json"
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


def _parent(engine: Engine, marker: str) -> tuple[str, object, str, dict[str, object]]:
    task_id, lease, execution_id = _running(engine, marker)
    recommendation = _recommendation(engine, task_id, execution_id, marker)
    SpecialistRecommendationService(engine).save(recommendation)
    return task_id, lease, execution_id, recommendation


def _decision(recommendation: dict[str, object], marker: str) -> dict[str, object]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    source = recommendation["identity"]
    identity = payload["identity"]
    assert isinstance(source, dict) and isinstance(identity, dict)
    identity.update(
        decision_id="RSK-" + marker.upper() * 32,
        decision_key=compute_decision_key(str(source["recommendation_key"])),
        recommendation_id=source["recommendation_id"],
        recommendation_key=source["recommendation_key"],
        run_id=source["run_id"],
        task_id=source["task_id"],
    )
    return payload


def _fusion_decision(fusion: dict[str, object], marker: str) -> dict[str, object]:
    payload = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "contracts"
            / "risk_decision"
            / "fixtures"
            / "valid"
            / "fusion-stop-line-approval.json"
        ).read_text(encoding="utf-8")
    )
    source = fusion["identity"]
    identity = payload["identity"]
    assert isinstance(source, dict) and isinstance(identity, dict)
    identity.update(
        decision_id="RSK-" + marker.upper() * 32,
        decision_key=compute_decision_key(str(source["fusion_key"])),
        fusion_id=source["fusion_id"],
        fusion_key=source["fusion_key"],
        run_id=source["run_id"],
        coordinator_execution_id=source["coordinator_execution_id"],
        round=source["round"],
    )
    return payload


def test_save_fusion_subject_persists_and_replays(mysql_engine: Engine):
    run_id, coordinator_id, sources = _parents(mysql_engine, "f")
    fusion = _fusion(run_id, coordinator_id, sources, "f")
    CoordinatorFusionService(mysql_engine).save(fusion)
    payload = _fusion_decision(fusion, "f")
    service = RiskDecisionService(mysql_engine)

    assert service.save(payload).outcome is RiskDecisionSaveOutcome.APPLIED
    assert service.save(payload).outcome is RiskDecisionSaveOutcome.DUPLICATE_IDENTICAL
    assert service.get_by_key(str(payload["identity"]["decision_key"])) == payload
    with mysql_engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    "SELECT subject_type,fusion_id,recommendation_id FROM risk_decisions WHERE decision_key=:key"
                ),
                {"key": payload["identity"]["decision_key"]},
            )
            .mappings()
            .one()
        )
    assert row == {
        "subject_type": "FUSION",
        "fusion_id": fusion["identity"]["fusion_id"],
        "recommendation_id": None,
    }


def test_concurrent_conflicting_fusion_decisions_keep_one_fact(mysql_engine: Engine):
    run_id, coordinator_id, sources = _parents(mysql_engine, "e")
    fusion = _fusion(run_id, coordinator_id, sources, "e")
    CoordinatorFusionService(mysql_engine).save(fusion)
    first = _fusion_decision(fusion, "e")
    second = copy.deepcopy(first)
    second["gate"]["confidence"] = 0.5
    service = RiskDecisionService(mysql_engine)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.save, (first, second)))

    assert {result.outcome for result in results} == {
        RiskDecisionSaveOutcome.APPLIED,
        RiskDecisionSaveOutcome.DUPLICATE_CONFLICTING,
    }


def test_missing_or_corrupt_fusion_source_is_rejected(mysql_engine: Engine):
    run_id, coordinator_id, sources = _parents(mysql_engine, "d")
    fusion = _fusion(run_id, coordinator_id, sources, "d")
    payload = _fusion_decision(fusion, "d")
    with pytest.raises(RiskDecisionPersistenceRejected, match="Fusion"):
        RiskDecisionService(mysql_engine).save(payload)

    CoordinatorFusionService(mysql_engine).save(fusion)
    service = RiskDecisionService(mysql_engine)
    service.save(payload)
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE coordinator_fusions SET canonical_sha256=:hash WHERE fusion_id=:id"
            ),
            {"hash": "0" * 64, "id": fusion["identity"]["fusion_id"]},
        )
    with pytest.raises(RiskDecisionPersistenceIntegrityError, match="Fusion"):
        service.get_by_key(str(payload["identity"]["decision_key"]))


def test_save_persists_fact_without_advancing_parent_state(mysql_engine: Engine):
    task_id, lease, execution_id, recommendation = _parent(mysql_engine, "1")
    payload = _decision(recommendation, "1")
    service = RiskDecisionService(mysql_engine)

    result = service.save(payload)

    assert result.outcome is RiskDecisionSaveOutcome.APPLIED
    assert service.get_by_key(str(payload["identity"]["decision_key"])) == payload
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT status FROM agent_tasks WHERE task_id=:id"),
                {"id": task_id},
            )
            == "RUNNING"
        )
        assert (
            connection.scalar(
                text("SELECT status FROM agent_executions WHERE execution_id=:id"),
                {"id": execution_id},
            )
            == "RUNNING"
        )
        assert (
            connection.scalar(
                text("SELECT lease_token FROM agent_task_leases WHERE task_id=:id"),
                {"id": task_id},
            )
            == lease.lease_token
        )


def test_replay_after_completion_is_stable(mysql_engine: Engine):
    task_id, lease, execution_id, recommendation = _parent(mysql_engine, "2")
    payload = _decision(recommendation, "2")
    service = RiskDecisionService(mysql_engine)
    service.save(payload)
    WorkerTaskExecutionService(mysql_engine).complete(
        _success(task_id, execution_id, lease.owner_id, lease.lease_token, "d")
    )

    assert service.save(payload).outcome is RiskDecisionSaveOutcome.DUPLICATE_IDENTICAL
    changed = copy.deepcopy(payload)
    gate = changed["gate"]
    assert isinstance(gate, dict)
    gate["confidence"] = 0.5
    assert (
        service.save(changed).outcome is RiskDecisionSaveOutcome.DUPLICATE_CONFLICTING
    )


def test_missing_or_mismatched_recommendation_is_rejected(mysql_engine: Engine):
    _, _, _, recommendation = _parent(mysql_engine, "3")
    payload = _decision(recommendation, "3")
    identity = payload["identity"]
    assert isinstance(identity, dict)
    identity["recommendation_key"] = "RCK-" + "F" * 64
    identity["decision_key"] = compute_decision_key(str(identity["recommendation_key"]))

    with pytest.raises(RiskDecisionPersistenceRejected, match="Recommendation"):
        RiskDecisionService(mysql_engine).save(payload)
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM risk_decisions WHERE decision_key=:key"),
                {"key": identity["decision_key"]},
            )
            == 0
        )


def test_concurrent_identical_and_conflicting_save_one_fact(mysql_engine: Engine):
    _, _, _, recommendation = _parent(mysql_engine, "4")
    payload = _decision(recommendation, "4")
    service = RiskDecisionService(mysql_engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.save, (payload, payload)))
    assert {result.outcome for result in results} == {
        RiskDecisionSaveOutcome.APPLIED,
        RiskDecisionSaveOutcome.DUPLICATE_IDENTICAL,
    }

    _, _, _, other_recommendation = _parent(mysql_engine, "5")
    first = _decision(other_recommendation, "5")
    second = copy.deepcopy(first)
    gate = second["gate"]
    assert isinstance(gate, dict)
    gate["confidence"] = 0.4
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.save, (first, second)))
    assert {result.outcome for result in results} == {
        RiskDecisionSaveOutcome.APPLIED,
        RiskDecisionSaveOutcome.DUPLICATE_CONFLICTING,
    }
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT COUNT(*) FROM risk_decisions WHERE recommendation_id=:id"),
                {"id": other_recommendation["identity"]["recommendation_id"]},
            )
            == 1
        )


def test_same_id_for_other_recommendation_is_conflicting(mysql_engine: Engine):
    _, _, _, first_recommendation = _parent(mysql_engine, "6")
    _, _, _, second_recommendation = _parent(mysql_engine, "7")
    first = _decision(first_recommendation, "6")
    second = _decision(second_recommendation, "6")
    service = RiskDecisionService(mysql_engine)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.save, (first, second)))
    assert {result.outcome for result in results} == {
        RiskDecisionSaveOutcome.APPLIED,
        RiskDecisionSaveOutcome.DUPLICATE_CONFLICTING,
    }


def test_same_key_with_different_ids_is_concurrently_conflicting(mysql_engine: Engine):
    _, _, _, recommendation = _parent(mysql_engine, "a")
    first = _decision(recommendation, "a")
    second = copy.deepcopy(first)
    identity = second["identity"]
    assert isinstance(identity, dict)
    identity["decision_id"] = "RSK-" + "B" * 32
    service = RiskDecisionService(mysql_engine)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.save, (first, second)))
    assert {result.outcome for result in results} == {
        RiskDecisionSaveOutcome.APPLIED,
        RiskDecisionSaveOutcome.DUPLICATE_CONFLICTING,
    }


@pytest.mark.parametrize("column", ["canonical_sha256", "risk_level"])
def test_corrupt_storage_is_rejected_on_read(mysql_engine: Engine, column: str):
    marker = "8" if column == "canonical_sha256" else "9"
    _, _, _, recommendation = _parent(mysql_engine, marker)
    payload = _decision(recommendation, marker)
    service = RiskDecisionService(mysql_engine)
    service.save(payload)
    key = payload["identity"]["decision_key"]
    value = "0" * 64 if column == "canonical_sha256" else "LOW"
    statement = (
        "UPDATE risk_decisions SET canonical_sha256=:value WHERE decision_key=:key"
        if column == "canonical_sha256"
        else "UPDATE risk_decisions SET risk_level=:value WHERE decision_key=:key"
    )
    with mysql_engine.begin() as connection:
        connection.execute(
            text(statement),
            {"value": value, "key": key},
        )

    with pytest.raises(RiskDecisionPersistenceIntegrityError):
        service.get_by_key(str(key))


def test_noncanonical_payload_with_matching_hash_is_rejected(mysql_engine: Engine):
    _, _, _, recommendation = _parent(mysql_engine, "c")
    payload = _decision(recommendation, "c")
    service = RiskDecisionService(mysql_engine)
    service.save(payload)
    key = payload["identity"]["decision_key"]
    noncanonical = json.dumps(payload, indent=2)
    import hashlib

    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                """UPDATE risk_decisions
                SET payload_json=:payload,canonical_sha256=:hash
                WHERE decision_key=:key"""
            ),
            {
                "payload": noncanonical,
                "hash": hashlib.sha256(noncanonical.encode()).hexdigest(),
                "key": key,
            },
        )

    with pytest.raises(RiskDecisionPersistenceIntegrityError, match="Contract"):
        service.get_by_key(str(key))
