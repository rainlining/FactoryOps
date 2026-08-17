from dataclasses import dataclass
from datetime import datetime

from .model import ExecutionStatus, TransitionCommand

LEGAL = {
    ExecutionStatus.PENDING: {ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED},
    ExecutionStatus.RUNNING: {
        ExecutionStatus.SUCCEEDED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
    },
    ExecutionStatus.SUCCEEDED: set(),
    ExecutionStatus.FAILED: set(),
    ExecutionStatus.CANCELLED: set(),
}
TERMINAL = {
    ExecutionStatus.SUCCEEDED,
    ExecutionStatus.FAILED,
    ExecutionStatus.CANCELLED,
}


class LifecycleRuleViolation(ValueError):
    pass


@dataclass(frozen=True)
class TransitionPlan:
    revision: int
    started_at: datetime | None
    ended_at: datetime | None


def plan_transition(
    command: TransitionCommand, *, started_at: datetime | None, occurred_at: datetime
) -> TransitionPlan:
    if command.to_status not in LEGAL[command.expected_status]:
        raise LifecycleRuleViolation(
            f"illegal transition: {command.expected_status.value} -> {command.to_status.value}"
        )
    if (
        not command.actor_kind.strip()
        or not command.actor_id.strip()
        or not command.reason_message.strip()
    ):
        raise LifecycleRuleViolation("actor and reason must not be blank")
    if command.to_status is ExecutionStatus.SUCCEEDED and (
        command.result is None or command.failure is not None
    ):
        raise LifecycleRuleViolation("SUCCEEDED requires only result")
    if command.to_status is ExecutionStatus.FAILED and (
        command.failure is None or command.result is not None
    ):
        raise LifecycleRuleViolation("FAILED requires only failure")
    if command.to_status in {ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED} and (
        command.result is not None or command.failure is not None
    ):
        raise LifecycleRuleViolation("non-result state cannot carry result or failure")
    first_started = (
        occurred_at
        if command.expected_status is ExecutionStatus.PENDING
        and command.to_status is ExecutionStatus.RUNNING
        else started_at
    )
    return TransitionPlan(
        command.expected_revision + 1,
        first_started,
        occurred_at if command.to_status in TERMINAL else None,
    )
