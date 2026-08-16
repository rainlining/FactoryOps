"""Validation and relation semantics for Agent Task Contract v1.0.0."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

ROOT = Path(__file__).resolve().parent
ROLE_BY_TYPE = {
    "QUALITY_ANALYSIS": "quality",
    "PRODUCTION_ANALYSIS": "production",
    "SLA_ANALYSIS": "sla",
    "RISK_ASSESSMENT": "risk",
}
LEGAL_TRANSITIONS = {
    "PENDING": frozenset({"RUNNING", "CANCELLED", "SKIPPED"}),
    "RUNNING": frozenset({"RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"}),
    "SUCCEEDED": frozenset(),
    "FAILED": frozenset(),
    "CANCELLED": frozenset(),
    "SKIPPED": frozenset(),
}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


class AgentTaskValidationError(ValueError):
    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(f"{i.path}: {i.message}" for i in self.issues))


def compute_task_key(run_id: str, task_request_id: str) -> str:
    raw = f"v1\n{run_id}\n{task_request_id}".encode()
    return "TAK-" + hashlib.sha256(raw).hexdigest().upper()


def validate_task(
    task: Mapping[str, object], supported_versions: Collection[str] = ("1.0.0",)
) -> None:
    version = task.get("contract_version")
    if not isinstance(version, str) or version not in supported_versions:
        _raise(
            "unsupported_contract_version",
            "$.contract_version",
            f"unsupported: {version!r}",
        )
    validator = Draft202012Validator(_schema(version), format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(task), key=lambda e: tuple(map(str, e.absolute_path))
    )
    if errors:
        error = _most_specific(errors)
        _raise("schema_validation_failed", _error_path(error), error.message)

    identity = task["identity"]
    assignment = task["assignment"]
    input_refs = task["input"]
    lifecycle = task["lifecycle"]
    execution = task["execution"]
    completion = task["completion"]
    failure = task["failure"]
    assert all(
        isinstance(value, Mapping)
        for value in (identity, assignment, input_refs, lifecycle, execution)
    )

    expected = compute_task_key(
        str(identity["run_id"]), str(identity["task_request_id"])
    )
    if identity["task_key"] != expected:
        _raise(
            "task_key_mismatch",
            "$.identity.task_key",
            "task_key does not match run_id and task_request_id",
        )
    if assignment["target_agent_role"] != ROLE_BY_TYPE[str(assignment["task_type"])]:
        _raise(
            "task_role_mismatch",
            "$.assignment.target_agent_role",
            "target role does not match task type",
        )

    dependencies = input_refs["dependency_task_ids"]
    assert isinstance(dependencies, list)
    for index, dependency in enumerate(dependencies):
        if dependency == identity["task_id"]:
            _raise(
                "task_self_dependency",
                f"$.input.dependency_task_ids[{index}]",
                "a task cannot depend on itself",
            )
    _unique(dependencies, "$.input.dependency_task_ids")
    _unique(input_refs["evidence_refs"], "$.input.evidence_refs")

    current = execution["current_execution_id"]
    if (
        isinstance(completion, Mapping)
        and completion["successful_execution_id"] != current
    ):
        _raise(
            "completion_execution_mismatch",
            "$.completion.successful_execution_id",
            "completion must reference current execution",
        )
    if isinstance(failure, Mapping) and failure["failed_execution_id"] != current:
        _raise(
            "failure_execution_mismatch",
            "$.failure.failed_execution_id",
            "failure must reference current execution",
        )

    status = lifecycle["status"]
    if status != "PENDING" and lifecycle["status_reason"] is None:
        _raise(
            "task_status_reason_required",
            "$.lifecycle.status_reason",
            "every non-pending task snapshot requires a stable status reason",
        )
    if (
        status == "FAILED"
        and isinstance(failure, Mapping)
        and failure["recoverability"] != "non_retryable"
    ):
        _raise(
            "terminal_task_failure_must_be_non_retryable",
            "$.failure.recoverability",
            "a terminal failed task cannot advertise another retry",
        )

    updated = _time(lifecycle["updated_at"])
    for field in ("created_at", "started_at", "ended_at"):
        value = lifecycle.get(field)
        if value is not None and _time(value) > updated:
            _raise(
                "lifecycle_timestamp_order_invalid",
                f"$.lifecycle.{field}",
                f"{field} cannot be later than updated_at",
            )
    started = lifecycle.get("started_at")
    ended = lifecycle.get("ended_at")
    if started is not None and ended is not None and _time(ended) < _time(started):
        _raise(
            "lifecycle_timestamp_order_invalid",
            "$.lifecycle.ended_at",
            "ended_at cannot be earlier than started_at",
        )


def canonicalize_task(task: Mapping[str, object]) -> bytes:
    validate_task(task)
    return _canonical(task)


def classify_task_relation(
    first: Mapping[str, object], second: Mapping[str, object]
) -> str:
    first_bytes = canonicalize_task(first)
    second_bytes = canonicalize_task(second)
    first_id = first["identity"]
    second_id = second["identity"]
    assert isinstance(first_id, Mapping) and isinstance(second_id, Mapping)
    if (
        first_id["task_key"] == second_id["task_key"]
        and first_id["task_id"] != second_id["task_id"]
    ):
        return "duplicate-conflicting"
    if first_id["task_id"] != second_id["task_id"]:
        return "distinct"
    if first_bytes == second_bytes:
        return "duplicate-identical"
    return (
        "same-task-next-revision"
        if _is_next(first, second)
        else "duplicate-conflicting"
    )


def _is_next(first: Mapping[str, object], second: Mapping[str, object]) -> bool:
    for field in ("identity", "assignment", "input"):
        if _canonical(first[field]) != _canonical(second[field]):
            return False
    a = first["lifecycle"]
    b = second["lifecycle"]
    x = first["execution"]
    y = second["execution"]
    assert all(isinstance(value, Mapping) for value in (a, b, x, y))
    if (
        b["revision"] != a["revision"] + 1
        or b["status"] not in LEGAL_TRANSITIONS[str(a["status"])]
    ):
        return False
    if b["created_at"] != a["created_at"] or _time(b["updated_at"]) < _time(
        a["updated_at"]
    ):
        return False
    if a.get("started_at") is not None and b.get("started_at") != a.get("started_at"):
        return False
    old_attempt, new_attempt = int(x["attempt_count"]), int(y["attempt_count"])
    if new_attempt < old_attempt or new_attempt > old_attempt + 1:
        return False
    return not (
        new_attempt == old_attempt
        and y["current_execution_id"] != x["current_execution_id"]
    )


def _unique(value: object, path: str) -> None:
    assert isinstance(value, list)
    seen: set[object] = set()
    for index, item in enumerate(value):
        if item in seen:
            _raise(
                "duplicate_reference", f"{path}[{index}]", "references cannot repeat"
            )
        seen.add(item)


def _schema(version: str) -> Mapping[str, object]:
    return json.loads(
        (ROOT / f"v{version}" / "schema.json").read_text(encoding="utf-8")
    )


def _leaf(error: ValidationError) -> list[ValidationError]:
    return (
        [error]
        if not error.context
        else [leaf for child in error.context for leaf in _leaf(child)]
    )


def _most_specific(errors: Sequence[ValidationError]) -> ValidationError:
    leaves = [leaf for error in errors for leaf in _leaf(error)]
    depth = max(len(error.absolute_path) for error in leaves)
    return min(
        (e for e in leaves if len(e.absolute_path) == depth),
        key=lambda e: tuple(map(str, e.absolute_path)),
    )


def _error_path(error: ValidationError) -> str:
    parts = list(error.absolute_path)
    if error.validator == "required" and isinstance(error.instance, Mapping):
        parts.append(
            next(name for name in error.validator_value if name not in error.instance)
        )
    elif error.validator == "additionalProperties" and isinstance(
        error.instance, Mapping
    ):
        parts.append(min(set(error.instance) - set(error.schema.get("properties", {}))))
    return "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in parts)


def _raise(code: str, path: str, message: str) -> None:
    raise AgentTaskValidationError((ValidationIssue(code, path, message),))


def _time(value: object) -> datetime:
    assert isinstance(value, str)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _normalize(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return int(value) if isinstance(value, float) and value.is_integer() else value


def _canonical(value: object) -> bytes:
    return json.dumps(
        _normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()
