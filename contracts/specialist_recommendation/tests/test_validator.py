import copy
import json
from pathlib import Path

import pytest

from contracts.specialist_recommendation.validator import (
    SpecialistRecommendationValidationError,
    canonicalize_recommendation,
    classify_recommendation_relation,
    compute_recommendation_key,
    validate_recommendation,
)

ROOT = Path(__file__).resolve().parents[1]


def fixture(category: str, name: str) -> dict[str, object]:
    return json.loads((ROOT / "fixtures" / category / name).read_text(encoding="utf-8"))


def issue(payload: dict[str, object]) -> tuple[str, str]:
    with pytest.raises(SpecialistRecommendationValidationError) as caught:
        validate_recommendation(payload)
    found = caught.value.issues[0]
    return found.code, found.path


def test_accepts_all_specialist_role_fixtures() -> None:
    for name in ("quality.json", "production.json", "sla.json"):
        validate_recommendation(fixture("valid", name))


def test_recommendation_key_has_stable_vector() -> None:
    assert compute_recommendation_key("EXE-" + "1" * 32) == (
        "RCK-B221BE3D3DBC757E9FD394930157F16E2098D539CB244DC70A5899232ED9D33E"
    )


def test_rejects_unsupported_version_before_schema_lookup() -> None:
    payload = fixture("valid", "quality.json")
    payload["contract_version"] = "2.0.0"
    assert issue(payload) == (
        "unsupported_contract_version",
        "$.contract_version",
    )


def test_rejects_expected_action_evaluation_label() -> None:
    payload = fixture("valid", "quality.json")
    payload["expected_action"] = "HOLD_BATCH"
    assert issue(payload) == (
        "schema_validation_failed",
        "$.expected_action",
    )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("ground-truth-leak.json", ("schema_validation_failed", "$.ground_truth")),
        ("role-details-mismatch.json", ("role_details_mismatch", "$.details")),
    ],
)
def test_invalid_fixtures_have_stable_paths(
    name: str, expected: tuple[str, str]
) -> None:
    assert issue(fixture("invalid", name)) == expected


def test_rejects_key_mismatch_and_duplicate_arrays() -> None:
    payload = fixture("valid", "quality.json")
    identity = payload["identity"]
    assert isinstance(identity, dict)
    identity["recommendation_key"] = "RCK-" + "0" * 64
    assert issue(payload) == (
        "recommendation_key_mismatch",
        "$.identity.recommendation_key",
    )

    payload = fixture("valid", "quality.json")
    recommendation = payload["recommendation"]
    assert isinstance(recommendation, dict)
    recommendation["evidence_refs"] = ["batch:B17", "batch:B17"]
    assert issue(payload) == (
        "duplicate_reference",
        "$.recommendation.evidence_refs[1]",
    )


@pytest.mark.parametrize(
    ("fixture_name", "owner", "field", "path"),
    [
        ("quality.json", "recommendation", "confidence", "$.recommendation.confidence"),
        ("sla.json", "details", "expected_cost", "$.details.expected_cost"),
    ],
)
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_rejects_non_finite_numbers(
    fixture_name: str, owner: str, field: str, path: str, value: float
) -> None:
    payload = fixture("valid", fixture_name)
    target = payload[owner]
    assert isinstance(target, dict)
    target[field] = value
    assert issue(payload) == ("non_finite_number", path)


def test_role_specific_boundaries_are_strict() -> None:
    production = fixture("valid", "production.json")
    details = production["details"]
    assert isinstance(details, dict)
    details["estimated_delay_minutes"] = 525600
    validate_recommendation(production)
    details["estimated_delay_minutes"] = 525601
    assert issue(production) == (
        "schema_validation_failed",
        "$.details.estimated_delay_minutes",
    )

    sla = fixture("valid", "sla.json")
    sla_details = sla["details"]
    assert isinstance(sla_details, dict)
    sla_details["alternative_costs"] = {}
    assert issue(sla) == (
        "schema_validation_failed",
        "$.details.alternative_costs",
    )


def test_relation_classifies_identical_conflicting_and_distinct() -> None:
    first = fixture("valid", "quality.json")
    assert (
        classify_recommendation_relation(first, copy.deepcopy(first))
        == "duplicate-identical"
    )
    changed = copy.deepcopy(first)
    recommendation = changed["recommendation"]
    assert isinstance(recommendation, dict)
    recommendation["confidence"] = 0.8
    assert classify_recommendation_relation(first, changed) == "duplicate-conflicting"
    assert (
        classify_recommendation_relation(first, fixture("valid", "production.json"))
        == "distinct"
    )


def test_canonical_ignores_key_order_and_integral_float() -> None:
    first = fixture("valid", "sla.json")
    second = dict(reversed(list(first.items())))
    details = second["details"]
    assert isinstance(details, dict)
    details["expected_cost"] = 120
    assert canonicalize_recommendation(first) == canonicalize_recommendation(second)
