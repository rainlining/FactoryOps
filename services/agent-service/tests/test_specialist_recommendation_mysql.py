from __future__ import annotations

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from contracts.specialist_recommendation.validator import compute_recommendation_key
from sqlalchemy import Engine, create_engine, text
from test_worker_task_completion_mysql import _running, _success
from testcontainers.community.mysql import MySqlContainer

from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.specialist_recommendation import (
    RecommendationPersistenceIntegrityError,
    RecommendationPersistenceRejected,
    RecommendationSaveOutcome,
    SpecialistRecommendationService,
)
from factoryops_agent_service.worker_task_execution import WorkerTaskExecutionService

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "specialist_recommendation"
    / "fixtures"
    / "valid"
    / "quality.json"
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


def _recommendation(
    engine: Engine, task_id: str, execution_id: str, marker: str
) -> dict[str, object]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    with engine.connect() as connection:
        task = (
            connection.execute(
                text(
                    "SELECT run_id,target_agent_role FROM agent_tasks WHERE task_id=:id"
                ),
                {"id": task_id},
            )
            .mappings()
            .one()
        )
    identity = payload["identity"]
    assert isinstance(identity, dict)
    identity.update(
        recommendation_id="REC-" + marker.upper() * 32,
        recommendation_key=compute_recommendation_key(execution_id),
        execution_id=execution_id,
        run_id=task["run_id"],
        task_id=task_id,
        agent_role=task["target_agent_role"],
    )
    return payload


def test_save_persists_canonical_fact_without_advancing_execution(
    mysql_engine: Engine,
):
    task_id, lease, execution_id = _running(mysql_engine, "3")
    payload = _recommendation(mysql_engine, task_id, execution_id, "1")
    service = SpecialistRecommendationService(mysql_engine)

    result = service.save(payload)

    assert result.outcome is RecommendationSaveOutcome.APPLIED
    assert service.get_by_key(payload["identity"]["recommendation_key"]) == payload
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


def test_replay_after_completion_is_identical_and_conflict_is_stable(
    mysql_engine: Engine,
):
    task_id, lease, execution_id = _running(mysql_engine, "4")
    payload = _recommendation(mysql_engine, task_id, execution_id, "2")
    service = SpecialistRecommendationService(mysql_engine)
    service.save(payload)
    WorkerTaskExecutionService(mysql_engine).complete(
        _success(task_id, execution_id, lease.owner_id, lease.lease_token, "a")
    )

    assert (
        service.save(payload).outcome is RecommendationSaveOutcome.DUPLICATE_IDENTICAL
    )
    changed = copy.deepcopy(payload)
    recommendation = changed["recommendation"]
    assert isinstance(recommendation, dict)
    recommendation["confidence"] = 0.5
    assert (
        service.save(changed).outcome is RecommendationSaveOutcome.DUPLICATE_CONFLICTING
    )


def test_parent_mismatch_is_rejected_without_fact(mysql_engine: Engine):
    task_id, _, execution_id = _running(mysql_engine, "5")
    payload = _recommendation(mysql_engine, task_id, execution_id, "3")
    identity = payload["identity"]
    assert isinstance(identity, dict)
    identity["run_id"] = "RUN-" + "F" * 32

    with pytest.raises(RecommendationPersistenceRejected, match="current RUNNING"):
        SpecialistRecommendationService(mysql_engine).save(payload)


def test_concurrent_identical_save_has_one_fact(mysql_engine: Engine):
    task_id, _, execution_id = _running(mysql_engine, "6")
    payload = _recommendation(mysql_engine, task_id, execution_id, "4")
    service = SpecialistRecommendationService(mysql_engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.save, (payload, payload)))

    assert {result.outcome for result in results} == {
        RecommendationSaveOutcome.APPLIED,
        RecommendationSaveOutcome.DUPLICATE_IDENTICAL,
    }
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM specialist_recommendations WHERE task_id=:id"
                ),
                {"id": task_id},
            )
            == 1
        )


def test_same_id_for_other_execution_is_conflicting(mysql_engine: Engine):
    first_task, _, first_execution = _running(mysql_engine, "7")
    second_task, _, second_execution = _running(mysql_engine, "8")
    first = _recommendation(mysql_engine, first_task, first_execution, "5")
    second = _recommendation(mysql_engine, second_task, second_execution, "5")
    service = SpecialistRecommendationService(mysql_engine)

    service.save(first)
    assert (
        service.save(second).outcome is RecommendationSaveOutcome.DUPLICATE_CONFLICTING
    )


def test_concurrent_conflicting_save_has_one_fact(mysql_engine: Engine):
    task_id, _, execution_id = _running(mysql_engine, "b")
    first = _recommendation(mysql_engine, task_id, execution_id, "8")
    second = copy.deepcopy(first)
    recommendation = second["recommendation"]
    assert isinstance(recommendation, dict)
    recommendation["confidence"] = 0.4
    service = SpecialistRecommendationService(mysql_engine)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.save, (first, second)))

    assert {result.outcome for result in results} == {
        RecommendationSaveOutcome.APPLIED,
        RecommendationSaveOutcome.DUPLICATE_CONFLICTING,
    }
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM specialist_recommendations WHERE task_id=:id"
                ),
                {"id": task_id},
            )
            == 1
        )


def test_corrupt_hash_is_rejected_on_read(mysql_engine: Engine):
    task_id, _, execution_id = _running(mysql_engine, "9")
    payload = _recommendation(mysql_engine, task_id, execution_id, "6")
    service = SpecialistRecommendationService(mysql_engine)
    service.save(payload)
    key = payload["identity"]["recommendation_key"]
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE specialist_recommendations SET canonical_sha256=:bad WHERE recommendation_key=:key"
            ),
            {"bad": "0" * 64, "key": key},
        )

    with pytest.raises(RecommendationPersistenceIntegrityError, match="hash"):
        service.get_by_key(str(key))


def test_corrupt_typed_column_is_rejected_on_read(mysql_engine: Engine):
    task_id, _, execution_id = _running(mysql_engine, "a")
    payload = _recommendation(mysql_engine, task_id, execution_id, "7")
    service = SpecialistRecommendationService(mysql_engine)
    service.save(payload)
    key = payload["identity"]["recommendation_key"]
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE specialist_recommendations SET action='PASS' WHERE recommendation_key=:key"
            ),
            {"key": key},
        )

    with pytest.raises(RecommendationPersistenceIntegrityError, match="typed"):
        service.get_by_key(str(key))
