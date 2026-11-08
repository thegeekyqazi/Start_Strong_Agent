"""C2b: C's whole path reads Dev B's saved question sets (C2 spec rev 1.3 s13).

Producer: Dev B's public ``ApplicationDefinitionReader`` (handoff
``docs/handoffs/dev-b/bundle-002-question-reader-r1.md``). Definitions are saved through
B's real public API into a temporary store, then consumed through C's real routes. A
labelled double built from B's committed sample covers the fixture-adapter side (s20.3:
consumer tests against both the fixture and the real producer).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.automation.public import get_application_definition_reader
from strongstart_contracts.application_publication import (
    ApplicationDefinitionIntegrityError,
    ApplicationDefinitionNotFound,
    PublishedApplicationVersion,
)

A = "/api/applications"
FIXTURE_SRC = {"mode": "fixture", "fixture_id": "rep-portal-definition-v1"}
BUNDLE = "demo-evidence-a-v1"
SAMPLE = (
    Path(__file__).resolve().parents[1] / "fixtures/automation/published-definition-v1.sample.json"
)
UNKNOWN_QS = "qs-def-" + "0" * 26 + "-v1"


def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        auth_mode="fixture",
        funding_capture_store_dir=tmp_path / "captures",
        dev_b_store_dir=tmp_path / "dev-b",
    )


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(settings(tmp_path)))


def save_definition(
    c: TestClient, key: str, definition_id: str | None = None, expected: int | None = None
) -> dict[str, Any]:
    """Save through Dev B's public API exactly as staff would (preview hash required)."""
    sha = c.post("/api/automation/intake", json={"source": FIXTURE_SRC}).json()["input"]["sha256"]
    body: dict[str, Any] = {
        "source": FIXTURE_SRC,
        "expected_input_sha256": sha,
        "idempotency_key": key,
    }
    if definition_id is not None:
        body |= {"definition_id": definition_id, "expected_version": expected}
    r = c.post("/api/automation/definitions", json=body)
    assert r.status_code in (200, 201), r.text
    publication: dict[str, Any] = r.json()["publication"]
    return publication


def qid(pub: dict[str, Any], original: str) -> str:
    published: str = next(
        m["published_question_id"]
        for m in pub["id_mapping"]
        if m["original_question_id"] == original
    )
    return published


# --- workspace -----------------------------------------------------------------------------


def test_workspace_reads_the_exact_saved_question_set(client: TestClient) -> None:
    pub = save_definition(client, "c2b-ws-01")
    r = client.get(f"{A}/workspace", params={"question_set_id": pub["question_set_id"]})
    assert r.status_code == 200, r.text
    ws = r.json()
    assert ws["question_source"] == "dev_b_saved_definition"
    ref = ws["question_set_ref"]
    assert ref["question_set_id"] == pub["question_set_id"]
    assert ref["definition_id"] == pub["definition_id"] and ref["definition_version"] == 1
    assert ref["review_status"] == "saved_not_reviewed" and ref["is_fixture"] is True
    assert len(ws["question_set"]["questions"]) == 9
    assert all(
        q["question_id"].startswith(pub["definition_id"] + ":")
        for q in ws["question_set"]["questions"]
    )
    assert "Dev B saved definition" in ws["data_label"] and "FIXTURE" in ws["data_label"]
    assert ws["evidence_bundle"]["bundle_id"] == BUNDLE  # evidence unchanged (fixture)


def test_conflicts_unknowns_and_unresolved_are_kept_not_resolved(client: TestClient) -> None:
    pub = save_definition(client, "c2b-ws-02")
    ws = client.get(f"{A}/workspace", params={"question_set_id": pub["question_set_id"]}).json()
    by_id = {q["question_id"]: q for q in ws["question_set"]["questions"]}
    partnership = by_id[qid(pub, "rp-partnership")]
    assert partnership["limit"] is None
    assert [(c["maximum"], c["unit"]) for c in partnership["conflicts"][0]["candidate_limits"]] == [
        (350, "words"),
        (500, "words"),
    ]
    assert by_id[qid(pub, "rp-other-funding")]["limit"]["unit"] == "unknown"
    assert by_id[qid(pub, "rp-pending-applications")]["required"] is None
    kinds = {(u["question_id"], u["kind"]) for u in ws["unresolved"]}
    assert (qid(pub, "rp-partnership"), "limit_conflict") in kinds
    assert (qid(pub, "rp-other-funding"), "unknown_limit_unit") in kinds


def test_default_is_still_the_demo_fixture(client: TestClient) -> None:
    ws = client.get(f"{A}/workspace").json()
    assert ws["question_source"] == "fixture_bundle" and ws["question_set_ref"] is None
    assert ws["question_set"]["question_set_id"] == "demo-gos-questions-v1"


# --- no silent fallback ----------------------------------------------------------------------


def test_unknown_question_set_is_404_never_the_demo_fixture(client: TestClient) -> None:
    r = client.get(f"{A}/workspace", params={"question_set_id": UNKNOWN_QS})
    assert r.status_code == 404 and r.json()["details"]["reason"] == "unknown_question_set"
    body = {"question_version": 1, "evidence_bundle_id": BUNDLE, "question_set_id": UNKNOWN_QS}
    assert client.post(f"{A}/questions/mission-q1/draft", json=body).status_code == 404
    assert (
        client.post(f"{A}/questions/mission-q1/check", json={**body, "text": "x"}).status_code
        == 404
    )
    plan = {"evidence_bundle_id": BUNDLE, "question_set_id": UNKNOWN_QS}
    assert client.post(f"{A}/plan", json=plan).status_code == 404


class _Reader:
    """Labelled fixture double from B's committed sample (s20.3 fixture side)."""

    is_fixture = True

    def __init__(self, fail: Exception | None = None) -> None:
        self.sample = PublishedApplicationVersion.model_validate(
            json.loads(SAMPLE.read_text("utf-8"))
        )
        self.fail = fail

    def get_version(
        self, organization_id: str, question_set_id: str
    ) -> PublishedApplicationVersion:
        if self.fail is not None:
            raise self.fail
        if (organization_id, question_set_id) != (
            self.sample.organization_id,
            self.sample.question_set_id,
        ):
            raise ApplicationDefinitionNotFound(question_set_id)
        return self.sample

    def get_current(self, organization_id: str, definition_id: str) -> PublishedApplicationVersion:
        return self.get_version(organization_id, self.sample.question_set_id)


def with_reader(reader: object) -> TestClient:
    app = create_app(Settings(_env_file=None, auth_mode="fixture"))
    app.dependency_overrides[get_application_definition_reader] = lambda: reader
    return TestClient(app)


def test_fixture_double_from_b_sample_behaves_like_the_real_producer() -> None:
    reader = _Reader()
    c = with_reader(reader)
    ws = c.get(f"{A}/workspace", params={"question_set_id": reader.sample.question_set_id}).json()
    assert ws["question_set_ref"]["definition_id"] == reader.sample.definition_id
    assert len(ws["question_set"]["questions"]) == 9


def test_integrity_failure_is_surfaced_not_replaced() -> None:
    c = with_reader(_Reader(fail=ApplicationDefinitionIntegrityError("tampered")))
    r = c.get(f"{A}/workspace", params={"question_set_id": UNKNOWN_QS})
    assert r.status_code == 502
    assert r.json()["details"]["reason"] == "question_set_integrity_failure"


def test_reader_unavailable_is_503_not_fallback(tmp_path: Path) -> None:
    from strongstart_contracts.application_publication import (
        UnconfiguredApplicationDefinitionReader,
    )

    c = with_reader(UnconfiguredApplicationDefinitionReader())
    r = c.get(f"{A}/workspace", params={"question_set_id": UNKNOWN_QS})
    assert r.status_code == 503 and r.json()["code"] == "capability_unavailable"


def test_other_organization_question_set_is_indistinguishable_from_unknown() -> None:
    reader = _Reader()
    sample = reader.sample.model_copy(update={"organization_id": "other-org"})
    reader.sample = sample
    c = with_reader(reader)
    r = c.get(f"{A}/workspace", params={"question_set_id": sample.question_set_id})
    assert r.status_code == 404 and r.json()["details"]["reason"] == "unknown_question_set"


@pytest.mark.parametrize("bad", [123, "", "Bad ID!", "x" * 200])
def test_question_set_id_is_strictly_typed(client: TestClient, bad: object) -> None:
    body = {"question_version": 1, "evidence_bundle_id": BUNDLE, "question_set_id": bad}
    assert client.post(f"{A}/questions/mission-q1/draft", json=body).status_code == 422


# --- the whole C path reads the producer -------------------------------------------------------


def test_plan_draft_and_check_use_the_saved_questions(client: TestClient) -> None:
    pub = save_definition(client, "c2b-path-01")
    qs = pub["question_set_id"]
    mission = qid(pub, "rp-mission")
    plan = client.post(f"{A}/plan", json={"evidence_bundle_id": BUNDLE, "question_set_id": qs})
    assert plan.status_code == 200, plan.text
    assert all(
        i["question_id"].startswith(pub["definition_id"] + ":") for i in plan.json()["items"]
    )
    body = {"question_version": 1, "evidence_bundle_id": BUNDLE, "question_set_id": qs}
    draft = client.post(f"{A}/questions/{mission}/draft", json=body)
    assert draft.status_code == 200, draft.text
    assert draft.json()["question_id"] == mission
    check = client.post(
        f"{A}/questions/{mission}/check", json={**body, "text": "We served 500 children."}
    ).json()
    app01 = next(f for f in check["findings"] if f["result"]["rule_id"] == "APP-01")
    assert "of 50 words" in app01["message"]  # B's 50-word limit, convention unconfirmed
    assert any(f["affected_text"] == "500" for f in check["findings"])  # APP-03 still applies
    partnership = qid(pub, "rp-partnership")
    conflict = client.post(f"{A}/questions/{partnership}/check", json={**body, "text": "w " * 400})
    assert (
        next(f for f in conflict.json()["findings"] if f["result"]["rule_id"] == "APP-01")[
            "result"
        ]["outcome"]
        == "needs_review"
    )


def test_question_version_mismatch_is_409(client: TestClient) -> None:
    pub = save_definition(client, "c2b-ver-01")
    body = {
        "question_version": 2,
        "evidence_bundle_id": BUNDLE,
        "question_set_id": pub["question_set_id"],
    }
    r = client.post(f"{A}/questions/{qid(pub, 'rp-mission')}/draft", json=body)
    assert r.status_code == 409


def test_save_approve_and_resolve_on_a_saved_question_set(client: TestClient) -> None:
    pub = save_definition(client, "c2b-c3-01")
    qs, mission = pub["question_set_id"], qid(pub, "rp-mission")
    v = client.post(
        f"{A}/answers/versions",
        json={"question_id": mission, "question_version": 1, "evidence_bundle_id": BUNDLE,
              "text": "Our mission is early learning.", "question_set_id": qs},
    )  # fmt: skip
    assert v.status_code == 201, v.text
    version = v.json()
    assert version["question_set_id"] == qs
    decided = client.post(
        f"{A}/answers/decisions",
        json={"answer_version_id": version["answer_version_id"],
              "expected_content_sha256": version["content_sha256"],
              "expected_snapshot_sha256": version["snapshot_sha256"],
              "decision": "approve", "acknowledge_review_items": True},
    )  # fmt: skip
    assert decided.status_code == 200, decided.text
    h = client.get(f"{A}/answers/{mission}", params={"question_set_id": qs}).json()
    assert h["versions"][-1]["state"] == "approved" and h["prefill_ready"] is True
    export = client.post(
        f"{A}/exports", json={"mode": "working", "question_ids": [mission], "question_set_id": qs}
    ).json()
    assert export["blocked"] is False


def test_definition_revision_stales_approvals_on_the_old_version(client: TestClient) -> None:
    v1 = save_definition(client, "c2b-rev-01")
    mission = qid(v1, "rp-mission")
    saved = client.post(
        f"{A}/answers/versions",
        json={"question_id": mission, "question_version": 1, "evidence_bundle_id": BUNDLE,
              "text": "Our mission is early learning.", "question_set_id": v1["question_set_id"]},
    ).json()  # fmt: skip
    client.post(
        f"{A}/answers/decisions",
        json={"answer_version_id": saved["answer_version_id"],
              "expected_content_sha256": saved["content_sha256"],
              "expected_snapshot_sha256": saved["snapshot_sha256"],
              "decision": "approve", "acknowledge_review_items": True},
    )  # fmt: skip
    v2 = save_definition(client, "c2b-rev-02", definition_id=v1["definition_id"], expected=1)
    assert v2["version"] == 2 and v2["question_set_id"] != v1["question_set_id"]
    h = client.get(
        f"{A}/answers/{mission}", params={"question_set_id": v1["question_set_id"]}
    ).json()
    assert h["versions"][-1]["state"] == "stale"
    assert h["approvals"][0]["stale_reason"] == "question_definition_revised"
    assert h["prefill_ready"] is False
