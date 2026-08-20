from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from contracts.human_approval.validator import (
    HumanApprovalValidationError,
    canonicalize_human_approval,
    classify_human_approval_relation,
    compute_approval_id,
    compute_approval_key,
    validate_human_approval,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def pending() -> dict[str, object]:
    return json.loads((ROOT / "fixtures/valid/pending.json").read_text())


@pytest.fixture
def source(pending: dict[str, object]) -> dict[str, object]:
    identity = pending["identity"]
    request = pending["request"]
    return {
        "contract_version": "1.1.0",
        "identity": {
            key: identity[key]
            for key in (
                "decision_id",
                "decision_key",
                "fusion_id",
                "fusion_key",
                "run_id",
                "coordinator_execution_id",
                "round",
            )
        }
        | {"subject_type": "FUSION"},
        "gate": {
            "proposed_action": request["proposed_action"],
            "decision": "REQUIRE_APPROVAL",
            "risk_level": request["risk_level"],
            "approval_required": True,
            "allowed_actions": [],
            "policy_refs": request["policy_refs"],
            "reason_codes": request["reason_codes"],
            "confidence": 0.9,
        },
        "generated_at": "2026-08-20T10:59:00Z",
    }


def test_pending_binds_source_and_key(pending, source):
    validate_human_approval(pending, source)
    assert pending["identity"]["approval_key"] == compute_approval_key(
        source["identity"]["decision_key"]
    )


def test_approved_is_valid_next_revision(pending, source):
    approved = copy.deepcopy(pending)
    approved["state"] = {
        "revision": 2,
        "status": "APPROVED",
        "outcome": {
            "actor_type": "HUMAN",
            "actor_id": "user:owner",
            "decided_at": "2026-08-20T11:30:00Z",
            "reason_code": "OWNER_APPROVED",
        },
    }
    validate_human_approval(approved, source)
    assert classify_human_approval_relation(pending, approved) == "next-revision"


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda p: p["identity"].update(decision_key="RDK-" + "F" * 64), "key"),
        (lambda p: p["request"].update(proposed_action="HOLD_BATCH"), "source"),
        (lambda p: p["state"].update(revision=2), "revision"),
        (lambda p: p.update(ground_truth="hidden"), "schema"),
    ],
)
def test_invalid_payload_is_rejected(pending, source, mutation, match):
    mutation(pending)
    with pytest.raises(HumanApprovalValidationError, match=match):
        validate_human_approval(pending, source)


def test_non_approval_source_is_rejected(pending, source):
    source["gate"]["proposed_action"] = "HOLD_BATCH"
    source["gate"]["risk_level"] = "MEDIUM"
    source["gate"]["decision"] = "ALLOW"
    source["gate"]["approval_required"] = False
    source["gate"]["allowed_actions"] = ["HOLD_BATCH"]
    with pytest.raises(HumanApprovalValidationError, match="REQUIRE_APPROVAL"):
        validate_human_approval(pending, source)


def test_actor_and_terminal_transition_rules(pending, source):
    approved = copy.deepcopy(pending)
    approved["state"] = {
        "revision": 2,
        "status": "APPROVED",
        "outcome": {
            "actor_type": "SYSTEM",
            "actor_id": "system:expiry",
            "decided_at": "2026-08-20T11:30:00Z",
            "reason_code": "OWNER_APPROVED",
        },
    }
    with pytest.raises(HumanApprovalValidationError, match="HUMAN"):
        validate_human_approval(approved, source)

    valid = copy.deepcopy(approved)
    valid["state"]["outcome"]["actor_type"] = "HUMAN"
    validate_human_approval(valid, source)
    later = copy.deepcopy(valid)
    later["state"]["status"] = "REJECTED"
    assert classify_human_approval_relation(valid, later) == "duplicate-conflicting"


def test_canonical_and_relation_ignore_set_order_and_integer_float(pending):
    other = copy.deepcopy(pending)
    other["request"]["policy_refs"].reverse()
    other["request"]["reason_codes"].reverse()
    assert canonicalize_human_approval(pending) == canonicalize_human_approval(other)
    assert classify_human_approval_relation(pending, other) == "duplicate-identical"

    distinct = copy.deepcopy(pending)
    distinct["identity"]["decision_key"] = "RDK-" + "B" * 64
    distinct["identity"]["approval_id"] = compute_approval_id(
        distinct["identity"]["decision_key"]
    )
    distinct["identity"]["approval_key"] = compute_approval_key(
        distinct["identity"]["decision_key"]
    )
    assert classify_human_approval_relation(pending, distinct) == "distinct"
