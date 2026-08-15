from __future__ import annotations

import json
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
VALID_FIXTURE = (
    REPOSITORY_ROOT
    / "contracts"
    / "quality_incident_opened"
    / "fixtures"
    / "valid"
    / "incident-opened.json"
)


@pytest.fixture
def valid_event() -> dict[str, object]:
    return json.loads(VALID_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def valid_payload(valid_event: dict[str, object]) -> bytes:
    return json.dumps(
        valid_event,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
