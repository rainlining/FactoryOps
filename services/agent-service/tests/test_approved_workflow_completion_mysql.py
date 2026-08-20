from __future__ import annotations

import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from factoryops_agent_service.approved_workflow_completion import (
    ApprovedWorkflowCompletionIntegrityError,
    ApprovedWorkflowCompletionRejected,
    ApprovedWorkflowCompletionService,
    WorkflowCompletionOutcome,
)
from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.execution_lifecycle.model import (
    ExecutionStatus,
    TransitionCommand,
)
from factoryops_agent_service.execution_lifecycle.service import (
    AgentExecutionLifecycleService,
)
from factoryops_agent_service.worker_task_execution import WorkerTaskExecutionService
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.pool import QueuePool
from test_approved_action_resume_mysql import RecordingBusinessClient, _terminal
from test_worker_task_completion_mysql import _success
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


@pytest.fixture()
def isolated_mysql_engine() -> Engine:
    with MySqlContainer("mysql:8.4") as mysql:
        engine = create_engine(
            mysql.get_connection_url().replace("mysql://", "mysql+pymysql://", 1)
        )
        migrate(engine)
        yield engine
        engine.dispose()


def _complete_specialists(engine: Engine, run_id: str) -> None:
    with engine.connect() as connection:
        rows = (
            connection.execute(
                text(
                    "SELECT t.task_id,t.current_execution_id,l.owner_id,l.lease_token "
                    "FROM agent_tasks t JOIN agent_task_leases l ON l.task_id=t.task_id "
                    "WHERE t.run_id=:run ORDER BY t.task_id"
                ),
                {"run": run_id},
            )
            .mappings()
            .all()
        )
    assert len(rows) == 3
    for index, row in enumerate(rows, 1):
        command = _success(
            str(row["task_id"]),
            str(row["current_execution_id"]),
            str(row["owner_id"]),
            str(row["lease_token"]),
            str(index),
        )
        WorkerTaskExecutionService(engine).complete(
            replace(
                command,
                request_id="WCR-"
                + hashlib.sha256(str(row["task_id"]).encode()).hexdigest().upper()[:32],
            )
        )


def _ready(engine: Engine, marker: str):
    terminal = _terminal(engine, marker)
    _complete_specialists(engine, str(terminal["identity"]["run_id"]))
    return terminal, RecordingBusinessClient(terminal)


def test_completes_coordinator_and_run_atomically(mysql_engine: Engine):
    terminal, client = _ready(mysql_engine, "e")
    result = ApprovedWorkflowCompletionService(mysql_engine, client).complete(terminal)
    assert result.outcome is WorkflowCompletionOutcome.APPLIED
    assert result.run["lifecycle"]["status"] == "SUCCEEDED"
    assert result.coordinator_execution["lifecycle"]["status"] == "SUCCEEDED"
    assert result.coordinator_execution["result"] == {
        "output_artifact_refs": ["fusion:" + terminal["identity"]["fusion_key"]],
        "decision_id": None,
        "evidence_refs": [
            "approval:" + terminal["identity"]["approval_key"],
            "risk:" + terminal["identity"]["decision_key"],
        ],
    }
    with mysql_engine.connect() as connection:
        assert connection.execute(
            text(
                "SELECT status FROM agent_runs WHERE run_id=:run UNION ALL "
                "SELECT status FROM agent_executions WHERE execution_id=:execution"
            ),
            {
                "run": terminal["identity"]["run_id"],
                "execution": terminal["identity"]["coordinator_execution_id"],
            },
        ).scalars().all() == ["SUCCEEDED", "SUCCEEDED"]
        assert connection.execute(
            text(
                "SELECT task_count,completed_task_count,agent_execution_count "
                "FROM agent_runs WHERE run_id=:run"
            ),
            {"run": terminal["identity"]["run_id"]},
        ).one() == (3, 3, 4)


def test_identical_replay_has_one_completion_fact_per_aggregate(mysql_engine: Engine):
    terminal, client = _ready(mysql_engine, "a")
    service = ApprovedWorkflowCompletionService(mysql_engine, client)
    assert service.complete(terminal).outcome is WorkflowCompletionOutcome.APPLIED
    assert (
        service.complete(terminal).outcome
        is WorkflowCompletionOutcome.DUPLICATE_IDENTICAL
    )
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM agent_run_transitions "
                    "WHERE run_id=:run AND reason_code='APPROVED_WORKFLOW_COMPLETED'"
                ),
                {"run": terminal["identity"]["run_id"]},
            )
            == 1
        )
        assert (
            connection.scalar(
                text(
                    "SELECT COUNT(*) FROM agent_execution_transitions "
                    "WHERE execution_id=:execution "
                    "AND reason_code='APPROVED_WORKFLOW_COMPLETED'"
                ),
                {"execution": terminal["identity"]["coordinator_execution_id"]},
            )
            == 1
        )


def test_incomplete_specialists_leave_workflow_running(mysql_engine: Engine):
    terminal = _terminal(mysql_engine, "b")
    client = RecordingBusinessClient(terminal)
    with pytest.raises(ApprovedWorkflowCompletionRejected, match="Task"):
        ApprovedWorkflowCompletionService(mysql_engine, client).complete(terminal)
    assert client.calls == 0
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT status FROM agent_runs WHERE run_id=:run"),
                {"run": terminal["identity"]["run_id"]},
            )
            == "WAITING_FOR_APPROVAL"
        )
        assert (
            connection.scalar(
                text(
                    "SELECT status FROM agent_executions WHERE execution_id=:execution"
                ),
                {"execution": terminal["identity"]["coordinator_execution_id"]},
            )
            == "RUNNING"
        )


def test_failure_between_updates_rolls_back_both_aggregates(mysql_engine: Engine):
    terminal, client = _ready(mysql_engine, "c")

    def fail_after_coordinator():
        raise RuntimeError("injected between aggregate updates")

    with pytest.raises(ApprovedWorkflowCompletionIntegrityError):
        ApprovedWorkflowCompletionService(
            mysql_engine, client, after_coordinator_hook=fail_after_coordinator
        ).complete(terminal)
    with mysql_engine.connect() as connection:
        assert connection.execute(
            text(
                "SELECT status FROM agent_runs WHERE run_id=:run UNION ALL "
                "SELECT status FROM agent_executions WHERE execution_id=:execution"
            ),
            {
                "run": terminal["identity"]["run_id"],
                "execution": terminal["identity"]["coordinator_execution_id"],
            },
        ).scalars().all() == ["RUNNING", "RUNNING"]
    assert (
        ApprovedWorkflowCompletionService(mysql_engine, client)
        .complete(terminal)
        .outcome
        is WorkflowCompletionOutcome.APPLIED
    )


def test_concurrent_identical_completion_has_single_winner(mysql_engine: Engine):
    terminal, client = _ready(mysql_engine, "d")
    service = ApprovedWorkflowCompletionService(mysql_engine, client)
    start = threading.Barrier(2)

    def complete():
        start.wait()
        return service.complete(terminal).outcome

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = {
            future.result() for future in (pool.submit(complete), pool.submit(complete))
        }
    assert outcomes == {
        WorkflowCompletionOutcome.APPLIED,
        WorkflowCompletionOutcome.DUPLICATE_IDENTICAL,
    }


def test_split_completion_transition_fails_closed(mysql_engine: Engine):
    terminal, client = _ready(mysql_engine, "f")
    service = ApprovedWorkflowCompletionService(mysql_engine, client)
    assert service.complete(terminal).outcome is WorkflowCompletionOutcome.APPLIED
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE agent_execution_transitions SET transition_request_id=:bad "
                "WHERE execution_id=:execution AND reason_code='APPROVED_WORKFLOW_COMPLETED'"
            ),
            {
                "bad": "ETQ-" + "F" * 32,
                "execution": terminal["identity"]["coordinator_execution_id"],
            },
        )
    with pytest.raises(ApprovedWorkflowCompletionIntegrityError):
        service.complete(terminal)


def test_cross_task_execution_binding_fails_before_business(mysql_engine: Engine):
    terminal, client = _ready(mysql_engine, "7")
    run_id = terminal["identity"]["run_id"]
    with mysql_engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT task_id,completion_execution_id FROM agent_tasks "
                "WHERE run_id=:run ORDER BY task_id LIMIT 2"
            ),
            {"run": run_id},
        ).all()
        connection.execute(
            text(
                "UPDATE agent_tasks SET current_execution_id=:foreign,"
                "completion_execution_id=:foreign WHERE task_id=:task"
            ),
            {"foreign": rows[1][1], "task": rows[0][0]},
        )
    with pytest.raises(ApprovedWorkflowCompletionIntegrityError, match="Task"):
        ApprovedWorkflowCompletionService(mysql_engine, client).complete(terminal)
    assert client.calls == 0


def test_missing_early_run_history_fails_before_business(mysql_engine: Engine):
    terminal, client = _ready(mysql_engine, "8")
    with mysql_engine.begin() as connection:
        connection.execute(
            text(
                "DELETE FROM agent_run_transitions WHERE run_id=:run AND to_revision=0"
            ),
            {"run": terminal["identity"]["run_id"]},
        )
    with pytest.raises(ApprovedWorkflowCompletionIntegrityError, match="Run history"):
        ApprovedWorkflowCompletionService(mysql_engine, client).complete(terminal)
    assert client.calls == 0


def test_slow_identical_completion_waits_for_winner(mysql_engine: Engine):
    terminal, client = _ready(mysql_engine, "9")
    original_execute = client.execute
    first = True
    guard = threading.Lock()

    def slow_execute(approval_key: str):
        nonlocal first
        with guard:
            should_sleep = first
            first = False
        if should_sleep:
            time.sleep(0.3)
        return original_execute(approval_key)

    client.execute = slow_execute
    service = ApprovedWorkflowCompletionService(
        mysql_engine, client, admission_wait_seconds=0.05
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        first_call = pool.submit(service.complete, terminal)
        time.sleep(0.2)
        second_call = pool.submit(service.complete, terminal)
        assert {first_call.result().outcome, second_call.result().outcome} == {
            WorkflowCompletionOutcome.APPLIED,
            WorkflowCompletionOutcome.DUPLICATE_IDENTICAL,
        }


def test_cancelled_coordinator_fails_before_business(isolated_mysql_engine: Engine):
    mysql_engine = isolated_mysql_engine
    terminal, client = _ready(mysql_engine, "a")
    coordinator_id = str(terminal["identity"]["coordinator_execution_id"])
    coordinator = AgentExecutionLifecycleService(mysql_engine).get_execution(
        coordinator_id
    )
    assert coordinator is not None
    AgentExecutionLifecycleService(mysql_engine).transition_execution(
        TransitionCommand(
            transition_request_id="ERQ-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA1",
            execution_id=coordinator_id,
            expected_status=ExecutionStatus.RUNNING,
            expected_revision=int(coordinator["lifecycle"]["revision"]),
            to_status=ExecutionStatus.CANCELLED,
            actor_kind="SYSTEM",
            actor_id="test-suite",
            reason_code="TEST_CANCELLED",
            reason_message="cancelled before approved workflow completion",
        )
    )

    with pytest.raises(ApprovedWorkflowCompletionRejected, match="Coordinator"):
        ApprovedWorkflowCompletionService(mysql_engine, client).complete(terminal)
    assert client.calls == 0


def test_identical_callers_at_business_pool_capacity_do_not_starve_winner(
    isolated_mysql_engine: Engine,
):
    terminal, client = _ready(isolated_mysql_engine, "b")
    constrained = create_engine(
        isolated_mysql_engine.url,
        poolclass=QueuePool,
        pool_size=2,
        max_overflow=0,
        pool_timeout=1,
    )
    try:
        service = ApprovedWorkflowCompletionService(
            constrained, client, admission_wait_seconds=0.05
        )
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(service.complete, terminal) for _ in range(3)]
            outcomes = [future.result(timeout=10).outcome for future in futures]
        assert outcomes.count(WorkflowCompletionOutcome.APPLIED) == 1
        assert outcomes.count(WorkflowCompletionOutcome.DUPLICATE_IDENTICAL) == 2
    finally:
        constrained.dispose()


def test_external_admission_owner_has_bounded_infrastructure_failure(
    isolated_mysql_engine: Engine,
):
    terminal, client = _ready(isolated_mysql_engine, "c")
    approval_id = str(terminal["identity"]["approval_id"])
    lock_name = (
        "workflow-complete:" + hashlib.sha256(approval_id.encode()).hexdigest()[:45]
    )
    with isolated_mysql_engine.connect() as owner:
        assert owner.scalar(text("SELECT GET_LOCK(:name,0)"), {"name": lock_name}) == 1
        owner.commit()
        started = time.monotonic()
        with pytest.raises(ApprovedWorkflowCompletionIntegrityError, match="deadline"):
            ApprovedWorkflowCompletionService(
                isolated_mysql_engine,
                client,
                admission_wait_seconds=0.05,
                admission_deadline_seconds=0.15,
            ).complete(terminal)
        assert time.monotonic() - started < 2
        assert client.calls == 0
        owner.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
        owner.commit()
