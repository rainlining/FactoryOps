from __future__ import annotations

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from contracts.coordinator_fusion.validator import (
    canonicalize_coordinator_fusion,
    compute_fusion_key,
)
from contracts.specialist_recommendation.validator import compute_recommendation_key
from sqlalchemy import Engine, create_engine, text
from test_coordinator_start_mysql import _command, _run, _service
from test_coordinator_task_dispatch_mysql import _dispatch
from test_worker_task_execution_mysql import _start_command
from testcontainers.community.mysql import MySqlContainer

from factoryops_agent_service.coordinator_fusion import (
    CoordinatorFusionService,
    FusionPersistenceIntegrityError,
    FusionPersistenceRejected,
    FusionSaveOutcome,
)
from factoryops_agent_service.coordinator_task_dispatch.service import (
    CoordinatorTaskDispatchService,
)
from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.specialist_recommendation import (
    SpecialistRecommendationService,
)
from factoryops_agent_service.task_lease import AgentTaskLeaseService
from factoryops_agent_service.worker_task_execution import WorkerTaskExecutionService

ROOT = Path(__file__).resolve().parents[3] / "contracts"


@pytest.fixture(scope="module")
def mysql_engine() -> Engine:
    with MySqlContainer("mysql:8.4") as mysql:
        engine = create_engine(
            mysql.get_connection_url().replace("mysql://", "mysql+pymysql://", 1)
        )
        migrate(engine)
        yield engine
        engine.dispose()


def _parents(engine: Engine, marker: str) -> tuple[str, str, list[dict[str, object]]]:
    run_id = _run(engine, marker)
    coordinator = _service(engine).start(_command(run_id, marker))
    coordinator_id = str(coordinator.execution["identity"]["execution_id"])
    recommendations = []
    for index, (role, task_type, fixture_name) in enumerate(
        (
            ("quality", "QUALITY_ANALYSIS", "quality.json"),
            ("production", "PRODUCTION_ANALYSIS", "production.json"),
            ("sla", "SLA_ANALYSIS", "sla.json"),
        ),
        1,
    ):
        token = marker
        command = replace(
            _dispatch(run_id, coordinator_id, token),
            task_request_id="TQR-" + (marker + str(index)).upper().ljust(32, "0")[:32],
            context_snapshot_id="CTX-"
            + (marker + str(index)).upper().ljust(32, "0")[:32],
            target_agent_role=role,
            task_type=task_type,
        )
        task = CoordinatorTaskDispatchService(engine).dispatch(command).task
        task_id = str(task["identity"]["task_id"])
        lease = AgentTaskLeaseService(engine).claim(task_id, "worker-" + token, 120)
        start_command = replace(
            _start_command(task_id, lease.owner_id, lease.lease_token, token),
            request_id="WSR-" + (marker + str(index)).upper().ljust(32, "0")[:32],
        )
        execution_id = str(
            WorkerTaskExecutionService(engine).start(start_command).execution_id
        )
        payload = json.loads(
            (
                ROOT / "specialist_recommendation" / "fixtures" / "valid" / fixture_name
            ).read_text(encoding="utf-8")
        )
        identity = payload["identity"]
        identity.update(
            recommendation_id="REC-"
            + (marker + str(index)).upper().ljust(32, "0")[:32],
            recommendation_key=compute_recommendation_key(execution_id),
            execution_id=execution_id,
            run_id=run_id,
            task_id=task_id,
            agent_role=role,
        )
        SpecialistRecommendationService(engine).save(payload)
        recommendations.append(payload)
    return run_id, coordinator_id, recommendations


def _fusion(
    run_id: str, coordinator_id: str, sources: list[dict[str, object]], marker: str
) -> dict[str, object]:
    payload = json.loads(
        (
            ROOT
            / "coordinator_fusion"
            / "fixtures"
            / "valid"
            / "three-specialists.json"
        ).read_text(encoding="utf-8")
    )
    identity = payload["identity"]
    identity.update(
        fusion_id="FUS-" + marker.upper() * 32,
        run_id=run_id,
        coordinator_execution_id=coordinator_id,
        round=1,
        fusion_key=compute_fusion_key(run_id, coordinator_id, 1),
    )
    payload["inputs"]["recommendations"] = [
        {
            "recommendation_id": s["identity"]["recommendation_id"],
            "recommendation_key": s["identity"]["recommendation_key"],
            "execution_id": s["identity"]["execution_id"],
            "task_id": s["identity"]["task_id"],
            "agent_role": s["identity"]["agent_role"],
            "action": s["recommendation"]["action"],
            "severity": s["recommendation"]["severity"],
            "confidence": s["recommendation"]["confidence"],
        }
        for s in sources
    ]
    return payload


def test_save_and_read_without_advancing_execution(mysql_engine: Engine):
    run_id, coordinator_id, sources = _parents(mysql_engine, "a")
    payload = _fusion(run_id, coordinator_id, sources, "a")
    service = CoordinatorFusionService(mysql_engine)
    assert service.save(payload).outcome is FusionSaveOutcome.APPLIED
    assert service.get_by_key(str(payload["identity"]["fusion_key"])) == json.loads(
        canonicalize_coordinator_fusion(payload)
    )
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT status FROM agent_executions WHERE execution_id=:id"),
                {"id": coordinator_id},
            )
            == "RUNNING"
        )
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM coordinator_fusion_recommendations WHERE fusion_id=:id"
                ),
                {"id": payload["identity"]["fusion_id"]},
            )
            == 3
        )


def test_concurrent_identical_and_conflicting_are_stable(mysql_engine: Engine):
    run_id, coordinator_id, sources = _parents(mysql_engine, "b")
    payload = _fusion(run_id, coordinator_id, sources, "b")
    service = CoordinatorFusionService(mysql_engine)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.save, (payload, payload)))
    assert {r.outcome for r in results} == {
        FusionSaveOutcome.APPLIED,
        FusionSaveOutcome.DUPLICATE_IDENTICAL,
    }

    run_id, coordinator_id, sources = _parents(mysql_engine, "f")
    first = _fusion(run_id, coordinator_id, sources, "f")
    second = copy.deepcopy(first)
    second["fusion"]["reason_codes"] = ["MANUAL_REVIEW_SELECTED"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.save, (first, second)))
    assert {r.outcome for r in results} == {
        FusionSaveOutcome.APPLIED,
        FusionSaveOutcome.DUPLICATE_CONFLICTING,
    }


def test_concurrent_identity_splits_are_conflicting(mysql_engine: Engine):
    service = CoordinatorFusionService(mysql_engine)
    run_id, coordinator_id, sources = _parents(mysql_engine, "6")
    first = _fusion(run_id, coordinator_id, sources, "6")
    second = copy.deepcopy(first)
    second["identity"]["fusion_id"] = "FUS-" + "7" * 32
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.save, (first, second)))
    assert {r.outcome for r in results} == {
        FusionSaveOutcome.APPLIED,
        FusionSaveOutcome.DUPLICATE_CONFLICTING,
    }

    run_id, coordinator_id, sources = _parents(mysql_engine, "8")
    first = _fusion(run_id, coordinator_id, sources, "8")
    second = copy.deepcopy(first)
    second["identity"]["round"] = 2
    second["identity"]["fusion_key"] = compute_fusion_key(run_id, coordinator_id, 2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(service.save, (first, second)))
    assert {r.outcome for r in results} == {
        FusionSaveOutcome.APPLIED,
        FusionSaveOutcome.DUPLICATE_CONFLICTING,
    }


def test_missing_source_and_wrong_coordinator_are_rejected(mysql_engine: Engine):
    run_id, coordinator_id, sources = _parents(mysql_engine, "c")
    payload = _fusion(run_id, coordinator_id, sources, "c")
    payload["inputs"]["recommendations"][0]["recommendation_key"] = "RCK-" + "F" * 64
    with pytest.raises(FusionPersistenceRejected, match="Recommendation"):
        CoordinatorFusionService(mysql_engine).save(payload)

    run_id, _, sources = _parents(mysql_engine, "9")
    worker_execution_id = str(sources[0]["identity"]["execution_id"])
    payload = _fusion(run_id, worker_execution_id, sources, "9")
    with pytest.raises(FusionPersistenceRejected, match="Coordinator Execution"):
        CoordinatorFusionService(mysql_engine).save(payload)


def test_read_rejects_coordinator_execution_run_corruption(mysql_engine: Engine):
    run_id, coordinator_id, sources = _parents(mysql_engine, "7")
    payload = _fusion(run_id, coordinator_id, sources, "7")
    service = CoordinatorFusionService(mysql_engine)
    service.save(payload)
    other_run = _run(mysql_engine, "0")
    with mysql_engine.begin() as connection:
        connection.execute(
            text("UPDATE agent_executions SET run_id=:run WHERE execution_id=:id"),
            {"run": other_run, "id": coordinator_id},
        )
    with pytest.raises(FusionPersistenceIntegrityError, match="Coordinator"):
        service.get_by_key(str(payload["identity"]["fusion_key"]))


@pytest.mark.parametrize("column", ["canonical_sha256", "proposed_action"])
def test_corrupt_storage_is_rejected(mysql_engine: Engine, column: str):
    marker = "d" if column == "canonical_sha256" else "e"
    run_id, coordinator_id, sources = _parents(mysql_engine, marker)
    payload = _fusion(run_id, coordinator_id, sources, marker)
    service = CoordinatorFusionService(mysql_engine)
    service.save(payload)
    value = "0" * 64 if column == "canonical_sha256" else "PASS"
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                f"UPDATE coordinator_fusions SET {column}=:value WHERE fusion_key=:key"
            ),
            {"value": value, "key": payload["identity"]["fusion_key"]},
        )
    with pytest.raises(FusionPersistenceIntegrityError):
        service.get_by_key(str(payload["identity"]["fusion_key"]))
