from dataclasses import replace
from datetime import datetime, timezone

import pytest

from factoryops_agent_service.task_lifecycle.model import TaskStatus, TransitionCommand
from factoryops_agent_service.task_lifecycle.rules import (
    LifecycleRuleViolation,
    plan_transition,
)

NOW = datetime(2026, 8, 16, 8, 0, tzinfo=timezone.utc)


def command(
    source: TaskStatus, target: TaskStatus, execution: str | None = None
) -> TransitionCommand:
    return TransitionCommand(
        "TRQ-" + "1" * 32,
        "TSK-" + "1" * 32,
        source,
        0,
        target,
        "COORDINATOR",
        "coordinator",
        "TASK_CHANGED",
        "changed",
        execution,
    )


@pytest.mark.parametrize(
    ("source", "target"),
    (
        (TaskStatus.PENDING, TaskStatus.RUNNING),
        (TaskStatus.PENDING, TaskStatus.CANCELLED),
        (TaskStatus.PENDING, TaskStatus.SKIPPED),
        (TaskStatus.RUNNING, TaskStatus.RUNNING),
        (TaskStatus.RUNNING, TaskStatus.SUCCEEDED),
        (TaskStatus.RUNNING, TaskStatus.FAILED),
        (TaskStatus.RUNNING, TaskStatus.CANCELLED),
    ),
)
def test_accepts_contract_edges(source: TaskStatus, target: TaskStatus) -> None:
    execution = (
        None
        if target in {TaskStatus.CANCELLED, TaskStatus.SKIPPED}
        else "EXE-" + "1" * 32
    )
    candidate = command(source, target, execution)
    if target is TaskStatus.SUCCEEDED:
        candidate = replace(candidate, completion_execution_id=execution)
    if target is TaskStatus.FAILED:
        candidate = replace(
            candidate,
            failure_code="ATTEMPTS_EXHAUSTED",
            failure_message="failed",
            failure_recoverability="non_retryable",
        )
    current_execution = (
        execution
        if source is TaskStatus.RUNNING and target is not TaskStatus.RUNNING
        else None
    )
    plan = plan_transition(
        candidate,
        current_started_at=NOW if source is TaskStatus.RUNNING else None,
        current_execution_id=current_execution,
        current_attempt_count=1 if current_execution else 0,
        occurred_at=NOW,
    )
    assert plan.to_revision == 1


def test_terminal_state_cannot_leave() -> None:
    with pytest.raises(LifecycleRuleViolation, match="illegal transition"):
        plan_transition(
            command(TaskStatus.SUCCEEDED, TaskStatus.RUNNING, "EXE-" + "1" * 32),
            current_started_at=NOW,
            current_execution_id="EXE-" + "1" * 32,
            current_attempt_count=1,
            occurred_at=NOW,
        )
