from __future__ import annotations

import pytest

from factoryops_agent_service.event_ingress.decoder import KafkaRecordDecoder
from factoryops_agent_service.event_ingress.model import KafkaRecord
from factoryops_agent_service.event_ingress.run_starter import (
    IncidentRunStarter,
    RunStartIntegrityError,
    RunStartOutcome,
)
from factoryops_agent_service.event_ingress.runtime_config import AgentRuntimeConfig
from factoryops_agent_service.run_lifecycle.model import (
    OperationOutcome,
    RunOperationResult,
)
from factoryops_agent_service.run_lifecycle.service import PersistenceIntegrityError

RUN_ID = "RUN-" + "1" * 32


class FakeLifecycle:
    def __init__(self, result: RunOperationResult | Exception) -> None:
        self.result = result
        self.commands: list[object] = []

    def create_original_run(self, command: object) -> RunOperationResult:
        self.commands.append(command)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def runtime_config() -> AgentRuntimeConfig:
    return AgentRuntimeConfig(
        runtime_version="agent-runtime:0.1.0",
        workflow_version="incident-workflow:0.1.0",
        prompt_set_version="prompt-set:0.1.0",
        model_policy_version="model-policy:0.1.0",
        tool_policy_version="tool-policy:0.1.0",
        context_policy_version="context-policy:0.1.0",
        code_revision="651228b9d71ee81e80e6a5030e4c49a50ec60f88",
    )


def contract_run(incident_id: str) -> dict[str, object]:
    return {
        "identity": {"run_id": RUN_ID},
        "provenance": {"incident_id": incident_id},
    }


def decoded_event(valid_event: dict[str, object], valid_payload: bytes):
    incident_id = valid_event["payload"]["incident_id"]
    return KafkaRecordDecoder().decode(
        KafkaRecord("topic", 0, 0, incident_id.encode(), valid_payload)
    )


@pytest.mark.parametrize(
    ("lifecycle_outcome", "expected_outcome"),
    [
        (OperationOutcome.APPLIED, RunStartOutcome.CREATED),
        (OperationOutcome.DUPLICATE_IDENTICAL, RunStartOutcome.ALREADY_STARTED),
        (OperationOutcome.DUPLICATE_CONFLICTING, RunStartOutcome.ALREADY_STARTED),
    ],
)
def test_ensures_original_run_for_same_incident(
    valid_event: dict[str, object],
    valid_payload: bytes,
    lifecycle_outcome: OperationOutcome,
    expected_outcome: RunStartOutcome,
) -> None:
    event = decoded_event(valid_event, valid_payload)
    lifecycle = FakeLifecycle(
        RunOperationResult(lifecycle_outcome, contract_run(event.incident_id))
    )

    result = IncidentRunStarter(lifecycle, runtime_config()).ensure_original_run(event)

    assert result.outcome is expected_outcome
    assert result.run_id == RUN_ID
    command = lifecycle.commands[0]
    assert command.trigger_event_id == event.event_id
    assert command.provenance.incident_id == event.incident_id


def test_rejects_existing_run_for_different_incident(
    valid_event: dict[str, object],
    valid_payload: bytes,
) -> None:
    event = decoded_event(valid_event, valid_payload)
    lifecycle = FakeLifecycle(
        RunOperationResult(
            OperationOutcome.DUPLICATE_CONFLICTING,
            contract_run("QI-" + "B" * 64),
        )
    )

    with pytest.raises(RunStartIntegrityError, match="Incident"):
        IncidentRunStarter(lifecycle, runtime_config()).ensure_original_run(event)


@pytest.mark.parametrize(
    "run",
    [
        None,
        {},
        {"identity": {}, "provenance": {"incident_id": "QI-" + "A" * 64}},
        {"identity": {"run_id": RUN_ID}, "provenance": {}},
    ],
)
def test_rejects_missing_persisted_contract_fields(
    valid_event: dict[str, object],
    valid_payload: bytes,
    run: dict[str, object] | None,
) -> None:
    event = decoded_event(valid_event, valid_payload)
    lifecycle = FakeLifecycle(RunOperationResult(OperationOutcome.APPLIED, run))

    with pytest.raises(RunStartIntegrityError, match="Contract"):
        IncidentRunStarter(lifecycle, runtime_config()).ensure_original_run(event)


def test_converts_persistence_integrity_failure_to_start_integrity_failure(
    valid_event: dict[str, object],
    valid_payload: bytes,
) -> None:
    event = decoded_event(valid_event, valid_payload)
    lifecycle = FakeLifecycle(PersistenceIntegrityError("invalid stored Run"))

    with pytest.raises(RunStartIntegrityError, match="invalid stored Run"):
        IncidentRunStarter(lifecycle, runtime_config()).ensure_original_run(event)
