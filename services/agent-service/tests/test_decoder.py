from __future__ import annotations

import hashlib

import pytest

from factoryops_agent_service.event_ingress.decoder import (
    DecodeFailure,
    KafkaRecordDecoder,
)
from factoryops_agent_service.event_ingress.model import KafkaRecord


def test_decodes_valid_contract_and_routing_key(
    valid_event: dict[str, object],
    valid_payload: bytes,
) -> None:
    incident_id = valid_event["payload"]["incident_id"]
    record = KafkaRecord(
        "factoryops.quality.incident.v1", 1, 4, incident_id.encode(), valid_payload
    )

    decoded = KafkaRecordDecoder().decode(record)

    assert decoded.event_id == valid_event["event_id"]
    assert decoded.incident_id == incident_id
    assert decoded.message_key == incident_id
    assert len(decoded.canonical_sha256) == hashlib.sha256().digest_size


def test_rejects_mismatched_message_key(valid_payload: bytes) -> None:
    record = KafkaRecord(
        "factoryops.quality.incident.v1", 0, 2, b"QI-wrong", valid_payload
    )

    with pytest.raises(DecodeFailure) as raised:
        KafkaRecordDecoder().decode(record)

    assert raised.value.code == "message_key_mismatch"
    assert raised.value.event_id is not None


def test_rejects_invalid_utf8_without_exposing_payload() -> None:
    record = KafkaRecord("factoryops.quality.incident.v1", 0, 3, None, b"\xffsecret")

    with pytest.raises(DecodeFailure) as raised:
        KafkaRecordDecoder().decode(record)

    assert raised.value.code == "invalid_utf8"
    assert "secret" not in raised.value.detail


def test_rejects_kafka_tombstone_as_missing_payload() -> None:
    record = KafkaRecord("factoryops.quality.incident.v1", 0, 4, b"key", None)

    with pytest.raises(DecodeFailure) as raised:
        KafkaRecordDecoder().decode(record)

    assert raised.value.code == "missing_payload"
