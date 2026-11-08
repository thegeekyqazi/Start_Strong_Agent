"""Applications API boundaries (C1 spec s6): identity, fixture scope, versions, bodies."""

from __future__ import annotations

from .conftest import DRAFT_BODY, DRAFT_URL, make_client


def test_workspace_requires_identity() -> None:
    c = make_client()
    for r in (c.get("/api/applications/workspace"), c.post(DRAFT_URL, json=DRAFT_BODY)):
        assert r.status_code == 401 and r.json()["code"] == "unauthenticated"


def test_workspace_returns_labelled_fixture_data() -> None:
    body = make_client(auth_mode="fixture").get("/api/applications/workspace").json()
    assert body["is_fixture"] is True and "FIXTURE" in body["data_label"]
    assert [q["question_id"] for q in body["question_set"]["questions"]] == [
        "mission-q1",
        "services-q2",
        "partnership-q3",
        "pending-q4",
    ]
    fact = body["evidence_bundle"]["facts"][0]
    assert (fact["value"], fact["unit"], fact["reporting_period"]) == (
        "120",
        "children",
        "2025-09/2026-06",
    )
    assert fact["provenance"]["is_simulated"] is True


def test_workspace_unavailable_outside_fixture_mode() -> None:
    from strongstart_api.features.applications.router import get_workspace_source
    from strongstart_api.features.applications.workspace import UnconfiguredWorkspaceSource
    from strongstart_api.identity import require_identity
    from strongstart_contracts import SessionIdentity

    c = make_client()
    c.app.dependency_overrides[require_identity] = lambda: SessionIdentity(  # type: ignore[attr-defined]
        actor_id="a", organization_id="demo-org", roles=[], is_fixture=False, label="test"
    )
    c.app.dependency_overrides[get_workspace_source] = UnconfiguredWorkspaceSource  # type: ignore[attr-defined]
    r = c.get("/api/applications/workspace")
    assert r.status_code == 503 and r.json()["code"] == "capability_unavailable"


def test_draft_conflicts_and_unknowns() -> None:
    c = make_client(auth_mode="fixture")
    r = c.post(DRAFT_URL, json={**DRAFT_BODY, "question_version": 2})
    assert r.status_code == 409 and r.json()["code"] == "version_conflict"
    r = c.post("/api/applications/questions/nope-q9/draft", json=DRAFT_BODY)
    assert r.status_code == 404 and r.json()["details"]["reason"] == "unknown_question"
    r = c.post(DRAFT_URL, json={**DRAFT_BODY, "evidence_bundle_id": "other-bundle"})
    assert r.status_code == 404 and r.json()["details"]["reason"] == "unknown_evidence_bundle"


def test_client_cannot_send_approval_or_extra_fields() -> None:
    c = make_client(auth_mode="fixture")
    for extra in ({"approved": True}, {"status": "approved"}, {"organization_id": "other-org"}):
        r = c.post(DRAFT_URL, json={**DRAFT_BODY, **extra})
        assert r.status_code == 422, extra


def test_draft_proposal_has_no_approval_or_status_fields() -> None:
    body = make_client(auth_mode="fixture").post(DRAFT_URL, json=DRAFT_BODY).json()
    assert not {"approved", "status", "state", "approval"} & set(body)


def test_capabilities_report_fixture_workspace_and_fake_model() -> None:
    caps = {
        c["feature"]: c
        for c in make_client(auth_mode="fixture").get("/api/capabilities").json()["capabilities"]
    }
    assert caps["applications"]["status"] == "fixture_only"
    assert caps["applications.model"]["status"] == "fixture_only"
    assert caps["review"]["status"] == "fixture_only"
    # C4-SKL-001: implemented, but this fixture app has no PostgreSQL store.
    assert caps["skills"]["status"] == "unavailable"
