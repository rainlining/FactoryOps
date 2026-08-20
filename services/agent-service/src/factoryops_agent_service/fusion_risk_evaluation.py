from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import Engine

from contracts.risk_decision.validator import compute_decision_key
from factoryops_agent_service.coordinator_fusion import CoordinatorFusionService
from factoryops_agent_service.risk_decision import (
    RiskDecisionSaveResult,
    RiskDecisionService,
)


class FusionRiskEvaluationRejected(ValueError):
    pass


@dataclass(frozen=True)
class FusionRiskEvaluationCommand:
    fusion_key: str
    generated_at: str


_RISK_BY_ACTION = {
    "PASS": "LOW",
    "RECHECK": "LOW",
    "REJECT_ITEM": "MEDIUM",
    "HOLD_BATCH": "MEDIUM",
    "STOP_LINE": "HIGH",
    "ESCALATE": "HIGH",
}


def evaluate_fusion_policy(fusion: Mapping[str, object]) -> dict[str, object]:
    block = fusion.get("fusion")
    if not isinstance(block, Mapping):
        raise FusionRiskEvaluationRejected(
            "Fusion policy input is missing fusion block"
        )
    action = str(block.get("proposed_action"))
    try:
        risk_level = _RISK_BY_ACTION[action]
    except KeyError as error:
        raise FusionRiskEvaluationRejected(
            f"Fusion proposed action is not supported: {action}"
        ) from error
    has_conflict = bool(block.get("has_conflict"))
    candidates = block.get("candidates")
    if not isinstance(candidates, list):
        raise FusionRiskEvaluationRejected("Fusion candidates are missing")
    winner = next(
        (
            candidate
            for candidate in candidates
            if isinstance(candidate, Mapping)
            and candidate.get("rank") == 1
            and candidate.get("action") == action
        ),
        None,
    )
    if winner is None:
        raise FusionRiskEvaluationRejected(
            "Fusion rank 1 candidate does not match proposed action"
        )

    approval_required = risk_level == "HIGH" or (
        risk_level == "MEDIUM" and has_conflict
    )
    if risk_level == "HIGH":
        reason = "HIGH_RISK_ACTION_REQUIRES_APPROVAL"
    elif approval_required:
        reason = "SPECIALIST_CONFLICT_REQUIRES_APPROVAL"
    elif risk_level == "MEDIUM":
        reason = "MEDIUM_RISK_ACTION_ALLOWED"
    else:
        reason = "LOW_RISK_ACTION_ALLOWED"
    policy_refs = ["policy:risk-action-v1"]
    if has_conflict:
        policy_refs.append("policy:risk-conflict-v1")
    return {
        "proposed_action": action,
        "decision": "REQUIRE_APPROVAL" if approval_required else "ALLOW",
        "risk_level": risk_level,
        "approval_required": approval_required,
        "allowed_actions": [] if approval_required else [action],
        "policy_refs": policy_refs,
        "reason_codes": [reason],
        "confidence": winner["score"],
    }


class FusionRiskEvaluationService:
    def __init__(self, engine: Engine) -> None:
        self._fusion_service = CoordinatorFusionService(engine)
        self._risk_service = RiskDecisionService(engine)

    def evaluate(self, command: FusionRiskEvaluationCommand) -> RiskDecisionSaveResult:
        fusion = self._fusion_service.get_by_key(command.fusion_key)
        if fusion is None:
            raise FusionRiskEvaluationRejected("Fusion does not exist")
        identity = fusion["identity"]
        if not isinstance(identity, Mapping):
            raise FusionRiskEvaluationRejected("Fusion identity is invalid")
        decision_key = compute_decision_key(command.fusion_key)
        decision = {
            "contract_version": "1.1.0",
            "identity": {
                "decision_id": "RSK-" + decision_key[4:36],
                "decision_key": decision_key,
                "subject_type": "FUSION",
                "fusion_id": identity["fusion_id"],
                "fusion_key": identity["fusion_key"],
                "run_id": identity["run_id"],
                "coordinator_execution_id": identity["coordinator_execution_id"],
                "round": identity["round"],
            },
            "gate": evaluate_fusion_policy(fusion),
            "generated_at": command.generated_at,
        }
        return self._risk_service.save(decision)
