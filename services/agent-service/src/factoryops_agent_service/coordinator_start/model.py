from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class StartOutcome(str, Enum):
    APPLIED = "applied"
    DUPLICATE_IDENTICAL = "duplicate-identical"
    DUPLICATE_CONFLICTING = "duplicate-conflicting"
    CONCURRENCY_CONFLICT = "concurrency-conflict"


@dataclass(frozen=True)
class StartCoordinatorCommand:
    start_request_id: str
    run_id: str
    prompt_version: str
    context_snapshot_id: str
    evidence_refs: tuple[str, ...]
    command_version: str = "1.0.0"


@dataclass(frozen=True)
class StartResult:
    outcome: StartOutcome
    run: Mapping[str, object] | None
    execution: Mapping[str, object] | None
