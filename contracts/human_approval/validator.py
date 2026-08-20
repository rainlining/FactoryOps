from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from contracts.risk_decision.validator import (
    RiskDecisionValidationError,
    canonicalize_risk_decision,
)

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


class HumanApprovalValidationError(ValueError):
    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__(
            "; ".join(f"{issue.path}: {issue.message}" for issue in issues)
        )


def compute_approval_key(decision_key: str) -> str:
    return "APK-" + hashlib.sha256(f"v1\n{decision_key}".encode()).hexdigest().upper()


def compute_approval_id(decision_key: str) -> str:
    return "APR-" + compute_approval_key(decision_key)[4:36]


def validate_human_approval(
    payload: Mapping[str, object], risk_decision: Mapping[str, object]
) -> None:
    _validate_payload(payload)
    try:
        canonicalize_risk_decision(risk_decision)
    except RiskDecisionValidationError as error:
        _raise("source_invalid", "$source", f"source Risk Decision is invalid: {error}")

    source_identity = risk_decision["identity"]
    source_gate = risk_decision["gate"]
    identity = payload["identity"]
    request = payload["request"]
    assert all(
        isinstance(value, Mapping)
        for value in (source_identity, source_gate, identity, request)
    )
    if source_identity.get("subject_type") != "FUSION":
        _raise(
            "source_subject_invalid",
            "$source.identity.subject_type",
            "approval source must bind a Fusion Risk Decision",
        )
    if (
        source_gate.get("decision") != "REQUIRE_APPROVAL"
        or source_gate.get("approval_required") is not True
    ):
        _raise(
            "source_gate_invalid",
            "$source.gate.decision",
            "source gate must REQUIRE_APPROVAL",
        )
    for field in (
        "decision_id",
        "decision_key",
        "fusion_id",
        "fusion_key",
        "run_id",
        "coordinator_execution_id",
        "round",
    ):
        if identity.get(field) != source_identity.get(field):
            _raise(
                "source_identity_mismatch",
                f"$.identity.{field}",
                "approval identity does not match source",
            )
    for field in ("proposed_action", "risk_level", "policy_refs", "reason_codes"):
        left, right = request.get(field), source_gate.get(field)
        if field in {"policy_refs", "reason_codes"}:
            left, right = sorted(left), sorted(right)
        if left != right:
            _raise(
                "source_gate_mismatch",
                f"$.request.{field}",
                "approval request does not match source",
            )


def canonicalize_human_approval(payload: Mapping[str, object]) -> bytes:
    _validate_payload(payload)
    normalized = json.loads(json.dumps(payload))
    normalized["request"]["policy_refs"] = sorted(normalized["request"]["policy_refs"])
    normalized["request"]["reason_codes"] = sorted(
        normalized["request"]["reason_codes"]
    )
    return json.dumps(
        normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def classify_human_approval_relation(
    first: Mapping[str, object], second: Mapping[str, object]
) -> str:
    a, b = canonicalize_human_approval(first), canonicalize_human_approval(second)
    first_identity, second_identity = first["identity"], second["identity"]
    assert isinstance(first_identity, Mapping) and isinstance(second_identity, Mapping)
    if first_identity["approval_key"] != second_identity["approval_key"]:
        return "distinct"
    if a == b:
        return "duplicate-identical"
    if _is_next(first, second):
        return "next-revision"
    return "duplicate-conflicting"


def _validate_payload(payload: Mapping[str, object]) -> None:
    version = payload.get("contract_version")
    if version != "1.0.0":
        _raise(
            "unsupported_contract_version",
            "$.contract_version",
            "unsupported contract version",
        )
    schema = json.loads((ROOT / "v1.0.0/schema.json").read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
            payload
        ),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        error = errors[0]
        path = "$" + "".join(
            f"[{part}]" if isinstance(part, int) else f".{part}"
            for part in error.absolute_path
        )
        _raise(
            "schema_validation_failed",
            path,
            f"schema validation failed: {error.message}",
        )
    identity, request, state = payload["identity"], payload["request"], payload["state"]
    assert (
        isinstance(identity, Mapping)
        and isinstance(request, Mapping)
        and isinstance(state, Mapping)
    )
    if identity["approval_key"] != compute_approval_key(str(identity["decision_key"])):
        _raise(
            "approval_key_mismatch",
            "$.identity.approval_key",
            "approval key does not match decision key",
        )
    if identity["approval_id"] != compute_approval_id(str(identity["decision_key"])):
        _raise(
            "approval_id_mismatch",
            "$.identity.approval_id",
            "approval id does not match decision key",
        )
    for field in ("policy_refs", "reason_codes"):
        values = request[field]
        if len(values) != len(set(values)):
            _raise("duplicate_value", f"$.request.{field}", "values must be unique")
    requested = _timestamp(str(request["requested_at"]))
    expires = _timestamp(str(request["expires_at"]))
    if requested >= expires:
        _raise(
            "invalid_time_order",
            "$.request.expires_at",
            "expires_at must be after requested_at",
        )
    outcome = state.get("outcome")
    if isinstance(outcome, Mapping):
        status, actor = state["status"], outcome["actor_type"]
        if status in {"APPROVED", "REJECTED"} and actor != "HUMAN":
            _raise(
                "actor_type_mismatch",
                "$.state.outcome.actor_type",
                "approved or rejected outcome requires HUMAN actor",
            )
        if status == "EXPIRED" and actor != "SYSTEM":
            _raise(
                "actor_type_mismatch",
                "$.state.outcome.actor_type",
                "expired outcome requires SYSTEM actor",
            )
        if _timestamp(str(outcome["decided_at"])) < requested:
            _raise(
                "invalid_time_order",
                "$.state.outcome.decided_at",
                "decided_at cannot precede requested_at",
            )


def _is_next(first: Mapping[str, object], second: Mapping[str, object]) -> bool:
    for field in ("identity", "request"):
        if first[field] != second[field]:
            return False
    first_state, second_state = first["state"], second["state"]
    assert isinstance(first_state, Mapping) and isinstance(second_state, Mapping)
    return (
        first_state["revision"] == 1
        and first_state["status"] == "PENDING"
        and second_state["revision"] == 2
        and second_state["status"] in {"APPROVED", "REJECTED", "EXPIRED"}
    )


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _raise(code: str, path: str, message: str) -> None:
    raise HumanApprovalValidationError((ValidationIssue(code, path, message),))
