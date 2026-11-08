"""Real PostgreSQL constraint, resource and binary-integrity failure evidence."""

from __future__ import annotations

import time
from dataclasses import replace

import pytest
from psycopg import Error as PsycopgError
from sqlalchemy import event, insert, select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError

from strongstart_api.database_profile import build_engine
from strongstart_api.db import c_answer_versions, c_decisions, c_exports, c_notes, organizations
from strongstart_api.features.applications.postgres_store import PostgresAnswerStore
from strongstart_api.features.applications.store import (
    ExportTooLarge,
    NotFoundInStore,
    StoreFailure,
)
from tests.data.support import prepared

pytestmark = pytest.mark.db


@pytest.mark.parametrize(
    "bad",
    [
        "cross_note",
        "cross_decision",
        "duplicate_version",
        "nonpositive",
        "bad_decision",
        "duplicate_decision",
    ],
)
def test_database_enforces_scoped_immutable_constraints(data_db, tmp_path, bad):
    _, _, _, version, _, _ = prepared(data_db, tmp_path)
    with data_db.engine.begin() as conn:
        conn.execute(
            insert(organizations).values(
                id="other-org",
                display_name="SYNTHETIC other",
                provenance_class="simulated",
                is_simulated=True,
            )
        )
    with data_db.engine.connect() as conn:
        row = dict(conn.execute(select(c_answer_versions)).mappings().one())
        decision = dict(conn.execute(select(c_decisions)).mappings().one())
    with pytest.raises(IntegrityError) as failure, data_db.engine.begin() as conn:
        if bad == "cross_note":
            conn.execute(
                insert(c_notes).values(
                    note_id="foreign-note",
                    organization_id="other-org",
                    answer_version_id=version["answer_version_id"],
                    payload_version=1,
                    payload="{}",
                )
            )
        elif bad in {"cross_decision", "bad_decision", "duplicate_decision"}:
            decision["approval_id"] = "different-approval"
            if bad == "cross_decision":
                decision["organization_id"] = "other-org"
            if bad == "bad_decision":
                decision["decision"] = "maybe"
            conn.execute(insert(c_decisions).values(**decision))
        else:
            row["answer_version_id"] = "different-version"
            if bad == "nonpositive":
                row["answer_version"] = 0
            conn.execute(insert(c_answer_versions).values(**row))
    cause = failure.value.orig
    assert isinstance(cause, PsycopgError)
    expected = {
        "cross_note": "23503",
        "cross_decision": "23503",
        "duplicate_version": "23505",
        "duplicate_decision": "23505",
        "nonpositive": "23514",
        "bad_decision": "23514",
    }
    assert cause.sqlstate == expected[bad]
    if bad in {"nonpositive", "bad_decision"}:
        assert cause.diag.constraint_name == (
            "ck_c_version_positive" if bad == "nonpositive" else "ck_c_decision"
        )


def test_export_budget_corruption_and_org_scope(data_db, tmp_path):
    c, _, pub, version, _, store = prepared(data_db, tmp_path)
    body = {
        "mode": "reviewed",
        "question_ids": [version["question_id"]],
        "question_set_id": pub["question_set_id"],
    }
    store.max_export_bytes = 1
    response = c.post("/api/applications/exports", json=body)
    assert (
        response.status_code == 422 and response.json()["details"]["reason"] == "export_size_limit"
    )
    with data_db.engine.connect() as conn:
        assert not conn.execute(select(c_exports)).all()
    assert not any(e.action == "export_created" for e in store.audit("demo-org"))
    store.max_export_bytes = 8_388_608
    result = c.post("/api/applications/exports", json=body).json()
    blob = store.get_export("demo-org", result["export_id"])
    with pytest.raises(ExportTooLarge):
        store.add_export("demo-org", replace(blob, docx=bytes(8_388_609)))
    for org in ("other-org", "unknown-org"):
        with pytest.raises(NotFoundInStore):
            store.get_export(org, result["export_id"])
        assert (
            store.notes(org)
            == store.proposals(org)
            == store.audit(org)
            == store.applied_change_sets(org)
            == []
        )
        assert store.decision_for(org, version["answer_version_id"]) is None
    with data_db.engine.begin() as conn:
        conn.execute(update(c_exports).values(docx=b"corrupted bytes"))
    response = c.get(f"/api/applications/exports/{result['export_id']}/docx")
    assert response.status_code == 503 and b"corrupted bytes" not in response.content


def test_real_lock_statement_and_pool_timeout_release_resources(data_db, tmp_path):
    prepared(data_db, tmp_path)
    engine = build_engine(
        data_db.url,
        pool_size=1,
        max_overflow=0,
        pool_timeout=0.1,
        lock_timeout_ms=100,
        statement_timeout_ms=150,
    )
    store = PostgresAnswerStore(engine)
    before = store.state("demo-org")
    try:
        with data_db.engine.begin() as blocker:
            blocker.execute(text("select id from organizations where id='demo-org' for update"))
            started = time.monotonic()
            with pytest.raises(StoreFailure, match="database_unavailable"):
                with store.unit_of_work("demo-org"):
                    pytest.fail("lock timeout did not guard mutation")
            assert time.monotonic() - started < 3
        with pytest.raises(StoreFailure), store._read("demo-org") as conn:
            conn.execute(
                text("select pg_sleep(1)")
            )  # deliberate server timeout, not scheduling proof
        with engine.connect():
            started = time.monotonic()
            with pytest.raises(StoreFailure):
                store.state("demo-org")
            assert time.monotonic() - started < 3
        assert store.state("demo-org") == before
        with store.unit_of_work("demo-org", before):
            pass
    finally:
        engine.dispose()


def test_dropped_owned_connection_recovers_and_commit_fault_is_not_replayed(data_db, tmp_path):
    _, _, _, _, _, original = prepared(data_db, tmp_path)
    engine = build_engine(data_db.url, pool_size=1, max_overflow=0)
    store = PostgresAnswerStore(engine)
    try:
        state = store.state("demo-org")
        with engine.connect() as conn:
            pid = conn.execute(text("select pg_backend_pid()")).scalar_one()
        with data_db.engine.begin() as conn:
            assert conn.execute(
                text("select pg_terminate_backend(:pid)"), {"pid": pid}
            ).scalar_one()
        assert store.state("demo-org") == state  # pre-ping replaces dropped connection
        attempts = []

        def lost_commit(conn):
            attempts.append(True)
            raise OperationalError("commit", None, Exception("private connection failure"))

        event.listen(engine, "commit", lost_commit)
        with pytest.raises(StoreFailure, match="commit_outcome_unknown") as failure:
            with store.unit_of_work("demo-org", state):
                active = store._active.get()
                assert active is not None
                store._changed(active[1], "demo-org")
        assert len(attempts) == 1 and "private connection" not in str(failure.value)
        event.remove(engine, "commit", lost_commit)
        assert store.state("demo-org") == state == original.state("demo-org")
    finally:
        engine.dispose()
