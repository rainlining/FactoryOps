from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable

from confluent_kafka import Consumer
from sqlalchemy import create_engine

from factoryops_agent_service.run_lifecycle.service import AgentRunLifecycleService

from .decoder import KafkaRecordDecoder
from .kafka_adapter import ConfluentKafkaConsumer
from .migration import migrate
from .processor import EventIngressProcessor
from .repository import MySqlInboxRepository
from .run_starter import IncidentRunStarter, RunStartIntegrityError
from .runtime_config import AgentRuntimeConfig
from .worker import KafkaIngressWorker

TOPIC = "factoryops.quality.incident.v1"
GROUP_ID = "factoryops-agent-event-ingress-v1"


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    database_url = _required("FACTORYOPS_AGENT_DATABASE_URL")
    bootstrap_servers = _required("FACTORYOPS_KAFKA_BOOTSTRAP_SERVERS")
    runtime_config = AgentRuntimeConfig.from_environment(os.environ)

    engine = create_engine(database_url, pool_pre_ping=True)
    migrate(engine)
    native_consumer = Consumer(
        {
            "bootstrap.servers": bootstrap_servers,
            "group.id": GROUP_ID,
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
            "auto.offset.reset": "earliest",
        }
    )
    native_consumer.subscribe([TOPIC])
    consumer = ConfluentKafkaConsumer(native_consumer)
    worker = KafkaIngressWorker(
        consumer,
        EventIngressProcessor(
            KafkaRecordDecoder(),
            MySqlInboxRepository(engine),
            IncidentRunStarter(
                AgentRunLifecycleService(engine),
                runtime_config,
            ),
        ),
    )
    try:
        run_forever(worker)
    finally:
        consumer.close()
        engine.dispose()


def run_forever(
    worker: KafkaIngressWorker,
    *,
    sleep: Callable[[float], None] = time.sleep,
    stop_after_success: bool = False,
) -> None:
    while True:
        try:
            worker.run_once()
        except RunStartIntegrityError:
            raise
        except Exception:  # noqa: BLE001 -- process boundary retries transient adapters
            sleep(1.0)
            continue
        if stop_after_success:
            return


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable is missing: {name}")
    return value
