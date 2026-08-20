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


@pytest.fixture
def bound_pending(pending: dict[str, object]) -> dict[str, object]:
    value = copy.deepcopy(pending)
    value["contract_version"] = "1.1.0"
    value["identity"]["incident_id"] = "QI-" + "A" * 64
    return value


@pytest.fixture
def source_run(bound_pending: dict[str, object]) -> dict[str, object]:
    return {
        "contract_version": "1.0.0",
        "identity": {
            "run_id": bound_pending["identity"]["run_id"],
            "run_kind": "original",
            "original_run_id": bound_pending["identity"]["run_id"],
            "trigger_event_id": "EVT-" + "B" * 64,
        },
        "provenance": {
            "incident_id": bound_pending["identity"]["incident_id"],
            "runtime_version": "agent-runtime:0.1.0",
            "workflow_version": "quality-incident-workflow:1.0.0",
            "prompt_set_version": "quality-incident-prompts:1.0.0",
            "model_policy_version": "default-model-policy:1.0.0",
            "tool_policy_version": "quality-tool-policy:1.0.0",
            "context_policy_version": "incident-context-policy:1.0.0",
            "code_revision": "a" * 40,
            "created_at": "2026-08-20T10:00:00Z",
        },
        "lifecycle": {
            "status": "PENDING",
            "revision": 0,
            "updated_at": "2026-08-20T10:00:00Z",
            "status_reason": None,
        },
        "execution_refs": {
            "coordinator_execution_id": None,
            "latest_checkpoint_id": None,
        },
        "progress": {
            "agent_execution_count": 0,
            "task_count": 0,
            "completed_task_count": 0,
        },
    }


def test_v11_binds_incident_to_source_run(bound_pending, source, source_run):
    validate_human_approval(bound_pending, source, source_run)
    changed = copy.deepcopy(bound_pending)
    changed["identity"]["incident_id"] = "QI-" + "F" * 64
    with pytest.raises(HumanApprovalValidationError, match="incident"):
        validate_human_approval(changed, source, source_run)


def test_v11_requires_matching_source_run(bound_pending, source, source_run):
    with pytest.raises(HumanApprovalValidationError, match="source Run"):
        validate_human_approval(bound_pending, source)
    source_run["identity"]["run_id"] = "RUN-" + "F" * 32
    with pytest.raises(HumanApprovalValidationError, match="run"):
        validate_human_approval(bound_pending, source, source_run)


def test_v11_relation_preserves_incident_identity(bound_pending):
    identical = copy.deepcopy(bound_pending)
    assert (
        classify_human_approval_relation(bound_pending, identical)
        == "duplicate-identical"
    )
    changed = copy.deepcopy(bound_pending)
    changed["identity"]["incident_id"] = "QI-" + "F" * 64
    assert (
        classify_human_approval_relation(bound_pending, changed)
        == "duplicate-conflicting"
    )


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


@pytest.mark.parametrize(
    ("status", "actor", "decided_at", "valid"),
    [
        ("APPROVED", "HUMAN", "2026-08-20T11:59:59Z", True),
        ("APPROVED", "HUMAN", "2026-08-20T12:00:00Z", False),
        ("REJECTED", "HUMAN", "2026-08-20T12:00:01Z", False),
        ("EXPIRED", "SYSTEM", "2026-08-20T11:59:59Z", False),
        ("EXPIRED", "SYSTEM", "2026-08-20T12:00:00Z", True),
        ("EXPIRED", "SYSTEM", "2026-08-20T12:00:01Z", True),
    ],
)
def test_outcome_respects_expiry_boundary(
    pending, source, status, actor, decided_at, valid
):
    terminal = copy.deepcopy(pending)
    terminal["state"] = {
        "revision": 2,
        "status": status,
        "outcome": {
            "actor_type": actor,
            "actor_id": "user:owner" if actor == "HUMAN" else "system:expiry",
            "decided_at": decided_at,
            "reason_code": "OWNER_DECIDED" if actor == "HUMAN" else "APPROVAL_EXPIRED",
        },
    }
    if valid:
        validate_human_approval(terminal, source)
    else:
        with pytest.raises(HumanApprovalValidationError, match="expires_at"):
            validate_human_approval(terminal, source)


def test_next_revision_ignores_set_array_order(pending, source):
    terminal = copy.deepcopy(pending)
    terminal["request"]["policy_refs"].reverse()
    terminal["request"]["reason_codes"].reverse()
    terminal["state"] = {
        "revision": 2,
        "status": "APPROVED",
        "outcome": {
            "actor_type": "HUMAN",
            "actor_id": "user:owner",
            "decided_at": "2026-08-20T11:59:59Z",
            "reason_code": "OWNER_APPROVED",
        },
    }
    validate_human_approval(terminal, source)
    assert classify_human_approval_relation(pending, terminal) == "next-revision"


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
