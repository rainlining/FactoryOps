import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]


class QualityIncidentOpenedSchemaTest(unittest.TestCase):
    def test_v1_schema_exists_and_accepts_the_valid_fixture(self) -> None:
        schema_path = ROOT / "v1.0" / "schema.json"
        self.assertTrue(schema_path.is_file(), "v1.0 schema must exist")

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        payload = json.loads(
            (
                ROOT
                / "fixtures"
                / "valid"
                / "incident-opened.json"
            ).read_text(encoding="utf-8")
        )

        Draft202012Validator(
            schema,
            format_checker=FormatChecker(),
        ).validate(payload)


if __name__ == "__main__":
    unittest.main()
