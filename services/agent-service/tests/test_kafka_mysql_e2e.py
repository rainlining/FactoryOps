from __future__ import annotations

import socket
import uuid

import pytest
from confluent_kafka import Consumer, Producer, TopicPartition
from confluent_kafka.admin import AdminClient, NewTopic
from sqlalchemy import create_engine, text
from testcontainers.community.mysql import MySqlContainer
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

from factoryops_agent_service.event_ingress.decoder import KafkaRecordDecoder
from factoryops_agent_service.event_ingress.kafka_adapter import (
    ConfluentKafkaConsumer,
)
from factoryops_agent_service.event_ingress.migration import migrate
from factoryops_agent_service.event_ingress.model import IngressOutcome, KafkaRecord
from factoryops_agent_service.event_ingress.processor import EventIngressProcessor
from factoryops_agent_service.event_ingress.repository import MySqlInboxRepository
from factoryops_agent_service.event_ingress.worker import KafkaIngressWorker

TOPIC = "factoryops.quality.incident.v1"


class FailFirstCommitConsumer:
    def __init__(self, delegate: ConfluentKafkaConsumer) -> None:
        self._delegate = delegate
        self._first = True

    def poll(self, timeout_seconds: float) -> KafkaRecord | None:
        return self._delegate.poll(timeout_seconds)

    def commit(self, record: KafkaRecord) -> None:
        if self._first:
            self._first = False
            raise RuntimeError("injected offset commit failure")
        self._delegate.commit(record)

    def seek(self, record: KafkaRecord) -> None:
        self._delegate.seek(record)


def test_db_commit_before_offset_failure_redelivers_as_identical_duplicate(
    valid_event: dict[str, object],
    valid_payload: bytes,
) -> None:
    host_port = _free_port()
    kafka = _kafka(host_port)
    with kafka, MySqlContainer("mysql:8.4") as mysql:
        bootstrap = f"localhost:{host_port}"
        _create_topic(bootstrap)
        produced = _produce(bootstrap, valid_event, valid_payload)

        database_url = mysql.get_connection_url().replace(
            "mysql://",
            "mysql+pymysql://",
            1,
        )
        engine = create_engine(database_url)
        migrate(engine)
        group_id = f"agent-ingress-e2e-{uuid.uuid4()}"
        native = Consumer(
            {
                "bootstrap.servers": bootstrap,
                "group.id": group_id,
                "enable.auto.commit": False,
                "enable.auto.offset.store": False,
                "auto.offset.reset": "earliest",
            }
        )
        native.subscribe([TOPIC])
        adapter = ConfluentKafkaConsumer(native)
        consumer = FailFirstCommitConsumer(adapter)
        worker = KafkaIngressWorker(
            consumer,
            EventIngressProcessor(
                KafkaRecordDecoder(),
                MySqlInboxRepository(engine),
            ),
        )

        try:
            with pytest.raises(RuntimeError, match="offset commit failure"):
                worker.run_once(timeout_seconds=20)

            with engine.connect() as connection:
                assert (
                    connection.scalar(text("SELECT COUNT(*) FROM agent_event_inbox"))
                    == 1
                )
            committed_after_failure = native.committed(
                [TopicPartition(TOPIC, produced.partition())],
                timeout=10,
            )[0].offset
            assert committed_after_failure != produced.offset() + 1

            result = worker.run_once(timeout_seconds=20)

            assert result is not None
            assert result.outcome is IngressOutcome.DUPLICATE_IDENTICAL
            committed_after_retry = native.committed(
                [TopicPartition(TOPIC, produced.partition())],
                timeout=10,
            )[0].offset
            assert committed_after_retry == produced.offset() + 1
            with engine.connect() as connection:
                assert (
                    connection.scalar(text("SELECT COUNT(*) FROM agent_event_inbox"))
                    == 1
                )
        finally:
            adapter.close()
            engine.dispose()


def _kafka(host_port: int) -> DockerContainer:
    container = DockerContainer("apache/kafka:4.1.0")
    container.with_bind_ports(19092, host_port)
    environment = {
        "KAFKA_NODE_ID": "1",
        "KAFKA_PROCESS_ROLES": "broker,controller",
        "KAFKA_LISTENERS": ("CONTROLLER://:9093,PLAINTEXT://:9092,HOST://:19092"),
        "KAFKA_ADVERTISED_LISTENERS": (
            f"PLAINTEXT://localhost:9092,HOST://localhost:{host_port}"
        ),
        "KAFKA_LISTENER_SECURITY_PROTOCOL_MAP": (
            "CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,HOST:PLAINTEXT"
        ),
        "KAFKA_CONTROLLER_QUORUM_VOTERS": "1@localhost:9093",
        "KAFKA_CONTROLLER_LISTENER_NAMES": "CONTROLLER",
        "KAFKA_INTER_BROKER_LISTENER_NAME": "PLAINTEXT",
        "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR": "1",
        "KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR": "1",
        "KAFKA_TRANSACTION_STATE_LOG_MIN_ISR": "1",
        "KAFKA_AUTO_CREATE_TOPICS_ENABLE": "false",
    }
    for name, value in environment.items():
        container.with_env(name, value)
    container.waiting_for(
        LogMessageWaitStrategy("Kafka Server started").with_startup_timeout(60)
    )
    return container


def _create_topic(bootstrap: str) -> None:
    admin = AdminClient({"bootstrap.servers": bootstrap})
    future = admin.create_topics(
        [NewTopic(TOPIC, num_partitions=3, replication_factor=1)]
    )
    future[TOPIC].result(timeout=20)


def _produce(
    bootstrap: str,
    event: dict[str, object],
    payload: bytes,
) -> object:
    producer = Producer({"bootstrap.servers": bootstrap, "acks": "all"})
    delivered: list[object] = []

    def on_delivery(error: object, message: object) -> None:
        if error:
            raise RuntimeError(str(error))
        delivered.append(message)

    incident_id = event["payload"]["incident_id"]
    producer.produce(
        TOPIC,
        key=incident_id.encode(),
        value=payload,
        callback=on_delivery,
    )
    producer.flush(20)
    assert len(delivered) == 1
    return delivered[0]


def _free_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return candidate.getsockname()[1]
