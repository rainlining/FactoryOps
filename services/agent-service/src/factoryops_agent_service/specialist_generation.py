from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import Engine, text

from contracts.specialist_recommendation.validator import compute_recommendation_key
from factoryops_agent_service.specialist_recommendation import (
    RecommendationSaveOutcome,
    RecommendationSaveResult,
    SpecialistRecommendationService,
)


class SpecialistGenerationRejected(ValueError):
    pass


class SpecialistGenerationFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class SpecialistGenerationContext:
    execution_id: str
    run_id: str
    task_id: str
    agent_role: str
    task_type: str
    context_snapshot_id: str
    evidence_refs: tuple[str, ...]


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
    def generate(
        self, context: SpecialistGenerationContext
    ) -> SpecialistRecommendationDraft: ...


class RecordedSpecialistProvider:
    def __init__(
        self, drafts_by_role: Mapping[str, SpecialistRecommendationDraft]
    ) -> None:
        self._drafts_by_role = copy.deepcopy(dict(drafts_by_role))

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

    def generate(
        self,
        command: SpecialistRecommendationGenerationCommand,
        provider: SpecialistRecommendationProvider,
    ) -> RecommendationSaveResult:
        key = compute_recommendation_key(command.execution_id)
        existing = self._recommendations.get_by_key(key)
        if existing is not None:
            return RecommendationSaveResult(
                RecommendationSaveOutcome.DUPLICATE_IDENTICAL
                if existing["generated_at"] == command.generated_at
                else RecommendationSaveOutcome.DUPLICATE_CONFLICTING,
                existing,
            )

        pair = self._read_pair(command.execution_id)
        if pair is None:
            raise SpecialistGenerationRejected("Execution does not exist")
        task_id = pair["execution_task_id"]
        role = str(pair["execution_role"])
        if (
            role not in self._SPECIALIST_ROLES
            or pair["execution_status"] != "RUNNING"
            or not isinstance(task_id, str)
        ):
            raise SpecialistGenerationRejected(
                "Execution is not a RUNNING Specialist execution"
            )
        if pair["task_id"] is None:
            raise SpecialistGenerationRejected("Task does not exist")
        self._validate_pair(pair)
        task_evidence = self._load_refs(pair["task_evidence_refs"])
        execution_evidence = self._load_refs(pair["execution_evidence_refs"])
        evidence_refs = tuple(
            dict.fromkeys(
                [
                    *(str(ref) for ref in task_evidence),
                    *(str(ref) for ref in execution_evidence),
                ]
            )
        )
        context = SpecialistGenerationContext(
            execution_id=command.execution_id,
            run_id=str(pair["execution_run_id"]),
            task_id=task_id,
            agent_role=role,
            task_type=str(pair["task_type"]),
            context_snapshot_id=str(pair["execution_context_snapshot_id"]),
            evidence_refs=evidence_refs,
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
        payload = {
            "contract_version": "1.0.0",
            "identity": {
                "recommendation_id": "REC-" + key[4:36],
                "recommendation_key": key,
                "execution_id": command.execution_id,
                "run_id": pair["execution_run_id"],
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
    def _validate_pair(pair: Mapping[str, object]) -> None:
        if (
            pair["task_status"] != "RUNNING"
            or pair["current_execution_id"] != pair["execution_id"]
            or pair["task_run_id"] != pair["execution_run_id"]
            or pair["target_agent_role"] != pair["execution_role"]
            or pair["task_context_snapshot_id"] != pair["execution_context_snapshot_id"]
        ):
            raise SpecialistGenerationRejected(
                "Task and Execution are not the current RUNNING Specialist pair"
            )

    def _read_pair(self, execution_id: str) -> Mapping[str, object] | None:
        with self._engine.connect() as connection:
            return (
                connection.execute(
                    text(
                        """SELECT e.execution_id,e.run_id AS execution_run_id,
                        e.agent_role AS execution_role,e.task_id AS execution_task_id,
                        e.status AS execution_status,
                        e.context_snapshot_id AS execution_context_snapshot_id,
                        e.input_evidence_refs AS execution_evidence_refs,
                        t.task_id,t.run_id AS task_run_id,t.task_type,
                        t.target_agent_role,t.status AS task_status,
                        t.current_execution_id,
                        t.context_snapshot_id AS task_context_snapshot_id,
                        t.evidence_refs AS task_evidence_refs
                        FROM agent_executions e
                        LEFT JOIN agent_tasks t ON t.task_id=e.task_id
                        WHERE e.execution_id=:execution_id"""
                    ),
                    {"execution_id": execution_id},
                )
                .mappings()
                .one_or_none()
            )

    @staticmethod
    def _load_refs(value: object) -> list[object]:
        loaded = json.loads(value) if isinstance(value, str) else value
        return list(loaded) if isinstance(loaded, list) else []
