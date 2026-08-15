from __future__ import annotations

from .decoder import DecodeFailure, KafkaRecordDecoder
from .model import IngressOutcome, KafkaRecord, ProcessingResult, RunStartOutcome
from .repository import MySqlInboxRepository
from .run_starter import IncidentRunStarter


class EventIngressProcessor:
    def __init__(
        self,
        decoder: KafkaRecordDecoder,
        repository: MySqlInboxRepository,
        run_starter: IncidentRunStarter,
    ) -> None:
        self._decoder = decoder
        self._repository = repository
        self._run_starter = run_starter

    def process(self, record: KafkaRecord) -> ProcessingResult:
        try:
            event = self._decoder.decode(record)
        except DecodeFailure as failure:
            outcome = self._repository.reject(record, failure)
            return ProcessingResult(
                outcome,
                failure.event_id,
                None,
                RunStartOutcome.NOT_APPLICABLE,
            )
        outcome = self._repository.accept(event)
        if outcome in {
            IngressOutcome.ACCEPTED,
            IngressOutcome.DUPLICATE_IDENTICAL,
        }:
            started = self._run_starter.ensure_original_run(event)
            return ProcessingResult(
                outcome,
                event.event_id,
                started.run_id,
                started.outcome,
            )
        return ProcessingResult(
            outcome,
            event.event_id,
            None,
            RunStartOutcome.NOT_APPLICABLE,
        )
