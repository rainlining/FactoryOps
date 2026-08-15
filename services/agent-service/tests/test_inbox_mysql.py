from __future__ import annotations

import copy
import hashlib
import json

from sqlalchemy import create_engine, text
from testcontainers.community.mysql import MySqlContainer

from factoryops_agent_service.event_ingress.decoder import (
    DecodeFailure,
    KafkaRecordDecoder,
)
from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.event_ingress.model import IngressOutcome, KafkaRecord
from factoryops_agent_service.event_ingress.repository import MySqlInboxRepository


def test_mysql_inbox_classifies_new_identical_conflict_and_invalid(
    valid_event: dict[str, object],
    valid_payload: bytes,
) -> None:
    with MySqlContainer("mysql:8.4") as mysql:
        database_url = mysql.get_connection_url().replace(
            "mysql://",
            "mysql+pymysql://",
            1,
        )
        engine = create_engine(database_url)
        migrate(engine)
        repository = MySqlInboxRepository(engine)
        incident_id = valid_event["payload"]["incident_id"]
        first_record = KafkaRecord(
            "factoryops.quality.incident.v1",
            0,
            0,
            incident_id.encode(),
            valid_payload,
        )
        first = KafkaRecordDecoder().decode(first_record)

        assert repository.accept(first) is IngressOutcome.ACCEPTED

        duplicate_record = KafkaRecord(
            first_record.topic,
            0,
            1,
            first_record.key,
            json.dumps(valid_event, indent=2).encode(),
        )
        duplicate = KafkaRecordDecoder().decode(duplicate_record)
        assert repository.accept(duplicate) is IngressOutcome.DUPLICATE_IDENTICAL

        conflicting_event = copy.deepcopy(valid_event)
        conflicting_event["occurred_at"] = "2026-08-15T00:00:00Z"
        conflict_record = KafkaRecord(
            first_record.topic,
            0,
            2,
            first_record.key,
            json.dumps(conflicting_event).encode(),
        )
        conflict = KafkaRecordDecoder().decode(conflict_record)
        assert repository.accept(conflict) is IngressOutcome.REJECTED_CONFLICTING

        invalid_record = KafkaRecord(first_record.topic, 0, 3, None, b"\xffsecret")
        try:
            KafkaRecordDecoder().decode(invalid_record)
        except DecodeFailure as failure:
            assert (
                repository.reject(invalid_record, failure)
                is IngressOutcome.REJECTED_INVALID
            )

        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT COUNT(*) FROM agent_event_inbox")) == 1
            )
            assert (
                connection.scalar(text("SELECT COUNT(*) FROM agent_event_rejections"))
                == 2
            )
            stored = connection.execute(
                text("SELECT raw_payload FROM agent_event_inbox")
            ).scalar_one()
            assert stored == valid_payload
            invalid_hash = connection.execute(
                text(
                    """
                    SELECT payload_sha256
                    FROM agent_event_rejections
                    WHERE kafka_offset=3
                    """
                )
            ).scalar_one()
            assert invalid_hash == hashlib.sha256(b"\xffsecret").digest()
        engine.dispose()
