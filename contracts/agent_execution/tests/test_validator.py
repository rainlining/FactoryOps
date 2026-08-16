import copy
import json
from pathlib import Path

import pytest

from contracts.agent_execution.validator import (
    AgentExecutionValidationError,
    canonicalize_execution,
    classify_execution_relation,
    compute_execution_key,
    validate_execution,
)

ROOT = Path(__file__).resolve().parents[1]


def fixture(category: str, name: str) -> dict[str, object]:
    return json.loads((ROOT / "fixtures" / category / name).read_text(encoding="utf-8"))


def issue(payload: dict[str, object]) -> tuple[str, str]:
    with pytest.raises(AgentExecutionValidationError) as caught:
        validate_execution(payload)
    found = caught.value.issues[0]
    return found.code, found.path


def test_accepts_coordinator_pending_and_specialist_terminal_fixtures() -> None:
    validate_execution(fixture("valid", "coordinator-pending.json"))
    validate_execution(fixture("valid", "quality-succeeded.json"))
    validate_execution(fixture("valid", "quality-failed-retryable.json"))


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (
            "unsupported-version.json",
            ("unsupported_contract_version", "$.contract_version"),
        ),
        ("ground-truth-leak.json", ("schema_validation_failed", "$.ground_truth")),
        (
            "execution-key-mismatch.json",
            ("execution_key_mismatch", "$.identity.execution_key"),
        ),
        (
            "specialist-without-task.json",
            ("specialist_task_required", "$.input.task_id"),
        ),
        (
            "duplicate-evidence.json",
            ("duplicate_reference", "$.input.evidence_refs[1]"),
        ),
    ],
)
def test_invalid_fixtures_preserve_error_boundaries(
    name: str, expected: tuple[str, str]
) -> None:
    assert issue(fixture("invalid", name)) == expected


def test_compute_execution_key_is_stable_and_role_attempt_sensitive() -> None:
    run_id = "RUN-11111111111111111111111111111111"
    assert compute_execution_key(run_id, "coordinator", None, 1) == (
        "EXK-EF3680DE751393D6684481B689CCBF5808F7729DCBB23315C8DE0C955863FEAB"
    )
    assert compute_execution_key(run_id, "quality", "TSK-" + "1" * 32, 1) != (
        compute_execution_key(run_id, "quality", "TSK-" + "2" * 32, 1)
    )


def test_rejects_ended_at_before_started_at() -> None:
    payload = fixture("valid", "quality-succeeded.json")
    lifecycle = payload["lifecycle"]
    assert isinstance(lifecycle, dict)
    lifecycle["ended_at"] = "2026-08-16T01:59:59.000000Z"
    assert issue(payload) == (
        "lifecycle_timestamp_order_invalid",
        "$.lifecycle.ended_at",
    )


def test_relation_distinguishes_next_revision_from_conflict() -> None:
    pending = fixture("valid", "coordinator-pending.json")
    running = copy.deepcopy(pending)
    lifecycle = running["lifecycle"]
    assert isinstance(lifecycle, dict)
    lifecycle.update(
        status="RUNNING",
        revision=1,
        updated_at="2026-08-16T01:00:01.000000Z",
        started_at="2026-08-16T01:00:01.000000Z",
    )
    assert (
        classify_execution_relation(pending, running) == "same-execution-next-revision"
    )

    lifecycle["revision"] = 2
    assert classify_execution_relation(pending, running) == "duplicate-conflicting"


def test_relation_identical_distinct_and_immutable_conflict() -> None:
    first = fixture("valid", "coordinator-pending.json")
    assert (
        classify_execution_relation(first, copy.deepcopy(first))
        == "duplicate-identical"
    )

    distinct = fixture("valid", "quality-succeeded.json")
    assert classify_execution_relation(first, distinct) == "distinct"

    changed = copy.deepcopy(first)
    provenance = changed["provenance"]
    assert isinstance(provenance, dict)
    provenance["model_policy_version"] = "model-policy/v2"
    assert classify_execution_relation(first, changed) == "duplicate-conflicting"


def test_canonical_form_ignores_key_order_and_integral_float() -> None:
    first = fixture("valid", "coordinator-pending.json")
    second = dict(reversed(list(first.items())))
    lifecycle = second["lifecycle"]
    assert isinstance(lifecycle, dict)
    lifecycle["revision"] = 0.0
    assert canonicalize_execution(first) == canonicalize_execution(second)


def test_invalid_payload_is_rejected_before_relation_classification() -> None:
    first = fixture("valid", "coordinator-pending.json")
    second = copy.deepcopy(first)
    identity = second["identity"]
    assert isinstance(identity, dict)
    identity["attempt"] = 2
    with pytest.raises(AgentExecutionValidationError):
        classify_execution_relation(first, second)
