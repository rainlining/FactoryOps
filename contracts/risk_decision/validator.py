from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


class RiskDecisionValidationError(ValueError):
    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(f"{i.path}: {i.message}" for i in self.issues))


def compute_decision_key(recommendation_key: str) -> str:
    return (
        "RDK-"
        + hashlib.sha256(f"v1\n{recommendation_key}".encode()).hexdigest().upper()
    )


def validate_risk_decision(
    payload: Mapping[str, object], supported_versions: Collection[str] = ("1.0.0",)
) -> None:
    version = payload.get("contract_version")
    if not isinstance(version, str) or version not in supported_versions:
        _raise(
            "unsupported_contract_version",
            "$.contract_version",
            "unsupported contract version",
        )
    gate = payload.get("gate")
    if isinstance(gate, Mapping):
        confidence = gate.get("confidence")
        if isinstance(confidence, (int, float)) and not math.isfinite(confidence):
            _raise(
                "non_finite_number", "$.gate.confidence", "confidence must be finite"
            )
        _preflight_gate(gate)
    schema = json.loads(
        (ROOT / f"v{version}" / "schema.json").read_text(encoding="utf-8")
    )
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
            payload
        ),
        key=lambda e: tuple(str(p) for p in e.absolute_path),
    )
    if errors:
        error = _most_specific(errors)
        _raise("schema_validation_failed", _path(error), error.message)
    identity = payload["identity"]
    assert isinstance(identity, Mapping)
    if identity["decision_key"] != compute_decision_key(
        str(identity["recommendation_key"])
    ):
        _raise(
            "decision_key_mismatch",
            "$.identity.decision_key",
            "decision_key does not match recommendation_key",
        )
    assert isinstance(gate, Mapping)
    for field in ("allowed_actions", "policy_refs", "reason_codes"):
        _unique(gate[field], f"$.gate.{field}")


def canonicalize_risk_decision(payload: Mapping[str, object]) -> bytes:
    validate_risk_decision(payload)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def classify_risk_decision_relation(
    first: Mapping[str, object], second: Mapping[str, object]
) -> str:
    a, b = canonicalize_risk_decision(first), canonicalize_risk_decision(second)
    fi, si = first["identity"], second["identity"]
    assert isinstance(fi, Mapping) and isinstance(si, Mapping)
    if fi["decision_key"] != si["decision_key"]:
        return "distinct"
    return "duplicate-identical" if a == b else "duplicate-conflicting"


def _preflight_gate(gate: Mapping[str, object]) -> None:
    action, decision = gate.get("proposed_action"), gate.get("decision")
    risk, approval = gate.get("risk_level"), gate.get("approval_required")
    allowed_actions = gate.get("allowed_actions")
    if action == "STOP_LINE" and (
        decision != "REQUIRE_APPROVAL" or risk != "HIGH" or approval is not True
    ):
        _raise(
            "high_risk_approval_required",
            "$.gate",
            "STOP_LINE requires HIGH risk approval",
        )
    if action in {"PASS", "RECHECK"} and risk not in {None, "LOW"}:
        _raise(
            "risk_level_mismatch",
            "$.gate.risk_level",
            "low-risk action requires LOW risk",
        )
    if decision == "REQUIRE_APPROVAL" and approval is not True:
        _raise(
            "approval_flag_mismatch",
            "$.gate.approval_required",
            "approval flag must match decision",
        )
    if decision in {"ALLOW", "BLOCK"} and approval is True:
        _raise(
            "approval_flag_mismatch",
            "$.gate.approval_required",
            "approval flag must match decision",
        )
    if isinstance(allowed_actions, list):
        action_is_allowed = action in allowed_actions
        if decision == "ALLOW" and not action_is_allowed:
            _raise(
                "allowed_action_mismatch",
                "$.gate.allowed_actions",
                "allowed decision must include proposed action",
            )
        if decision in {"BLOCK", "REQUIRE_APPROVAL"} and action_is_allowed:
            _raise(
                "allowed_action_mismatch",
                "$.gate.allowed_actions",
                "non-allowed decision must exclude proposed action",
            )


def _unique(value: object, path: str) -> None:
    assert isinstance(value, list)
    seen: set[object] = set()
    for index, item in enumerate(value):
        if item in seen:
            _raise("duplicate_value", f"{path}[{index}]", "array values must be unique")
        seen.add(item)


def _path(error: ValidationError) -> str:
    parts = list(error.absolute_path)
    if error.validator == "required" and isinstance(error.instance, Mapping):
        parts.append(next(x for x in error.validator_value if x not in error.instance))
    elif error.validator == "additionalProperties" and isinstance(
        error.instance, Mapping
    ):
        parts.append(min(set(error.instance) - set(error.schema.get("properties", {}))))
    return "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in parts)


def _most_specific(errors: Sequence[ValidationError]) -> ValidationError:
    leaves: list[ValidationError] = []

    def add(error: ValidationError) -> None:
        if not error.context:
            leaves.append(error)
        else:
            for child in error.context:
                add(child)

    for error in errors:
        add(error)
    depth = max(len(e.absolute_path) for e in leaves)
    return min(
        (e for e in leaves if len(e.absolute_path) == depth),
        key=lambda e: tuple(str(p) for p in e.absolute_path),
    )


def _raise(code: str, path: str, message: str) -> None:
    raise RiskDecisionValidationError((ValidationIssue(code, path, message),))
