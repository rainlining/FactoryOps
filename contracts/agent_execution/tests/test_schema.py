import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_schema_accepts_all_valid_fixtures() -> None:
    schema_path = ROOT / "v1.0.0" / "schema.json"
    assert schema_path.is_file()
    validator = Draft202012Validator(
        load_json(schema_path),
        format_checker=FormatChecker(),
    )

    for fixture_path in sorted((ROOT / "fixtures" / "valid").glob("*.json")):
        validator.validate(load_json(fixture_path))


def test_all_declared_object_shapes_are_strict() -> None:
    schema = load_json(ROOT / "v1.0.0" / "schema.json")

    def find_objects(node: object) -> list[dict[str, object]]:
        if isinstance(node, dict):
            found = [node] if node.get("type") == "object" else []
            return found + [
                item for value in node.values() for item in find_objects(value)
            ]
        if isinstance(node, list):
            return [item for value in node for item in find_objects(value)]
        return []

    object_schemas = find_objects(schema)
    assert len(object_schemas) >= 8
    assert all(item.get("additionalProperties") is False for item in object_schemas)
