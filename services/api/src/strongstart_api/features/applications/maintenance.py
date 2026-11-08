"""Explicit operator-only epoch rotation after reset/restore; never called by a GET."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime

from sqlalchemy import Engine, update

from strongstart_contracts.answers import AuditEvent

from ...db import c_store_state
from .postgres_store import PostgresAnswerStore
from .store import StoreState


def rotate_dataset_epoch(engine: Engine, organization_id: str, expected: StoreState) -> StoreState:
    """Requires operator UPDATE(epoch), deliberately absent from the runtime grants."""
    store = PostgresAnswerStore(engine)
    with store.unit_of_work(organization_id, expected):
        active = store._active.get()
        assert active is not None
        active[1].execute(
            update(c_store_state)
            .where(c_store_state.c.organization_id == organization_id)
            .values(
                epoch="c-dataset-" + secrets.token_hex(16), revision=c_store_state.c.revision + 1
            )
        )
        store.add_audit(
            organization_id,
            AuditEvent(
                event_id="audit-" + secrets.token_hex(16),
                actor_id="operator-recovery",
                action="approval_staled",
                object_type="dataset_epoch",
                object_id=organization_id,
                object_version=str(expected.revision),
                decision="rotate_after_recovery",
                at=datetime.now(UTC),
                details={"reason": "dataset_epoch_rotated"},
            ),
        )
    return store.state(organization_id)
