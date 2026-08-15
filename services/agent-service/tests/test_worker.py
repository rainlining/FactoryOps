from __future__ import annotations

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
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure

    def process(self, record: KafkaRecord) -> ProcessingResult:
        if self.failure:
            raise self.failure
        return ProcessingResult(IngressOutcome.ACCEPTED, "EVT-1")


def test_commits_next_offset_only_after_processing() -> None:
    consumer = FakeConsumer()

    result = KafkaIngressWorker(consumer, FakeProcessor()).run_once()

    assert result == ProcessingResult(IngressOutcome.ACCEPTED, "EVT-1")
    assert consumer.actions == ["poll", "commit:10"]


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
