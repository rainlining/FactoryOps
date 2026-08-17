from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class OperationOutcome(str, Enum):
    APPLIED = "applied"
    DUPLICATE_IDENTICAL = "duplicate-identical"
    DUPLICATE_CONFLICTING = "duplicate-conflicting"
    CONCURRENCY_CONFLICT = "concurrency-conflict"


@dataclass(frozen=True)
class CreateExecutionCommand:
    run_id: str
    agent_role: str
    attempt: int
    task_id: str | None
    runtime_version: str
    prompt_version: str
    model_policy_version: str
    tool_policy_version: str
    context_policy_version: str
    code_revision: str
    context_snapshot_id: str
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class TransitionCommand:
    transition_request_id: str
    execution_id: str
    expected_status: ExecutionStatus
    expected_revision: int
    to_status: ExecutionStatus
    actor_kind: str
    actor_id: str
    reason_code: str
    reason_message: str
    result: Mapping[str, object] | None = None
    failure: Mapping[str, object] | None = None


@dataclass(frozen=True)
class OperationResult:
    outcome: OperationOutcome
    execution: Mapping[str, object] | None
