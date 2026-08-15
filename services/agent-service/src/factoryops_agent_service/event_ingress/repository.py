from __future__ import annotations

from collections.abc import Mapping

from sqlalchemy import Engine, text

from .decoder import DecodeFailure
from .model import DecodedEvent, IngressOutcome, KafkaRecord


class InboxStateError(RuntimeError):
    pass


class MySqlInboxRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def accept(self, event: DecodedEvent) -> IngressOutcome:
        with self._engine.begin() as connection:
            inserted = connection.execute(
                text(
                    """
                    INSERT IGNORE INTO agent_event_inbox (
                      event_id, event_type, contract_version, topic,
                      kafka_partition, kafka_offset, message_key,
                      raw_payload, canonical_sha256, received_at)
                    VALUES (
                      :event_id, :event_type, :contract_version, :topic,
                      :partition, :offset, :message_key,
                      :raw_payload, :canonical_sha256, CURRENT_TIMESTAMP(6))
                    """
                ),
                self._event_parameters(event),
            )
            if inserted.rowcount == 1:
                return IngressOutcome.ACCEPTED

            existing = (
                connection.execute(
                    text(
                        """
                    SELECT canonical_sha256
                    FROM agent_event_inbox
                    WHERE event_id = :event_id
                    FOR UPDATE
                    """
                    ),
                    {"event_id": event.event_id},
                )
                .mappings()
                .one_or_none()
            )
            if existing is None:
                raise InboxStateError(
                    "inbox insert was ignored without an existing event_id"
                )
            if existing["canonical_sha256"] == event.canonical_sha256:
                return IngressOutcome.DUPLICATE_IDENTICAL

            self._insert_rejection(
                connection,
                event.record,
                "duplicate_conflicting",
                "same event_id has different canonical content",
                event.event_id,
                event.canonical_sha256,
            )
            return IngressOutcome.REJECTED_CONFLICTING

    def reject(self, record: KafkaRecord, failure: DecodeFailure) -> IngressOutcome:
        with self._engine.begin() as connection:
            self._insert_rejection(
                connection,
                record,
                failure.code,
                failure.detail,
                failure.event_id,
                failure.payload_sha256,
            )
        return IngressOutcome.REJECTED_INVALID

    def _event_parameters(self, event: DecodedEvent) -> Mapping[str, object]:
        return {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "contract_version": event.contract_version,
            "topic": event.record.topic,
            "partition": event.record.partition,
            "offset": event.record.offset,
            "message_key": event.message_key,
            "raw_payload": event.record.value,
            "canonical_sha256": event.canonical_sha256,
        }

    def _insert_rejection(
        self,
        connection: object,
        record: KafkaRecord,
        reason_code: str,
        reason_detail: str,
        event_id: str | None,
        payload_sha256: bytes,
    ) -> None:
        connection.execute(
            text(
                """
                INSERT IGNORE INTO agent_event_rejections (
                  topic, kafka_partition, kafka_offset, event_id,
                  reason_code, reason_detail, payload_sha256, rejected_at)
                VALUES (
                  :topic, :partition, :offset, :event_id,
                  :reason_code, :reason_detail, :payload_sha256,
                  CURRENT_TIMESTAMP(6))
                """
            ),
            {
                "topic": record.topic,
                "partition": record.partition,
                "offset": record.offset,
                "event_id": event_id,
                "reason_code": reason_code,
                "reason_detail": reason_detail[:1024],
                "payload_sha256": payload_sha256,
            },
        )
