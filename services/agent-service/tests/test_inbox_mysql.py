from __future__ import annotations

import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock

import pytest
from sqlalchemy import create_engine, text
from testcontainers.community.mysql import MySqlContainer

from factoryops_agent_service.event_ingress.decoder import (
    DecodeFailure,
    KafkaRecordDecoder,
)
from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.event_ingress.model import IngressOutcome, KafkaRecord
from factoryops_agent_service.event_ingress.processor import EventIngressProcessor
from factoryops_agent_service.event_ingress.repository import MySqlInboxRepository
from factoryops_agent_service.event_ingress.run_starter import (
    IncidentRunStarter,
    RunStartIntegrityError,
    RunStartOutcome,
    RunStartResult,
)
from factoryops_agent_service.event_ingress.runtime_config import AgentRuntimeConfig
from factoryops_agent_service.run_lifecycle.service import AgentRunLifecycleService


class RecordingStarter:
    def __init__(self) -> None:
        self.event_ids: list[str] = []

    def ensure_original_run(self, event):
        self.event_ids.append(event.event_id)
        return RunStartResult(RunStartOutcome.CREATED, "RUN-" + "1" * 32)


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

        starter = RecordingStarter()
        processor = EventIngressProcessor(KafkaRecordDecoder(), repository, starter)
        recovered = processor.process(duplicate_record)
        assert recovered.outcome is IngressOutcome.DUPLICATE_IDENTICAL
        assert recovered.run_start_outcome is RunStartOutcome.CREATED
        assert starter.event_ids == [first.event_id]

        create_barrier = Barrier(2)
        synchronization_lock = Lock()
        synchronized_lookups: list[str] = []
        processors = [
            EventIngressProcessor(
                KafkaRecordDecoder(),
                repository,
                IncidentRunStarter(
                    _synchronized_lifecycle(
                        engine,
                        create_barrier,
                        synchronization_lock,
                        synchronized_lookups,
                    ),
                    _runtime_config(),
                ),
            )
            for _ in range(2)
        ]
        with ThreadPoolExecutor(max_workers=2) as executor:
            concurrent_results = list(
                executor.map(
                    lambda processor: processor.process(duplicate_record),
                    processors,
                )
            )
        assert len(synchronized_lookups) == 2
        assert sorted(
            result.run_start_outcome.value for result in concurrent_results
        ) == [
            "already-started",
            "created",
        ]

        changed_config = _runtime_config(runtime_version="agent-runtime:9.9.9")
        changed_processor = EventIngressProcessor(
            KafkaRecordDecoder(),
            repository,
            IncidentRunStarter(AgentRunLifecycleService(engine), changed_config),
        )
        changed_result = changed_processor.process(duplicate_record)
        assert changed_result.run_start_outcome is RunStartOutcome.ALREADY_STARTED
        real_processor = processors[0]

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
            stored_run = (
                connection.execute(
                    text(
                        """
                    SELECT incident_id, runtime_version
                    FROM agent_runs
                    """
                    )
                )
                .mappings()
                .one()
            )
            assert stored_run["incident_id"] == incident_id
            assert stored_run["runtime_version"] == "agent-runtime:0.1.0"
            assert connection.scalar(text("SELECT COUNT(*) FROM agent_runs")) == 1
            assert (
                connection.scalar(text("SELECT COUNT(*) FROM agent_run_transitions"))
                == 1
            )
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

        with engine.begin() as connection:
            connection.execute(
                text("UPDATE agent_runs SET incident_id=:incident_id"),
                {"incident_id": "QI-" + "B" * 64},
            )
        try:
            with pytest.raises(RunStartIntegrityError, match="Incident"):
                real_processor.process(duplicate_record)
        finally:
            with engine.begin() as connection:
                connection.execute(
                    text("UPDATE agent_runs SET incident_id=:incident_id"),
                    {"incident_id": incident_id},
                )
        engine.dispose()


def _runtime_config(
    *,
    runtime_version: str = "agent-runtime:0.1.0",
) -> AgentRuntimeConfig:
    return AgentRuntimeConfig(
        runtime_version=runtime_version,
        workflow_version="incident-workflow:0.1.0",
        prompt_set_version="prompt-set:0.1.0",
        model_policy_version="model-policy:0.1.0",
        tool_policy_version="tool-policy:0.1.0",
        context_policy_version="context-policy:0.1.0",
        code_revision="651228b9d71ee81e80e6a5030e4c49a50ec60f88",
    )


def _synchronized_lifecycle(
    engine,
    barrier: Barrier,
    synchronization_lock: Lock,
    synchronized_lookups: list[str],
) -> AgentRunLifecycleService:
    lifecycle = AgentRunLifecycleService(engine)
    original_find = lifecycle._repository.find_run_by_trigger_event
    first_lookup = True

    def find_after_both_requests_reach_create(trigger_event_id: str):
        nonlocal first_lookup
        existing = original_find(trigger_event_id)
        if first_lookup and existing is None:
            first_lookup = False
            with synchronization_lock:
                synchronized_lookups.append(trigger_event_id)
            barrier.wait(timeout=10)
        return existing

    lifecycle._repository.find_run_by_trigger_event = (
        find_after_both_requests_reach_create
    )
    return lifecycle
