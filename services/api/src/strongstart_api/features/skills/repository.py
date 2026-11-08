"""PostgreSQL practice repository (C4-SKL-001 s8.2, s10.2).

One guarded ``skl_scope_state`` row per organization/context is locked ``FOR UPDATE`` for every
mutation; the currentness check, the record writes and the required audit share that single
transaction (no check-then-write across transactions). Records are append-only and immutable.
No lock is held during model or draft work: callers capture state, do external work, then
re-check under the lock.
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Connection, Engine, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from strongstart_contracts.skills import PracticeAuditEvent

from ...db import skl_records, skl_scope_state


class ScopeConflict(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Scope:
    current_source_version_id: str | None
    active_release_id: str | None
    revision: int


@dataclass(frozen=True)
class Record:
    record_id: str
    kind: str
    parent_id: str | None
    sha256: str
    payload: str
    actor_id: str
    ordinal: int


def new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(12)}"


def now() -> datetime:
    return datetime.now(UTC)


class PracticeRepository:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    # ---- guarded mutation boundary -------------------------------------------------------
    @contextmanager
    def locked(self, org: str, context_id: str) -> Iterator[tuple[Connection, Scope]]:
        with self.engine.begin() as conn:
            conn.execute(
                pg_insert(skl_scope_state)
                .values(organization_id=org, context_id=context_id, revision=0)
                .on_conflict_do_nothing()
            )
            row = (
                conn.execute(
                    select(skl_scope_state)
                    .where(
                        skl_scope_state.c.organization_id == org,
                        skl_scope_state.c.context_id == context_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .one()
            )
            yield (
                conn,
                Scope(row["current_source_version_id"], row["active_release_id"], row["revision"]),
            )

    def set_scope(
        self, conn: Connection, org: str, context_id: str, expected: Scope, **values: Any
    ) -> None:
        result = conn.execute(
            update(skl_scope_state)
            .where(
                skl_scope_state.c.organization_id == org,
                skl_scope_state.c.context_id == context_id,
                skl_scope_state.c.revision == expected.revision,
            )
            .values(revision=expected.revision + 1, **values)
        )
        if result.rowcount != 1:  # defence in depth; the row lock already serializes
            raise ScopeConflict("scope_revision_changed")

    def add(
        self,
        conn: Connection,
        org: str,
        context_id: str,
        kind: str,
        record_id: str,
        payload: str,
        actor: str,
        *,
        parent_id: str | None = None,
        sha256: str | None = None,
    ) -> None:
        conn.execute(
            skl_records.insert().values(
                record_id=record_id,
                organization_id=org,
                context_id=context_id,
                kind=kind,
                parent_id=parent_id,
                sha256=sha256 or hashlib.sha256(payload.encode()).hexdigest(),
                payload=payload,
                actor_id=actor,
            )
        )

    def audit(
        self,
        conn: Connection,
        org: str,
        context_id: str,
        action: str,
        object_id: str,
        actor: str,
        detail: str,
    ) -> None:
        event = PracticeAuditEvent(
            event_id=new_id("skl-audit"),
            action=action,
            object_id=object_id,
            actor_id=actor,
            at=now(),
            detail=detail[:300],
        )
        self.add(
            conn,
            org,
            context_id,
            "audit",
            event.event_id,
            event.model_dump_json(),
            actor,
            parent_id=object_id,
        )

    # ---- reads (no locks) ----------------------------------------------------------------
    def scope(self, org: str, context_id: str) -> Scope:
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(skl_scope_state).where(
                        skl_scope_state.c.organization_id == org,
                        skl_scope_state.c.context_id == context_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return Scope(None, None, 0)
        return Scope(row["current_source_version_id"], row["active_release_id"], row["revision"])

    def records(self, org: str, context_id: str, kind: str) -> list[Record]:
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(skl_records)
                .where(
                    skl_records.c.organization_id == org,
                    skl_records.c.context_id == context_id,
                    skl_records.c.kind == kind,
                )
                .order_by(skl_records.c.ordinal)
            ).mappings()
            return [self._record(r) for r in rows]

    def get(self, org: str, kind: str, record_id: str) -> Record | None:
        """Organization-scoped: another org's ID is indistinguishable from an unknown one."""
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(skl_records).where(
                        skl_records.c.organization_id == org,
                        skl_records.c.kind == kind,
                        skl_records.c.record_id == record_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
        return self._record(row) if row else None

    @staticmethod
    def _record(row: Any) -> Record:
        return Record(
            row["record_id"],
            row["kind"],
            row["parent_id"],
            row["sha256"],
            row["payload"],
            row["actor_id"],
            row["ordinal"],
        )
