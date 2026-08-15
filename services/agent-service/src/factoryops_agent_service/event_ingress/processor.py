from __future__ import annotations

from .decoder import DecodeFailure, KafkaRecordDecoder
from .model import KafkaRecord, ProcessingResult
from .repository import MySqlInboxRepository


class EventIngressProcessor:
    def __init__(
        self,
        decoder: KafkaRecordDecoder,
        repository: MySqlInboxRepository,
    ) -> None:
        self._decoder = decoder
        self._repository = repository

    def process(self, record: KafkaRecord) -> ProcessingResult:
        try:
            event = self._decoder.decode(record)
        except DecodeFailure as failure:
            outcome = self._repository.reject(record, failure)
            return ProcessingResult(outcome, failure.event_id)
        outcome = self._repository.accept(event)
        return ProcessingResult(outcome, event.event_id)
