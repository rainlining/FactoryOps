from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pytest

from factoryops_agent_service.event_ingress.model import (
    IngressOutcome,
    KafkaRecord,
    ProcessingResult,
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
        self.result = result or ProcessingResult(IngressOutcome.ACCEPTED, "EVT-1")

    def process(self, record: KafkaRecord) -> ProcessingResult:
        if self.failure:
            raise self.failure
        return self.result


def test_commits_next_offset_only_after_processing() -> None:
    consumer = FakeConsumer()

    result = KafkaIngressWorker(consumer, FakeProcessor()).run_once()

    assert result == ProcessingResult(IngressOutcome.ACCEPTED, "EVT-1")
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
        result=ProcessingResult(IngressOutcome.DUPLICATE_IDENTICAL, "EVT-1")
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
