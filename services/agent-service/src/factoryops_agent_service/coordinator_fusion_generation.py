from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import Engine

from contracts.coordinator_fusion.validator import compute_fusion_key
from factoryops_agent_service.coordinator_fusion import (
    CoordinatorFusionService,
    FusionSaveOutcome,
    FusionSaveResult,
)
from factoryops_agent_service.execution_lifecycle.service import (
    AgentExecutionLifecycleService,
)
from factoryops_agent_service.specialist_recommendation import (
    SpecialistRecommendationService,
)


class FusionGenerationRejected(ValueError):
    pass


class FusionGenerationFailed(RuntimeError):
    pass


@dataclass(frozen=True)
class CoordinatorFusionProviderProvenance:
    runtime_version: str
    prompt_version: str
    model_policy_version: str
    tool_policy_version: str
    context_policy_version: str
    code_revision: str


@dataclass(frozen=True)
class FusionRecommendationContext:
    recommendation_id: str
    recommendation_key: str
    execution_id: str
    task_id: str
    agent_role: str
    action: str
    severity: str
    confidence: float
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[str, ...]
    details: dict[str, object]


@dataclass(frozen=True)
class FusionGenerationContext:
    coordinator_execution_id: str
    run_id: str
    round: int
    recommendations: tuple[FusionRecommendationContext, ...]
    provenance: CoordinatorFusionProviderProvenance


@dataclass
class FusionCandidateDraft:
    action: str
    rank: int
    score: float
    supporting_roles: list[str]
    opposing_roles: list[str]


@dataclass
class CoordinatorFusionDraft:
    proposed_action: str
    candidates: tuple[FusionCandidateDraft, ...]
    has_conflict: bool
    conflict_codes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    reason_codes: tuple[str, ...]


class CoordinatorFusionProvider(Protocol):
    provenance: CoordinatorFusionProviderProvenance

    def generate(self, context: FusionGenerationContext) -> CoordinatorFusionDraft: ...


class RecordedCoordinatorFusionProvider:
    def __init__(
        self,
        drafts_by_round: dict[int, CoordinatorFusionDraft],
        provenance: CoordinatorFusionProviderProvenance,
    ) -> None:
        self._drafts_by_round = copy.deepcopy(drafts_by_round)
        self.provenance = provenance

    def generate(self, context: FusionGenerationContext) -> CoordinatorFusionDraft:
        draft = self._drafts_by_round.get(context.round)
        if draft is None:
            raise FusionGenerationRejected(
                f"recorded provider is not configured for round: {context.round}"
            )
        return copy.deepcopy(draft)


@dataclass(frozen=True)
class CoordinatorFusionGenerationCommand:
    coordinator_execution_id: str
    round: int
    recommendation_keys: tuple[str, ...]
    generated_at: str


class CoordinatorFusionGenerationService:
    _ROLES = frozenset({"quality", "production", "sla"})

    def __init__(self, engine: Engine) -> None:
        self._executions = AgentExecutionLifecycleService(engine)
        self._recommendations = SpecialistRecommendationService(engine)
        self._fusions = CoordinatorFusionService(engine)

    def generate(
        self,
        command: CoordinatorFusionGenerationCommand,
        provider: CoordinatorFusionProvider,
    ) -> FusionSaveResult:
        self._validate_command(command)
        execution = self._executions.get_execution(command.coordinator_execution_id)
        if execution is None:
            raise FusionGenerationRejected("Coordinator Execution does not exist")
        identity = execution["identity"]
        if identity["agent_role"] != "coordinator":
            raise FusionGenerationRejected("Execution is not a Coordinator")
        provenance = CoordinatorFusionProviderProvenance(
            **{
                field: str(execution["provenance"][field])
                for field in CoordinatorFusionProviderProvenance.__dataclass_fields__
            }
        )
        if getattr(provider, "provenance", None) != provenance:
            raise FusionGenerationRejected(
                "provider provenance does not match frozen Coordinator provenance"
            )
        run_id = str(identity["run_id"])
        key = compute_fusion_key(
            run_id, command.coordinator_execution_id, command.round
        )
        existing = self._fusions.get_by_key(key)
        if existing is not None:
            existing_keys = {
                str(reference["recommendation_key"])
                for reference in existing["inputs"]["recommendations"]
            }
            identical = (
                existing_keys == set(command.recommendation_keys)
                and existing["generated_at"] == command.generated_at
            )
            return FusionSaveResult(
                FusionSaveOutcome.DUPLICATE_IDENTICAL
                if identical
                else FusionSaveOutcome.DUPLICATE_CONFLICTING,
                existing,
            )
        if execution["lifecycle"]["status"] != "RUNNING":
            raise FusionGenerationRejected("Coordinator Execution is not RUNNING")

        sources = self._load_sources(command.recommendation_keys, run_id)
        contexts = tuple(self._source_context(source) for source in sources)
        context = FusionGenerationContext(
            coordinator_execution_id=command.coordinator_execution_id,
            run_id=run_id,
            round=command.round,
            recommendations=contexts,
            provenance=provenance,
        )
        try:
            draft = provider.generate(context)
        except FusionGenerationRejected:
            raise
        except Exception as error:
            raise FusionGenerationFailed(f"fusion provider failed: {error}") from error
        if not isinstance(draft, CoordinatorFusionDraft):
            raise FusionGenerationRejected("fusion provider returned unsupported draft")
        self._validate_draft(draft)
        authorized_evidence = {
            reference for source in contexts for reference in source.evidence_refs
        }
        if not set(draft.evidence_refs).issubset(authorized_evidence):
            raise FusionGenerationRejected(
                "provider Fusion references unauthorized evidence"
            )

        references = [self._source_reference(source) for source in sources]
        present_roles = {str(reference["agent_role"]) for reference in references}
        payload = {
            "contract_version": "1.0.0",
            "identity": {
                "fusion_id": "FUS-" + key[4:36],
                "fusion_key": key,
                "run_id": run_id,
                "coordinator_execution_id": command.coordinator_execution_id,
                "round": command.round,
            },
            "inputs": {
                "recommendations": references,
                "missing_roles": sorted(self._ROLES - present_roles),
            },
            "fusion": {
                "proposed_action": draft.proposed_action,
                "authorization_state": "NOT_EVALUATED",
                "candidates": [asdict(candidate) for candidate in draft.candidates],
                "has_conflict": draft.has_conflict,
                "conflict_codes": list(draft.conflict_codes),
                "evidence_refs": list(draft.evidence_refs),
                "reason_codes": list(draft.reason_codes),
            },
            "generated_at": command.generated_at,
        }
        return self._fusions.save(
            payload,
            expected_execution_provenance=asdict(provenance),
        )

    def _load_sources(
        self, keys: tuple[str, ...], run_id: str
    ) -> list[dict[str, object]]:
        sources: list[dict[str, object]] = []
        roles: set[str] = set()
        for key in keys:
            source = self._recommendations.get_by_key(key)
            if source is None:
                raise FusionGenerationRejected(
                    f"Specialist Recommendation does not exist: {key}"
                )
            identity = source["identity"]
            role = str(identity["agent_role"])
            if identity["run_id"] != run_id:
                raise FusionGenerationRejected(
                    "Specialist Recommendations must belong to Coordinator Run"
                )
            if role in roles:
                raise FusionGenerationRejected(
                    "Specialist Recommendation roles must be unique"
                )
            roles.add(role)
            sources.append(copy.deepcopy(dict(source)))
        return sorted(
            sources,
            key=lambda source: (
                str(source["identity"]["agent_role"]),
                str(source["identity"]["recommendation_key"]),
            ),
        )

    @staticmethod
    def _validate_draft(draft: CoordinatorFusionDraft) -> None:
        string_sequences = (
            draft.conflict_codes,
            draft.evidence_refs,
            draft.reason_codes,
        )
        if (
            not isinstance(draft.proposed_action, str)
            or not isinstance(draft.candidates, tuple)
            or not isinstance(draft.has_conflict, bool)
            or any(
                not isinstance(values, tuple)
                or any(not isinstance(value, str) for value in values)
                for values in string_sequences
            )
        ):
            raise FusionGenerationRejected("fusion provider returned unsupported draft")
        for candidate in draft.candidates:
            if (
                not isinstance(candidate, FusionCandidateDraft)
                or not isinstance(candidate.action, str)
                or not isinstance(candidate.rank, int)
                or isinstance(candidate.rank, bool)
                or not isinstance(candidate.score, (int, float))
                or isinstance(candidate.score, bool)
                or not isinstance(candidate.supporting_roles, list)
                or not isinstance(candidate.opposing_roles, list)
                or any(
                    not isinstance(role, str)
                    for role in candidate.supporting_roles + candidate.opposing_roles
                )
            ):
                raise FusionGenerationRejected(
                    "fusion provider returned unsupported draft"
                )

    @staticmethod
    def _source_context(source: dict[str, object]) -> FusionRecommendationContext:
        identity = source["identity"]
        recommendation = source["recommendation"]
        return FusionRecommendationContext(
            recommendation_id=str(identity["recommendation_id"]),
            recommendation_key=str(identity["recommendation_key"]),
            execution_id=str(identity["execution_id"]),
            task_id=str(identity["task_id"]),
            agent_role=str(identity["agent_role"]),
            action=str(recommendation["action"]),
            severity=str(recommendation["severity"]),
            confidence=float(recommendation["confidence"]),
            evidence_refs=tuple(recommendation["evidence_refs"]),
            reason_codes=tuple(recommendation["reason_codes"]),
            details=copy.deepcopy(dict(source["details"])),
        )

    @staticmethod
    def _source_reference(source: dict[str, object]) -> dict[str, object]:
        identity = source["identity"]
        recommendation = source["recommendation"]
        return {
            "recommendation_id": identity["recommendation_id"],
            "recommendation_key": identity["recommendation_key"],
            "execution_id": identity["execution_id"],
            "task_id": identity["task_id"],
            "agent_role": identity["agent_role"],
            "action": recommendation["action"],
            "severity": recommendation["severity"],
            "confidence": recommendation["confidence"],
        }

    @staticmethod
    def _validate_command(command: CoordinatorFusionGenerationCommand) -> None:
        if command.round < 1 or command.round > 1000:
            raise FusionGenerationRejected("round must be between 1 and 1000")
        if not 2 <= len(command.recommendation_keys) <= 3 or len(
            set(command.recommendation_keys)
        ) != len(command.recommendation_keys):
            raise FusionGenerationRejected(
                "recommendation keys must contain 2 or 3 unique values"
            )
        if not command.generated_at.endswith("Z"):
            raise FusionGenerationRejected("generated_at must be a UTC timestamp")
        try:
            datetime.fromisoformat(command.generated_at[:-1] + "+00:00")
        except ValueError as error:
            raise FusionGenerationRejected(
                "generated_at must be a UTC timestamp"
            ) from error
