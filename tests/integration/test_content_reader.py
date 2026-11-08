"""INT-01 through INT-10: actual C store/decisions, exact identities, consistent snapshots."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.applications.store import InMemoryAnswerStore
from strongstart_api.features.applications.workspace import (
    DefinitionWorkspaceSource,
    FixtureWorkspaceSource,
)
from strongstart_api.features.automation.public import build_application_definition_reader
from strongstart_contracts.fixture_adapters import ApprovalNotUsable

from .support import FACT, ORG, decide, prepare, publish, reader_for, save


@pytest.fixture
def setup(tmp_path):
    settings = Settings(
        _env_file=None,
        answer_store_backend="memory",
        auth_mode="fixture",
        dev_b_store_dir=tmp_path / "store",
    )
    app = create_app(settings)
    c = TestClient(app)
    pub = publish(c)
    v = save(c, pub, "pf-org-name", "Linked: {{fact:" + FACT + "}}.")
    approval = decide(c, v)
    return settings, app, c, pub, v, approval


def test_factory_store_epoch_parity_and_saved_rendering(setup):
    settings, app, c, pub, v, approval = setup
    reader = reader_for(app, settings)
    content = reader.resolve_for_prefill(ORG, approval)
    assert content.approval == reader.resolve(ORG, approval)
    assert content.rendered_text == v["rendered"]["text"]
    assert content.template_sha256 != content.rendered_sha256
    assert content.renderer_version == "c-fact-renderer/1"
    assert content.typed_value is None and content.provenance.is_simulated
    assert content.currentness_checked_at.utcoffset().total_seconds() == 0
    assert (
        reader_for(app, settings).resolve_for_prefill(ORG, approval).producer_epoch
        == content.producer_epoch
    )
    r = prepare(c, pub, {"pf-org-name": approval})
    assert r.status_code == 201, r.text
    assert r.json()["actions"][0]["intended_value"] == content.rendered_text
    assert r.json()["producers"]["approval_reader"] == "c_reader"
    other = create_app(settings)
    with pytest.raises(ApprovalNotUsable, match="no such approval"):
        reader_for(other, settings).resolve(ORG, approval)
    assert other.state.c3_answer_store.epoch != content.producer_epoch


@pytest.mark.parametrize("scope", ["other-org", "unknown-org"])
def test_unknown_other_org_indistinguishable(setup, scope):
    settings, app, _, _, _, approval = setup
    with pytest.raises(ApprovalNotUsable, match="no such approval"):
        reader_for(app, settings).resolve_for_prefill(scope, approval)


@pytest.mark.parametrize(
    "corrupt",
    [
        "text",
        "rendered",
        "decision_content",
        "decision_snapshot",
        "snapshot",
        "unsupported",
        "token",
    ],
)
def test_corrupted_saved_state_refused_by_both_readers(setup, corrupt):
    settings, app, _, _, v, approval = setup
    store = app.state.c3_answer_store
    with store._lock:
        org = store._org(ORG)
        q = v["question_id"]
        version = org.versions[q][-1]
        if corrupt == "text":
            version = replace(version, text=version.text + "x")
        elif corrupt == "rendered":
            version = replace(
                version, rendered=version.rendered.model_copy(update={"text_sha256": "0" * 64})
            )
        elif corrupt.startswith("decision_"):
            d = org.decisions[version.answer_version_id]
            field = "content_sha256" if corrupt == "decision_content" else "snapshot_sha256"
            org.decisions[version.answer_version_id] = replace(d, **{field: "0" * 64})
        elif corrupt == "snapshot":
            version = replace(version, snapshot_sha256="0" * 64)
        else:
            from strongstart_contracts.answers import UnsupportedMarker
            from tests.automation.prefill_support import sha

            rendered = version.rendered.model_copy(
                update={
                    "text": "{{fact:missing}}" if corrupt == "token" else "[unsupported: missing]",
                    "unsupported_markers": [
                        UnsupportedMarker(reason="missing", span_start=0, span_end=1)
                    ],
                }
            )
            rendered = rendered.model_copy(update={"text_sha256": sha(rendered.text)})
            version = replace(
                version,
                rendered=rendered,
                check=version.check.model_copy(update={"rendered": rendered}),
            )
        org.versions[q][-1] = version
    reader = reader_for(app, settings)
    for method in (reader.resolve, reader.resolve_for_prefill):
        with pytest.raises(ApprovalNotUsable):
            method(ORG, approval)


def test_old_version_rejection_and_store_replacement(setup):
    settings, app, c, pub, _, approval = setup
    v2 = save(c, pub, "pf-org-name", "Edited.", 1)
    rejection = decide(c, v2, "reject")
    reader = reader_for(app, settings)
    with pytest.raises(ApprovalNotUsable, match="newer_version_saved"):
        reader.resolve(ORG, approval)
    with pytest.raises(ApprovalNotUsable, match="rejected"):
        reader.resolve_for_prefill(ORG, rejection)
    app.state.c3_answer_store = InMemoryAnswerStore()
    with pytest.raises(ApprovalNotUsable, match="no such approval"):
        reader_for(app, settings).resolve_for_prefill(ORG, approval)


def test_concurrent_save_during_resolution_is_explicitly_refused(setup):
    settings, app, c, pub, _, approval = setup
    entered, release = threading.Event(), threading.Event()

    class PausedSource(DefinitionWorkspaceSource):
        def get(self, organization_id, question_set_id=None):
            entered.set()
            assert release.wait(5)
            return super().get(organization_id, question_set_id)

    source = PausedSource(build_application_definition_reader(settings), FixtureWorkspaceSource())
    reader = reader_for(app, settings, source)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(reader.resolve_for_prefill, ORG, approval)
        try:
            assert entered.wait(5)
            save(c, pub, "pf-org-name", "Changed during read.", 1)
        finally:
            release.set()
        with pytest.raises(ApprovalNotUsable, match="approval_changed_during_read"):
            future.result(timeout=5)


def test_inconsistent_unknown_fact_fixture_cannot_authorize_a_fill(setup):
    from strongstart_api.features.applications.store import StoredDecision

    settings, app, c, pub, _, _ = setup
    version = save(c, pub, "pf-summary", "Linked: {{fact:missing-fact}}.")
    assert (
        c.post(
            "/api/applications/answers/decisions",
            json={
                "answer_version_id": version["answer_version_id"],
                "decision": "approve",
                "expected_content_sha256": version["content_sha256"],
                "expected_snapshot_sha256": version["snapshot_sha256"],
                "acknowledge_review_items": True,
            },
        ).status_code
        == 422
    )
    # Deliberately inconsistent stored fixture: strip old findings and insert a forged
    # approve decision to prove a matching saved hash cannot bypass the live gate.
    store = app.state.c3_answer_store
    with store._lock:
        org = store._org(ORG)
        q = version["question_id"]
        stored = org.versions[q][-1]
        org.versions[q][-1] = replace(
            stored, check=stored.check.model_copy(update={"findings": []})
        )
    store.record_decision(
        ORG,
        StoredDecision(
            approval_id="apr-inconsistent-fixture",
            answer_version_id=stored.answer_version_id,
            decision="approve",
            content_sha256=stored.content_sha256,
            snapshot_sha256=stored.snapshot_sha256,
            reviewer_id="fixture-staff",
            reviewer_is_fixture_identity=True,
            acknowledged_review_items=True,
            note="inconsistent fixture",
            decided_at=stored.created_at,
        ),
        True,
    )
    with pytest.raises(ApprovalNotUsable, match="approval_gate_blocked"):
        reader_for(app, settings).resolve_for_prefill(ORG, "apr-inconsistent-fixture")
