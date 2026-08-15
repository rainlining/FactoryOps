from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from factoryops_agent_service.run_lifecycle.model import (
    ActorKind,
    RunStatus,
    TransitionCommand,
)
from factoryops_agent_service.run_lifecycle.rules import (
    LifecycleRuleViolation,
    plan_transition,
)

NOW = datetime(2026, 8, 15, 4, 0, tzinfo=timezone.utc)
STARTED = datetime(2026, 8, 15, 3, 0, tzinfo=timezone.utc)


def command(
    expected_status: RunStatus,
    to_status: RunStatus,
    *,
    checkpoint_id: str | None = None,
) -> TransitionCommand:
    return TransitionCommand(
        transition_request_id="TRQ-" + "1" * 32,
        run_id="RUN-" + "1" * 32,
        expected_status=expected_status,
        expected_revision=4,
        to_status=to_status,
        actor_kind=ActorKind.COORDINATOR,
        actor_id="coordinator-execution-1",
        reason_code="TEST_TRANSITION",
        reason_message="A deterministic test transition.",
        checkpoint_id=checkpoint_id,
    )


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    (
        (RunStatus.PENDING, RunStatus.RUNNING),
        (RunStatus.PENDING, RunStatus.CANCELLED),
        (RunStatus.RUNNING, RunStatus.WAITING_FOR_APPROVAL),
        (RunStatus.RUNNING, RunStatus.SUSPENDED),
        (RunStatus.RUNNING, RunStatus.SUCCEEDED),
        (RunStatus.RUNNING, RunStatus.FAILED),
        (RunStatus.RUNNING, RunStatus.CANCELLED),
        (RunStatus.WAITING_FOR_APPROVAL, RunStatus.RUNNING),
        (RunStatus.WAITING_FOR_APPROVAL, RunStatus.SUSPENDED),
        (RunStatus.WAITING_FOR_APPROVAL, RunStatus.CANCELLED),
        (RunStatus.SUSPENDED, RunStatus.RUNNING),
        (RunStatus.SUSPENDED, RunStatus.FAILED),
        (RunStatus.SUSPENDED, RunStatus.CANCELLED),
    ),
)
def test_accepts_each_legal_transition(
    from_status: RunStatus,
    to_status: RunStatus,
) -> None:
    checkpoint_id = "checkpoint-1" if to_status is RunStatus.SUSPENDED else None

    plan = plan_transition(
        command(from_status, to_status, checkpoint_id=checkpoint_id),
        current_started_at=None if from_status is RunStatus.PENDING else STARTED,
        occurred_at=NOW,
    )

    assert plan.to_status is to_status
    assert plan.to_revision == 5


@pytest.mark.parametrize(
    "terminal_status",
    (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED),
)
def test_rejects_transition_from_terminal_state(
    terminal_status: RunStatus,
) -> None:
    with pytest.raises(LifecycleRuleViolation, match="illegal transition"):
        plan_transition(
            command(terminal_status, RunStatus.RUNNING),
            current_started_at=STARTED,
            occurred_at=NOW,
        )


def test_suspended_requires_checkpoint() -> None:
    with pytest.raises(LifecycleRuleViolation, match="checkpoint"):
        plan_transition(
            command(RunStatus.RUNNING, RunStatus.SUSPENDED),
            current_started_at=STARTED,
            occurred_at=NOW,
        )


def test_first_start_sets_started_at_once() -> None:
    plan = plan_transition(
        command(RunStatus.PENDING, RunStatus.RUNNING),
        current_started_at=None,
        occurred_at=NOW,
    )

    assert plan.started_at == NOW
    assert plan.ended_at is None


def test_resume_preserves_first_started_at() -> None:
    plan = plan_transition(
        command(RunStatus.SUSPENDED, RunStatus.RUNNING),
        current_started_at=STARTED,
        occurred_at=NOW,
    )

    assert plan.started_at == STARTED


def test_cancel_before_start_keeps_started_at_empty() -> None:
    plan = plan_transition(
        command(RunStatus.PENDING, RunStatus.CANCELLED),
        current_started_at=None,
        occurred_at=NOW,
    )

    assert plan.started_at is None
    assert plan.ended_at == NOW


def test_rejects_short_reason_code() -> None:
    invalid = command(RunStatus.PENDING, RunStatus.RUNNING)
    invalid = replace(invalid, reason_code="X")

    with pytest.raises(LifecycleRuleViolation, match="reason_code"):
        plan_transition(invalid, current_started_at=None, occurred_at=NOW)
