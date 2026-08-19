import copy
import json
from pathlib import Path

import pytest

from contracts.coordinator_fusion.validator import (
    CoordinatorFusionValidationError,
    canonicalize_coordinator_fusion,
    classify_coordinator_fusion_relation,
    compute_fusion_key,
    validate_coordinator_fusion,
)

ROOT = Path(__file__).resolve().parents[1]
RECOMMENDATION_ROOT = (
    ROOT.parents[0] / "specialist_recommendation" / "fixtures" / "valid"
)


def fixture() -> dict[str, object]:
    return json.loads(
        (ROOT / "fixtures" / "valid" / "three-specialists.json").read_text(
            encoding="utf-8"
        )
    )


def sources() -> list[dict[str, object]]:
    return [
        json.loads((RECOMMENDATION_ROOT / name).read_text(encoding="utf-8"))
        for name in ("quality.json", "production.json", "sla.json")
    ]


def issue(payload: dict[str, object]) -> tuple[str, str]:
    with pytest.raises(CoordinatorFusionValidationError) as caught:
        validate_coordinator_fusion(payload, sources())
    found = caught.value.issues[0]
    return found.code, found.path


def test_accepts_three_specialist_fusion_and_stable_key() -> None:
    validate_coordinator_fusion(fixture(), sources())
    assert (
        compute_fusion_key("RUN-" + "1" * 32, "EXE-" + "A" * 32, 1)
        == "FUK-653931439FAF8B473B1D4980E483206DAF065DBECAD135A0BB9367089E588FCC"
    )


def test_rejects_source_mismatch_and_cross_run() -> None:
    payload = fixture()
    inputs = payload["inputs"]
    assert isinstance(inputs, dict)
    references = inputs["recommendations"]
    assert isinstance(references, list)
    references[0]["confidence"] = 0.1
    assert issue(payload) == (
        "source_recommendation_mismatch",
        "$.inputs.recommendations[0].confidence",
    )

    changed_sources = sources()
    identity = changed_sources[0]["identity"]
    assert isinstance(identity, dict)
    identity["run_id"] = "RUN-" + "F" * 32
    with pytest.raises(CoordinatorFusionValidationError) as caught:
        validate_coordinator_fusion(fixture(), changed_sources)
    assert caught.value.issues[0].code == "cross_run_recommendation"


def test_rejects_role_coverage_duplicates_and_bad_rank() -> None:
    payload = fixture()
    inputs = payload["inputs"]
    assert isinstance(inputs, dict)
    references = inputs["recommendations"]
    assert isinstance(references, list)
    references[1]["agent_role"] = "quality"
    assert issue(payload)[0] == "duplicate_value"

    payload = fixture()
    inputs = payload["inputs"]
    assert isinstance(inputs, dict)
    inputs["missing_roles"] = ["quality"]
    assert issue(payload) == ("role_coverage_mismatch", "$.inputs")

    payload = fixture()
    fusion = payload["fusion"]
    assert isinstance(fusion, dict)
    candidates = fusion["candidates"]
    assert isinstance(candidates, list)
    candidates[1]["rank"] = 3
    assert issue(payload)[0] == "candidate_rank_mismatch"


def test_rejects_authorization_ground_truth_nonfinite_and_conflict_mismatch() -> None:
    payload = fixture()
    fusion = payload["fusion"]
    assert isinstance(fusion, dict)
    fusion["authorization_state"] = "APPROVED"
    assert issue(payload)[0] == "schema_validation_failed"

    payload = fixture()
    payload["ground_truth"] = {"expected_action": "HOLD_BATCH"}
    assert issue(payload) == ("schema_validation_failed", "$.ground_truth")

    payload = fixture()
    fusion = payload["fusion"]
    assert isinstance(fusion, dict)
    candidates = fusion["candidates"]
    assert isinstance(candidates, list)
    candidates[0]["score"] = float("nan")
    assert issue(payload)[0] == "non_finite_number"

    payload = fixture()
    fusion = payload["fusion"]
    assert isinstance(fusion, dict)
    fusion["has_conflict"] = False
    assert issue(payload) == ("conflict_flag_mismatch", "$.fusion.has_conflict")


def test_canonical_normalizes_set_order_numbers_and_candidate_order() -> None:
    first = fixture()
    second = copy.deepcopy(first)
    inputs = second["inputs"]
    fusion = second["fusion"]
    assert isinstance(inputs, dict) and isinstance(fusion, dict)
    inputs["recommendations"].reverse()
    fusion["candidates"].reverse()
    fusion["evidence_refs"].reverse()
    fusion["candidates"][1]["score"] = 1.0
    first_fusion = first["fusion"]
    assert isinstance(first_fusion, dict)
    first_fusion["candidates"][0]["score"] = 1
    assert canonicalize_coordinator_fusion(first) == canonicalize_coordinator_fusion(
        second
    )


def test_relation_identical_conflicting_and_distinct() -> None:
    first = fixture()
    assert (
        classify_coordinator_fusion_relation(first, copy.deepcopy(first))
        == "duplicate-identical"
    )
    changed = copy.deepcopy(first)
    fusion = changed["fusion"]
    assert isinstance(fusion, dict)
    fusion["reason_codes"] = ["MANUAL_REVIEW_SELECTED"]
    assert (
        classify_coordinator_fusion_relation(first, changed) == "duplicate-conflicting"
    )
    other = copy.deepcopy(first)
    identity = other["identity"]
    assert isinstance(identity, dict)
    identity["round"] = 2
    identity["fusion_key"] = compute_fusion_key(
        str(identity["run_id"]), str(identity["coordinator_execution_id"]), 2
    )
    assert classify_coordinator_fusion_relation(first, other) == "distinct"
