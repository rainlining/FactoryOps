from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from contracts.quality_incident_opened.validator import (
    QualityIncidentOpenedValidationError,
    canonicalize_event,
)

from .model import DecodedEvent, KafkaRecord


@dataclass(frozen=True)
class DecodeFailure(ValueError):
    code: str
    detail: str
    payload_sha256: bytes
    event_id: str | None = None

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class KafkaRecordDecoder:
    def decode(self, record: KafkaRecord) -> DecodedEvent:
        if record.value is None:
            raise DecodeFailure(
                "missing_payload",
                "Kafka value is required",
                hashlib.sha256(b"").digest(),
            )
        payload_sha256 = hashlib.sha256(record.value).digest()
        try:
            text = record.value.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise DecodeFailure(
                "invalid_utf8",
                str(error),
                payload_sha256,
            ) from error

        try:
            event: Any = json.loads(text)
        except json.JSONDecodeError as error:
            raise DecodeFailure(
                "invalid_json",
                str(error),
                payload_sha256,
            ) from error
        if not isinstance(event, dict):
            raise DecodeFailure(
                "json_not_object",
                "event root must be an object",
                payload_sha256,
            )

        event_id = event.get("event_id")
        safe_event_id = (
            event_id if isinstance(event_id, str) and len(event_id) <= 68 else None
        )
        try:
            canonical = canonicalize_event(event)
        except QualityIncidentOpenedValidationError as error:
            issue = error.issues[0]
            raise DecodeFailure(
                issue.code,
                f"{issue.path}: contract validation failed",
                payload_sha256,
                safe_event_id,
            ) from error

        key = self._decode_key(record, payload_sha256, safe_event_id)
        incident_id = event["payload"]["incident_id"]
        if key != incident_id:
            raise DecodeFailure(
                "message_key_mismatch",
                "Kafka key must equal payload.incident_id",
                payload_sha256,
                safe_event_id,
            )

        return DecodedEvent(
            record=record,
            event_id=event["event_id"],
            event_type=event["event_type"],
            contract_version=event["contract_version"],
            message_key=key,
            canonical_sha256=hashlib.sha256(canonical).digest(),
        )

    def _decode_key(
        self,
        record: KafkaRecord,
        payload_sha256: bytes,
        event_id: str | None,
    ) -> str:
        if record.key is None:
            raise DecodeFailure(
                "missing_message_key",
                "Kafka key is required",
                payload_sha256,
                event_id,
            )
        try:
            return record.key.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise DecodeFailure(
                "invalid_message_key_utf8",
                str(error),
                payload_sha256,
                event_id,
            ) from error
