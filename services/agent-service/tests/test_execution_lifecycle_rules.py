from datetime import datetime, timezone

import pytest

from factoryops_agent_service.execution_lifecycle.model import (
    ExecutionStatus,
    TransitionCommand,
)
from factoryops_agent_service.execution_lifecycle.rules import (
    LifecycleRuleViolation,
    plan_transition,
)

NOW = datetime(2026, 8, 17, 1, 0, tzinfo=timezone.utc)


def command(source: ExecutionStatus, target: ExecutionStatus) -> TransitionCommand:
    result = (
        {
            "output_artifact_refs": ["artifact:1"],
            "decision_id": None,
            "evidence_refs": [],
        }
        if target is ExecutionStatus.SUCCEEDED
        else None
    )
    failure = (
        {
            "code": "MODEL_TIMEOUT",
            "message": "timeout",
            "recoverability": "retryable",
            "failed_dependency_ref": "model:x",
        }
        if target is ExecutionStatus.FAILED
        else None
    )
    return TransitionCommand(
        "ERQ-" + "1" * 32,
        "EXE-" + "1" * 32,
        source,
        0,
        target,
        "WORKER",
        "worker",
        "STATE_CHANGED",
        "changed",
        result,
        failure,
    )


@pytest.mark.parametrize(
    ("source", "target"),
    (
        (ExecutionStatus.PENDING, ExecutionStatus.RUNNING),
        (ExecutionStatus.PENDING, ExecutionStatus.CANCELLED),
        (ExecutionStatus.RUNNING, ExecutionStatus.SUCCEEDED),
        (ExecutionStatus.RUNNING, ExecutionStatus.FAILED),
        (ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED),
    ),
)
def test_contract_edges(source: ExecutionStatus, target: ExecutionStatus) -> None:
    assert (
        plan_transition(
            command(source, target),
            started_at=NOW if source is ExecutionStatus.RUNNING else None,
            occurred_at=NOW,
        ).revision
        == 1
    )


def test_terminal_cannot_leave() -> None:
    with pytest.raises(LifecycleRuleViolation, match="illegal transition"):
        plan_transition(
            command(ExecutionStatus.SUCCEEDED, ExecutionStatus.RUNNING),
            started_at=NOW,
            occurred_at=NOW,
        )
