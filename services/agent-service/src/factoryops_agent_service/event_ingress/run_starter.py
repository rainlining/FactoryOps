from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from factoryops_agent_service.run_lifecycle.model import (
    OperationOutcome,
    OriginalRunCommand,
    RunOperationResult,
)
from factoryops_agent_service.run_lifecycle.service import (
    PersistenceIntegrityError,
    RunCreationRejected,
)

from .model import DecodedEvent, RunStartOutcome
from .runtime_config import AgentRuntimeConfig


@dataclass(frozen=True)
class RunStartResult:
    outcome: RunStartOutcome
    run_id: str


class RunStartIntegrityError(RuntimeError):
    """Raised when persisted Run identity contradicts the trusted Inbox event."""


class RunLifecyclePort(Protocol):
    def create_original_run(
        self,
        command: OriginalRunCommand,
    ) -> RunOperationResult:
        raise NotImplementedError


class IncidentRunStarter:
    def __init__(
        self,
        lifecycle: RunLifecyclePort,
        config: AgentRuntimeConfig,
    ) -> None:
        self._lifecycle = lifecycle
        self._config = config

    def ensure_original_run(self, event: DecodedEvent) -> RunStartResult:
        command = OriginalRunCommand(
            trigger_event_id=event.event_id,
            provenance=self._config.to_provenance(event.incident_id),
        )
        try:
            result = self._lifecycle.create_original_run(command)
        except (PersistenceIntegrityError, RunCreationRejected) as error:
            raise RunStartIntegrityError(str(error)) from error

        run_id, incident_id = self._identity(result.run)
        if incident_id != event.incident_id:
            raise RunStartIntegrityError(
                "persisted Run Incident does not match the trusted Inbox event"
            )
        if result.outcome is OperationOutcome.APPLIED:
            outcome = RunStartOutcome.CREATED
        elif result.outcome in {
            OperationOutcome.DUPLICATE_IDENTICAL,
            OperationOutcome.DUPLICATE_CONFLICTING,
        }:
            outcome = RunStartOutcome.ALREADY_STARTED
        else:
            raise RunStartIntegrityError(
                f"unexpected original Run outcome: {result.outcome.value}"
            )
        return RunStartResult(outcome=outcome, run_id=run_id)

    @staticmethod
    def _identity(run: Mapping[str, object] | None) -> tuple[str, str]:
        if not isinstance(run, Mapping):
            raise RunStartIntegrityError("persisted Run Contract is missing")
        identity = run.get("identity")
        provenance = run.get("provenance")
        if not isinstance(identity, Mapping) or not isinstance(provenance, Mapping):
            raise RunStartIntegrityError("persisted Run Contract sections are missing")
        run_id = identity.get("run_id")
        incident_id = provenance.get("incident_id")
        if not isinstance(run_id, str) or not isinstance(incident_id, str):
            raise RunStartIntegrityError("persisted Run Contract identity is missing")
        return run_id, incident_id
