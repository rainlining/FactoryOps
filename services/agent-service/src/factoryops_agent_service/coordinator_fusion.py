from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from contracts.coordinator_fusion.validator import (
    canonicalize_coordinator_fusion,
    validate_coordinator_fusion,
)
from contracts.specialist_recommendation.validator import canonicalize_recommendation
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError


class FusionPersistenceRejected(ValueError):
    pass


class FusionPersistenceIntegrityError(RuntimeError):
    pass


class FusionSaveOutcome(str, Enum):
    APPLIED = "applied"
    DUPLICATE_IDENTICAL = "duplicate-identical"
    DUPLICATE_CONFLICTING = "duplicate-conflicting"


@dataclass(frozen=True)
class FusionSaveResult:
    outcome: FusionSaveOutcome
    fusion: Mapping[str, object]


class CoordinatorFusionService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save(self, fusion: Mapping[str, object]) -> FusionSaveResult:
        canonical = canonicalize_coordinator_fusion(fusion)
        payload = json.loads(canonical)
        identity = payload["identity"]
        key, fusion_id = str(identity["fusion_key"]), str(identity["fusion_id"])
        locks = sorted({self._lock_name("key", key), self._lock_name("id", fusion_id)})
        with self._engine.connect() as connection:
            acquired: list[str] = []
            try:
                for name in locks:
                    if (
                        connection.scalar(
                            text("SELECT GET_LOCK(:name,10)"), {"name": name}
                        )
                        != 1
                    ):
                        raise FusionPersistenceRejected("admission lock timed out")
                    acquired.append(name)
                connection.commit()
                try:
                    with connection.begin():
                        existing = self._read_identity(connection, key, fusion_id, True)
                        if existing is not None:
                            return self._classify(connection, existing, canonical)
                        execution = self._lock_execution(
                            connection, str(identity["coordinator_execution_id"])
                        )
                        if (
                            execution is None
                            or execution["agent_role"] != "coordinator"
                            or execution["run_id"] != identity["run_id"]
                            or execution["status"] != "RUNNING"
                        ):
                            raise FusionPersistenceRejected(
                                "Coordinator Execution is not current RUNNING owner"
                            )
                        sources = self._read_sources(connection, payload, True)
                        validate_coordinator_fusion(payload, sources)
                        block = payload["fusion"]
                        connection.execute(
                            text("""INSERT INTO coordinator_fusions
                            (fusion_id,fusion_key,run_id,coordinator_execution_id,fusion_round,proposed_action,has_conflict,canonical_sha256,payload_json,generated_at,created_at)
                            VALUES (:id,:key,:run,:execution,:round,:action,:conflict,:hash,:payload,:generated,CURRENT_TIMESTAMP(6))"""),
                            {
                                "id": fusion_id,
                                "key": key,
                                "run": identity["run_id"],
                                "execution": identity["coordinator_execution_id"],
                                "round": identity["round"],
                                "action": block["proposed_action"],
                                "conflict": block["has_conflict"],
                                "hash": hashlib.sha256(canonical).hexdigest(),
                                "payload": canonical.decode(),
                                "generated": self._timestamp(payload["generated_at"]),
                            },
                        )
                        for reference in payload["inputs"]["recommendations"]:
                            connection.execute(
                                text("""INSERT INTO coordinator_fusion_recommendations
                                (fusion_id,recommendation_id,recommendation_key,agent_role)
                                VALUES (:fusion,:id,:key,:role)"""),
                                {
                                    "fusion": fusion_id,
                                    "id": reference["recommendation_id"],
                                    "key": reference["recommendation_key"],
                                    "role": reference["agent_role"],
                                },
                            )
                except IntegrityError:
                    connection.rollback()
                    existing = self._read_identity(connection, key, fusion_id)
                    if existing is None:
                        raise FusionPersistenceIntegrityError(
                            "fusion uniqueness failed without readable winner"
                        )
                    return self._classify(connection, existing, canonical)
            finally:
                connection.rollback()
                for name in reversed(acquired):
                    connection.execute(
                        text("SELECT RELEASE_LOCK(:name)"), {"name": name}
                    )
                connection.commit()
        return FusionSaveResult(FusionSaveOutcome.APPLIED, payload)

    def get_by_key(self, key: str) -> Mapping[str, object] | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text("SELECT * FROM coordinator_fusions WHERE fusion_key=:key"),
                    {"key": key},
                )
                .mappings()
                .one_or_none()
            )
            return None if row is None else self._decode(connection, row)

    def _classify(
        self, connection: Connection, row: Mapping[str, object], canonical: bytes
    ) -> FusionSaveResult:
        stored = self._decode(connection, row)
        outcome = (
            FusionSaveOutcome.DUPLICATE_IDENTICAL
            if str(row["payload_json"]).encode() == canonical
            else FusionSaveOutcome.DUPLICATE_CONFLICTING
        )
        return FusionSaveResult(outcome, stored)

    def _decode(
        self, connection: Connection, row: Mapping[str, object]
    ) -> Mapping[str, object]:
        raw = str(row["payload_json"])
        if hashlib.sha256(raw.encode()).hexdigest() != row["canonical_sha256"]:
            raise FusionPersistenceIntegrityError(
                "Fusion canonical hash is inconsistent"
            )
        try:
            payload = json.loads(raw)
            if canonicalize_coordinator_fusion(payload) != raw.encode():
                raise ValueError("noncanonical Fusion")
            sources = self._read_sources(connection, payload)
            validate_coordinator_fusion(payload, sources)
        except (json.JSONDecodeError, ValueError) as error:
            raise FusionPersistenceIntegrityError(
                "Fusion payload or source binding is inconsistent"
            ) from error
        identity, block = payload["identity"], payload["fusion"]
        execution = (
            connection.execute(
                text(
                    "SELECT run_id,agent_role FROM agent_executions WHERE execution_id=:id"
                ),
                {"id": identity["coordinator_execution_id"]},
            )
            .mappings()
            .one_or_none()
        )
        if (
            execution is None
            or execution["agent_role"] != "coordinator"
            or execution["run_id"] != identity["run_id"]
        ):
            raise FusionPersistenceIntegrityError(
                "Fusion Coordinator Execution binding is inconsistent"
            )
        typed = {
            "fusion_id": row["fusion_id"],
            "fusion_key": row["fusion_key"],
            "run_id": row["run_id"],
            "coordinator_execution_id": row["coordinator_execution_id"],
            "round": row["fusion_round"],
        }
        if (
            any(identity[field] != value for field, value in typed.items())
            or block["proposed_action"] != row["proposed_action"]
            or bool(block["has_conflict"]) != bool(row["has_conflict"])
            or self._timestamp(payload["generated_at"])
            != self._utc(row["generated_at"])
        ):
            raise FusionPersistenceIntegrityError(
                "Fusion typed columns are inconsistent"
            )
        links = (
            connection.execute(
                text(
                    "SELECT recommendation_id,recommendation_key,agent_role FROM coordinator_fusion_recommendations WHERE fusion_id=:id"
                ),
                {"id": row["fusion_id"]},
            )
            .mappings()
            .all()
        )
        expected = {
            (r["recommendation_id"], r["recommendation_key"], r["agent_role"])
            for r in payload["inputs"]["recommendations"]
        }
        if {
            (r["recommendation_id"], r["recommendation_key"], r["agent_role"])
            for r in links
        } != expected:
            raise FusionPersistenceIntegrityError(
                "Fusion source links are inconsistent"
            )
        return payload

    def _read_sources(
        self,
        connection: Connection,
        payload: Mapping[str, object],
        for_update: bool = False,
    ) -> list[Mapping[str, object]]:
        refs = payload["inputs"]["recommendations"]
        sources = []
        suffix = " FOR UPDATE" if for_update else ""
        for key in sorted(str(r["recommendation_key"]) for r in refs):
            row = (
                connection.execute(
                    text(
                        "SELECT * FROM specialist_recommendations WHERE recommendation_key=:key"
                        + suffix
                    ),
                    {"key": key},
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise FusionPersistenceRejected(
                    "Specialist Recommendation does not exist"
                )
            raw = str(row["payload_json"])
            if hashlib.sha256(raw.encode()).hexdigest() != row["canonical_sha256"]:
                raise FusionPersistenceIntegrityError(
                    "Recommendation canonical hash is inconsistent"
                )
            try:
                source = json.loads(raw)
                if canonicalize_recommendation(source) != raw.encode():
                    raise ValueError("noncanonical Recommendation")
            except (json.JSONDecodeError, ValueError) as error:
                raise FusionPersistenceIntegrityError(
                    "Recommendation payload is inconsistent"
                ) from error
            identity = source["identity"]
            common = source["recommendation"]
            typed = {
                "recommendation_id": row["recommendation_id"],
                "recommendation_key": row["recommendation_key"],
                "execution_id": row["execution_id"],
                "run_id": row["run_id"],
                "task_id": row["task_id"],
                "agent_role": row["agent_role"],
            }
            if any(identity[field] != value for field, value in typed.items()) or (
                common["action"] != row["action"]
                or common["severity"] != row["severity"]
                or self._timestamp(source["generated_at"])
                != self._utc(row["generated_at"])
            ):
                raise FusionPersistenceIntegrityError(
                    "Recommendation typed columns are inconsistent"
                )
            sources.append(source)
        return sources

    @staticmethod
    def _read_identity(
        connection: Connection, key: str, fusion_id: str, for_update: bool = False
    ) -> Mapping[str, object] | None:
        suffix = " FOR UPDATE" if for_update else ""
        rows = (
            connection.execute(
                text(
                    "SELECT * FROM coordinator_fusions WHERE fusion_key=:key OR fusion_id=:id"
                    + suffix
                ),
                {"key": key, "id": fusion_id},
            )
            .mappings()
            .all()
        )
        if len(rows) > 1:
            raise FusionPersistenceIntegrityError(
                "fusion key and ID resolve to different facts"
            )
        return rows[0] if rows else None

    @staticmethod
    def _lock_execution(
        connection: Connection, execution_id: str
    ) -> Mapping[str, object] | None:
        return (
            connection.execute(
                text(
                    "SELECT * FROM agent_executions WHERE execution_id=:id FOR UPDATE"
                ),
                {"id": execution_id},
            )
            .mappings()
            .one_or_none()
        )

    @staticmethod
    def _lock_name(kind: str, value: str) -> str:
        return (
            "coord-fusion:"
            + kind
            + ":"
            + hashlib.sha256(value.encode()).hexdigest()[:42]
        )

    @staticmethod
    def _timestamp(value: object) -> datetime:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(
            timezone.utc
        )

    @staticmethod
    def _utc(value: object) -> datetime:
        assert isinstance(value, datetime)
        return (
            value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        ).astimezone(timezone.utc)
