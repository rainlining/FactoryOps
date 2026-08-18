"""Validation for Specialist Recommendation Contract v1.0.0."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

CONTRACT_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


class SpecialistRecommendationValidationError(ValueError):
    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__(
            "; ".join(f"{issue.path}: {issue.message}" for issue in self.issues)
        )


def compute_recommendation_key(execution_id: str) -> str:
    digest = hashlib.sha256(f"v1\n{execution_id}".encode()).hexdigest().upper()
    return "RCK-" + digest


def validate_recommendation(
    recommendation: Mapping[str, object],
    supported_versions: Collection[str] = ("1.0.0",),
) -> None:
    version = recommendation.get("contract_version")
    if not isinstance(version, str) or version not in supported_versions:
        _raise(
            "unsupported_contract_version",
            "$.contract_version",
            f"unsupported contract version: {version!r}",
        )
    _preflight_finite(recommendation)
    _preflight_role_details(recommendation)
    validator = Draft202012Validator(
        _load_schema(version), format_checker=FormatChecker()
    )
    errors = sorted(
        validator.iter_errors(recommendation),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        error = _most_specific_error(errors)
        _raise("schema_validation_failed", _schema_error_path(error), error.message)

    identity = recommendation["identity"]
    common = recommendation["recommendation"]
    details = recommendation["details"]
    assert isinstance(identity, Mapping)
    assert isinstance(common, Mapping)
    assert isinstance(details, Mapping)
    if identity["recommendation_key"] != compute_recommendation_key(
        str(identity["execution_id"])
    ):
        _raise(
            "recommendation_key_mismatch",
            "$.identity.recommendation_key",
            "recommendation_key does not match execution_id",
        )
    _unique(common["evidence_refs"], "$.recommendation.evidence_refs")
    _unique(common["reason_codes"], "$.recommendation.reason_codes")
    _unique(common["output_artifact_refs"], "$.recommendation.output_artifact_refs")
    if identity["agent_role"] == "production":
        _unique(details["affected_order_refs"], "$.details.affected_order_refs")
    _finite(common["confidence"], "$.recommendation.confidence")
    if identity["agent_role"] == "sla":
        _finite(details["expected_cost"], "$.details.expected_cost")
        alternatives = details["alternative_costs"]
        assert isinstance(alternatives, Mapping)
        for action, value in alternatives.items():
            _finite(value, f"$.details.alternative_costs.{action}")


def _preflight_finite(recommendation: Mapping[str, object]) -> None:
    common = recommendation.get("recommendation")
    if isinstance(common, Mapping) and "confidence" in common:
        _finite(common["confidence"], "$.recommendation.confidence")
    identity = recommendation.get("identity")
    details = recommendation.get("details")
    if not isinstance(identity, Mapping) or not isinstance(details, Mapping):
        return
    if identity.get("agent_role") == "sla":
        if "expected_cost" in details:
            _finite(details["expected_cost"], "$.details.expected_cost")
        alternatives = details.get("alternative_costs")
        if isinstance(alternatives, Mapping):
            for action, value in alternatives.items():
                _finite(value, f"$.details.alternative_costs.{action}")


def _preflight_role_details(recommendation: Mapping[str, object]) -> None:
    identity = recommendation.get("identity")
    details = recommendation.get("details")
    if not isinstance(identity, Mapping) or not isinstance(details, Mapping):
        return
    expected = {
        "quality": {"consecutive_defect_suspected"},
        "production": {
            "estimated_delay_minutes",
            "estimated_downtime_minutes",
            "affected_order_refs",
        },
        "sla": {"expected_cost", "currency", "alternative_costs"},
    }.get(identity.get("agent_role"))
    if expected is not None and set(details) != expected:
        _raise(
            "role_details_mismatch",
            "$.details",
            "details fields do not match agent_role",
        )


def canonicalize_recommendation(recommendation: Mapping[str, object]) -> bytes:
    validate_recommendation(recommendation)
    return json.dumps(
        _normalize_numbers(recommendation),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def classify_recommendation_relation(
    first: Mapping[str, object], second: Mapping[str, object]
) -> str:
    first_bytes = canonicalize_recommendation(first)
    second_bytes = canonicalize_recommendation(second)
    first_identity = first["identity"]
    second_identity = second["identity"]
    assert isinstance(first_identity, Mapping)
    assert isinstance(second_identity, Mapping)
    if first_identity["recommendation_key"] != second_identity["recommendation_key"]:
        return "distinct"
    return (
        "duplicate-identical"
        if first_bytes == second_bytes
        else "duplicate-conflicting"
    )


def _unique(value: object, path: str) -> None:
    assert isinstance(value, list)
    seen: set[object] = set()
    for index, item in enumerate(value):
        if item in seen:
            _raise(
                "duplicate_reference",
                f"{path}[{index}]",
                "array values must be unique",
            )
        seen.add(item)


def _finite(value: object, path: str) -> None:
    if isinstance(value, (int, float)) and not math.isfinite(value):
        _raise("non_finite_number", path, "number must be finite")


def _load_schema(version: str) -> Mapping[str, object]:
    return json.loads(
        (CONTRACT_ROOT / f"v{version}" / "schema.json").read_text(encoding="utf-8")
    )


def _schema_error_path(error: ValidationError) -> str:
    parts = list(error.absolute_path)
    if error.validator == "required" and isinstance(error.instance, Mapping):
        parts.append(
            next(name for name in error.validator_value if name not in error.instance)
        )
    elif error.validator == "additionalProperties" and isinstance(
        error.instance, Mapping
    ):
        parts.append(min(set(error.instance) - set(error.schema.get("properties", {}))))
    return "$" + "".join(
        f"[{part}]" if isinstance(part, int) else f".{part}" for part in parts
    )


def _leaf_errors(error: ValidationError) -> list[ValidationError]:
    if not error.context:
        return [error]
    return [leaf for child in error.context for leaf in _leaf_errors(child)]


def _most_specific_error(errors: Sequence[ValidationError]) -> ValidationError:
    leaves = [leaf for error in errors for leaf in _leaf_errors(error)]
    depth = max(len(error.absolute_path) for error in leaves)
    deepest = [error for error in leaves if len(error.absolute_path) == depth]
    return min(
        deepest, key=lambda error: tuple(str(part) for part in error.absolute_path)
    )


def _raise(code: str, path: str, message: str) -> None:
    raise SpecialistRecommendationValidationError(
        (ValidationIssue(code, path, message),)
    )


def _normalize_numbers(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _normalize_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_numbers(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value
