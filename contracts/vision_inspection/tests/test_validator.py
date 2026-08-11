import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from contracts.vision_inspection.validator import (
    VisionContractValidationError,
    validate_result,
)


ROOT = Path(__file__).resolve().parents[1]


def load_fixture(*parts: str) -> dict[str, object]:
    fixture_path = ROOT / "fixtures" / Path(*parts)
    return json.loads(fixture_path.read_text(encoding="utf-8"))


class VisionInspectionSchemaTest(unittest.TestCase):
    def test_vision_service_fixture_matches_v1_schema(self) -> None:
        schema = json.loads(
            (ROOT / "v1.0" / "schema.json").read_text(encoding="utf-8")
        )
        payload = json.loads(
            (
                ROOT
                / "fixtures"
                / "valid"
                / "vision-service-result.json"
            ).read_text(encoding="utf-8")
        )

        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).validate(payload)


class VisionInspectionSemanticValidationTest(unittest.TestCase):
    def assert_schema_issue_path(
        self,
        fixture_name: str,
        expected_path: str,
    ) -> None:
        payload = load_fixture("invalid", fixture_name)

        with self.assertRaises(VisionContractValidationError) as caught:
            validate_result(payload)

        self.assertEqual(
            caught.exception.issues[0].code,
            "schema_validation_failed",
        )
        self.assertEqual(caught.exception.issues[0].path, expected_path)

    def test_rejects_boolean_that_disagrees_with_score_and_threshold(self) -> None:
        payload = load_fixture("invalid", "anomaly-decision-conflict.json")

        with self.assertRaises(VisionContractValidationError) as caught:
            validate_result(payload)

        self.assertEqual(
            caught.exception.issues[0].code,
            "inconsistent_anomaly_decision",
        )
        self.assertEqual(
            caught.exception.issues[0].path,
            "$.observation.is_anomaly",
        )

    def test_rejects_minor_version_that_consumer_did_not_list(self) -> None:
        payload = load_fixture("invalid", "unsupported-version.json")

        with self.assertRaises(VisionContractValidationError) as caught:
            validate_result(payload, supported_versions=("1.0",))

        self.assertEqual(
            caught.exception.issues[0].code,
            "unsupported_contract_version",
        )
        self.assertEqual(
            caught.exception.issues[0].path,
            "$.contract_version",
        )

    def test_rejects_non_finite_anomaly_score(self) -> None:
        payload = load_fixture("valid", "vision-service-result.json")
        observation = payload["observation"]
        assert isinstance(observation, dict)
        observation["anomaly_score"] = float("nan")

        with self.assertRaises(VisionContractValidationError) as caught:
            validate_result(payload)

        self.assertEqual(caught.exception.issues[0].code, "non_finite_number")
        self.assertEqual(
            caught.exception.issues[0].path,
            "$.observation.anomaly_score",
        )

    def test_fake_result_requires_model_provenance(self) -> None:
        self.assert_schema_issue_path(
            "fake-result-without-model.json",
            "$.model",
        )

    def test_ground_truth_cannot_leak_into_result(self) -> None:
        self.assert_schema_issue_path(
            "ground-truth-leak.json",
            "$.ground_truth",
        )

    def test_business_recommendation_cannot_leak_into_result(self) -> None:
        self.assert_schema_issue_path(
            "unknown-field.json",
            "$.recommended_action",
        )


if __name__ == "__main__":
    unittest.main()
