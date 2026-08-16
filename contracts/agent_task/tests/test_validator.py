import copy
import json
from pathlib import Path

import pytest

from contracts.agent_task.validator import (
    AgentTaskValidationError,
    canonicalize_task,
    classify_task_relation,
    compute_task_key,
    validate_task,
)

ROOT = Path(__file__).resolve().parents[1]


def fixture(category: str, name: str) -> dict[str, object]:
    return json.loads((ROOT / "fixtures" / category / name).read_text(encoding="utf-8"))


def issue(task: dict[str, object]) -> tuple[str, str]:
    with pytest.raises(AgentTaskValidationError) as caught:
        validate_task(task)
    item = caught.value.issues[0]
    return item.code, item.path


def test_accepts_pending_success_and_failure() -> None:
    validate_task(fixture("valid", "quality-pending.json"))
    validate_task(fixture("valid", "risk-succeeded.json"))
    validate_task(fixture("valid", "production-failed.json"))


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (
            "unsupported-version.json",
            ("unsupported_contract_version", "$.contract_version"),
        ),
        ("ground-truth-leak.json", ("schema_validation_failed", "$.ground_truth")),
        ("task-key-mismatch.json", ("task_key_mismatch", "$.identity.task_key")),
        (
            "role-type-mismatch.json",
            ("task_role_mismatch", "$.assignment.target_agent_role"),
        ),
        (
            "self-dependency.json",
            ("task_self_dependency", "$.input.dependency_task_ids[0]"),
        ),
        (
            "duplicate-evidence.json",
            ("duplicate_reference", "$.input.evidence_refs[1]"),
        ),
    ],
)
def test_invalid_fixtures_preserve_boundaries(
    name: str, expected: tuple[str, str]
) -> None:
    assert issue(fixture("invalid", name)) == expected


def test_task_key_is_stable_and_request_sensitive() -> None:
    run_id = "RUN-11111111111111111111111111111111"
    first = compute_task_key(run_id, "TQR-" + "1" * 32)
    assert first.startswith("TAK-") and len(first) == 68
    assert first != compute_task_key(run_id, "TQR-" + "2" * 32)


def test_rejects_lifecycle_times_after_updated_at() -> None:
    task = fixture("valid", "risk-succeeded.json")
    lifecycle = task["lifecycle"]
    assert isinstance(lifecycle, dict)
    lifecycle["started_at"] = "2026-08-16T03:00:04.000000Z"
    assert issue(task) == (
        "lifecycle_timestamp_order_invalid",
        "$.lifecycle.started_at",
    )


def test_rejects_non_pending_task_without_reason() -> None:
    task = fixture("valid", "risk-succeeded.json")
    lifecycle = task["lifecycle"]
    assert isinstance(lifecycle, dict)
    lifecycle["status_reason"] = None
    assert issue(task) == ("task_status_reason_required", "$.lifecycle.status_reason")


def test_terminal_failure_cannot_claim_it_is_retryable() -> None:
    task = fixture("valid", "production-failed.json")
    failure = task["failure"]
    assert isinstance(failure, dict)
    failure["recoverability"] = "retryable"
    assert issue(task) == (
        "terminal_task_failure_must_be_non_retryable",
        "$.failure.recoverability",
    )


def test_relation_recognizes_next_revision_and_conflicts() -> None:
    pending = fixture("valid", "quality-pending.json")
    running = copy.deepcopy(pending)
    lifecycle = running["lifecycle"]
    execution = running["execution"]
    assert isinstance(lifecycle, dict) and isinstance(execution, dict)
    lifecycle.update(
        status="RUNNING",
        revision=1,
        updated_at="2026-08-16T01:00:01.000000Z",
        started_at="2026-08-16T01:00:01.000000Z",
        status_reason={"code": "TASK_STARTED", "message": "Execution started."},
    )
    execution.update(
        current_execution_id="EXE-11111111111111111111111111111111",
        attempt_count=1,
    )
    assert classify_task_relation(pending, running) == "same-task-next-revision"

    lifecycle["revision"] = 2
    assert classify_task_relation(pending, running) == "duplicate-conflicting"


def test_relation_identical_distinct_and_immutable_conflict() -> None:
    task = fixture("valid", "quality-pending.json")
    assert classify_task_relation(task, copy.deepcopy(task)) == "duplicate-identical"
    assert (
        classify_task_relation(task, fixture("valid", "risk-succeeded.json"))
        == "distinct"
    )

    changed = copy.deepcopy(task)
    assignment = changed["assignment"]
    assert isinstance(assignment, dict)
    assignment["priority"] = 90
    assert classify_task_relation(task, changed) == "duplicate-conflicting"


def test_canonical_form_ignores_key_order_and_integral_float() -> None:
    first = fixture("valid", "quality-pending.json")
    second = dict(reversed(list(first.items())))
    lifecycle = second["lifecycle"]
    assert isinstance(lifecycle, dict)
    lifecycle["revision"] = 0.0
    assert canonicalize_task(first) == canonicalize_task(second)


def test_invalid_task_is_rejected_before_relation() -> None:
    task = fixture("valid", "quality-pending.json")
    changed = copy.deepcopy(task)
    identity = changed["identity"]
    assert isinstance(identity, dict)
    identity["task_request_id"] = "TQR-" + "A" * 32
    with pytest.raises(AgentTaskValidationError):
        classify_task_relation(task, changed)
