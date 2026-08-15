from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pytest

from factoryops_agent_service.event_ingress.decoder import KafkaRecordDecoder
from factoryops_agent_service.event_ingress.model import (
    IngressOutcome,
    KafkaRecord,
    ProcessingResult,
)
from factoryops_agent_service.event_ingress.processor import EventIngressProcessor
from factoryops_agent_service.event_ingress.run_starter import (
    RunStartOutcome,
    RunStartResult,
)
from factoryops_agent_service.event_ingress.worker import KafkaIngressWorker

RECORD = KafkaRecord("topic", 2, 9, b"key", b"value")


@dataclass
class FakeConsumer:
    record: KafkaRecord | None = RECORD
    fail_commit: bool = False
    actions: list[str] = field(default_factory=list)

    def poll(self, timeout_seconds: float) -> KafkaRecord | None:
        self.actions.append("poll")
        return self.record

    def commit(self, record: KafkaRecord) -> None:
        self.actions.append(f"commit:{record.offset + 1}")
        if self.fail_commit:
            raise RuntimeError("commit unavailable")

    def seek(self, record: KafkaRecord) -> None:
        self.actions.append(f"seek:{record.offset}")


class FakeProcessor:
    def __init__(self, failure: Exception | None = None, result=None) -> None:
        self.failure = failure
        self.result = result or ProcessingResult(
            IngressOutcome.ACCEPTED,
            "EVT-1",
            "RUN-1",
            RunStartOutcome.CREATED,
        )

    def process(self, record: KafkaRecord) -> ProcessingResult:
        if self.failure:
            raise self.failure
        return self.result


def test_commits_next_offset_only_after_processing() -> None:
    consumer = FakeConsumer()

    result = KafkaIngressWorker(consumer, FakeProcessor()).run_once()

    assert result == ProcessingResult(
        IngressOutcome.ACCEPTED,
        "EVT-1",
        "RUN-1",
        RunStartOutcome.CREATED,
    )
    assert consumer.actions == ["poll", "commit:10"]


def test_logs_redelivery_false_for_first_accept(caplog) -> None:
    caplog.set_level(
        logging.INFO, logger="factoryops_agent_service.event_ingress.worker"
    )
    consumer = FakeConsumer()

    KafkaIngressWorker(consumer, FakeProcessor()).run_once()

    assert any(
        "outcome=accepted" in message and "redelivery=false" in message
        for message in caplog.messages
    )


def test_logs_redelivery_true_for_identical_duplicate(caplog) -> None:
    caplog.set_level(
        logging.INFO, logger="factoryops_agent_service.event_ingress.worker"
    )
    consumer = FakeConsumer()
    processor = FakeProcessor(
        result=ProcessingResult(
            IngressOutcome.DUPLICATE_IDENTICAL,
            "EVT-1",
            "RUN-1",
            RunStartOutcome.ALREADY_STARTED,
        )
    )

    KafkaIngressWorker(consumer, processor).run_once()

    assert any(
        "outcome=duplicate-identical" in message and "redelivery=true" in message
        for message in caplog.messages
    )


@pytest.mark.parametrize(
    ("processor", "fail_commit"),
    [
        (FakeProcessor(RuntimeError("database unavailable")), False),
        (FakeProcessor(), True),
    ],
)
def test_seeks_current_offset_on_processing_or_commit_failure(
    processor: FakeProcessor,
    fail_commit: bool,
) -> None:
    consumer = FakeConsumer(fail_commit=fail_commit)

    with pytest.raises(RuntimeError):
        KafkaIngressWorker(consumer, processor).run_once()

    assert consumer.actions[-1] == "seek:9"


class FakeRepository:
    def __init__(self, outcome: IngressOutcome) -> None:
        self.outcome = outcome

    def accept(self, event):
        return self.outcome

    def reject(self, record, failure):
        return self.outcome


class FakeStarter:
    def __init__(self) -> None:
        self.events = []

    def ensure_original_run(self, event):
        self.events.append(event)
        return RunStartResult(RunStartOutcome.CREATED, "RUN-1")


@pytest.mark.parametrize(
    "outcome",
    [IngressOutcome.ACCEPTED, IngressOutcome.DUPLICATE_IDENTICAL],
)
def test_processor_starts_run_for_trusted_inbox_outcome(
    outcome: IngressOutcome,
    valid_event: dict[str, object],
    valid_payload: bytes,
) -> None:
    starter = FakeStarter()
    processor = EventIngressProcessor(
        KafkaRecordDecoder(),
        FakeRepository(outcome),
        starter,
    )
    incident_id = valid_event["payload"]["incident_id"]
    record = KafkaRecord("topic", 0, 0, incident_id.encode(), valid_payload)

    result = processor.process(record)

    assert result.run_id == "RUN-1"
    assert result.run_start_outcome is RunStartOutcome.CREATED
    assert len(starter.events) == 1


@pytest.mark.parametrize(
    "outcome",
    [IngressOutcome.REJECTED_INVALID, IngressOutcome.REJECTED_CONFLICTING],
)
def test_processor_does_not_start_run_for_rejected_outcome(
    outcome: IngressOutcome,
    valid_event: dict[str, object],
    valid_payload: bytes,
) -> None:
    starter = FakeStarter()
    processor = EventIngressProcessor(
        KafkaRecordDecoder(),
        FakeRepository(outcome),
        starter,
    )
    incident_id = valid_event["payload"]["incident_id"]
    if outcome is IngressOutcome.REJECTED_INVALID:
        record = KafkaRecord("topic", 0, 0, incident_id.encode(), b"not-json")
    else:
        record = KafkaRecord("topic", 0, 0, incident_id.encode(), valid_payload)

    result = processor.process(record)

    assert result.run_id is None
    assert result.run_start_outcome is RunStartOutcome.NOT_APPLICABLE
    assert starter.events == []
