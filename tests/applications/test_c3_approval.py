"""C3 approval engine, staleness and resolver (C3 spec s4, s8).

Rules: APP-04, APP-06, JOB-02, JOB-05, SEC-14 plus the resolver contract for Dev B.
"""

from __future__ import annotations

import threading
from typing import Any

import pytest
from fastapi.testclient import TestClient

from strongstart_api.features.applications.approval import Context
from strongstart_api.features.applications.resolver import StoreApprovedAnswerResolver
from strongstart_api.features.applications.router import get_policy, get_workspace_source
from strongstart_api.features.applications.rules.policy import fixture_policy
from strongstart_api.features.applications.store import InMemoryAnswerStore
from strongstart_api.features.applications.workspace import FixtureWorkspaceSource
from strongstart_api.identity import require_identity
from strongstart_contracts import SessionIdentity
from strongstart_contracts.answers import ApplicationWorkspace
from strongstart_contracts.fixture_adapters import ApprovalNotUsable
from strongstart_contracts.ports import ApprovedAnswerResolver

from .conftest import FACT, make_client

A = "/api/applications"
Q = "mission-q1"
BOUND = f"Demo Org supports early learning. Linked: {{{{fact:{FACT}}}}}."
PLAIN = "Demo Org supports early learning in its community."


def save(c: TestClient, text: str, expected: int | None = None, question: str = Q) -> Any:
    return c.post(
        f"{A}/answers/versions",
        json={
            "question_id": question,
            "question_version": 1,
            "evidence_bundle_id": "demo-evidence-a-v1",
            "text": text,
            "expected_answer_version": expected,
        },
    )


def approve(c: TestClient, v: dict[str, Any], ack: bool = True, decision: str = "approve") -> Any:
    return c.post(
        f"{A}/answers/decisions",
        json={
            "answer_version_id": v["answer_version_id"],
            "expected_content_sha256": v["content_sha256"],
            "expected_snapshot_sha256": v["snapshot_sha256"],
            "decision": decision,
            "acknowledge_review_items": ack,
        },
    )


def history(c: TestClient, question: str = Q) -> dict[str, Any]:
    body: dict[str, Any] = c.get(f"{A}/answers/{question}").json()
    return body


def fixture_client() -> TestClient:
    return make_client(auth_mode="fixture")


def approved_version(c: TestClient, text: str = BOUND) -> dict[str, Any]:
    v: dict[str, Any] = save(c, text).json()
    assert approve(c, v).status_code == 200
    return v


# --- saving / freezing -----------------------------------------------------------------


def test_saved_version_is_frozen_with_hashes_and_server_state() -> None:
    c = fixture_client()
    r = save(c, BOUND)
    assert r.status_code == 201
    v = r.json()
    assert v["answer_version"] == 1 and v["is_latest"] is True
    assert v["state"] == "ready_for_review"
    assert len(v["content_sha256"]) == 64 and len(v["snapshot_sha256"]) == 64
    assert v["rendered"]["bindings"][0]["fact_id"] == FACT
    assert {d["kind"] for d in v["dependencies"]} >= {
        "question",
        "pack",
        "fact",
        "policy",
        "rule_set",
    }


def test_failing_text_is_needs_attention() -> None:
    c = fixture_client()
    assert save(c, "We served 500 children.").json()["state"] == "needs_attention"


# --- APP-04 ------------------------------------------------------------------------------


def test_app04_one_character_edit_stales_approval_and_prevents_replay() -> None:
    c = fixture_client()
    v1 = approved_version(c)
    assert history(c)["prefill_ready"] is True
    v2 = save(c, BOUND + "!", expected=1).json()
    h = history(c)
    assert [x["state"] for x in h["versions"]] == ["stale", "ready_for_review"]
    assert (
        h["approvals"][0]["is_stale"] and h["approvals"][0]["stale_reason"] == "newer_version_saved"
    )
    assert h["prefill_ready"] is False
    replay = approve(c, v1)
    assert replay.status_code == 409  # old version cannot be approved again
    assert v2["content_sha256"] != v1["content_sha256"]


def test_app04_policy_version_change_stales_approval() -> None:
    c = fixture_client()
    approved_version(c, "The Demo Literacy Program (DLP) helps families.")
    policy = fixture_policy()
    assert policy is not None
    bumped = policy.model_copy(update={"policy_version": "2"})
    c.app.dependency_overrides[get_policy] = lambda: bumped  # type: ignore[attr-defined]
    h = history(c)
    assert h["versions"][-1]["state"] == "stale"
    assert h["approvals"][0]["stale_reason"] == "dependency_changed"


# --- JOB-05 / APP-06 -----------------------------------------------------------------------


def _with_fact_value(value: str) -> ApplicationWorkspace:
    real = FixtureWorkspaceSource().get("demo-org")
    bundle = real.evidence_bundle
    fact = bundle.facts[0].model_copy(update={"value": value})
    return real.model_copy(update={"evidence_bundle": bundle.model_copy(update={"facts": [fact]})})


def test_job05_fact_modification_stales_approval_and_blocks_resolve_and_export() -> None:
    c = fixture_client()
    v = approved_version(c)
    approval_id = history(c)["approvals"][0]["approval_id"]
    changed = _with_fact_value("121")

    class Source:
        is_fixture = True

        def get(self, organization_id: str) -> ApplicationWorkspace:
            return changed

    c.app.dependency_overrides[get_workspace_source] = lambda: Source()  # type: ignore[attr-defined]
    h = history(c)
    assert h["versions"][-1]["state"] == "stale"
    assert h["approvals"][0]["stale_reason"] == "dependency_changed"
    assert approve(c, v).status_code == 409  # old approval/snapshot cannot be reused
    export = c.post(f"{A}/exports", json={"mode": "reviewed", "question_ids": [Q]}).json()
    assert export["blocked"] and export["blocked_by"][0]["reason"] == "stale_approval"
    store = c.app.state.c3_answer_store  # type: ignore[attr-defined]
    resolver = StoreApprovedAnswerResolver(
        lambda org: Context(store, Source(), fixture_policy(), _settings(), org), True
    )
    with pytest.raises(ApprovalNotUsable, match="stale"):
        resolver.resolve("demo-org", approval_id)


def test_app06_change_set_stales_only_dependent_approvals() -> None:
    c = fixture_client()
    approved_version(c)  # binds demo-fact-children-served
    plain = save(c, PLAIN, question="services-q2").json()
    assert approve(c, plain).status_code == 200
    r = c.post(f"{A}/fixture/change-sets/demo-change-fact-v2/apply")
    assert r.status_code == 200 and r.json() == ["demo-change-fact-v2"]
    assert history(c)["versions"][-1]["state"] == "stale"
    assert history(c)["approvals"][0]["stale_reason"] == "change_set_applied:demo-change-fact-v2"
    assert history(c, "services-q2")["versions"][-1]["state"] == "approved"  # untouched
    actions = [e["action"] for e in c.get(f"{A}/audit-events").json()]
    assert actions.count("approval_staled") == 1


def test_change_set_route_is_fixture_only() -> None:
    c = make_client()
    c.app.dependency_overrides[require_identity] = lambda: SessionIdentity(  # type: ignore[attr-defined]
        actor_id="a", organization_id="demo-org", roles=[], is_fixture=False, label="t"
    )
    assert c.post(f"{A}/fixture/change-sets/demo-change-fact-v2/apply").status_code == 503


# --- JOB-02 ------------------------------------------------------------------------------


def test_job02_optimistic_versions_on_save() -> None:
    c = fixture_client()
    assert save(c, PLAIN).status_code == 201
    stale_first = save(c, PLAIN + " again")  # expected None but v1 exists
    assert stale_first.status_code == 409
    assert stale_first.json()["details"]["current_answer_version"] == 1
    assert save(c, PLAIN + " v2", expected=1).status_code == 201
    assert save(c, PLAIN + " v3", expected=1).status_code == 409  # concurrent editor lost


def test_job02_simultaneous_approvals_only_one_wins() -> None:
    c = fixture_client()
    v = save(c, BOUND).json()
    results: list[int] = []
    barrier = threading.Barrier(4)

    def go() -> None:
        barrier.wait()
        results.append(approve(c, v).status_code)

    threads = [threading.Thread(target=go) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == [200, 409, 409, 409]


def test_job02_expected_hash_mismatch_is_409() -> None:
    c = fixture_client()
    v = save(c, BOUND).json()
    wrong = {**v, "content_sha256": "0" * 64}
    assert approve(c, wrong).status_code == 409
    wrong = {**v, "snapshot_sha256": "1" * 64}
    assert approve(c, wrong).status_code == 409


# --- approval gate (s9.2) -----------------------------------------------------------------


def test_gate_requires_acknowledging_review_items() -> None:
    c = fixture_client()
    v = save(c, BOUND).json()  # unconfirmed counter + unverified fact -> needs_review items
    r = approve(c, v, ack=False)
    assert r.status_code == 422
    assert r.json()["details"]["reason"] == "review_items_not_acknowledged"
    assert approve(c, v, ack=True).status_code == 200


def test_gate_blocks_failing_findings_but_reject_is_allowed() -> None:
    c = fixture_client()
    v = save(c, "We served 500 children. XXX").json()
    r = approve(c, v)
    assert r.status_code == 422 and r.json()["details"]["reason"] == "blocking_findings"
    rules = {f["result"]["rule_id"] for f in r.json()["details"]["findings"]}
    assert {"APP-03", "POL-03"} <= rules
    assert approve(c, v, decision="reject").status_code == 200
    assert history(c)["versions"][-1]["state"] == "rejected"


def test_only_fixture_identity_in_fixture_mode_may_approve() -> None:
    c = fixture_client()
    v = save(c, BOUND).json()
    c.app.dependency_overrides[require_identity] = lambda: SessionIdentity(  # type: ignore[attr-defined]
        actor_id="secondary",
        organization_id="demo-org",
        roles=["staff"],
        is_fixture=False,
        label="t",
    )
    r = approve(c, v)
    assert r.status_code == 403 and r.json()["details"]["reason"] == "not_an_approver"
    # A secondary reviewer can still leave a note, which changes nothing.
    note = c.post(
        f"{A}/answers/notes",
        json={"answer_version_id": v["answer_version_id"], "text": "Check the period."},
    )
    assert note.status_code == 201
    assert history(c)["versions"][-1]["state"] == "ready_for_review"


# --- SEC-14 ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "extra"),
    [
        ("/answers/versions", {"state": "approved"}),
        ("/answers/versions", {"approved": True}),
        ("/answers/decisions", {"status": "approved"}),
        ("/answers/notes", {"decision": "approve"}),
    ],
)
def test_sec14_clients_cannot_send_state_or_approval(url: str, extra: dict[str, Any]) -> None:
    c = fixture_client()
    v = save(c, BOUND).json()
    base: dict[str, Any] = {
        "/answers/versions": {
            "question_id": Q,
            "question_version": 1,
            "evidence_bundle_id": "demo-evidence-a-v1",
            "text": "x",
            "expected_answer_version": 1,
        },
        "/answers/decisions": {
            "answer_version_id": v["answer_version_id"],
            "expected_content_sha256": v["content_sha256"],
            "expected_snapshot_sha256": v["snapshot_sha256"],
            "decision": "approve",
        },
        "/answers/notes": {"answer_version_id": v["answer_version_id"], "text": "n"},
    }[url]
    assert c.post(f"{A}{url}", json={**base, **extra}).status_code == 422
    assert history(c)["versions"][-1]["state"] == "ready_for_review"


def test_strict_typing_on_c3_requests() -> None:
    c = fixture_client()
    r = c.post(
        f"{A}/answers/versions",
        json={
            "question_id": Q,
            "question_version": "1",
            "evidence_bundle_id": "demo-evidence-a-v1",
            "text": "x",
        },
    )
    assert r.status_code == 422


# --- resolver (Dev B prefill contract) ------------------------------------------------------


def _settings() -> Any:
    from strongstart_api.config import Settings

    return Settings(_env_file=None, auth_mode="fixture")


def _resolver(store: InMemoryAnswerStore) -> StoreApprovedAnswerResolver:
    return StoreApprovedAnswerResolver(
        lambda org: Context(store, FixtureWorkspaceSource(), fixture_policy(), _settings(), org),
        store.is_fixture,
    )


def test_resolver_satisfies_port_and_resolves_current_approval() -> None:
    c = fixture_client()
    v = approved_version(c)
    approval_id = history(c)["approvals"][0]["approval_id"]
    resolver = _resolver(c.app.state.c3_answer_store)  # type: ignore[attr-defined]
    assert isinstance(resolver, ApprovedAnswerResolver)
    snap = resolver.resolve("demo-org", approval_id)
    assert snap.content_sha256 == v["content_sha256"]
    assert snap.answer_snapshot_id == v["answer_version_id"]
    assert snap.provenance.is_simulated is True


def test_resolver_refuses_other_org_unknown_rejected_and_stale() -> None:
    c = fixture_client()
    approved_version(c)
    approval_id = history(c)["approvals"][0]["approval_id"]
    resolver = _resolver(c.app.state.c3_answer_store)  # type: ignore[attr-defined]
    with pytest.raises(ApprovalNotUsable, match="no such approval") as other:
        resolver.resolve("other-org", approval_id)
    with pytest.raises(ApprovalNotUsable, match="no such approval") as unknown:
        resolver.resolve("demo-org", "apr-unknown")
    assert other.value.reason == unknown.value.reason  # indistinguishable
    save(c, BOUND + " edit", expected=1)
    with pytest.raises(ApprovalNotUsable, match="stale"):
        resolver.resolve("demo-org", approval_id)
    c2 = fixture_client()
    v = save(c2, BOUND).json()
    approve(c2, v, decision="reject")
    rejected_id = history(c2)["approvals"][0]["approval_id"]
    with pytest.raises(ApprovalNotUsable, match="rejected"):
        _resolver(c2.app.state.c3_answer_store).resolve("demo-org", rejected_id)  # type: ignore[attr-defined]


def test_store_unavailable_outside_fixture_mode() -> None:
    c = make_client()
    c.app.dependency_overrides[require_identity] = lambda: SessionIdentity(  # type: ignore[attr-defined]
        actor_id="a", organization_id="demo-org", roles=[], is_fixture=False, label="t"
    )
    assert c.get(f"{A}/answers/{Q}").status_code == 503
