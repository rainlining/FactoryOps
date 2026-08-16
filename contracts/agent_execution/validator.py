"""Validation and relation semantics for Agent Execution Contract v1.0.0."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

CONTRACT_ROOT = Path(__file__).resolve().parent
SPECIALIST_ROLES = frozenset({"quality", "production", "sla", "risk"})
LEGAL_TRANSITIONS = {
    "PENDING": frozenset({"RUNNING", "CANCELLED"}),
    "RUNNING": frozenset({"SUCCEEDED", "FAILED", "CANCELLED"}),
    "SUCCEEDED": frozenset(),
    "FAILED": frozenset(),
    "CANCELLED": frozenset(),
}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


class AgentExecutionValidationError(ValueError):
    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__(
            "; ".join(f"{item.path}: {item.message}" for item in self.issues)
        )


def compute_execution_key(
    run_id: str, agent_role: str, task_id: str | None, attempt: int
) -> str:
    task_component = task_id if task_id is not None else "-"
    canonical_identity = (
        f"v1\n{run_id}\n{agent_role}\n{task_component}\n{attempt}".encode()
    )
    return "EXK-" + hashlib.sha256(canonical_identity).hexdigest().upper()


def validate_execution(
    execution: Mapping[str, object],
    supported_versions: Collection[str] = ("1.0.0",),
) -> None:
    version = execution.get("contract_version")
    if not isinstance(version, str) or version not in supported_versions:
        _raise_issue(
            "unsupported_contract_version",
            "$.contract_version",
            f"unsupported contract version: {version!r}",
        )

    validator = Draft202012Validator(
        _load_schema(version), format_checker=FormatChecker()
    )
    errors = sorted(
        validator.iter_errors(execution),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        error = _most_specific_error(errors)
        _raise_issue(
            "schema_validation_failed", _schema_error_path(error), error.message
        )

    identity = execution["identity"]
    input_refs = execution["input"]
    lifecycle = execution["lifecycle"]
    result = execution["result"]
    assert isinstance(identity, Mapping)
    assert isinstance(input_refs, Mapping)
    assert isinstance(lifecycle, Mapping)

    expected_key = compute_execution_key(
        str(identity["run_id"]),
        str(identity["agent_role"]),
        input_refs["task_id"] if isinstance(input_refs["task_id"], str) else None,
        int(identity["attempt"]),
    )
    if identity["execution_key"] != expected_key:
        _raise_issue(
            "execution_key_mismatch",
            "$.identity.execution_key",
            "execution_key does not match run_id, agent_role, task_id and attempt",
        )
    if identity["agent_role"] in SPECIALIST_ROLES and input_refs["task_id"] is None:
        _raise_issue(
            "specialist_task_required",
            "$.input.task_id",
            "a specialist execution must reference its assigned task",
        )

    _validate_unique_refs(input_refs["evidence_refs"], "$.input.evidence_refs")
    if isinstance(result, Mapping):
        _validate_unique_refs(
            result["output_artifact_refs"], "$.result.output_artifact_refs"
        )
        _validate_unique_refs(result["evidence_refs"], "$.result.evidence_refs")

    started_at = lifecycle.get("started_at")
    ended_at = lifecycle.get("ended_at")
    if (
        started_at is not None
        and ended_at is not None
        and _timestamp(ended_at) < _timestamp(started_at)
    ):
        _raise_issue(
            "lifecycle_timestamp_order_invalid",
            "$.lifecycle.ended_at",
            "ended_at cannot be earlier than started_at",
        )


def canonicalize_execution(execution: Mapping[str, object]) -> bytes:
    validate_execution(execution)
    return json.dumps(
        _normalize_numbers(execution),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def classify_execution_relation(
    first: Mapping[str, object], second: Mapping[str, object]
) -> str:
    first_canonical = canonicalize_execution(first)
    second_canonical = canonicalize_execution(second)
    first_identity = first["identity"]
    second_identity = second["identity"]
    assert isinstance(first_identity, Mapping)
    assert isinstance(second_identity, Mapping)
    if first_identity["execution_id"] != second_identity["execution_id"]:
        return "distinct"
    if first_canonical == second_canonical:
        return "duplicate-identical"
    if _is_next_revision(first, second):
        return "same-execution-next-revision"
    return "duplicate-conflicting"


def _is_next_revision(
    first: Mapping[str, object], second: Mapping[str, object]
) -> bool:
    for field in ("identity", "provenance", "input"):
        if _canonical_value(first[field]) != _canonical_value(second[field]):
            return False
    first_lifecycle = first["lifecycle"]
    second_lifecycle = second["lifecycle"]
    assert isinstance(first_lifecycle, Mapping)
    assert isinstance(second_lifecycle, Mapping)
    if second_lifecycle["revision"] != first_lifecycle["revision"] + 1:
        return False
    if (
        second_lifecycle["status"]
        not in LEGAL_TRANSITIONS[str(first_lifecycle["status"])]
    ):
        return False
    return _timestamp(second_lifecycle["updated_at"]) >= _timestamp(
        first_lifecycle["updated_at"]
    )


def _validate_unique_refs(value: object, path: str) -> None:
    assert isinstance(value, list)
    seen: set[object] = set()
    for index, reference in enumerate(value):
        if reference in seen:
            _raise_issue(
                "duplicate_reference",
                f"{path}[{index}]",
                "reference arrays cannot contain duplicates",
            )
        seen.add(reference)


def _load_schema(version: str) -> Mapping[str, object]:
    return json.loads(
        (CONTRACT_ROOT / f"v{version}" / "schema.json").read_text(encoding="utf-8")
    )


def _schema_error_path(error: ValidationError) -> str:
    parts = list(error.absolute_path)
    if error.validator == "required" and isinstance(error.instance, Mapping):
        missing = next(
            name for name in error.validator_value if name not in error.instance
        )
        parts.append(missing)
    elif error.validator == "additionalProperties" and isinstance(
        error.instance, Mapping
    ):
        declared = error.schema.get("properties", {})
        parts.append(min(set(error.instance) - set(declared)))
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


def _raise_issue(code: str, path: str, message: str) -> None:
    raise AgentExecutionValidationError((ValidationIssue(code, path, message),))


def _timestamp(value: object) -> datetime:
    assert isinstance(value, str)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _normalize_numbers(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _normalize_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_numbers(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _canonical_value(value: object) -> bytes:
    return json.dumps(
        _normalize_numbers(value), sort_keys=True, separators=(",", ":")
    ).encode()
