"""Validation for the versioned Vision Inspection Contract."""

from __future__ import annotations

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


class VisionContractValidationError(ValueError):
    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__(
            "; ".join(
                f"{issue.path}: {issue.message}" for issue in self.issues
            )
        )


def _json_path(parts: Sequence[object]) -> str:
    return "$" + "".join(
        f"[{part}]" if isinstance(part, int) else f".{part}"
        for part in parts
    )


def _schema_for(version: str) -> Mapping[str, object]:
    schema_path = CONTRACT_ROOT / f"v{version}" / "schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _schema_error_path(error: ValidationError) -> str:
    parts = list(error.absolute_path)
    if error.validator == "required" and isinstance(error.instance, Mapping):
        missing = next(
            name
            for name in error.validator_value
            if name not in error.instance
        )
        parts.append(missing)
    elif error.validator == "additionalProperties" and isinstance(
        error.instance,
        Mapping,
    ):
        declared = error.schema.get("properties", {})
        extra = sorted(set(error.instance) - set(declared))[0]
        parts.append(extra)
    return _json_path(parts)


def validate_result(
    payload: Mapping[str, object],
    supported_versions: Collection[str] = ("1.0",),
) -> None:
    version = payload.get("contract_version")
    if not isinstance(version, str) or version not in supported_versions:
        raise VisionContractValidationError(
            (
                ValidationIssue(
                    code="unsupported_contract_version",
                    path="$.contract_version",
                    message=f"unsupported contract version: {version!r}",
                ),
            )
        )
    validator = Draft202012Validator(
        _schema_for(version),
        format_checker=FormatChecker(),
    )
    schema_errors = sorted(
        validator.iter_errors(payload),
        key=lambda error: list(error.absolute_path),
    )
    if schema_errors:
        error = schema_errors[0]
        raise VisionContractValidationError(
            (
                ValidationIssue(
                    code="schema_validation_failed",
                    path=_schema_error_path(error),
                    message=error.message,
                ),
            )
        )

    observation = payload["observation"]
    assert isinstance(observation, Mapping)
    score = observation["anomaly_score"]
    threshold = observation["decision_threshold"]
    is_anomaly = observation["is_anomaly"]
    assert isinstance(score, (int, float)) and not isinstance(score, bool)
    assert isinstance(threshold, (int, float)) and not isinstance(threshold, bool)
    assert isinstance(is_anomaly, bool)

    for field_name, value in (
        ("anomaly_score", score),
        ("decision_threshold", threshold),
    ):
        if not math.isfinite(value):
            raise VisionContractValidationError(
                (
                    ValidationIssue(
                        code="non_finite_number",
                        path=f"$.observation.{field_name}",
                        message="must be a finite number",
                    ),
                )
            )

    if is_anomaly != (score >= threshold):
        raise VisionContractValidationError(
            (
                ValidationIssue(
                    code="inconsistent_anomaly_decision",
                    path="$.observation.is_anomaly",
                    message="must equal anomaly_score >= decision_threshold",
                ),
            )
        )


def canonicalize_result(payload: Mapping[str, object]) -> bytes:
    validate_result(payload)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def classify_result_relation(
    first: Mapping[str, object],
    second: Mapping[str, object],
) -> str:
    first_canonical = canonicalize_result(first)
    second_canonical = canonicalize_result(second)

    if first["result_id"] == second["result_id"]:
        if first_canonical == second_canonical:
            return "duplicate-identical"
        return "duplicate-conflicting"
    if first["inspection_id"] == second["inspection_id"]:
        return "same-inspection-new-result"
    return "unrelated-result"
