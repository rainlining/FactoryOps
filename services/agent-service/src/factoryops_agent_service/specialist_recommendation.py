from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from contracts.specialist_recommendation.validator import (
    canonicalize_recommendation,
    validate_recommendation,
)


class RecommendationPersistenceRejected(ValueError):
    pass


class RecommendationPersistenceIntegrityError(RuntimeError):
    pass


class RecommendationSaveOutcome(str, Enum):
    APPLIED = "applied"
    DUPLICATE_IDENTICAL = "duplicate-identical"
    DUPLICATE_CONFLICTING = "duplicate-conflicting"


@dataclass(frozen=True)
class RecommendationSaveResult:
    outcome: RecommendationSaveOutcome
    recommendation: Mapping[str, object]


class SpecialistRecommendationService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save(
        self,
        recommendation: Mapping[str, object],
        *,
        expected_execution_provenance: Mapping[str, str] | None = None,
    ) -> RecommendationSaveResult:
        canonical = canonicalize_recommendation(recommendation)
        payload = json.loads(canonical)
        identity = payload["identity"]
        common = payload["recommendation"]
        key = str(identity["recommendation_key"])
        digest = hashlib.sha256(canonical).hexdigest()
        lock_name = "specialist-rec:" + hashlib.sha256(key.encode()).hexdigest()[:49]

        with self._engine.connect() as connection:
            acquired = connection.scalar(
                text("SELECT GET_LOCK(:name, 10)"), {"name": lock_name}
            )
            connection.commit()
            if acquired != 1:
                raise RecommendationPersistenceRejected("admission lock timed out")
            try:
                try:
                    with connection.begin():
                        existing = self._find_existing(
                            connection,
                            key,
                            str(identity["recommendation_id"]),
                        )
                        if existing is not None:
                            return self._classify(existing, canonical)
                        task = self._lock_task(connection, str(identity["task_id"]))
                        execution = self._lock_execution(
                            connection, str(identity["execution_id"])
                        )
                        self._validate_parent(
                            identity,
                            task,
                            execution,
                            expected_execution_provenance,
                        )
                        connection.execute(
                            text(
                                """INSERT INTO specialist_recommendations
                                (recommendation_id,recommendation_key,execution_id,run_id,task_id,agent_role,
                                action,severity,canonical_sha256,payload_json,generated_at,created_at)
                                VALUES (:id,:key,:execution,:run,:task,:role,:action,:severity,:hash,:payload,
                                :generated,CURRENT_TIMESTAMP(6))"""
                            ),
                            {
                                "id": identity["recommendation_id"],
                                "key": key,
                                "execution": identity["execution_id"],
                                "run": identity["run_id"],
                                "task": identity["task_id"],
                                "role": identity["agent_role"],
                                "action": common["action"],
                                "severity": common["severity"],
                                "hash": digest,
                                "payload": canonical.decode(),
                                "generated": self._timestamp(payload["generated_at"]),
                            },
                        )
                except IntegrityError:
                    connection.rollback()
                    existing = self._read_row_by_identity(
                        connection,
                        key,
                        str(identity["recommendation_id"]),
                    )
                    if existing is None:
                        raise RecommendationPersistenceIntegrityError(
                            "recommendation uniqueness failed without readable winner"
                        )
                    return self._classify(existing, canonical)
            finally:
                connection.execute(
                    text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name}
                )
                connection.commit()
        return RecommendationSaveResult(RecommendationSaveOutcome.APPLIED, payload)

    def get_by_key(self, recommendation_key: str) -> Mapping[str, object] | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT * FROM specialist_recommendations WHERE recommendation_key=:key"
                    ),
                    {"key": recommendation_key},
                )
                .mappings()
                .one_or_none()
            )
        return None if row is None else self._decode(row)

    @staticmethod
    def _validate_parent(
        identity: Mapping[str, object],
        task: Mapping[str, object] | None,
        execution: Mapping[str, object] | None,
        expected_execution_provenance: Mapping[str, str] | None,
    ) -> None:
        if task is None or execution is None:
            raise RecommendationPersistenceRejected("Task or Execution does not exist")
        if (
            task["status"] != "RUNNING"
            or task["current_execution_id"] != identity["execution_id"]
            or task["run_id"] != identity["run_id"]
            or task["target_agent_role"] != identity["agent_role"]
            or execution["status"] != "RUNNING"
            or execution["task_id"] != identity["task_id"]
            or execution["run_id"] != identity["run_id"]
            or execution["agent_role"] != identity["agent_role"]
            or task["context_snapshot_id"] != execution["context_snapshot_id"]
        ):
            raise RecommendationPersistenceRejected(
                "Recommendation parent is not current RUNNING Specialist pair"
            )
        if expected_execution_provenance is not None and any(
            execution[field] != value
            for field, value in expected_execution_provenance.items()
        ):
            raise RecommendationPersistenceRejected(
                "Execution provenance changed during recommendation generation"
            )

    def _classify(
        self, row: Mapping[str, object], canonical: bytes
    ) -> RecommendationSaveResult:
        stored = self._decode(row)
        stored_bytes = str(row["payload_json"]).encode()
        return RecommendationSaveResult(
            RecommendationSaveOutcome.DUPLICATE_IDENTICAL
            if stored_bytes == canonical
            else RecommendationSaveOutcome.DUPLICATE_CONFLICTING,
            stored,
        )

    @staticmethod
    def _decode(row: Mapping[str, object]) -> Mapping[str, object]:
        payload_text = str(row["payload_json"])
        if hashlib.sha256(payload_text.encode()).hexdigest() != row["canonical_sha256"]:
            raise RecommendationPersistenceIntegrityError(
                "Recommendation canonical hash is inconsistent"
            )
        try:
            payload = json.loads(payload_text)
            validate_recommendation(payload)
        except (json.JSONDecodeError, ValueError) as error:
            raise RecommendationPersistenceIntegrityError(
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
            or SpecialistRecommendationService._timestamp(payload["generated_at"])
            != SpecialistRecommendationService._utc(row["generated_at"])
        ):
            raise RecommendationPersistenceIntegrityError(
                "Recommendation typed columns are inconsistent"
            )
        return payload

    @staticmethod
    def _find_existing(
        connection: Connection, key: str, recommendation_id: str
    ) -> Mapping[str, object] | None:
        return SpecialistRecommendationService._read_row_by_identity(
            connection, key, recommendation_id, for_update=True
        )

    @staticmethod
    def _read_row_by_identity(
        connection: Connection,
        key: str,
        recommendation_id: str,
        *,
        for_update: bool = False,
    ) -> Mapping[str, object] | None:
        suffix = " FOR UPDATE" if for_update else ""
        rows = (
            connection.execute(
                text(
                    "SELECT * FROM specialist_recommendations "
                    "WHERE recommendation_key=:key OR recommendation_id=:id" + suffix
                ),
                {"key": key, "id": recommendation_id},
            )
            .mappings()
            .all()
        )
        if len(rows) > 1:
            raise RecommendationPersistenceIntegrityError(
                "recommendation key and ID resolve to different facts"
            )
        return rows[0] if rows else None

    @staticmethod
    def _lock_task(connection: Connection, task_id: str) -> Mapping[str, object] | None:
        return (
            connection.execute(
                text("SELECT * FROM agent_tasks WHERE task_id=:id FOR UPDATE"),
                {"id": task_id},
            )
            .mappings()
            .one_or_none()
        )

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
