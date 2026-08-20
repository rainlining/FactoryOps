from __future__ import annotations

import hashlib
import threading
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
from factoryops_agent_service.worker_task_execution import WorkerTaskExecutionService
from sqlalchemy import Engine, create_engine, text
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
    with mysql_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT status FROM agent_runs WHERE run_id=:run"),
                {"run": terminal["identity"]["run_id"]},
            )
            == "RUNNING"
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
