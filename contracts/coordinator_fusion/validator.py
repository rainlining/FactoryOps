from __future__ import annotations

import copy
import hashlib
import json
import math
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from contracts.specialist_recommendation.validator import validate_recommendation

ROOT = Path(__file__).resolve().parent
ROLE_ORDER = {"quality": 0, "production": 1, "sla": 2}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


class CoordinatorFusionValidationError(ValueError):
    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(f"{i.path}: {i.message}" for i in self.issues))


def compute_fusion_key(run_id: str, coordinator_execution_id: str, round: int) -> str:
    material = f"v1\n{run_id}\n{coordinator_execution_id}\n{round}"
    return "FUK-" + hashlib.sha256(material.encode()).hexdigest().upper()


def validate_coordinator_fusion(
    payload: Mapping[str, object],
    source_recommendations: Sequence[Mapping[str, object]],
    supported_versions: Collection[str] = ("1.0.0",),
) -> None:
    _validate_payload(payload, supported_versions)
    inputs = payload["inputs"]
    identity = payload["identity"]
    assert isinstance(inputs, Mapping) and isinstance(identity, Mapping)
    references = inputs["recommendations"]
    assert isinstance(references, list)
    sources_by_key: dict[object, Mapping[str, object]] = {}
    for source in source_recommendations:
        validate_recommendation(source)
        source_identity = source["identity"]
        assert isinstance(source_identity, Mapping)
        key = source_identity["recommendation_key"]
        if key in sources_by_key:
            _raise(
                "duplicate_source_recommendation",
                "$.inputs.recommendations",
                "source recommendation keys must be unique",
            )
        sources_by_key[key] = source
    if set(sources_by_key) != {
        reference["recommendation_key"] for reference in references
    }:
        _raise(
            "source_recommendation_set_mismatch",
            "$.inputs.recommendations",
            "source recommendations do not match fusion references",
        )
    for index, reference in enumerate(references):
        source = sources_by_key[reference["recommendation_key"]]
        source_identity = source["identity"]
        source_common = source["recommendation"]
        assert isinstance(source_identity, Mapping) and isinstance(
            source_common, Mapping
        )
        expected = {
            "recommendation_id": source_identity["recommendation_id"],
            "recommendation_key": source_identity["recommendation_key"],
            "execution_id": source_identity["execution_id"],
            "task_id": source_identity["task_id"],
            "agent_role": source_identity["agent_role"],
            "action": source_common["action"],
            "severity": source_common["severity"],
            "confidence": source_common["confidence"],
        }
        for field, value in expected.items():
            if reference[field] != value:
                _raise(
                    "source_recommendation_mismatch",
                    f"$.inputs.recommendations[{index}].{field}",
                    "fusion reference does not match source recommendation",
                )
        if source_identity["run_id"] != identity["run_id"]:
            _raise(
                "cross_run_recommendation",
                f"$.inputs.recommendations[{index}]",
                "all source recommendations must belong to fusion run",
            )


def canonicalize_coordinator_fusion(payload: Mapping[str, object]) -> bytes:
    _validate_payload(payload)
    normalized = _normalize(copy.deepcopy(payload))
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def classify_coordinator_fusion_relation(
    first: Mapping[str, object], second: Mapping[str, object]
) -> str:
    first_bytes = canonicalize_coordinator_fusion(first)
    second_bytes = canonicalize_coordinator_fusion(second)
    first_identity, second_identity = first["identity"], second["identity"]
    assert isinstance(first_identity, Mapping) and isinstance(second_identity, Mapping)
    if first_identity["fusion_key"] != second_identity["fusion_key"]:
        return "distinct"
    return (
        "duplicate-identical"
        if first_bytes == second_bytes
        else "duplicate-conflicting"
    )


def _validate_payload(
    payload: Mapping[str, object], supported_versions: Collection[str] = ("1.0.0",)
) -> None:
    version = payload.get("contract_version")
    if not isinstance(version, str) or version not in supported_versions:
        _raise(
            "unsupported_contract_version",
            "$.contract_version",
            "unsupported contract version",
        )
    _preflight_finite(payload)
    schema = json.loads(
        (ROOT / f"v{version}" / "schema.json").read_text(encoding="utf-8")
    )
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(
            payload
        ),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        error = _most_specific(errors)
        _raise("schema_validation_failed", _path(error), error.message)
    identity, inputs, fusion = payload["identity"], payload["inputs"], payload["fusion"]
    assert isinstance(identity, Mapping)
    assert isinstance(inputs, Mapping)
    assert isinstance(fusion, Mapping)
    if identity["fusion_key"] != compute_fusion_key(
        str(identity["run_id"]),
        str(identity["coordinator_execution_id"]),
        int(identity["round"]),
    ):
        _raise(
            "fusion_key_mismatch",
            "$.identity.fusion_key",
            "fusion key does not match identity",
        )
    references = inputs["recommendations"]
    missing_roles = inputs["missing_roles"]
    candidates = fusion["candidates"]
    assert isinstance(references, list)
    assert isinstance(missing_roles, list)
    assert isinstance(candidates, list)
    _unique(references, "recommendation_key", "$.inputs.recommendations")
    _unique(references, "agent_role", "$.inputs.recommendations")
    _unique_values(missing_roles, "$.inputs.missing_roles")
    present_roles = {reference["agent_role"] for reference in references}
    if present_roles & set(missing_roles) or present_roles | set(missing_roles) != set(
        ROLE_ORDER
    ):
        _raise(
            "role_coverage_mismatch",
            "$.inputs",
            "present and missing roles must partition all specialist roles",
        )
    _unique(candidates, "action", "$.fusion.candidates")
    ranks = {candidate["rank"] for candidate in candidates}
    if ranks != set(range(1, len(candidates) + 1)):
        _raise(
            "candidate_rank_mismatch",
            "$.fusion.candidates",
            "candidate ranks must be consecutive from one",
        )
    top = next(candidate for candidate in candidates if candidate["rank"] == 1)
    if top["action"] != fusion["proposed_action"]:
        _raise(
            "proposed_action_mismatch",
            "$.fusion.proposed_action",
            "proposed action must equal rank-one candidate",
        )
    for index, candidate in enumerate(candidates):
        supporting = candidate["supporting_roles"]
        opposing = candidate["opposing_roles"]
        _unique_values(supporting, f"$.fusion.candidates[{index}].supporting_roles")
        _unique_values(opposing, f"$.fusion.candidates[{index}].opposing_roles")
        if (
            set(supporting) & set(opposing)
            or not (set(supporting) | set(opposing)) <= present_roles
        ):
            _raise(
                "candidate_role_mismatch",
                f"$.fusion.candidates[{index}]",
                "candidate roles must be disjoint present roles",
            )
    for field in ("conflict_codes", "evidence_refs", "reason_codes"):
        _unique_values(fusion[field], f"$.fusion.{field}")
    if bool(fusion["has_conflict"]) != bool(fusion["conflict_codes"]):
        _raise(
            "conflict_flag_mismatch",
            "$.fusion.has_conflict",
            "conflict flag must match conflict codes",
        )


def _preflight_finite(payload: Mapping[str, object]) -> None:
    inputs = payload.get("inputs")
    if isinstance(inputs, Mapping) and isinstance(inputs.get("recommendations"), list):
        for index, reference in enumerate(inputs["recommendations"]):
            if isinstance(reference, Mapping):
                _finite(
                    reference.get("confidence"),
                    f"$.inputs.recommendations[{index}].confidence",
                )
    fusion = payload.get("fusion")
    if isinstance(fusion, Mapping) and isinstance(fusion.get("candidates"), list):
        for index, candidate in enumerate(fusion["candidates"]):
            if isinstance(candidate, Mapping):
                _finite(candidate.get("score"), f"$.fusion.candidates[{index}].score")


def _finite(value: object, path: str) -> None:
    if isinstance(value, (int, float)) and not math.isfinite(value):
        _raise("non_finite_number", path, "number must be finite")


def _unique(items: list[object], field: str, path: str) -> None:
    values = [item[field] for item in items]
    _unique_values(values, path)


def _unique_values(items: object, path: str) -> None:
    assert isinstance(items, list)
    seen: set[object] = set()
    for index, item in enumerate(items):
        if item in seen:
            _raise("duplicate_value", f"{path}[{index}]", "values must be unique")
        seen.add(item)


def _normalize(value: object) -> object:
    if isinstance(value, Mapping):
        normalized = {key: _normalize(item) for key, item in value.items()}
        if set(normalized) == {"recommendations", "missing_roles"}:
            normalized["recommendations"] = sorted(
                normalized["recommendations"],
                key=lambda item: ROLE_ORDER[item["agent_role"]],
            )
            normalized["missing_roles"] = sorted(
                normalized["missing_roles"], key=ROLE_ORDER.__getitem__
            )
        if "candidates" in normalized:
            normalized["candidates"] = sorted(
                normalized["candidates"], key=lambda item: item["rank"]
            )
            for candidate in normalized["candidates"]:
                candidate["supporting_roles"] = sorted(
                    candidate["supporting_roles"], key=ROLE_ORDER.__getitem__
                )
                candidate["opposing_roles"] = sorted(
                    candidate["opposing_roles"], key=ROLE_ORDER.__getitem__
                )
            for field in ("conflict_codes", "evidence_refs", "reason_codes"):
                normalized[field] = sorted(normalized[field])
        return normalized
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _path(error: ValidationError) -> str:
    parts = list(error.absolute_path)
    if error.validator == "required" and isinstance(error.instance, Mapping):
        parts.append(next(x for x in error.validator_value if x not in error.instance))
    elif error.validator == "additionalProperties" and isinstance(
        error.instance, Mapping
    ):
        parts.append(min(set(error.instance) - set(error.schema.get("properties", {}))))
    return "$" + "".join(
        f"[{part}]" if isinstance(part, int) else f".{part}" for part in parts
    )


def _most_specific(errors: Sequence[ValidationError]) -> ValidationError:
    leaves: list[ValidationError] = []

    def add(error: ValidationError) -> None:
        if not error.context:
            leaves.append(error)
        else:
            for child in error.context:
                add(child)

    for error in errors:
        add(error)
    depth = max(len(error.absolute_path) for error in leaves)
    return min(
        (error for error in leaves if len(error.absolute_path) == depth),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )


def _raise(code: str, path: str, message: str) -> None:
    raise CoordinatorFusionValidationError((ValidationIssue(code, path, message),))
