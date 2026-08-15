import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class AgentRunSchemaTest(unittest.TestCase):
    def setUp(self) -> None:
        schema_path = ROOT / "v1.0.0" / "schema.json"
        self.assertTrue(schema_path.is_file(), "v1.0.0 schema must exist")
        self.schema = load_json(schema_path)
        self.validator = Draft202012Validator(
            self.schema,
            format_checker=FormatChecker(),
        )

    def test_schema_accepts_original_run_fixture(self) -> None:
        payload = load_json(ROOT / "fixtures" / "valid" / "original-run.json")

        self.validator.validate(payload)

    def test_schema_accepts_replay_run_fixture(self) -> None:
        payload = load_json(ROOT / "fixtures" / "valid" / "replay-run.json")

        self.validator.validate(payload)

    def test_all_declared_object_shapes_are_strict(self) -> None:
        object_schemas = [
            self.schema,
            *(
                value
                for value in self.schema["properties"].values()
                if isinstance(value, dict) and value.get("type") == "object"
            ),
        ]

        self.assertGreaterEqual(len(object_schemas), 6)
        for object_schema in object_schemas:
            with self.subTest(title=object_schema.get("title")):
                self.assertIs(object_schema.get("additionalProperties"), False)


if __name__ == "__main__":
    unittest.main()
