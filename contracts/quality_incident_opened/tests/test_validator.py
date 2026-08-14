import copy
import json
import unittest
from pathlib import Path

from contracts.quality_incident_opened.validator import (
    QualityIncidentOpenedValidationError,
    canonicalize_event,
    classify_event_relation,
    derive_event_id,
    validate_event,
)


ROOT = Path(__file__).resolve().parents[1]


def valid_event() -> dict[str, object]:
    fixture_path = ROOT / "fixtures" / "valid" / "incident-opened.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def invalid_event(fixture_name: str) -> dict[str, object]:
    fixture_path = ROOT / "fixtures" / "invalid" / fixture_name
    return json.loads(fixture_path.read_text(encoding="utf-8"))


class QualityIncidentOpenedValidationTest(unittest.TestCase):
    def assert_issue(
        self,
        payload: dict[str, object],
        expected_code: str,
        expected_path: str,
    ) -> None:
        with self.assertRaises(QualityIncidentOpenedValidationError) as caught:
            validate_event(payload)

        issue = caught.exception.issues[0]
        self.assertEqual(issue.code, expected_code)
        self.assertEqual(issue.path, expected_path)

    def test_accepts_valid_event(self) -> None:
        validate_event(valid_event())

    def test_derives_stable_event_id_from_incident_id(self) -> None:
        payload = valid_event()
        incident_id = payload["correlation_id"]
        assert isinstance(incident_id, str)

        self.assertEqual(derive_event_id(incident_id), payload["event_id"])

    def test_rejects_unsupported_version_before_loading_schema(self) -> None:
        payload = valid_event()
        payload["contract_version"] = "1.1"

        self.assert_issue(
            payload,
            "unsupported_contract_version",
            "$.contract_version",
        )

    def test_rejects_unknown_field(self) -> None:
        payload = valid_event()
        payload["ground_truth"] = {"is_anomaly": True}

        self.assert_issue(
            payload,
            "schema_validation_failed",
            "$.ground_truth",
        )

    def test_rejects_non_utc_timestamp(self) -> None:
        payload = valid_event()
        payload["occurred_at"] = "2026-08-14T09:02:03+08:00"

        self.assert_issue(
            payload,
            "schema_validation_failed",
            "$.occurred_at",
        )

    def test_rejects_incident_that_is_not_open(self) -> None:
        payload = valid_event()
        event_payload = payload["payload"]
        assert isinstance(event_payload, dict)
        event_payload["status"] = "CLOSED"

        self.assert_issue(
            payload,
            "schema_validation_failed",
            "$.payload.status",
        )

    def test_rejects_event_id_not_derived_from_incident(self) -> None:
        payload = valid_event()
        payload["event_id"] = "EVT-" + "A" * 64

        self.assert_issue(
            payload,
            "event_id_mismatch",
            "$.event_id",
        )

    def test_rejects_aggregate_id_not_matching_payload(self) -> None:
        payload = valid_event()
        aggregate = payload["aggregate"]
        assert isinstance(aggregate, dict)
        aggregate["id"] = "QI-" + "A" * 64

        self.assert_issue(
            payload,
            "aggregate_id_mismatch",
            "$.aggregate.id",
        )

    def test_rejects_correlation_id_not_matching_payload(self) -> None:
        payload = valid_event()
        payload["correlation_id"] = "QI-" + "A" * 64

        self.assert_issue(
            payload,
            "correlation_id_mismatch",
            "$.correlation_id",
        )

    def test_rejects_causation_id_not_matching_result(self) -> None:
        payload = valid_event()
        payload["causation_id"] = "result-other"

        self.assert_issue(
            payload,
            "causation_id_mismatch",
            "$.causation_id",
        )

    def test_invalid_fixtures_preserve_expected_failure_boundaries(self) -> None:
        cases = (
            (
                "unsupported-version.json",
                "unsupported_contract_version",
                "$.contract_version",
            ),
            (
                "ground-truth-leak.json",
                "schema_validation_failed",
                "$.ground_truth",
            ),
            (
                "event-id-mismatch.json",
                "event_id_mismatch",
                "$.event_id",
            ),
            (
                "causation-id-mismatch.json",
                "causation_id_mismatch",
                "$.causation_id",
            ),
        )

        for fixture_name, expected_code, expected_path in cases:
            with self.subTest(fixture_name=fixture_name):
                self.assert_issue(
                    invalid_event(fixture_name),
                    expected_code,
                    expected_path,
                )


class QualityIncidentOpenedRelationTest(unittest.TestCase):
    def test_canonical_form_ignores_object_key_order(self) -> None:
        first = valid_event()
        second = dict(reversed(list(first.items())))

        self.assertEqual(
            canonicalize_event(first),
            canonicalize_event(second),
        )

    def test_same_id_and_content_is_identical_duplicate(self) -> None:
        first = valid_event()
        second = copy.deepcopy(first)

        self.assertEqual(
            classify_event_relation(first, second),
            "duplicate-identical",
        )

    def test_same_id_with_different_valid_content_is_conflicting(self) -> None:
        first = valid_event()
        second = copy.deepcopy(first)
        producer = second["producer"]
        assert isinstance(producer, dict)
        producer["version"] = "0.1.1"

        self.assertEqual(
            classify_event_relation(first, second),
            "duplicate-conflicting",
        )

    def test_different_id_is_distinct(self) -> None:
        first = valid_event()
        second = copy.deepcopy(first)
        incident_id = "QI-" + "A" * 64
        aggregate = second["aggregate"]
        event_payload = second["payload"]
        assert isinstance(aggregate, dict)
        assert isinstance(event_payload, dict)
        second["event_id"] = derive_event_id(incident_id)
        second["correlation_id"] = incident_id
        aggregate["id"] = incident_id
        event_payload["incident_id"] = incident_id

        self.assertEqual(
            classify_event_relation(first, second),
            "distinct",
        )

    def test_invalid_event_is_rejected_before_relation_classification(self) -> None:
        first = valid_event()
        second = copy.deepcopy(first)
        second["event_type"] = "quality.incident.changed"

        with self.assertRaises(QualityIncidentOpenedValidationError):
            classify_event_relation(first, second)


if __name__ == "__main__":
    unittest.main()
