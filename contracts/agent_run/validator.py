"""Validation for the versioned FactoryOps Workflow Run Contract."""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

CONTRACT_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


class AgentRunValidationError(ValueError):
    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__(
            "; ".join(f"{issue.path}: {issue.message}" for issue in self.issues)
        )


def _json_path(parts: Sequence[object]) -> str:
    return "$" + "".join(
        f"[{part}]" if isinstance(part, int) else f".{part}" for part in parts
    )


def _schema_for(version: str) -> Mapping[str, object]:
    schema_path = CONTRACT_ROOT / f"v{version}" / "schema.json"
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _schema_error_path(error: ValidationError) -> str:
    parts = list(error.absolute_path)
    if error.validator == "required" and isinstance(error.instance, Mapping):
        missing = next(
            name for name in error.validator_value if name not in error.instance
        )
        parts.append(missing)
    elif error.validator == "additionalProperties" and isinstance(
        error.instance,
        Mapping,
    ):
        declared = error.schema.get("properties", {})
        extra = min(set(error.instance) - set(declared))
        parts.append(extra)
    elif error.validator == "not" and isinstance(error.instance, Mapping):
        forbidden_fields = (
            "replayed_from_run_id",
            "replay_request_id",
            "trigger_event_id",
            "ended_at",
        )
        forbidden = next(
            (field for field in forbidden_fields if field in error.instance),
            None,
        )
        if forbidden is not None:
            parts.append(forbidden)
    return _json_path(parts)


def _leaf_schema_errors(error: ValidationError) -> list[ValidationError]:
    if not error.context:
        return [error]
    return [leaf for child in error.context for leaf in _leaf_schema_errors(child)]


def _most_specific_schema_error(
    errors: Sequence[ValidationError],
) -> ValidationError:
    leaves = [leaf for error in errors for leaf in _leaf_schema_errors(error)]
    deepest_path_length = max(len(error.absolute_path) for error in leaves)
    deepest = [
        error for error in leaves if len(error.absolute_path) == deepest_path_length
    ]
    return min(
        deepest,
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )


def _raise_issue(code: str, path: str, message: str) -> None:
    raise AgentRunValidationError(
        (ValidationIssue(code=code, path=path, message=message),)
    )


def _parse_utc_timestamp(value: object) -> datetime:
    assert isinstance(value, str)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_run(
    run: Mapping[str, object],
    supported_versions: Collection[str] = ("1.0.0",),
) -> None:
    version = run.get("contract_version")
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
        validator.iter_errors(run),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if schema_errors:
        error = _most_specific_schema_error(schema_errors)
        _raise_issue(
            "schema_validation_failed",
            _schema_error_path(error),
            error.message,
        )

    identity = run["identity"]
    lifecycle = run["lifecycle"]
    progress = run["progress"]
    assert isinstance(identity, Mapping)
    assert isinstance(lifecycle, Mapping)
    assert isinstance(progress, Mapping)

    run_id = identity["run_id"]
    if identity["run_kind"] == "original":
        if identity["original_run_id"] != run_id:
            _raise_issue(
                "original_run_id_mismatch",
                "$.identity.original_run_id",
                "an original run must identify itself as the original run",
            )
    else:
        for field in ("original_run_id", "replayed_from_run_id"):
            if identity[field] == run_id:
                _raise_issue(
                    "replay_self_reference",
                    f"$.identity.{field}",
                    "a replay run cannot reference itself",
                )

    started_at = lifecycle.get("started_at")
    ended_at = lifecycle.get("ended_at")
    if (
        started_at is not None
        and ended_at is not None
        and _parse_utc_timestamp(ended_at) < _parse_utc_timestamp(started_at)
    ):
        _raise_issue(
            "lifecycle_timestamp_order_invalid",
            "$.lifecycle.ended_at",
            "ended_at cannot be earlier than started_at",
        )

    if progress["completed_task_count"] > progress["task_count"]:
        _raise_issue(
            "completed_task_count_exceeds_task_count",
            "$.progress.completed_task_count",
            "completed_task_count cannot exceed task_count",
        )


def _normalize_integral_numbers(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _normalize_integral_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_integral_numbers(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def canonicalize_run(run: Mapping[str, object]) -> bytes:
    validate_run(run)
    return json.dumps(
        _normalize_integral_numbers(run),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def classify_run_relation(
    first: Mapping[str, object],
    second: Mapping[str, object],
) -> str:
    first_canonical = canonicalize_run(first)
    second_canonical = canonicalize_run(second)

    first_identity = first["identity"]
    second_identity = second["identity"]
    assert isinstance(first_identity, Mapping)
    assert isinstance(second_identity, Mapping)

    if first_identity["run_id"] != second_identity["run_id"]:
        return "distinct"
    if first_canonical == second_canonical:
        return "duplicate-identical"
    return "duplicate-conflicting"
