import copy
import json
import unittest
from pathlib import Path

from contracts.agent_run.validator import (
    AgentRunValidationError,
    canonicalize_run,
    classify_run_relation,
    validate_run,
)

ROOT = Path(__file__).resolve().parents[1]


def load_fixture(category: str, fixture_name: str) -> dict[str, object]:
    fixture_path = ROOT / "fixtures" / category / fixture_name
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def valid_original() -> dict[str, object]:
    return load_fixture("valid", "original-run.json")


def valid_replay() -> dict[str, object]:
    return load_fixture("valid", "replay-run.json")


class AgentRunValidationTest(unittest.TestCase):
    def assert_issue(
        self,
        payload: dict[str, object],
        expected_code: str,
        expected_path: str,
    ) -> None:
        with self.assertRaises(AgentRunValidationError) as caught:
            validate_run(payload)

        issue = caught.exception.issues[0]
        self.assertEqual(issue.code, expected_code)
        self.assertEqual(issue.path, expected_path)

    def test_accepts_valid_original_and_replay(self) -> None:
        validate_run(valid_original())
        validate_run(valid_replay())

    def test_rejects_unsupported_version_before_schema_loading(self) -> None:
        self.assert_issue(
            load_fixture("invalid", "unsupported-version.json"),
            "unsupported_contract_version",
            "$.contract_version",
        )

    def test_invalid_fixtures_preserve_failure_boundaries(self) -> None:
        cases = (
            (
                "ground-truth-leak.json",
                "schema_validation_failed",
                "$.ground_truth",
            ),
            (
                "replay-self-reference.json",
                "replay_self_reference",
                "$.identity.replayed_from_run_id",
            ),
            (
                "short-status-reason-code.json",
                "schema_validation_failed",
                "$.lifecycle.status_reason.code",
            ),
        )

        for fixture_name, expected_code, expected_path in cases:
            with self.subTest(fixture_name=fixture_name):
                self.assert_issue(
                    load_fixture("invalid", fixture_name),
                    expected_code,
                    expected_path,
                )

    def test_rejects_original_identity_mismatch(self) -> None:
        payload = valid_original()
        identity = payload["identity"]
        assert isinstance(identity, dict)
        identity["original_run_id"] = "RUN-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

        self.assert_issue(
            payload,
            "original_run_id_mismatch",
            "$.identity.original_run_id",
        )

    def test_rejects_original_with_replay_request(self) -> None:
        payload = valid_original()
        identity = payload["identity"]
        assert isinstance(identity, dict)
        identity["replay_request_id"] = "RPR-AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

        self.assert_issue(
            payload,
            "schema_validation_failed",
            "$.identity.replay_request_id",
        )

    def test_rejects_replay_without_direct_source(self) -> None:
        payload = valid_replay()
        identity = payload["identity"]
        assert isinstance(identity, dict)
        del identity["replayed_from_run_id"]

        self.assert_issue(
            payload,
            "schema_validation_failed",
            "$.identity.replayed_from_run_id",
        )

    def test_rejects_unknown_status(self) -> None:
        payload = valid_original()
        lifecycle = payload["lifecycle"]
        assert isinstance(lifecycle, dict)
        lifecycle["status"] = "RETRYING"

        self.assert_issue(
            payload,
            "schema_validation_failed",
            "$.lifecycle.status",
        )

    def test_rejects_terminal_run_without_ended_at(self) -> None:
        payload = valid_replay()
        lifecycle = payload["lifecycle"]
        assert isinstance(lifecycle, dict)
        del lifecycle["ended_at"]

        self.assert_issue(
            payload,
            "schema_validation_failed",
            "$.lifecycle.ended_at",
        )

    def test_rejects_non_terminal_run_with_ended_at(self) -> None:
        payload = valid_original()
        lifecycle = payload["lifecycle"]
        assert isinstance(lifecycle, dict)
        lifecycle["ended_at"] = "2026-08-15T01:01:00.000000Z"

        self.assert_issue(
            payload,
            "schema_validation_failed",
            "$.lifecycle.ended_at",
        )

    def test_rejects_completed_count_above_task_count(self) -> None:
        payload = valid_replay()
        progress = payload["progress"]
        assert isinstance(progress, dict)
        progress["completed_task_count"] = 8

        self.assert_issue(
            payload,
            "completed_task_count_exceeds_task_count",
            "$.progress.completed_task_count",
        )

    def test_rejects_replay_that_self_references_original(self) -> None:
        payload = valid_replay()
        identity = payload["identity"]
        assert isinstance(identity, dict)
        identity["original_run_id"] = identity["run_id"]

        self.assert_issue(
            payload,
            "replay_self_reference",
            "$.identity.original_run_id",
        )

    def test_rejects_ended_at_before_started_at(self) -> None:
        payload = copy.deepcopy(valid_replay())
        lifecycle = payload["lifecycle"]
        assert isinstance(lifecycle, dict)
        lifecycle["ended_at"] = "2026-08-15T01:59:59.000000Z"

        self.assert_issue(
            payload,
            "lifecycle_timestamp_order_invalid",
            "$.lifecycle.ended_at",
        )


class AgentRunRelationTest(unittest.TestCase):
    def test_canonical_form_ignores_object_key_order(self) -> None:
        first = valid_original()
        second = dict(reversed(list(first.items())))

        self.assertEqual(canonicalize_run(first), canonicalize_run(second))

    def test_same_id_and_content_is_identical_duplicate(self) -> None:
        first = valid_original()
        second = copy.deepcopy(first)

        self.assertEqual(
            classify_run_relation(first, second),
            "duplicate-identical",
        )

    def test_same_id_with_different_valid_lifecycle_is_conflicting(self) -> None:
        first = valid_original()
        second = copy.deepcopy(first)
        lifecycle = second["lifecycle"]
        assert isinstance(lifecycle, dict)
        lifecycle["revision"] = 1
        lifecycle["updated_at"] = "2026-08-15T01:00:01.000000Z"

        self.assertEqual(
            classify_run_relation(first, second),
            "duplicate-conflicting",
        )

    def test_integral_float_and_integer_have_same_canonical_form(self) -> None:
        first = valid_original()
        second = copy.deepcopy(first)
        lifecycle = second["lifecycle"]
        assert isinstance(lifecycle, dict)
        lifecycle["revision"] = 0.0

        self.assertEqual(canonicalize_run(first), canonicalize_run(second))
        self.assertEqual(
            classify_run_relation(first, second),
            "duplicate-identical",
        )

    def test_different_run_id_is_distinct(self) -> None:
        first = valid_replay()
        second = copy.deepcopy(first)
        identity = second["identity"]
        assert isinstance(identity, dict)
        identity["run_id"] = "RUN-44444444444444444444444444444444"
        identity["replay_request_id"] = "RPR-44444444444444444444444444444444"

        self.assertEqual(
            classify_run_relation(first, second),
            "distinct",
        )

    def test_invalid_run_is_rejected_before_relation_classification(self) -> None:
        first = valid_replay()
        second = copy.deepcopy(first)
        identity = second["identity"]
        assert isinstance(identity, dict)
        identity["replayed_from_run_id"] = identity["run_id"]

        with self.assertRaises(AgentRunValidationError):
            classify_run_relation(first, second)


if __name__ == "__main__":
    unittest.main()
