from __future__ import annotations

import copy
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import Engine

from contracts.specialist_recommendation.validator import compute_recommendation_key
from factoryops_agent_service.execution_lifecycle.service import (
    AgentExecutionLifecycleService,
)
from factoryops_agent_service.specialist_recommendation import (
    RecommendationSaveOutcome,
    RecommendationSaveResult,
    SpecialistRecommendationService,
)
from factoryops_agent_service.task_lifecycle.service import AgentTaskLifecycleService


class SpecialistGenerationRejected(ValueError):
    pass


class SpecialistGenerationFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class SpecialistProviderProvenance:
    runtime_version: str
    prompt_version: str
    model_policy_version: str
    tool_policy_version: str
    context_policy_version: str
    code_revision: str


@dataclass(frozen=True)
class SpecialistGenerationContext:
    execution_id: str
    run_id: str
    task_id: str
    agent_role: str
    task_type: str
    context_snapshot_id: str
    evidence_refs: tuple[str, ...]
    provenance: SpecialistProviderProvenance


@dataclass(frozen=True)
class SpecialistRecommendationDraft:
    action: str
    severity: str
    confidence: float
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[str, ...]
    output_artifact_refs: tuple[str, ...]
    details: dict[str, object]


class SpecialistRecommendationProvider(Protocol):
    provenance: SpecialistProviderProvenance

    def generate(
        self, context: SpecialistGenerationContext
    ) -> SpecialistRecommendationDraft: ...


class RecordedSpecialistProvider:
    def __init__(
        self,
        drafts_by_role: Mapping[str, SpecialistRecommendationDraft],
        provenance: SpecialistProviderProvenance,
    ) -> None:
        self._drafts_by_role = copy.deepcopy(dict(drafts_by_role))
        self.provenance = provenance

    def generate(
        self, context: SpecialistGenerationContext
    ) -> SpecialistRecommendationDraft:
        draft = self._drafts_by_role.get(context.agent_role)
        if draft is None:
            raise SpecialistGenerationRejected(
                f"recorded provider is not configured for role: {context.agent_role}"
            )
        return copy.deepcopy(draft)


@dataclass(frozen=True)
class SpecialistRecommendationGenerationCommand:
    execution_id: str
    generated_at: str


class SpecialistRecommendationGenerationService:
    _SPECIALIST_ROLES = frozenset({"quality", "production", "sla"})

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._recommendations = SpecialistRecommendationService(engine)
        self._executions = AgentExecutionLifecycleService(engine)
        self._tasks = AgentTaskLifecycleService(engine)

    def generate(
        self,
        command: SpecialistRecommendationGenerationCommand,
        provider: SpecialistRecommendationProvider,
    ) -> RecommendationSaveResult:
        self._validate_generated_at(command.generated_at)
        execution = self._executions.get_execution(command.execution_id)
        if execution is None:
            raise SpecialistGenerationRejected("Execution does not exist")
        execution_identity = execution["identity"]
        execution_input = execution["input"]
        task_id = execution_input["task_id"]
        role = str(execution_identity["agent_role"])
        if (
            role not in self._SPECIALIST_ROLES
            or execution["lifecycle"]["status"] != "RUNNING"
            or not isinstance(task_id, str)
        ):
            raise SpecialistGenerationRejected(
                "Execution is not a RUNNING Specialist execution"
            )
        task = self._tasks.get_task(task_id)
        if task is None:
            raise SpecialistGenerationRejected("Task does not exist")
        self._validate_pair(task, execution)
        provenance = SpecialistProviderProvenance(
            **{
                field: str(execution["provenance"][field])
                for field in SpecialistProviderProvenance.__dataclass_fields__
            }
        )
        if getattr(provider, "provenance", None) != provenance:
            raise SpecialistGenerationRejected(
                "provider provenance does not match frozen Execution provenance"
            )
        key = compute_recommendation_key(command.execution_id)
        existing = self._recommendations.get_by_key(key)
        if existing is not None:
            return RecommendationSaveResult(
                RecommendationSaveOutcome.DUPLICATE_IDENTICAL
                if existing["generated_at"] == command.generated_at
                else RecommendationSaveOutcome.DUPLICATE_CONFLICTING,
                existing,
            )

        task_evidence = task["input"]["evidence_refs"]
        execution_evidence = execution_input["evidence_refs"]
        evidence_refs = tuple(
            dict.fromkeys(
                [
                    *task_evidence,
                    *execution_evidence,
                ]
            )
        )
        context = SpecialistGenerationContext(
            execution_id=command.execution_id,
            run_id=str(execution_identity["run_id"]),
            task_id=task_id,
            agent_role=role,
            task_type=str(task["assignment"]["task_type"]),
            context_snapshot_id=str(execution_input["context_snapshot_id"]),
            evidence_refs=evidence_refs,
            provenance=provenance,
        )
        try:
            draft = provider.generate(context)
        except SpecialistGenerationRejected:
            raise
        except Exception as error:
            raise SpecialistGenerationFailed(
                f"specialist provider failed: {error}"
            ) from error
        if not isinstance(draft, SpecialistRecommendationDraft):
            raise SpecialistGenerationRejected(
                "specialist provider returned an unsupported draft"
            )
        if not set(draft.evidence_refs).issubset(evidence_refs):
            raise SpecialistGenerationRejected(
                "provider recommendation references unauthorized evidence"
            )
        if draft.output_artifact_refs:
            raise SpecialistGenerationRejected(
                "provider artifact references require a trusted Artifact boundary"
            )
        payload = {
            "contract_version": "1.0.0",
            "identity": {
                "recommendation_id": "REC-" + key[4:36],
                "recommendation_key": key,
                "execution_id": command.execution_id,
                "run_id": execution_identity["run_id"],
                "task_id": task_id,
                "agent_role": role,
            },
            "recommendation": {
                "action": draft.action,
                "severity": draft.severity,
                "confidence": draft.confidence,
                "evidence_refs": list(draft.evidence_refs),
                "reason_codes": list(draft.reason_codes),
                "output_artifact_refs": list(draft.output_artifact_refs),
            },
            "details": copy.deepcopy(draft.details),
            "generated_at": command.generated_at,
        }
        return self._recommendations.save(payload)

    @staticmethod
    def _validate_pair(
        task: Mapping[str, object], execution: Mapping[str, object]
    ) -> None:
        task_identity = task["identity"]
        task_assignment = task["assignment"]
        task_input = task["input"]
        task_execution = task["execution"]
        execution_identity = execution["identity"]
        execution_input = execution["input"]
        if (
            task["lifecycle"]["status"] != "RUNNING"
            or task_execution["current_execution_id"]
            != execution_identity["execution_id"]
            or task_identity["run_id"] != execution_identity["run_id"]
            or task_assignment["target_agent_role"] != execution_identity["agent_role"]
            or task_input["context_snapshot_id"]
            != execution_input["context_snapshot_id"]
        ):
            raise SpecialistGenerationRejected(
                "Task and Execution are not the current RUNNING Specialist pair"
            )

    @staticmethod
    def _validate_generated_at(value: str) -> None:
        if not value.endswith("Z"):
            raise SpecialistGenerationRejected("generated_at must be a UTC timestamp")
        try:
            datetime.fromisoformat(value[:-1] + "+00:00")
        except ValueError as error:
            raise SpecialistGenerationRejected(
                "generated_at must be a UTC timestamp"
            ) from error
