from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from .model import TaskStatus, TransitionCommand

LEGAL = {
    TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.CANCELLED, TaskStatus.SKIPPED},
    TaskStatus.RUNNING: {
        TaskStatus.RUNNING,
        TaskStatus.SUCCEEDED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.SUCCEEDED: set(),
    TaskStatus.FAILED: set(),
    TaskStatus.CANCELLED: set(),
    TaskStatus.SKIPPED: set(),
}
TERMINAL = {
    TaskStatus.SUCCEEDED,
    TaskStatus.FAILED,
    TaskStatus.CANCELLED,
    TaskStatus.SKIPPED,
}


class LifecycleRuleViolation(ValueError):
    pass


@dataclass(frozen=True)
class TransitionPlan:
    to_revision: int
    started_at: datetime | None
    ended_at: datetime | None
    current_execution_id: str | None
    attempt_count: int


def plan_transition(
    command: TransitionCommand,
    *,
    current_started_at: datetime | None,
    current_execution_id: str | None,
    current_attempt_count: int,
    occurred_at: datetime,
) -> TransitionPlan:
    if command.to_status not in LEGAL[command.expected_status]:
        raise LifecycleRuleViolation(
            f"illegal transition: {command.expected_status.value} -> {command.to_status.value}"
        )
    if (
        not re.fullmatch(r"[A-Z][A-Z0-9_]{2,127}", command.reason_code)
        or not command.reason_message.strip()
    ):
        raise LifecycleRuleViolation("invalid status reason")
    if not command.actor_kind.strip() or not command.actor_id.strip():
        raise LifecycleRuleViolation("transition actor must not be blank")
    started, execution, attempts = (
        current_started_at,
        current_execution_id,
        current_attempt_count,
    )
    if command.to_status is TaskStatus.RUNNING:
        if not command.execution_id:
            raise LifecycleRuleViolation("RUNNING requires execution_id")
        if command.execution_id == current_execution_id:
            raise LifecycleRuleViolation("new attempt requires a new execution_id")
        started = started or occurred_at
        execution, attempts = command.execution_id, attempts + 1
    elif command.to_status in {TaskStatus.SUCCEEDED, TaskStatus.FAILED}:
        if not execution or command.execution_id != execution:
            raise LifecycleRuleViolation(
                "terminal result must reference current execution"
            )
    elif command.execution_id is not None:
        raise LifecycleRuleViolation("CANCELLED or SKIPPED cannot carry execution_id")
    if (
        command.to_status is TaskStatus.SUCCEEDED
        and command.completion_execution_id != execution
    ):
        raise LifecycleRuleViolation("SUCCEEDED requires matching completion execution")
    if command.to_status is TaskStatus.FAILED and (
        not command.failure_code
        or not command.failure_message
        or command.failure_recoverability != "non_retryable"
    ):
        raise LifecycleRuleViolation("FAILED requires non-retryable failure")
    ended = occurred_at if command.to_status in TERMINAL else None
    return TransitionPlan(
        command.expected_revision + 1, started, ended, execution, attempts
    )
