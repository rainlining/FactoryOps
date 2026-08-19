import copy
import json
from pathlib import Path

import pytest

from contracts.risk_decision.validator import (
    RiskDecisionValidationError,
    canonicalize_risk_decision,
    classify_risk_decision_relation,
    compute_decision_key,
    validate_risk_decision,
)

ROOT = Path(__file__).resolve().parents[1]


def fixture() -> dict[str, object]:
    payload = json.loads(
        (ROOT / "fixtures" / "valid" / "stop-line-approval.json").read_text(
            encoding="utf-8"
        )
    )
    return payload


def recommendation_identity() -> dict[str, object]:
    identity = fixture()["identity"]
    assert isinstance(identity, dict)
    return {
        field: identity[field]
        for field in ("recommendation_id", "recommendation_key", "run_id", "task_id")
    }


def issue(payload: dict[str, object]) -> tuple[str, str]:
    with pytest.raises(RiskDecisionValidationError) as caught:
        validate_risk_decision(payload, recommendation_identity())
    found = caught.value.issues[0]
    return found.code, found.path


def test_accepts_stop_line_only_with_approval() -> None:
    validate_risk_decision(fixture(), recommendation_identity())
    assert (
        compute_decision_key(
            "RCK-B221BE3D3DBC757E9FD394930157F16E2098D539CB244DC70A5899232ED9D33E"
        )
        == "RDK-9B300D208C0C63CDD7299688B758CDA7947DFCC7425FB648E93F7B1B4CF1A91D"
    )
    payload = fixture()
    gate = payload["gate"]
    assert isinstance(gate, dict)
    gate.update(decision="ALLOW", approval_required=False)
    assert issue(payload) == ("high_risk_approval_required", "$.gate")


def test_low_risk_action_cannot_claim_high_risk() -> None:
    payload = fixture()
    gate = payload["gate"]
    assert isinstance(gate, dict)
    gate.update(
        proposed_action="PASS",
        decision="ALLOW",
        approval_required=False,
        allowed_actions=["PASS"],
    )
    assert issue(payload) == ("risk_level_mismatch", "$.gate.risk_level")


def test_decision_and_allowed_actions_must_agree() -> None:
    payload = fixture()
    gate = payload["gate"]
    assert isinstance(gate, dict)
    gate["allowed_actions"] = ["STOP_LINE"]
    assert issue(payload) == ("allowed_action_mismatch", "$.gate.allowed_actions")

    payload = fixture()
    gate = payload["gate"]
    assert isinstance(gate, dict)
    gate.update(
        proposed_action="PASS",
        decision="ALLOW",
        risk_level="LOW",
        approval_required=False,
        allowed_actions=[],
    )
    assert issue(payload) == ("allowed_action_mismatch", "$.gate.allowed_actions")


def test_rejects_key_mismatch_duplicates_nonfinite_and_ground_truth() -> None:
    payload = fixture()
    identity = payload["identity"]
    assert isinstance(identity, dict)
    identity["decision_key"] = "RDK-" + "0" * 64
    assert issue(payload) == ("decision_key_mismatch", "$.identity.decision_key")
    payload = fixture()
    gate = payload["gate"]
    assert isinstance(gate, dict)
    gate["policy_refs"] = ["policy:x", "policy:x"]
    assert issue(payload) == ("duplicate_value", "$.gate.policy_refs[1]")
    payload = fixture()
    gate = payload["gate"]
    assert isinstance(gate, dict)
    gate["confidence"] = float("nan")
    assert issue(payload) == ("non_finite_number", "$.gate.confidence")
    payload = fixture()
    payload["ground_truth"] = "ALLOW"
    assert issue(payload) == ("schema_validation_failed", "$.ground_truth")


@pytest.mark.parametrize(
    "field,replacement",
    [
        ("recommendation_id", "REC-" + "F" * 32),
        ("run_id", "RUN-" + "F" * 32),
        ("task_id", "TSK-" + "F" * 32),
    ],
)
def test_rejects_source_recommendation_identity_mismatch(
    field: str, replacement: str
) -> None:
    expected = recommendation_identity()
    expected[field] = replacement
    with pytest.raises(RiskDecisionValidationError) as caught:
        validate_risk_decision(fixture(), expected)
    found = caught.value.issues[0]
    assert (found.code, found.path) == (
        "recommendation_identity_mismatch",
        f"$.identity.{field}",
    )


def test_relation_identical_conflicting_distinct_and_canonical() -> None:
    first = fixture()
    assert (
        classify_risk_decision_relation(first, copy.deepcopy(first))
        == "duplicate-identical"
    )
    changed = copy.deepcopy(first)
    gate = changed["gate"]
    assert isinstance(gate, dict)
    gate["confidence"] = 0.8
    assert classify_risk_decision_relation(first, changed) == "duplicate-conflicting"
    other = copy.deepcopy(first)
    identity = other["identity"]
    assert isinstance(identity, dict)
    identity["recommendation_key"] = "RCK-" + "F" * 64
    identity["decision_key"] = compute_decision_key(str(identity["recommendation_key"]))
    assert classify_risk_decision_relation(first, other) == "distinct"
    assert canonicalize_risk_decision(first) == canonicalize_risk_decision(
        dict(reversed(list(first.items())))
    )
    integral_float = copy.deepcopy(first)
    gate = integral_float["gate"]
    assert isinstance(gate, dict)
    gate["confidence"] = 1.0
    integer = copy.deepcopy(integral_float)
    integer_gate = integer["gate"]
    assert isinstance(integer_gate, dict)
    integer_gate["confidence"] = 1
    assert (
        classify_risk_decision_relation(integral_float, integer)
        == "duplicate-identical"
    )
