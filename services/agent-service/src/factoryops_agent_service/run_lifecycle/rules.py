from __future__ import annotations

import re
from datetime import datetime

from .model import RunStatus, TransitionCommand, TransitionPlan

LEGAL_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.PENDING: frozenset(
        {
            RunStatus.RUNNING,
            RunStatus.CANCELLED,
        }
    ),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.WAITING_FOR_APPROVAL,
            RunStatus.SUSPENDED,
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }
    ),
    RunStatus.WAITING_FOR_APPROVAL: frozenset(
        {
            RunStatus.RUNNING,
            RunStatus.SUSPENDED,
            RunStatus.CANCELLED,
        }
    ),
    RunStatus.SUSPENDED: frozenset(
        {
            RunStatus.RUNNING,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }
    ),
    RunStatus.SUCCEEDED: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
}

TERMINAL_STATUSES = frozenset(
    {
        RunStatus.SUCCEEDED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
    }
)
REASON_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,127}$")


class LifecycleRuleViolation(ValueError):
    pass


def plan_transition(
    command: TransitionCommand,
    *,
    current_started_at: datetime | None,
    occurred_at: datetime,
) -> TransitionPlan:
    allowed_targets = LEGAL_TRANSITIONS[command.expected_status]
    if command.to_status not in allowed_targets:
        raise LifecycleRuleViolation(
            "illegal transition: "
            f"{command.expected_status.value} -> {command.to_status.value}"
        )
    if command.expected_revision < 0:
        raise LifecycleRuleViolation("expected_revision must be non-negative")
    if not REASON_CODE_PATTERN.fullmatch(command.reason_code):
        raise LifecycleRuleViolation("reason_code must match the Contract format")
    if not command.actor_id.strip():
        raise LifecycleRuleViolation("actor_id must not be blank")
    if command.reason_message is not None and not command.reason_message.strip():
        raise LifecycleRuleViolation("reason_message must not be blank")
    if command.to_status is RunStatus.SUSPENDED and not command.checkpoint_id:
        raise LifecycleRuleViolation("SUSPENDED requires a checkpoint")
    if command.to_status is not RunStatus.SUSPENDED and command.checkpoint_id:
        raise LifecycleRuleViolation("checkpoint is only accepted for SUSPENDED")

    started_at = current_started_at
    if (
        command.expected_status is RunStatus.PENDING
        and command.to_status is RunStatus.RUNNING
    ):
        if current_started_at is not None:
            raise LifecycleRuleViolation("PENDING run already has started_at")
        started_at = occurred_at

    ended_at = occurred_at if command.to_status in TERMINAL_STATUSES else None
    return TransitionPlan(
        from_status=command.expected_status,
        to_status=command.to_status,
        from_revision=command.expected_revision,
        to_revision=command.expected_revision + 1,
        started_at=started_at,
        ended_at=ended_at,
        occurred_at=occurred_at,
        checkpoint_id=command.checkpoint_id,
    )
