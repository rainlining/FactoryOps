from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


class OperationOutcome(str, Enum):
    APPLIED = "applied"
    DUPLICATE_IDENTICAL = "duplicate-identical"
    DUPLICATE_CONFLICTING = "duplicate-conflicting"
    CONCURRENCY_CONFLICT = "concurrency-conflict"


@dataclass(frozen=True)
class CreateTaskCommand:
    task_request_id: str
    run_id: str
    task_type: str
    target_agent_role: str
    created_by_execution_id: str
    priority: int
    context_snapshot_id: str
    evidence_refs: tuple[str, ...]
    dependency_task_ids: tuple[str, ...]


@dataclass(frozen=True)
class TransitionCommand:
    transition_request_id: str
    task_id: str
    expected_status: TaskStatus
    expected_revision: int
    to_status: TaskStatus
    actor_kind: str
    actor_id: str
    reason_code: str
    reason_message: str
    execution_id: str | None = None
    completion_execution_id: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    failure_recoverability: str | None = None


@dataclass(frozen=True)
class OperationResult:
    outcome: OperationOutcome
    task: Mapping[str, object] | None
