from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class DispatchOutcome(str, Enum):
    APPLIED = "applied"
    DUPLICATE_IDENTICAL = "duplicate-identical"
    DUPLICATE_CONFLICTING = "duplicate-conflicting"
    CONCURRENCY_CONFLICT = "concurrency-conflict"


@dataclass(frozen=True)
class DispatchCommand:
    task_request_id: str
    run_id: str
    coordinator_execution_id: str
    task_type: str
    target_agent_role: str
    priority: int
    context_snapshot_id: str
    evidence_refs: tuple[str, ...]
    dependency_task_ids: tuple[str, ...]


@dataclass(frozen=True)
class DispatchResult:
    outcome: DispatchOutcome
    task: Mapping[str, object] | None
