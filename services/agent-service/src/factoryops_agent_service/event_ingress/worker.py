from __future__ import annotations

import logging
import time
from typing import Protocol

from .model import KafkaRecord, ProcessingResult
from .processor import EventIngressProcessor

LOGGER = logging.getLogger(__name__)


class ConsumerPort(Protocol):
    def poll(self, timeout_seconds: float) -> KafkaRecord | None: ...

    def commit(self, record: KafkaRecord) -> None: ...

    def seek(self, record: KafkaRecord) -> None: ...


class KafkaIngressWorker:
    def __init__(
        self,
        consumer: ConsumerPort,
        processor: EventIngressProcessor,
    ) -> None:
        self._consumer = consumer
        self._processor = processor

    def run_once(self, timeout_seconds: float = 1.0) -> ProcessingResult | None:
        record = self._consumer.poll(timeout_seconds)
        if record is None:
            return None
        started = time.monotonic()
        try:
            result = self._processor.process(record)
            processing_ms = round((time.monotonic() - started) * 1000)
            self._consumer.commit(record)
        except Exception:
            self._seek_for_retry(record)
            LOGGER.exception(
                "event_ingress_failed topic=%s partition=%s offset=%s",
                record.topic,
                record.partition,
                record.offset,
            )
            raise

        LOGGER.info(
            "event_ingress_processed topic=%s partition=%s offset=%s "
            "event_id=%s outcome=%s processing_ms=%s total_ms=%s "
            "offset_committed=true",
            record.topic,
            record.partition,
            record.offset,
            result.event_id,
            result.outcome.value,
            processing_ms,
            round((time.monotonic() - started) * 1000),
        )
        return result

    def _seek_for_retry(self, record: KafkaRecord) -> None:
        try:
            self._consumer.seek(record)
        except Exception:
            LOGGER.exception(
                "event_ingress_seek_failed topic=%s partition=%s offset=%s",
                record.topic,
                record.partition,
                record.offset,
            )
