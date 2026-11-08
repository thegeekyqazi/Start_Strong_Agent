"""Durable C store. No process cache, replayed writes, external calls or implicit seeding.

Business services bracket state and audit with unit_of_work. Direct port mutations also
have a short transaction. Lock order: organization -> C state -> lineage/record. Reads
outside a unit of work release their connection before caller performs dependency work.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import fields
from typing import Any, cast

from pydantic import BaseModel, TypeAdapter
from sqlalchemy import Connection, Engine, Table, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from strongstart_contracts import ChangeSet
from strongstart_contracts.answers import AuditEvent, ExportResult, ReviewerProposal, ReviewNote
from strongstart_contracts.approval_integrity import approval_snapshot_sha256

from ...db import (
    c_answer_heads,
    c_answer_versions,
    c_audit_events,
    c_change_sets,
    c_decisions,
    c_exports,
    c_notes,
    c_proposals,
    c_store_state,
    organizations,
)
from .store import (
    ApprovalRead,
    ExportTooLarge,
    NotFoundInStore,
    StaleExpectation,
    StoredDecision,
    StoredExport,
    StoredVersion,
    StoreFailure,
    StoreState,
)


def _hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _encode(value: Any) -> str:
    return TypeAdapter(type(value)).dump_json(value).decode("utf-8")


def _decode[T](cls: type[T], row: Any, key: str = "payload") -> T:
    try:
        if row["payload_version"] != 1:
            raise ValueError
        data = json.loads(row[key])
        if cls is StoredVersion:
            required = {f.name for f in fields(StoredVersion)}
        elif cls is StoredDecision:
            required = {f.name for f in fields(StoredDecision)}
        else:
            required = set(cast(type[BaseModel], cls).model_fields)
        if set(data) != required:
            raise ValueError
        if cls is StoredVersion and "renderer_version" not in data["rendered"]:
            raise ValueError
        result = TypeAdapter(cls).validate_json(row[key])
        if json.loads(TypeAdapter(cls).dump_json(result)) != data:
            # Nested omitted defaults/coerced values cannot acquire new meaning on load.
            raise ValueError
        for name in (
            "answer_version_id",
            "note_id",
            "proposal_id",
            "change_set_id",
            "export_id",
            "event_id",
            "actor_id",
            "action",
        ):
            if name in row and hasattr(result, name) and getattr(result, name) != row[name]:
                raise ValueError
        for name in ("created_at", "at", "decided_at", "checked_at"):
            value = getattr(result, name, None)
            if value is not None and value.tzinfo is None:
                raise ValueError
        return result
    except Exception:
        raise StoreFailure("stored_integrity_failure") from None


class PostgresAnswerStore:
    is_fixture = False  # backend, never used to infer content provenance
    backend = "postgres"
    durable = True

    def __init__(self, engine: Engine, max_export_bytes: int = 8_388_608) -> None:
        self.engine, self.max_export_bytes = engine, max_export_bytes
        self._active: ContextVar[tuple[str, Connection] | None] = ContextVar("c_uow", default=None)

    @contextmanager
    def _read(self, org: str) -> Iterator[Connection]:
        active = self._active.get()
        if active is not None:
            if active[0] != org:
                raise StoreFailure("organization_scope_mismatch")
            yield active[1]
            return
        try:
            with self.engine.connect() as conn:
                yield conn
        except SQLAlchemyError:
            raise StoreFailure() from None

    def state(self, organization_id: str) -> StoreState:
        with self._read(organization_id) as conn:
            row = (
                conn.execute(
                    select(c_store_state).where(c_store_state.c.organization_id == organization_id)
                )
                .mappings()
                .one_or_none()
            )
            return StoreState(None, 0) if row is None else StoreState(row["epoch"], row["revision"])

    @contextmanager
    def unit_of_work(
        self, organization_id: str, expected: StoreState | None = None
    ) -> Iterator[None]:
        active = self._active.get()
        if active is not None:
            if active[0] != organization_id:
                raise StoreFailure("organization_scope_mismatch")
            if expected is not None and self.state(organization_id) != expected:
                raise StaleExpectation("store_revision_changed")
            yield
            return
        phase = "writing"
        try:
            with self.engine.connect() as conn:
                tx = conn.begin()
                token = self._active.set((organization_id, conn))
                try:
                    # DATA-001 SERIALIZATION GUARD: mutation audit removes this parent
                    # lock plus state FOR UPDATE; no service/external calls under locks.
                    known = conn.execute(
                        select(organizations.c.id)
                        .where(organizations.c.id == organization_id)
                        .with_for_update()
                    ).scalar_one_or_none()
                    if known is None:
                        raise NotFoundInStore()
                    conn.execute(
                        pg_insert(c_store_state)
                        .values(
                            organization_id=organization_id,
                            epoch="c-dataset-" + secrets.token_hex(16),
                            revision=0,
                        )
                        .on_conflict_do_nothing()
                    )
                    row = (
                        conn.execute(
                            select(c_store_state)
                            .where(c_store_state.c.organization_id == organization_id)
                            .with_for_update()
                        )
                        .mappings()
                        .one()
                    )
                    # DATA-001 COMMIT GUARD: mutation audit disables this predicate only.
                    if expected is not None and (
                        row["revision"] != expected.revision
                        or (expected.epoch is not None and row["epoch"] != expected.epoch)
                    ):
                        raise StaleExpectation("store_revision_changed")
                    yield
                    phase = "committing"
                    tx.commit()
                except BaseException:
                    if phase == "committing":
                        # The server may have committed. Discard this connection, never replay.
                        conn.invalidate()
                    elif tx.is_active:
                        tx.rollback()
                    raise
                finally:
                    self._active.reset(token)
        except IntegrityError:
            raise StaleExpectation("immutable_record_conflict") from None
        except SQLAlchemyError:
            raise StoreFailure(
                "commit_outcome_unknown" if phase == "committing" else "database_unavailable"
            ) from None

    def _changed(self, conn: Connection, org: str) -> None:
        conn.execute(
            update(c_store_state)
            .where(c_store_state.c.organization_id == org)
            .values(revision=c_store_state.c.revision + 1)
        )

    def _version(self, row: Any) -> StoredVersion:
        version = _decode(StoredVersion, row)
        if (
            version.question_version < 1
            or version.check.question_id != version.question_id
            or version.check.question_version != version.question_version
            or version.check.evidence_bundle_id != version.evidence_bundle_id
            or version.check.submitted_text_sha256 != version.content_sha256
            or version.check.rendered != version.rendered
            or version.organization_id != row["organization_id"]
            or version.answer_version_id != row["answer_version_id"]
            or version.question_id != row["question_id"]
            or version.answer_version != row["answer_version"]
            or _hash(version.text.encode("utf-8")) != version.content_sha256
            or version.content_sha256 != row["content_sha256"]
            or _hash(version.rendered.text.encode("utf-8")) != version.rendered.text_sha256
            or version.rendered.text_sha256 != row["rendered_sha256"]
            or version.snapshot_sha256 != row["snapshot_sha256"]
            or approval_snapshot_sha256(
                version.content_sha256, version.organization_id, list(version.dependencies)
            )
            != version.snapshot_sha256
            or version.created_at.tzinfo is None
            or version.checked_at.tzinfo is None
            or (
                version.a4_binding is not None
                and version.a4_binding.organization_id != version.organization_id
            )
        ):
            raise StoreFailure("stored_integrity_failure")
        return version

    def versions(self, organization_id: str, question_id: str) -> list[StoredVersion]:
        with self._read(organization_id) as conn:
            return [
                self._version(r)
                for r in conn.execute(
                    select(c_answer_versions)
                    .where(
                        c_answer_versions.c.organization_id == organization_id,
                        c_answer_versions.c.question_id == question_id,
                    )
                    .order_by(c_answer_versions.c.answer_version)
                ).mappings()
            ]

    def all_versions(self, organization_id: str) -> list[StoredVersion]:
        with self._read(organization_id) as conn:
            return [
                self._version(r)
                for r in conn.execute(
                    select(c_answer_versions)
                    .where(c_answer_versions.c.organization_id == organization_id)
                    .order_by(c_answer_versions.c.question_id, c_answer_versions.c.answer_version)
                ).mappings()
            ]

    def get_version(self, organization_id: str, answer_version_id: str) -> StoredVersion:
        with self._read(organization_id) as conn:
            row = (
                conn.execute(
                    select(c_answer_versions).where(
                        c_answer_versions.c.organization_id == organization_id,
                        c_answer_versions.c.answer_version_id == answer_version_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise NotFoundInStore()
            return self._version(row)

    def append_version(
        self,
        organization_id: str,
        question_id: str,
        expected_latest: int | None,
        build: Callable[[int], StoredVersion],
    ) -> StoredVersion:
        with self.unit_of_work(organization_id), self._read(organization_id) as conn:
            conn.execute(
                pg_insert(c_answer_heads)
                .values(organization_id=organization_id, question_id=question_id, latest_version=0)
                .on_conflict_do_nothing()
            )
            current = conn.execute(
                select(c_answer_heads.c.latest_version).where(
                    c_answer_heads.c.organization_id == organization_id,
                    c_answer_heads.c.question_id == question_id,
                )
            ).scalar_one()
            if (current or None) != expected_latest:
                raise StaleExpectation("answer_version_conflict", current or None)
            version = build(current + 1)
            payload = _encode(version)
            values = {
                "organization_id": organization_id,
                "question_id": question_id,
                "answer_version_id": version.answer_version_id,
                "answer_version": current + 1,
                "content_sha256": version.content_sha256,
                "rendered_sha256": version.rendered.text_sha256,
                "snapshot_sha256": version.snapshot_sha256,
                "payload_version": 1,
                "payload": payload,
            }
            self._version(values)
            conn.execute(insert(c_answer_versions).values(**values))
            conn.execute(
                update(c_answer_heads)
                .where(
                    c_answer_heads.c.organization_id == organization_id,
                    c_answer_heads.c.question_id == question_id,
                )
                .values(latest_version=current + 1)
            )
            self._changed(conn, organization_id)
            return version

    def _decision(self, row: Any) -> StoredDecision:
        d = _decode(StoredDecision, row)
        if (
            d.approval_id != row["approval_id"]
            or d.answer_version_id != row["answer_version_id"]
            or d.decision != row["decision"]
            or d.decided_at.tzinfo is None
        ):
            raise StoreFailure("stored_integrity_failure")
        return d

    def decision_for(self, organization_id: str, answer_version_id: str) -> StoredDecision | None:
        with self._read(organization_id) as conn:
            row = (
                conn.execute(
                    select(c_decisions).where(
                        c_decisions.c.organization_id == organization_id,
                        c_decisions.c.answer_version_id == answer_version_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            return None if row is None else self._decision(row)

    def record_decision(
        self, organization_id: str, decision: StoredDecision, must_be_latest: bool
    ) -> StoredDecision:
        with self.unit_of_work(organization_id), self._read(organization_id) as conn:
            version = self.get_version(organization_id, decision.answer_version_id)
            latest = conn.execute(
                select(c_answer_heads.c.latest_version).where(
                    c_answer_heads.c.organization_id == organization_id,
                    c_answer_heads.c.question_id == version.question_id,
                )
            ).scalar_one()
            if must_be_latest and latest != version.answer_version:
                raise StaleExpectation("not_latest_version")
            if self.decision_for(organization_id, decision.answer_version_id) is not None:
                raise StaleExpectation("already_decided")
            if (
                decision.content_sha256 != version.content_sha256
                or decision.snapshot_sha256 != version.snapshot_sha256
            ):
                raise StaleExpectation("decision_snapshot_mismatch")
            conn.execute(
                insert(c_decisions).values(
                    organization_id=organization_id,
                    approval_id=decision.approval_id,
                    answer_version_id=decision.answer_version_id,
                    decision=decision.decision,
                    payload_version=1,
                    payload=_encode(decision),
                )
            )
            self._changed(conn, organization_id)
            return decision

    def capture_approval(self, organization_id: str, approval_id: str) -> ApprovalRead:
        # One SQL statement / MVCC observation captures all identities and state. No scan.
        with self._read(organization_id) as conn:
            row = (
                conn.execute(
                    select(
                        c_answer_versions,
                        c_decisions.c.approval_id,
                        c_decisions.c.decision,
                        c_decisions.c.answer_version_id.label("decision_version"),
                        c_decisions.c.payload.label("decision_payload"),
                        c_decisions.c.payload_version.label("decision_payload_version"),
                        c_store_state.c.epoch,
                        c_store_state.c.revision,
                    )
                    .select_from(
                        c_answer_versions.join(
                            c_decisions,
                            (c_answer_versions.c.organization_id == c_decisions.c.organization_id)
                            & (
                                c_answer_versions.c.answer_version_id
                                == c_decisions.c.answer_version_id
                            ),
                        ).join(
                            c_store_state,
                            c_store_state.c.organization_id == c_answer_versions.c.organization_id,
                        )
                    )
                    .where(
                        c_decisions.c.organization_id == organization_id,
                        c_decisions.c.approval_id == approval_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise NotFoundInStore()
            version = self._version(row)
            decision = self._decision(
                {
                    "payload_version": row["decision_payload_version"],
                    "payload": row["decision_payload"],
                    "approval_id": row["approval_id"],
                    "answer_version_id": row["decision_version"],
                    "decision": row["decision"],
                }
            )
            return ApprovalRead(version, decision, row["revision"], row["epoch"])

    def approval_read_current(self, organization_id: str, captured: ApprovalRead) -> bool:
        return self.state(organization_id) == StoreState(captured.epoch, captured.revision)

    def _append_model(self, org: str, table: Table, id_key: str, value: Any) -> Any:
        with self.unit_of_work(org), self._read(org) as conn:
            self.get_version(org, value.answer_version_id)
            conn.execute(
                insert(table).values(
                    organization_id=org,
                    **{id_key: getattr(value, id_key)},
                    answer_version_id=value.answer_version_id,
                    payload_version=1,
                    payload=_encode(value),
                )
            )
        return value

    def add_note(self, organization_id: str, note: ReviewNote) -> ReviewNote:
        return self._append_model(organization_id, c_notes, "note_id", note)  # type: ignore[no-any-return]

    def add_proposal(self, organization_id: str, proposal: ReviewerProposal) -> ReviewerProposal:
        return self._append_model(organization_id, c_proposals, "proposal_id", proposal)  # type: ignore[no-any-return]

    def notes(self, organization_id: str) -> list[ReviewNote]:
        with self._read(organization_id) as conn:
            return [
                _decode(ReviewNote, r)
                for r in conn.execute(
                    select(c_notes)
                    .where(c_notes.c.organization_id == organization_id)
                    .order_by(c_notes.c.ordinal)
                ).mappings()
            ]

    def proposals(self, organization_id: str) -> list[ReviewerProposal]:
        with self._read(organization_id) as conn:
            return [
                _decode(ReviewerProposal, r)
                for r in conn.execute(
                    select(c_proposals)
                    .where(c_proposals.c.organization_id == organization_id)
                    .order_by(c_proposals.c.ordinal)
                ).mappings()
            ]

    def apply_change_set(self, organization_id: str, change_set: ChangeSet) -> list[str]:
        payload = _encode(change_set)
        with self.unit_of_work(organization_id), self._read(organization_id) as conn:
            existing = (
                conn.execute(
                    select(c_change_sets).where(
                        c_change_sets.c.organization_id == organization_id,
                        c_change_sets.c.change_set_id == change_set.change_set_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                if _decode(ChangeSet, existing) != change_set:
                    raise StaleExpectation("change_set_payload_conflict")
            else:
                conn.execute(
                    insert(c_change_sets).values(
                        organization_id=organization_id,
                        change_set_id=change_set.change_set_id,
                        payload_version=1,
                        payload=payload,
                        payload_sha256=_hash(payload.encode("utf-8")),
                    )
                )
                self._changed(conn, organization_id)
            return [c.change_set_id for c in self.applied_change_sets(organization_id)]

    def applied_change_sets(self, organization_id: str) -> list[ChangeSet]:
        with self._read(organization_id) as conn:
            out = []
            for row in conn.execute(
                select(c_change_sets)
                .where(c_change_sets.c.organization_id == organization_id)
                .order_by(c_change_sets.c.ordinal)
            ).mappings():
                if _hash(row["payload"].encode("utf-8")) != row["payload_sha256"]:
                    raise StoreFailure("stored_integrity_failure")
                out.append(_decode(ChangeSet, row))
            return out

    def add_export(self, organization_id: str, export: StoredExport) -> None:
        if len(export.docx) + len(export.audit) > self.max_export_bytes:
            raise ExportTooLarge()
        if (
            export.organization_id != organization_id
            or export.result.blocked
            or export.result.export_id is None
        ):
            raise StoreFailure("stored_integrity_failure")
        if (
            _hash(export.docx) != export.result.docx_sha256
            or _hash(export.audit) != export.result.audit_sha256
        ):
            raise StoreFailure("stored_integrity_failure")
        with self.unit_of_work(organization_id), self._read(organization_id) as conn:
            conn.execute(
                insert(c_exports).values(
                    organization_id=organization_id,
                    export_id=export.result.export_id,
                    payload_version=1,
                    payload=_encode(export.result),
                    docx=export.docx,
                    audit=export.audit,
                    docx_sha256=export.result.docx_sha256,
                    audit_sha256=export.result.audit_sha256,
                )
            )

    def get_export(self, organization_id: str, export_id: str) -> StoredExport:
        with self._read(organization_id) as conn:
            row = (
                conn.execute(
                    select(c_exports).where(
                        c_exports.c.organization_id == organization_id,
                        c_exports.c.export_id == export_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                raise NotFoundInStore()
            if len(row["docx"]) + len(row["audit"]) > self.max_export_bytes:
                raise ExportTooLarge()
            result = _decode(ExportResult, row)
            if (
                result.export_id != export_id
                or result.docx_sha256 != _hash(row["docx"])
                or result.audit_sha256 != _hash(row["audit"])
                or result.docx_sha256 != row["docx_sha256"]
                or result.audit_sha256 != row["audit_sha256"]
            ):
                raise StoreFailure("stored_integrity_failure")
            return StoredExport(organization_id, result, bytes(row["docx"]), bytes(row["audit"]))

    def add_audit(self, organization_id: str, event: AuditEvent) -> None:
        with self.unit_of_work(organization_id), self._read(organization_id) as conn:
            conn.execute(
                insert(c_audit_events).values(
                    organization_id=organization_id,
                    event_id=event.event_id,
                    actor_id=event.actor_id,
                    action=event.action,
                    payload_version=1,
                    payload=_encode(event),
                )
            )

    def audit(self, organization_id: str) -> list[AuditEvent]:
        with self._read(organization_id) as conn:
            return [
                _decode(AuditEvent, r)
                for r in conn.execute(
                    select(c_audit_events)
                    .where(c_audit_events.c.organization_id == organization_id)
                    .order_by(c_audit_events.c.ordinal)
                ).mappings()
            ]
