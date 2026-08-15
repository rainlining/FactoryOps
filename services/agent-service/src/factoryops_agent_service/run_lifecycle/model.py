from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class RunKind(str, Enum):
    ORIGINAL = "original"
    REPLAY = "replay"


class RunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    SUSPENDED = "SUSPENDED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ActorKind(str, Enum):
    SYSTEM = "SYSTEM"
    COORDINATOR = "COORDINATOR"
    OPERATOR = "OPERATOR"
    RECOVERY_WORKER = "RECOVERY_WORKER"


class OperationOutcome(str, Enum):
    APPLIED = "applied"
    DUPLICATE_IDENTICAL = "duplicate-identical"
    DUPLICATE_CONFLICTING = "duplicate-conflicting"
    CONCURRENCY_CONFLICT = "concurrency-conflict"


@dataclass(frozen=True)
class RunProvenance:
    incident_id: str
    runtime_version: str
    workflow_version: str
    prompt_set_version: str
    model_policy_version: str
    tool_policy_version: str
    context_policy_version: str
    code_revision: str


@dataclass(frozen=True)
class OriginalRunCommand:
    trigger_event_id: str
    provenance: RunProvenance


@dataclass(frozen=True)
class ReplayRunCommand:
    replay_request_id: str
    original_run_id: str
    replayed_from_run_id: str
    provenance: RunProvenance


@dataclass(frozen=True)
class TransitionCommand:
    transition_request_id: str
    run_id: str
    expected_status: RunStatus
    expected_revision: int
    to_status: RunStatus
    actor_kind: ActorKind
    actor_id: str
    reason_code: str
    reason_message: str | None = None
    checkpoint_id: str | None = None


@dataclass(frozen=True)
class TransitionPlan:
    from_status: RunStatus
    to_status: RunStatus
    from_revision: int
    to_revision: int
    started_at: datetime | None
    ended_at: datetime | None
    occurred_at: datetime
    checkpoint_id: str | None


@dataclass(frozen=True)
class RunOperationResult:
    outcome: OperationOutcome
    run: Mapping[str, object] | None


@dataclass(frozen=True)
class TransitionOperationResult:
    outcome: OperationOutcome
    run: Mapping[str, object] | None
