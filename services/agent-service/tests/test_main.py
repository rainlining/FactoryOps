from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from factoryops_agent_service.event_ingress.main import main, run_forever
from factoryops_agent_service.event_ingress.run_starter import RunStartIntegrityError


class FakeWorker:
    def __init__(self, results: list[object]) -> None:
        self.results = list(results)
        self.calls = 0

    def run_once(self):
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def test_fatal_integrity_failure_is_not_retried() -> None:
    worker = FakeWorker([RunStartIntegrityError("Incident mismatch")])

    with pytest.raises(RunStartIntegrityError):
        run_forever(worker, sleep=lambda _: pytest.fail("must not sleep"))

    assert worker.calls == 1


def test_retryable_failure_waits_and_retries() -> None:
    retryable_error = OperationalError(
        "INSERT INTO agent_workflow_run",
        {},
        RuntimeError("database unavailable"),
    )
    sleeps: list[float] = []
    worker = FakeWorker([retryable_error, object()])

    run_forever(
        worker,
        sleep=sleeps.append,
        stop_after_success=True,
    )

    assert worker.calls == 2
    assert sleeps == [1.0]


def test_invalid_agent_config_fails_before_consumer_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FACTORYOPS_AGENT_DATABASE_URL", "mysql+pymysql://unused")
    monkeypatch.setenv("FACTORYOPS_KAFKA_BOOTSTRAP_SERVERS", "unused:9092")
    monkeypatch.delenv("FACTORYOPS_AGENT_RUNTIME_VERSION", raising=False)
    consumer_created = False

    def fail_if_consumer_is_created(*args, **kwargs):
        nonlocal consumer_created
        consumer_created = True
        raise AssertionError("Consumer must not be created")

    monkeypatch.setattr(
        "factoryops_agent_service.event_ingress.main.Consumer",
        fail_if_consumer_is_created,
    )

    with pytest.raises(ValueError, match="FACTORYOPS_AGENT_RUNTIME_VERSION"):
        main()

    assert consumer_created is False
