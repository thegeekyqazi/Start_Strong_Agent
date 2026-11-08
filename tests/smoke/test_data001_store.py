"""Real PostgreSQL durable C contract; no mocked SQL or approval producers."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, cast

import pytest
from fastapi import FastAPI
from sqlalchemy import select, update

from strongstart_api.config import Settings
from strongstart_api.db import (
    c_answer_versions,
    c_exports,
)
from strongstart_api.features.applications.approval import Context
from strongstart_api.features.applications.postgres_store import PostgresAnswerStore
from strongstart_api.features.applications.resolver import StoreApprovedAnswerResolver
from strongstart_api.features.applications.rules.policy import fixture_policy
from strongstart_api.features.applications.store import (
    AnswerStore,
    InMemoryAnswerStore,
    NotFoundInStore,
    StaleExpectation,
    StoreFailure,
)
from strongstart_api.features.applications.workspace import (
    DefinitionWorkspaceSource,
    FixtureWorkspaceSource,
)
from strongstart_api.features.automation.public import build_application_definition_reader
from strongstart_contracts import ChangedVersion, ChangeSet
from tests.data.db_support import runtime_role
from tests.data.support import prepared
from tests.integration.support import save

pytestmark = pytest.mark.db


def reader(store: AnswerStore, settings: Settings) -> StoreApprovedAnswerResolver:
    source = DefinitionWorkspaceSource(
        build_application_definition_reader(settings), FixtureWorkspaceSource()
    )
    return StoreApprovedAnswerResolver(
        lambda org: Context(store, source, fixture_policy(), settings, org), True
    )


@pytest.mark.parametrize("backend", ["memory", "postgres"])
def test_full_c_store_contract_and_exact_roundtrip(data_db, tmp_path, backend):
    selected = InMemoryAnswerStore() if backend == "memory" else PostgresAnswerStore(data_db.engine)
    c, settings, pub, version, approval, store = prepared(data_db, tmp_path, selected)
    copied = store.get_version("demo-org", version["answer_version_id"])
    assert copied.text == "  L'été 🦎\r\nLinked: {{fact:demo-fact-children-served}}.  "
    assert copied.question_set_id == pub["question_set_id"]
    assert copied.rendered.renderer_version == "c-fact-renderer/1"
    assert copied.rendered.model_dump(mode="json") == version["rendered"]
    assert [d.model_dump() for d in copied.dependencies] == version["dependencies"]
    content = reader(store, settings).resolve_for_prefill("demo-org", approval)
    assert content.provenance.is_simulated and content.is_fixture
    assert content.approval == reader(store, settings).resolve("demo-org", approval)
    for org in ("other-org", "unknown-org"):
        assert store.versions(org, copied.question_id) == []
        with pytest.raises(NotFoundInStore):
            store.get_version(org, copied.answer_version_id)
        with pytest.raises(NotFoundInStore):
            store.capture_approval(org, approval)
    note = c.post(
        "/api/applications/answers/notes",
        json={"answer_version_id": copied.answer_version_id, "text": "  Staff note 🦎\r\nexact  "},
    )
    assert note.status_code == 201, note.text
    proposal = c.post(
        "/api/applications/answers/reviews",
        json={"answer_version_id": copied.answer_version_id, "role": "meaning_reviewer"},
    )
    assert proposal.status_code == 201, proposal.text
    export = c.post(
        "/api/applications/exports",
        json={
            "mode": "reviewed",
            "question_ids": [copied.question_id],
            "question_set_id": pub["question_set_id"],
        },
    )
    assert export.status_code == 200 and not export.json()["blocked"], export.text
    eid = export.json()["export_id"]
    blob = store.get_export("demo-org", eid)
    assert b"SYNTHETIC DEMO DATA" in blob.audit
    assert store.notes("demo-org")[0].text == "  Staff note 🦎\r\nexact  "
    assert store.proposals("demo-org")[0].provenance.is_simulated
    assert {e.action for e in store.audit("demo-org")} >= {
        "answer_version_saved",
        "approval_decided",
        "review_note_added",
        "reviewer_proposal_added",
        "export_created",
    }
    if backend == "postgres":
        fresh = PostgresAnswerStore(data_db.engine)
        assert fresh.get_version("demo-org", copied.answer_version_id) == copied
        assert fresh.get_export("demo-org", eid) == blob
        assert fresh.notes("demo-org") == store.notes("demo-org")
        assert fresh.proposals("demo-org") == store.proposals("demo-org")
        fresh_content = reader(fresh, settings).resolve_for_prefill("demo-org", approval)
        assert fresh_content.model_dump(exclude={"currentness_checked_at"}) == content.model_dump(
            exclude={"currentness_checked_at"}
        )


@pytest.mark.parametrize(
    "failure", ["save", "decision", "note", "proposal", "export", "change_set"]
)
def test_mutations_and_required_audit_roll_back_together(data_db, tmp_path, monkeypatch, failure):
    c, _, pub, version, _, store = prepared(data_db, tmp_path)
    before = store.state("demo-org")
    old_history = store.all_versions("demo-org")
    old_audit = store.audit("demo-org")

    def fail(*args, **kwargs):
        raise StoreFailure("injected_audit_failure")

    monkeypatch.setattr(store, "add_audit", fail)
    if failure == "save":
        response = c.post(
            "/api/applications/answers/versions",
            json={
                "question_id": version["question_id"],
                "question_version": 1,
                "question_set_id": pub["question_set_id"],
                "evidence_bundle_id": "demo-evidence-a-v1",
                "text": "Edited",
                "expected_answer_version": 1,
            },
        )
    elif failure == "decision":
        # Save another question first with normal audit, then fail its decision audit.
        monkeypatch.undo()
        v2 = save(c, pub, "pf-org-name", "Synthetic organization")
        before, old_history, old_audit = (
            store.state("demo-org"),
            store.all_versions("demo-org"),
            store.audit("demo-org"),
        )
        monkeypatch.setattr(store, "add_audit", fail)
        response = c.post(
            "/api/applications/answers/decisions",
            json={
                "answer_version_id": v2["answer_version_id"],
                "expected_content_sha256": v2["content_sha256"],
                "expected_snapshot_sha256": v2["snapshot_sha256"],
                "decision": "approve",
                "acknowledge_review_items": True,
            },
        )
        assert store.decision_for("demo-org", v2["answer_version_id"]) is None
    elif failure == "note":
        response = c.post(
            "/api/applications/answers/notes",
            json={"answer_version_id": version["answer_version_id"], "text": "Must roll back"},
        )
        assert store.notes("demo-org") == []
    elif failure == "proposal":
        response = c.post(
            "/api/applications/answers/reviews",
            json={"answer_version_id": version["answer_version_id"], "role": "meaning_reviewer"},
        )
        assert store.proposals("demo-org") == []
    elif failure == "export":
        response = c.post(
            "/api/applications/exports",
            json={
                "mode": "reviewed",
                "question_ids": [version["question_id"]],
                "question_set_id": pub["question_set_id"],
            },
        )
        with data_db.engine.connect() as conn:
            assert conn.execute(select(c_exports.c.export_id)).all() == []
    else:
        response = c.post("/api/applications/fixture/change-sets/demo-change-fact-v2/apply")
        assert store.applied_change_sets("demo-org") == []
    assert response.status_code == 503, response.text
    assert store.state("demo-org") == before and store.all_versions("demo-org") == old_history
    assert store.audit("demo-org") == old_audit


@pytest.mark.parametrize(
    "corrupt", ["text", "rendered", "snapshot", "unknown_version", "malformed"]
)
def test_corrupt_payload_is_refused_with_sanitized_diagnostics(data_db, tmp_path, corrupt):
    _, _, _, version, _, store = prepared(data_db, tmp_path)
    with data_db.engine.begin() as conn:
        row = (
            conn.execute(
                select(c_answer_versions).where(
                    c_answer_versions.c.answer_version_id == version["answer_version_id"]
                )
            )
            .mappings()
            .one()
        )
        payload = json.loads(row["payload"])
        updates: dict[str, Any] = {}
        if corrupt == "text":
            payload["text"] += "x"
        elif corrupt == "rendered":
            payload["rendered"]["text"] += "x"
        elif corrupt == "snapshot":
            payload["snapshot_sha256"] = "0" * 64
        elif corrupt == "unknown_version":
            updates["payload_version"] = 999
        else:
            payload["check"] = {"unrecognized": "DO NOT LEAK THIS TEXT"}
        updates["payload"] = json.dumps(payload)
        conn.execute(
            update(c_answer_versions)
            .where(c_answer_versions.c.answer_version_id == version["answer_version_id"])
            .values(**updates)
        )
    with pytest.raises(StoreFailure, match="stored_integrity_failure") as exc:
        store.get_version("demo-org", version["answer_version_id"])
    assert "DO NOT LEAK" not in str(exc.value)


def test_change_set_exact_replay_and_conflict(data_db, tmp_path):
    _, _, _, _, _, store = prepared(data_db, tmp_path)
    change = ChangeSet(
        change_set_id="test-change",
        changes=[
            ChangedVersion(
                kind="fact",
                ref_id="demo-fact-children-served",
                previous_version="1",
                new_version="2",
            )
        ],
        affected_refs=[],
    )
    store.apply_change_set("demo-org", change)
    state = store.state("demo-org")
    assert PostgresAnswerStore(data_db.engine).applied_change_sets("demo-org") == [change]
    assert (
        store.apply_change_set("demo-org", change) == ["test-change"]
        and store.state("demo-org") == state
    )
    with pytest.raises(StaleExpectation, match="change_set_payload_conflict"):
        store.apply_change_set(
            "demo-org", change.model_copy(update={"affected_refs": ["different"]})
        )


def test_nonowner_runtime_performs_c_workflow(data_db, tmp_path):
    data_db.migrate()
    from strongstart_api.seed import seed_demo
    from tests.conftest import BUNDLE_PATH

    seed_demo(data_db.engine, BUNDLE_PATH)
    with runtime_role(data_db) as role:
        _, _, _, version, approval, store = prepared(
            data_db, tmp_path, PostgresAnswerStore(role.engine)
        )
        assert (
            store.capture_approval("demo-org", approval).version.answer_version_id
            == version["answer_version_id"]
        )
        assert store.audit("demo-org")


def test_exact_decimal_bindings_order_timezone_and_audit_credentials(data_db, tmp_path):
    from strongstart_api.features.applications.audit import redact
    from strongstart_api.features.applications.deps import get_workspace_source
    from strongstart_api.seed import seed_demo
    from tests.conftest import BUNDLE_PATH
    from tests.data.support import client_for
    from tests.integration.support import publish

    data_db.migrate()
    seed_demo(data_db.engine, BUNDLE_PATH)
    store = PostgresAnswerStore(data_db.engine)
    c, settings = client_for(store, tmp_path)
    decimal = "12345678901234567890.001230"

    class ExactWorkspace(DefinitionWorkspaceSource):
        def get(self, organization_id, question_set_id=None):
            ws = super().get(organization_id, question_set_id)
            facts = [
                f.model_copy(update={"value": decimal, "raw_value": decimal})
                if f.fact_id == "demo-fact-children-served"
                else f
                for f in ws.evidence_bundle.facts
            ]
            return ws.model_copy(
                update={"evidence_bundle": ws.evidence_bundle.model_copy(update={"facts": facts})}
            )

    source = ExactWorkspace(build_application_definition_reader(settings), FixtureWorkspaceSource())
    cast(FastAPI, c.app).dependency_overrides[get_workspace_source] = lambda: source
    pub = publish(c)
    version = save(c, pub, "pf-summary", "  {{fact:demo-fact-children-served}}.\r\n 🦎 ")
    stored = store.get_version("demo-org", version["answer_version_id"])
    assert decimal in stored.rendered.text
    assert stored.rendered.bindings[0].rendered_text.startswith(decimal)
    assert [d.model_dump() for d in stored.dependencies] == version["dependencies"]
    assert stored.created_at.utcoffset() == stored.checked_at.utcoffset() == timedelta(0)
    canary = Settings(_env_file=None, database_url="postgresql://user:p%40ss%3Acanary@localhost/db")
    assert canary.database_url is not None
    cleaned = redact(canary.database_url + " p@ss:canary", canary)
    assert "p@ss:canary" not in cleaned and "postgresql://" not in cleaned
    assert all(stored.text not in str(e.details) for e in store.audit("demo-org"))
    from strongstart_api.features.applications.audit import record

    event = record(
        store,
        canary,
        organization_id="demo-org",
        actor_id="canary-test",
        action="export_blocked",
        object_type="test",
        object_id="canary-probe",
        object_version="1",
        decision="blocked",
        details={"probe": canary.database_url + " p@ss:canary"},
    )
    assert store.audit("demo-org")[-1] == event
    assert "p@ss:canary" not in str(store.audit("demo-org")[-1].details)
    assert "postgresql://" not in str(store.audit("demo-org")[-1].details)
