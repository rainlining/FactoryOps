import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_schema_accepts_valid_fixtures() -> None:
    schema = load(ROOT / "v1.0.0" / "schema.json")
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for path in sorted((ROOT / "fixtures" / "valid").glob("*.json")):
        validator.validate(load(path))


def test_all_object_shapes_are_strict() -> None:
    schema = load(ROOT / "v1.0.0" / "schema.json")

    def objects(node: object) -> list[dict[str, object]]:
        if isinstance(node, dict):
            own = [node] if node.get("type") == "object" else []
            return own + [item for value in node.values() for item in objects(value)]
        if isinstance(node, list):
            return [item for value in node for item in objects(value)]
        return []

    found = objects(schema)
    assert len(found) >= 7
    assert all(item.get("additionalProperties") is False for item in found)
