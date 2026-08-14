"""Validation for the versioned Quality Incident Opened Event Contract."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


CONTRACT_ROOT = Path(__file__).resolve().parent
EVENT_ID_NAMESPACE = "factoryops:event:quality.incident.opened:v1:"


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


class QualityIncidentOpenedValidationError(ValueError):
    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__(
            "; ".join(
                f"{issue.path}: {issue.message}" for issue in self.issues
            )
        )


def derive_event_id(incident_id: str) -> str:
    digest_input = f"{EVENT_ID_NAMESPACE}{incident_id}".encode("utf-8")
    return f"EVT-{hashlib.sha256(digest_input).hexdigest().upper()}"


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


def _raise_issue(code: str, path: str, message: str) -> None:
    raise QualityIncidentOpenedValidationError(
        (ValidationIssue(code=code, path=path, message=message),)
    )


def validate_event(
    event: Mapping[str, object],
    supported_versions: Collection[str] = ("1.0",),
) -> None:
    version = event.get("contract_version")
    if not isinstance(version, str) or version not in supported_versions:
        _raise_issue(
            "unsupported_contract_version",
            "$.contract_version",
            f"unsupported contract version: {version!r}",
        )

    validator = Draft202012Validator(
        _schema_for(version),
        format_checker=FormatChecker(),
    )
    schema_errors = sorted(
        validator.iter_errors(event),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if schema_errors:
        error = schema_errors[0]
        _raise_issue(
            "schema_validation_failed",
            _schema_error_path(error),
            error.message,
        )

    aggregate = event["aggregate"]
    payload = event["payload"]
    assert isinstance(aggregate, Mapping)
    assert isinstance(payload, Mapping)
    incident_id = payload["incident_id"]
    result_id = payload["result_id"]
    assert isinstance(incident_id, str)
    assert isinstance(result_id, str)

    if event["event_id"] != derive_event_id(incident_id):
        _raise_issue(
            "event_id_mismatch",
            "$.event_id",
            "must be deterministically derived from payload.incident_id",
        )
    if aggregate["id"] != incident_id:
        _raise_issue(
            "aggregate_id_mismatch",
            "$.aggregate.id",
            "must equal payload.incident_id",
        )
    if event["correlation_id"] != incident_id:
        _raise_issue(
            "correlation_id_mismatch",
            "$.correlation_id",
            "must equal payload.incident_id",
        )
    if event["causation_id"] != result_id:
        _raise_issue(
            "causation_id_mismatch",
            "$.causation_id",
            "must equal payload.result_id",
        )


def canonicalize_event(event: Mapping[str, object]) -> bytes:
    validate_event(event)
    return json.dumps(
        event,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def classify_event_relation(
    first: Mapping[str, object],
    second: Mapping[str, object],
) -> str:
    first_canonical = canonicalize_event(first)
    second_canonical = canonicalize_event(second)

    if first["event_id"] != second["event_id"]:
        return "distinct"
    if first_canonical == second_canonical:
        return "duplicate-identical"
    return "duplicate-conflicting"
