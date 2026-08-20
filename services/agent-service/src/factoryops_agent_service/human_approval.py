from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from contracts.human_approval.validator import (
    canonicalize_human_approval,
    classify_human_approval_relation,
    validate_human_approval,
)
from factoryops_agent_service.risk_decision import (
    RiskDecisionPersistenceIntegrityError,
    RiskDecisionService,
)
from factoryops_agent_service.run_lifecycle.service import (
    AgentRunLifecycleService,
)
from factoryops_agent_service.run_lifecycle.service import (
    PersistenceIntegrityError as RunPersistenceIntegrityError,
)


class HumanApprovalPersistenceRejected(ValueError):
    pass


class HumanApprovalPersistenceIntegrityError(RuntimeError):
    pass


class HumanApprovalSaveOutcome(str, Enum):
    APPLIED = "applied"
    DUPLICATE_IDENTICAL = "duplicate-identical"
    DUPLICATE_CONFLICTING = "duplicate-conflicting"


@dataclass(frozen=True)
class HumanApprovalSaveResult:
    outcome: HumanApprovalSaveOutcome
    approval: Mapping[str, object]


class HumanApprovalService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save(self, approval: Mapping[str, object]) -> HumanApprovalSaveResult:
        canonical = canonicalize_human_approval(approval)
        payload = json.loads(canonical)
        identity = payload["identity"]
        key, approval_id = str(identity["approval_key"]), str(identity["approval_id"])
        lock_names = sorted(
            {self._lock_name("key", key), self._lock_name("id", approval_id)}
        )
        with self._engine.connect() as connection:
            acquired: list[str] = []
            try:
                for name in lock_names:
                    if (
                        connection.scalar(
                            text("SELECT GET_LOCK(:name,10)"), {"name": name}
                        )
                        != 1
                    ):
                        raise HumanApprovalPersistenceRejected(
                            "admission lock timed out"
                        )
                    acquired.append(name)
                connection.commit()
                try:
                    with connection.begin():
                        risk_service = RiskDecisionService(self._engine)
                        fusion_row = RiskDecisionService._read_fusion(
                            connection,
                            str(identity["fusion_key"]),
                            for_update=True,
                        )
                        if fusion_row is None:
                            raise HumanApprovalPersistenceRejected(
                                "Risk Decision Fusion does not exist"
                            )
                        try:
                            risk_service._decode_fusion(
                                connection, fusion_row, for_update=True
                            )
                        except RiskDecisionPersistenceIntegrityError as error:
                            raise HumanApprovalPersistenceIntegrityError(
                                "Risk Decision Fusion provenance is inconsistent"
                            ) from error
                        source_row = RiskDecisionService._read_row_by_identity(
                            connection,
                            str(identity["decision_key"]),
                            str(identity["decision_id"]),
                            for_update=True,
                        )
                        if source_row is None:
                            raise HumanApprovalPersistenceRejected(
                                "Risk Decision does not exist"
                            )
                        try:
                            source = risk_service._decode(connection, source_row)
                        except RiskDecisionPersistenceIntegrityError as error:
                            raise HumanApprovalPersistenceIntegrityError(
                                "Risk Decision provenance is inconsistent"
                            ) from error
                        source_run = self._read_source_run(
                            connection,
                            str(identity["run_id"]),
                            for_update=True,
                        )
                        validate_human_approval(payload, source, source_run)
                        existing = self._read_by_identity(
                            connection, key, approval_id, for_update=True
                        )
                        if existing is None:
                            if payload["state"]["revision"] != 1:
                                raise HumanApprovalPersistenceRejected(
                                    "first Approval snapshot must be revision 1"
                                )
                            self._insert_current(connection, payload, canonical)
                            self._insert_history(connection, payload, canonical)
                            return HumanApprovalSaveResult(
                                HumanApprovalSaveOutcome.APPLIED, payload
                            )
                        stored = self._decode(connection, existing, for_update=True)
                        relation = classify_human_approval_relation(stored, payload)
                        if relation == "duplicate-identical":
                            return HumanApprovalSaveResult(
                                HumanApprovalSaveOutcome.DUPLICATE_IDENTICAL, stored
                            )
                        if relation != "next-revision":
                            return HumanApprovalSaveResult(
                                HumanApprovalSaveOutcome.DUPLICATE_CONFLICTING, stored
                            )
                        result = connection.execute(
                            text(
                                "UPDATE human_approvals SET revision=2,status=:status,canonical_sha256=:hash,"
                                "payload_json=:payload,updated_at=CURRENT_TIMESTAMP(6) "
                                "WHERE approval_id=:id AND revision=1"
                            ),
                            {
                                "status": payload["state"]["status"],
                                "hash": hashlib.sha256(canonical).hexdigest(),
                                "payload": canonical.decode(),
                                "id": approval_id,
                            },
                        )
                        if result.rowcount != 1:
                            raise HumanApprovalPersistenceIntegrityError(
                                "Approval revision compare-and-set failed"
                            )
                        self._insert_history(connection, payload, canonical)
                        return HumanApprovalSaveResult(
                            HumanApprovalSaveOutcome.APPLIED, payload
                        )
                except IntegrityError as error:
                    raise HumanApprovalPersistenceIntegrityError(
                        "Approval persistence uniqueness failed"
                    ) from error
            finally:
                connection.rollback()
                for name in reversed(acquired):
                    connection.execute(
                        text("SELECT RELEASE_LOCK(:name)"), {"name": name}
                    )
                connection.commit()

    def get_by_key(self, approval_key: str) -> Mapping[str, object] | None:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text("SELECT * FROM human_approvals WHERE approval_key=:key"),
                    {"key": approval_key},
                )
                .mappings()
                .one_or_none()
            )
            return None if row is None else self._decode(connection, row)

    def _decode(
        self,
        connection: Connection,
        row: Mapping[str, object],
        *,
        for_update: bool = False,
    ) -> Mapping[str, object]:
        payload_text = str(row["payload_json"])
        if hashlib.sha256(payload_text.encode()).hexdigest() != row["canonical_sha256"]:
            raise HumanApprovalPersistenceIntegrityError(
                "Approval canonical hash is inconsistent"
            )
        try:
            payload = json.loads(payload_text)
            if canonicalize_human_approval(payload) != payload_text.encode():
                raise ValueError("Approval payload is not canonical")
            source_row = RiskDecisionService._read_row_by_identity(
                connection,
                str(row["decision_key"]),
                str(row["decision_id"]),
            )
            if source_row is None:
                raise ValueError("Risk Decision is missing")
            source = RiskDecisionService(self._engine)._decode(connection, source_row)
            source_run = self._read_source_run(
                connection, str(row["run_id"]), for_update=for_update
            )
            validate_human_approval(payload, source, source_run)
        except (
            json.JSONDecodeError,
            ValueError,
            RiskDecisionPersistenceIntegrityError,
            RunPersistenceIntegrityError,
        ) as error:
            raise HumanApprovalPersistenceIntegrityError(
                "Approval payload or provenance is inconsistent"
            ) from error
        identity, request, state = (
            payload["identity"],
            payload["request"],
            payload["state"],
        )
        typed = {
            "approval_id": row["approval_id"],
            "approval_key": row["approval_key"],
            "decision_id": row["decision_id"],
            "decision_key": row["decision_key"],
            "fusion_id": row["fusion_id"],
            "fusion_key": row["fusion_key"],
            "run_id": row["run_id"],
            "coordinator_execution_id": row["coordinator_execution_id"],
            "round": row["fusion_round"],
        }
        if payload["contract_version"] == "1.1.0":
            typed["incident_id"] = row["incident_id"]
        elif row["incident_id"] is not None:
            raise HumanApprovalPersistenceIntegrityError(
                "legacy Approval has unexpected incident binding"
            )
        if any(identity[field] != value for field, value in typed.items()) or (
            state["revision"] != row["revision"]
            or state["status"] != row["status"]
            or self._timestamp(request["requested_at"])
            != self._utc(row["requested_at"])
            or self._timestamp(request["expires_at"]) != self._utc(row["expires_at"])
        ):
            raise HumanApprovalPersistenceIntegrityError(
                "Approval typed columns are inconsistent"
            )
        history = (
            connection.execute(
                text(
                    "SELECT * FROM human_approval_history WHERE approval_id=:id ORDER BY revision"
                ),
                {"id": row["approval_id"]},
            )
            .mappings()
            .all()
        )
        if len(history) != int(row["revision"]):
            raise HumanApprovalPersistenceIntegrityError(
                "Approval history is incomplete"
            )
        previous: Mapping[str, object] | None = None
        try:
            for expected_revision, item in enumerate(history, 1):
                history_text = str(item["payload_json"])
                if (
                    item["revision"] != expected_revision
                    or hashlib.sha256(history_text.encode()).hexdigest()
                    != item["canonical_sha256"]
                ):
                    raise ValueError("history hash or revision mismatch")
                history_payload = json.loads(history_text)
                if (
                    canonicalize_human_approval(history_payload)
                    != history_text.encode()
                ):
                    raise ValueError("history payload is not canonical")
                validate_human_approval(history_payload, source, source_run)
                if (
                    history_payload["state"]["revision"] != item["revision"]
                    or history_payload["state"]["status"] != item["status"]
                    or history_payload["identity"] != payload["identity"]
                    or (
                        previous is not None
                        and classify_human_approval_relation(previous, history_payload)
                        != "next-revision"
                    )
                ):
                    raise ValueError("history binding or relation mismatch")
                previous = history_payload
        except (json.JSONDecodeError, ValueError) as error:
            raise HumanApprovalPersistenceIntegrityError(
                "Approval history is inconsistent"
            ) from error
        if str(history[-1]["payload_json"]) != payload_text:
            raise HumanApprovalPersistenceIntegrityError(
                "Approval current snapshot does not match history"
            )
        return payload

    @staticmethod
    def _read_by_identity(
        connection: Connection,
        key: str,
        approval_id: str,
        *,
        for_update: bool = False,
    ) -> Mapping[str, object] | None:
        suffix = " FOR UPDATE" if for_update else ""
        rows = (
            connection.execute(
                text(
                    "SELECT * FROM human_approvals WHERE approval_key=:key OR approval_id=:id"
                    + suffix
                ),
                {"key": key, "id": approval_id},
            )
            .mappings()
            .all()
        )
        if len(rows) > 1:
            raise HumanApprovalPersistenceIntegrityError(
                "Approval key and ID resolve to different facts"
            )
        return rows[0] if rows else None

    def _read_source_run(
        self,
        connection: Connection,
        run_id: str,
        *,
        for_update: bool = False,
    ) -> Mapping[str, object] | None:
        if not for_update:
            suffix = ""
        else:
            suffix = " FOR UPDATE"
        row = (
            connection.execute(
                text("SELECT * FROM agent_runs WHERE run_id=:run" + suffix),
                {"run": run_id},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        return AgentRunLifecycleService(self._engine).to_contract(row)

    @staticmethod
    def _insert_current(
        connection: Connection, payload: Mapping[str, object], canonical: bytes
    ) -> None:
        identity, request, state = (
            payload["identity"],
            payload["request"],
            payload["state"],
        )
        connection.execute(
            text(
                "INSERT INTO human_approvals (approval_id,approval_key,decision_id,decision_key,"
                "fusion_id,fusion_key,run_id,incident_id,coordinator_execution_id,fusion_round,revision,status,"
                "canonical_sha256,payload_json,requested_at,expires_at,updated_at,created_at) VALUES "
                "(:id,:key,:decision_id,:decision_key,:fusion_id,:fusion_key,:run_id,:incident_id,"
                ":execution_id,:round,:revision,:status,:hash,:payload,:requested,:expires,CURRENT_TIMESTAMP(6),CURRENT_TIMESTAMP(6))"
            ),
            {
                "id": identity["approval_id"],
                "key": identity["approval_key"],
                "decision_id": identity["decision_id"],
                "decision_key": identity["decision_key"],
                "fusion_id": identity["fusion_id"],
                "fusion_key": identity["fusion_key"],
                "run_id": identity["run_id"],
                "incident_id": identity.get("incident_id"),
                "execution_id": identity["coordinator_execution_id"],
                "round": identity["round"],
                "revision": state["revision"],
                "status": state["status"],
                "hash": hashlib.sha256(canonical).hexdigest(),
                "payload": canonical.decode(),
                "requested": HumanApprovalService._timestamp(request["requested_at"]),
                "expires": HumanApprovalService._timestamp(request["expires_at"]),
            },
        )

    @staticmethod
    def _insert_history(
        connection: Connection, payload: Mapping[str, object], canonical: bytes
    ) -> None:
        connection.execute(
            text(
                "INSERT INTO human_approval_history "
                "(approval_id,revision,status,canonical_sha256,payload_json,recorded_at) "
                "VALUES (:id,:revision,:status,:hash,:payload,CURRENT_TIMESTAMP(6))"
            ),
            {
                "id": payload["identity"]["approval_id"],
                "revision": payload["state"]["revision"],
                "status": payload["state"]["status"],
                "hash": hashlib.sha256(canonical).hexdigest(),
                "payload": canonical.decode(),
            },
        )

    @staticmethod
    def _lock_name(kind: str, value: str) -> str:
        return (
            "human-approval:"
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
