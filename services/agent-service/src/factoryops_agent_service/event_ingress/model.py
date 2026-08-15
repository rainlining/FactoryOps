from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class KafkaRecord:
    topic: str
    partition: int
    offset: int
    key: bytes | None
    value: bytes | None


@dataclass(frozen=True)
class DecodedEvent:
    record: KafkaRecord
    event_id: str
    incident_id: str
    event_type: str
    contract_version: str
    message_key: str
    canonical_sha256: bytes


class IngressOutcome(str, Enum):
    ACCEPTED = "accepted"
    DUPLICATE_IDENTICAL = "duplicate-identical"
    REJECTED_INVALID = "rejected-invalid"
    REJECTED_CONFLICTING = "rejected-conflicting"


class RunStartOutcome(str, Enum):
    CREATED = "created"
    ALREADY_STARTED = "already-started"
    NOT_APPLICABLE = "not-applicable"


@dataclass(frozen=True)
class ProcessingResult:
    outcome: IngressOutcome
    event_id: str | None
    run_id: str | None
    run_start_outcome: RunStartOutcome
