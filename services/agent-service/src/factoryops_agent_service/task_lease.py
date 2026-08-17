from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import Engine, text


class LeaseRejected(ValueError):
    pass


@dataclass(frozen=True)
class Lease:
    task_id: str
    owner_id: str
    lease_token: str
    expires_at: datetime


class AgentTaskLeaseService:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def claim(
        self,
        task_id: str,
        owner_id: str,
        ttl_seconds: int,
        *,
        now: datetime | None = None,
    ) -> Lease:
        if not owner_id.strip() or not self._valid_ttl(ttl_seconds):
            raise LeaseRejected("owner and ttl are invalid")
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        expires = now + timedelta(seconds=ttl_seconds)
        token = "LSE-" + uuid.uuid4().hex.upper() + secrets.token_hex(8).upper()
        with self._engine.begin() as c:
            task = (
                c.execute(
                    text("SELECT status FROM agent_tasks WHERE task_id=:id FOR UPDATE"),
                    {"id": task_id},
                )
                .mappings()
                .one_or_none()
            )
            if task is None or task["status"] != "PENDING":
                raise LeaseRejected("only existing PENDING Task can be claimed")
            current = (
                c.execute(
                    text(
                        "SELECT * FROM agent_task_leases WHERE task_id=:id FOR UPDATE"
                    ),
                    {"id": task_id},
                )
                .mappings()
                .one_or_none()
            )
            current_expiry = (
                current["expires_at"].replace(tzinfo=timezone.utc)
                if current is not None and current["expires_at"].tzinfo is None
                else current["expires_at"]
                if current is not None
                else None
            )
            if current_expiry is not None and current_expiry > now:
                raise LeaseRejected("Task lease is held")
            if current is None:
                c.execute(
                    text(
                        "INSERT INTO agent_task_leases(task_id,owner_id,lease_token,leased_at,expires_at) VALUES (:task,:owner,:token,:leased,:expires)"
                    ),
                    {
                        "task": task_id,
                        "owner": owner_id,
                        "token": token,
                        "leased": now,
                        "expires": expires,
                    },
                )
            else:
                c.execute(
                    text(
                        "UPDATE agent_task_leases SET owner_id=:owner,lease_token=:token,leased_at=:leased,expires_at=:expires WHERE task_id=:task"
                    ),
                    {
                        "task": task_id,
                        "owner": owner_id,
                        "token": token,
                        "leased": now,
                        "expires": expires,
                    },
                )
        return Lease(task_id, owner_id, token, expires)

    def renew(
        self, lease: Lease, ttl_seconds: int, *, now: datetime | None = None
    ) -> Lease:
        if not self._valid_ttl(ttl_seconds):
            raise LeaseRejected("ttl is invalid")
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        expires = now + timedelta(seconds=ttl_seconds)
        with self._engine.begin() as c:
            result = c.execute(
                text(
                    "UPDATE agent_task_leases SET expires_at=:expires WHERE task_id=:task AND owner_id=:owner AND lease_token=:token AND expires_at>:now"
                ),
                {
                    "expires": expires,
                    "task": lease.task_id,
                    "owner": lease.owner_id,
                    "token": lease.lease_token,
                    "now": now,
                },
            )
            if result.rowcount != 1:
                raise LeaseRejected("lease owner/token is stale or expired")
        return Lease(lease.task_id, lease.owner_id, lease.lease_token, expires)

    def release(self, lease: Lease, *, now: datetime | None = None) -> None:
        with self._engine.begin() as c:
            result = c.execute(
                text(
                    "DELETE FROM agent_task_leases WHERE task_id=:task AND owner_id=:owner AND lease_token=:token"
                ),
                {
                    "task": lease.task_id,
                    "owner": lease.owner_id,
                    "token": lease.lease_token,
                },
            )
            if result.rowcount != 1:
                raise LeaseRejected("lease owner/token does not match")

    @staticmethod
    def _valid_ttl(ttl_seconds: int) -> bool:
        return 1 <= ttl_seconds <= 3600
