from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from contracts.risk_decision.validator import (
    canonicalize_risk_decision,
    validate_risk_decision,
)
from contracts.specialist_recommendation.validator import (
    canonicalize_recommendation,
)
from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError


class RiskDecisionPersistenceRejected(ValueError):
    pass


class RiskDecisionPersistenceIntegrityError(RuntimeError):
    pass


class RiskDecisionSaveOutcome(str, Enum):
    APPLIED = "applied"
    DUPLICATE_IDENTICAL = "duplicate-identical"
    DUPLICATE_CONFLICTING = "duplicate-conflicting"


@dataclass(frozen=True)
class RiskDecisionSaveResult:
    outcome: RiskDecisionSaveOutcome
    decision: Mapping[str, object]


class RiskDecisionService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save(self, decision: Mapping[str, object]) -> RiskDecisionSaveResult:
        canonical = canonicalize_risk_decision(decision)
        payload = json.loads(canonical)
        identity = payload["identity"]
        gate = payload["gate"]
        key = str(identity["decision_key"])
        decision_id = str(identity["decision_id"])
        digest = hashlib.sha256(canonical).hexdigest()
        lock_names = sorted(
            {
                self._lock_name("key", key),
                self._lock_name("id", decision_id),
            }
        )

        with self._engine.connect() as connection:
            acquired: list[str] = []
            try:
                for lock_name in lock_names:
                    if (
                        connection.scalar(
                            text("SELECT GET_LOCK(:name, 10)"), {"name": lock_name}
                        )
                        != 1
                    ):
                        raise RiskDecisionPersistenceRejected(
                            "admission lock timed out"
                        )
                    acquired.append(lock_name)
                connection.commit()
                try:
                    with connection.begin():
                        source = self._lock_recommendation(
                            connection, str(identity["recommendation_key"])
                        )
                        if source is None:
                            raise RiskDecisionPersistenceRejected(
                                "Recommendation does not exist"
                            )
                        source_payload = self._decode_recommendation(source)
                        source_identity = source_payload["identity"]
                        assert isinstance(source_identity, Mapping)
                        validate_risk_decision(payload, source_identity)
                        existing = self._read_row_by_identity(
                            connection, key, decision_id, for_update=True
                        )
                        if existing is not None:
                            return self._classify(connection, existing, canonical)
                        connection.execute(
                            text(
                                """INSERT INTO risk_decisions
                                (decision_id,decision_key,recommendation_id,recommendation_key,
                                run_id,task_id,proposed_action,decision,risk_level,
                                approval_required,canonical_sha256,payload_json,generated_at,created_at)
                                VALUES (:id,:key,:recommendation_id,:recommendation_key,
                                :run,:task,:action,:decision,:risk,:approval,:hash,:payload,
                                :generated,CURRENT_TIMESTAMP(6))"""
                            ),
                            {
                                "id": decision_id,
                                "key": key,
                                "recommendation_id": identity["recommendation_id"],
                                "recommendation_key": identity["recommendation_key"],
                                "run": identity["run_id"],
                                "task": identity["task_id"],
                                "action": gate["proposed_action"],
                                "decision": gate["decision"],
                                "risk": gate["risk_level"],
                                "approval": gate["approval_required"],
                                "hash": digest,
                                "payload": canonical.decode(),
                                "generated": self._timestamp(payload["generated_at"]),
                            },
                        )
                except IntegrityError:
                    connection.rollback()
                    existing = self._read_row_by_identity(connection, key, decision_id)
                    if existing is None:
                        raise RiskDecisionPersistenceIntegrityError(
                            "risk decision uniqueness failed without readable winner"
                        )
                    return self._classify(connection, existing, canonical)
            finally:
                connection.rollback()
                for lock_name in reversed(acquired):
                    connection.execute(
                        text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name}
                    )
                connection.commit()
        return RiskDecisionSaveResult(RiskDecisionSaveOutcome.APPLIED, payload)

    def get_by_key(self, decision_key: str) -> Mapping[str, object] | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text("SELECT * FROM risk_decisions WHERE decision_key=:key"),
                    {"key": decision_key},
                )
                .mappings()
                .one_or_none()
            )
            return None if row is None else self._decode(connection, row)

    def _classify(
        self,
        connection: Connection,
        row: Mapping[str, object],
        canonical: bytes,
    ) -> RiskDecisionSaveResult:
        stored = self._decode(connection, row)
        return RiskDecisionSaveResult(
            RiskDecisionSaveOutcome.DUPLICATE_IDENTICAL
            if str(row["payload_json"]).encode() == canonical
            else RiskDecisionSaveOutcome.DUPLICATE_CONFLICTING,
            stored,
        )

    def _decode(
        self, connection: Connection, row: Mapping[str, object]
    ) -> Mapping[str, object]:
        payload_text = str(row["payload_json"])
        if hashlib.sha256(payload_text.encode()).hexdigest() != row["canonical_sha256"]:
            raise RiskDecisionPersistenceIntegrityError(
                "Risk Decision canonical hash is inconsistent"
            )
        try:
            payload = json.loads(payload_text)
            if canonicalize_risk_decision(payload) != payload_text.encode():
                raise ValueError("Risk Decision payload is not canonical")
            source = self._read_recommendation(
                connection, str(row["recommendation_key"])
            )
            if source is None:
                raise RiskDecisionPersistenceIntegrityError(
                    "Risk Decision source Recommendation is missing"
                )
            source_payload = self._decode_recommendation(source)
            source_identity = source_payload["identity"]
            assert isinstance(source_identity, Mapping)
            validate_risk_decision(payload, source_identity)
        except (json.JSONDecodeError, ValueError) as error:
            raise RiskDecisionPersistenceIntegrityError(
                "Risk Decision payload violates Contract or binding"
            ) from error
        identity = payload["identity"]
        gate = payload["gate"]
        typed = {
            "decision_id": row["decision_id"],
            "decision_key": row["decision_key"],
            "recommendation_id": row["recommendation_id"],
            "recommendation_key": row["recommendation_key"],
            "run_id": row["run_id"],
            "task_id": row["task_id"],
        }
        if any(identity[field] != value for field, value in typed.items()) or (
            gate["proposed_action"] != row["proposed_action"]
            or gate["decision"] != row["decision"]
            or gate["risk_level"] != row["risk_level"]
            or bool(gate["approval_required"]) != bool(row["approval_required"])
            or self._timestamp(payload["generated_at"])
            != self._utc(row["generated_at"])
        ):
            raise RiskDecisionPersistenceIntegrityError(
                "Risk Decision typed columns are inconsistent"
            )
        return payload

    @staticmethod
    def _decode_recommendation(row: Mapping[str, object]) -> Mapping[str, object]:
        payload_text = str(row["payload_json"])
        if hashlib.sha256(payload_text.encode()).hexdigest() != row["canonical_sha256"]:
            raise RiskDecisionPersistenceIntegrityError(
                "Recommendation canonical hash is inconsistent"
            )
        try:
            payload = json.loads(payload_text)
            if canonicalize_recommendation(payload) != payload_text.encode():
                raise ValueError("Recommendation payload is not canonical")
        except (json.JSONDecodeError, ValueError) as error:
            raise RiskDecisionPersistenceIntegrityError(
                "Recommendation payload violates Contract"
            ) from error
        identity = payload["identity"]
        common = payload["recommendation"]
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
            or RiskDecisionService._timestamp(payload["generated_at"])
            != RiskDecisionService._utc(row["generated_at"])
        ):
            raise RiskDecisionPersistenceIntegrityError(
                "Recommendation typed columns are inconsistent"
            )
        return payload

    @staticmethod
    def _read_row_by_identity(
        connection: Connection,
        decision_key: str,
        decision_id: str,
        *,
        for_update: bool = False,
    ) -> Mapping[str, object] | None:
        suffix = " FOR UPDATE" if for_update else ""
        rows = (
            connection.execute(
                text(
                    "SELECT * FROM risk_decisions "
                    "WHERE decision_key=:key OR decision_id=:id" + suffix
                ),
                {"key": decision_key, "id": decision_id},
            )
            .mappings()
            .all()
        )
        if len(rows) > 1:
            raise RiskDecisionPersistenceIntegrityError(
                "risk decision key and ID resolve to different facts"
            )
        return rows[0] if rows else None

    @staticmethod
    def _lock_recommendation(
        connection: Connection, recommendation_key: str
    ) -> Mapping[str, object] | None:
        return RiskDecisionService._read_recommendation(
            connection, recommendation_key, for_update=True
        )

    @staticmethod
    def _read_recommendation(
        connection: Connection,
        recommendation_key: str,
        *,
        for_update: bool = False,
    ) -> Mapping[str, object] | None:
        suffix = " FOR UPDATE" if for_update else ""
        return (
            connection.execute(
                text(
                    "SELECT * FROM specialist_recommendations "
                    "WHERE recommendation_key=:key" + suffix
                ),
                {"key": recommendation_key},
            )
            .mappings()
            .one_or_none()
        )

    @staticmethod
    def _lock_name(kind: str, value: str) -> str:
        return (
            "risk-decision:"
            + kind
            + ":"
            + hashlib.sha256(value.encode()).hexdigest()[:40]
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
