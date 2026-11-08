"""DEV-B-BUNDLE-002 M3: funding cases, evidence anchors, review and context binding.

Acceptance cases BND-22..BND-27 plus the case parts of BND-01..05 and BND-39/40.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from strongstart_api.config import Settings
from strongstart_api.features.funding.public import (
    build_funding_case_reader,
    get_funding_case_reader,
)
from strongstart_contracts.funding_review import (
    FundingCaseNotFound,
    FundingCaseReader,
    UnconfiguredFundingCaseReader,
)
from strongstart_contracts.ports import CapabilityUnavailable

from .case_helpers import (
    AMOUNT_QUOTE,
    FORM_PAGE,
    FULL_CONTEXT,
    OTHER,
    anchor,
    capture,
    client_for,
    create_case,
    evaluate,
    key,
    make_settings,
    outcomes,
    review,
    standard_case_body,
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def c(settings: Settings) -> TestClient:
    return client_for(settings)


# ------------------------------------------------------------------- boundaries


def test_bnd01_case_routes_require_identity_before_store_or_body(settings: Settings) -> None:
    anon = client_for(settings.model_copy(update={"auth_mode": "none"}))
    cid = "case-" + "0" * 26
    responses = [
        anon.post("/api/funding/cases", content=b"{broken"),
        anon.post(f"/api/funding/cases/{cid}/revisions", json={}),
        anon.get("/api/funding/cases"),
        anon.get(f"/api/funding/cases/{cid}"),
        anon.get(f"/api/funding/cases/{cid}/versions/1"),
        anon.post(f"/api/funding/cases/{cid}/versions/1/review", json={}),
        anon.post(f"/api/funding/cases/{cid}/evaluations", json={}),
        anon.get(f"/api/funding/cases/{cid}/evaluations"),
        anon.get("/api/funding/captures"),
    ]
    assert {r.status_code for r in responses} == {401}


def test_bnd02_other_org_case_is_indistinguishable_from_unknown(
    settings: Settings, c: TestClient
) -> None:
    env = create_case(c, standard_case_body(c, capture(c)))
    cid = env["version"]["case_id"]
    other = client_for(settings, OTHER)
    unknown = "case-" + "f" * 26
    a, b = other.get(f"/api/funding/cases/{cid}"), other.get(f"/api/funding/cases/{unknown}")
    assert a.status_code == b.status_code == 404
    assert a.json()["details"] == b.json()["details"] == {"reason": "case_not_found"}
    assert other.get("/api/funding/cases").json()["items"] == []
    ev = other.post(
        f"/api/funding/cases/{cid}/evaluations", json={"idempotency_key": key(), "case_version": 1}
    )
    assert ev.status_code == 404


@pytest.mark.parametrize(
    "patch",
    [
        {"expected_version": "1"},
        {"reviewed": True},
        {"organization_id": "demo-org"},
        {"context": {**FULL_CONTEXT, "stage": "current_round"}},
        {"context": {**FULL_CONTEXT, "verified": True}},
    ],
)
def test_bnd03_strict_case_command(c: TestClient, patch: dict[str, Any]) -> None:
    body = {"idempotency_key": key(), "context": FULL_CONTEXT, **patch}
    r = c.post("/api/funding/cases", json=body)
    assert r.status_code == 422
    assert r.json()["details"]["reason"] == "invalid_input"


def test_bnd03_strict_evaluate_and_review_commands(c: TestClient) -> None:
    env = create_case(c, standard_case_body(c, capture(c)))
    cid = env["version"]["case_id"]
    for bad in (
        {"case_version": True},
        {"case_version": 1.0},
        {"case_version": 1, "approved": 1},
        {"case_version": 1, "clock": "2026-03-31T17:00:00"},
    ):
        r = c.post(f"/api/funding/cases/{cid}/evaluations", json={"idempotency_key": key(), **bad})
        assert r.status_code == 422, bad
    r = c.post(
        f"/api/funding/cases/{cid}/versions/1/review",
        json={
            "idempotency_key": key(),
            "version_digest": env["version_digest"],
            "requirement_keys": ["standard-amount"],
            "reviewed": True,
        },
    )
    assert r.status_code == 422


@pytest.mark.parametrize(
    "path",
    [
        "/api/funding/cases/..%2F..%2Fetc",
        "/api/funding/cases/case-..%2F" + "0" * 22,
        "/api/funding/cases/CASE-" + "0" * 26,
        "/api/funding/cases/case-" + "0" * 26 + "/versions/99",
        "/api/funding/cases/case-" + "0" * 26 + "/versions/0",
    ],
)
def test_bnd04_malicious_case_paths(c: TestClient, path: str) -> None:
    assert c.get(path).status_code in (404, 422)


def test_bnd05_rule_and_anchor_budgets_at_n_plus_one(c: TestClient) -> None:
    doc = capture(c)
    one = anchor(c, doc, AMOUNT_QUOTE, "a0")
    anchors = [{**one, "anchor_key": f"a{i}"} for i in range(41)]
    r = c.post(
        "/api/funding/cases",
        json={"idempotency_key": key(), "context": FULL_CONTEXT, "anchors": anchors},
    )
    assert r.status_code == 413 and r.json()["details"]["reason"] == "too_large"
    ok = c.post(
        "/api/funding/cases",
        json={"idempotency_key": key(), "context": FULL_CONTEXT, "anchors": anchors[:40]},
    )
    assert ok.status_code == 201
    req = {
        "requirement_key": "r",
        "spec": {"kind": "geography", "allowed": ["x"]},
        "anchor_keys": ["a0"],
        "interpretation": "x",
    }
    reqs = [{**req, "requirement_key": f"r{i}"} for i in range(21)]
    r = c.post(
        "/api/funding/cases",
        json={
            "idempotency_key": key(),
            "context": FULL_CONTEXT,
            "anchors": [one],
            "requirements": reqs,
        },
    )
    assert r.status_code == 413
    dup = c.post(
        "/api/funding/cases", content=b'{"idempotency_key":"k-12345678","idempotency_key":"x"}'
    )
    assert dup.status_code == 422


# ------------------------------------------------------------------- BND-22


def test_bnd22_draft_case_keeps_unknowns_and_emits_no_opportunity(c: TestClient) -> None:
    r = c.post(
        "/api/funding/cases",
        json={"idempotency_key": key(), "context": {"funder_label": "FIXTURE Demo Funder"}},
    )
    assert r.status_code == 201
    env = r.json()
    assert env["opportunity"] is None and env["requirement_set"] is None
    assert set(env["opportunity_missing"]) == {"stream", "cycle", "source link"}
    assert set(env["version"]["context"]["unknown_fields"]) == {"stream", "cycle", "stage"}
    assert env["version"]["context"]["stream_id"] is None
    assert env["readiness"] == "no_rules" and env["review_status"] == "unreviewed"
    assert env["version"]["case_kind_label"] == "staff_selected_context_not_certified"


def test_bnd22_ids_are_server_derived_not_titles(c: TestClient) -> None:
    env = create_case(c, standard_case_body(c, capture(c)))
    ctx, opp = env["version"]["context"], env["opportunity"]
    assert ctx["cycle_id"].startswith("cyc-") and "2026" not in ctx["cycle_id"]
    assert opp["funder_id"] == ctx["funder_id"] and opp["stream_id"] == ctx["stream_id"]
    assert opp["deadline"]["status"] == "unknown"  # unreviewed: no deadline promoted


# ------------------------------------------------------------------- BND-23


def test_bnd23_valid_anchor_resolves_against_verified_bytes(c: TestClient) -> None:
    doc = capture(c)
    env = create_case(c, standard_case_body(c, doc))
    a = next(x for x in env["version"]["anchors"] if x["anchor_key"] == "amount")
    assert a["quote"] == AMOUNT_QUOTE and a["verification"] == "quote_matched_hash_verified_bytes"
    assert a["source_version_id"] == doc["source_reference"]["source_version_id"]
    assert a["is_simulated"] is True and a["coverage"] == "complete"


@pytest.mark.parametrize(
    ("mutate", "status", "reason"),
    [
        (
            lambda a: {**a, "quote": a["quote"].replace("100,000", "100,001")},
            422,
            "anchor_mismatch",
        ),
        (lambda a: {**a, "quote": a["quote"][:-1] + "!"}, 422, "anchor_mismatch"),
        (lambda a: {**a, "start": a["start"] + 1, "end": a["end"] + 1}, 422, "anchor_mismatch"),
        (lambda a: {**a, "end": a["start"] + 10**6}, 422, "anchor_mismatch"),
        (lambda a: {**a, "expected_artifact_sha256": "0" * 64}, 409, "anchor_source_changed"),
        (lambda a: {**a, "capture_id": "cap-" + "0" * 32}, 404, "capture_not_found"),
        (lambda a: {**a, "artifact_id": "cap-x-html"}, 404, "capture_not_found"),
    ],
)
def test_bnd23_wrong_quote_digit_range_hash_or_source_fails(
    c: TestClient, mutate: Any, status: int, reason: str
) -> None:
    doc = capture(c)
    bad = mutate(anchor(c, doc, AMOUNT_QUOTE, "amount"))
    r = c.post(
        "/api/funding/cases",
        json={"idempotency_key": key(), "context": FULL_CONTEXT, "anchors": [bad]},
    )
    assert r.status_code == status, r.text
    assert r.json()["details"]["reason"] == reason
    assert "100,000" not in r.text  # no source text echoed in errors


def test_bnd23_cross_org_capture_anchor_looks_unknown(settings: Settings, c: TestClient) -> None:
    doc = capture(c)
    other = client_for(settings, OTHER)
    a = anchor(c, doc, AMOUNT_QUOTE, "amount")
    r = other.post(
        "/api/funding/cases",
        json={"idempotency_key": key(), "context": FULL_CONTEXT, "anchors": [a]},
    )
    assert r.status_code == 404 and r.json()["details"]["reason"] == "capture_not_found"


def test_bnd23_requirement_without_verified_anchor_is_rejected(c: TestClient) -> None:
    body = {
        "idempotency_key": key(),
        "context": FULL_CONTEXT,
        "requirements": [
            {
                "requirement_key": "r",
                "spec": {"kind": "geography", "allowed": ["x"]},
                "anchor_keys": ["missing"],
                "interpretation": "x",
            }
        ],
    }
    r = c.post("/api/funding/cases", json=body)
    assert r.status_code == 422 and r.json()["details"]["missing_anchor_keys"] == ["missing"]
    code = {
        "idempotency_key": key(),
        "context": FULL_CONTEXT,
        "requirements": [
            {
                "requirement_key": "r",
                "spec": {"kind": "expression", "code": "eligible = True"},
                "anchor_keys": ["a"],
                "interpretation": "x",
            }
        ],
    }
    assert c.post("/api/funding/cases", json=code).status_code == 422


# ------------------------------------------------------------------- BND-24/25


def test_bnd24_requirements_inactive_until_exact_review(c: TestClient) -> None:
    env = create_case(c, standard_case_body(c, capture(c)))
    before = evaluate(
        c,
        env,
        inputs={
            "request_amount": {"amount": "50000", "currency": "CAD", "provenance": "staff_asserted"}
        },
    )
    assert set(outcomes(before).values()) == {"unknown"}
    assert "Not reviewed" in before["results"][0]["found"]
    cid, v = env["version"]["case_id"], env["version"]["version"]
    wrong_digest = c.post(
        f"/api/funding/cases/{cid}/versions/{v}/review",
        json={
            "idempotency_key": key(),
            "version_digest": "0" * 64,
            "requirement_keys": [r["requirement_key"] for r in env["version"]["requirements"]],
        },
    )
    assert (
        wrong_digest.status_code == 409
        and wrong_digest.json()["details"]["reason"] == "stale_snapshot"
    )
    subset = c.post(
        f"/api/funding/cases/{cid}/versions/{v}/review",
        json={
            "idempotency_key": key(),
            "version_digest": env["version_digest"],
            "requirement_keys": ["standard-amount"],
        },
    )
    assert (
        subset.status_code == 409 and subset.json()["details"]["reason"] == "review_scope_mismatch"
    )
    reviewed = review(c, env)
    assert reviewed["review_status"] == "reviewed"
    assert reviewed["readiness"] == "ready_for_evaluation"
    assert reviewed["review"]["reviewer"] == "demo-staff"
    assert reviewed["requirement_set"]["conditions"]
    assert {x["evaluation"] for x in reviewed["requirement_set"]["conditions"]} == {"unknown"}
    assert reviewed["opportunity"]["deadline"] == {"status": "known", "value": "2026-03-31"}


def test_bnd25_edit_or_relink_stales_review_and_keeps_history(c: TestClient) -> None:
    doc = capture(c)
    env = review(c, create_case(c, standard_case_body(c, doc)))
    cid = env["version"]["case_id"]
    body = standard_case_body(c, doc, expected_version=1)
    body["requirements"][0]["spec"]["maximum"] = "90000"
    r = c.post(f"/api/funding/cases/{cid}/revisions", json=body)
    assert r.status_code == 201, r.text
    v2 = r.json()
    assert v2["version"]["version"] == 2 and v2["review_status"] == "unreviewed"
    assert v2["readiness"] == "not_reviewed" and v2["requirement_set"] is None
    old = c.get(f"/api/funding/cases/{cid}/versions/1").json()
    assert old["review_status"] == "reviewed" and old["is_current"] is False
    assert (
        c.post(
            f"/api/funding/cases/{cid}/versions/1/review",
            json={
                "idempotency_key": key(),
                "version_digest": old["version_digest"],
                "requirement_keys": [x["requirement_key"] for x in old["version"]["requirements"]],
            },
        ).json()["details"]["reason"]
        == "not_current_version"
    )
    # Relinking anchors to a different capture is also a new, unreviewed version.
    doc2 = capture(c)
    relinked = standard_case_body(c, doc2, expected_version=2)
    r3 = c.post(f"/api/funding/cases/{cid}/revisions", json=relinked)
    assert r3.status_code == 201 and r3.json()["review_status"] == "unreviewed"
    stale = c.post(
        f"/api/funding/cases/{cid}/revisions", json=standard_case_body(c, doc2, expected_version=2)
    )
    assert stale.status_code == 409 and stale.json()["details"]["current_version"] == 3


# ------------------------------------------------------------------- BND-26/27


def _save(c: TestClient, source: dict[str, Any], **extra: Any) -> Any:
    sha = c.post("/api/automation/intake", json={"source": source}).json()["input"]["sha256"]
    return c.post(
        "/api/automation/definitions",
        json={
            "source": source,
            "expected_input_sha256": sha,
            "idempotency_key": key("save"),
            **extra,
        },
    )


def _html_source(doc: dict[str, Any]) -> dict[str, Any]:
    art = next(a for a in doc["artifacts"] if a["representation"] == "provider_html")
    return {"mode": "capture", "capture_id": doc["capture_id"], "artifact_id": art["artifact_id"]}


def _form_case(c: TestClient, doc: dict[str, Any], **ctx: Any) -> dict[str, Any]:
    return create_case(
        c,
        {
            "idempotency_key": key(),
            "context": {**FULL_CONTEXT, **ctx},
            "capture_links": [{"capture_id": doc["capture_id"]}],
        },
    )


def test_bnd26_reviewed_context_enables_captured_html_question_set(c: TestClient) -> None:
    form = capture(c, FORM_PAGE)
    src = _html_source(form)
    blocked = _save(c, src)
    assert (
        blocked.status_code == 422 and blocked.json()["details"]["reason"] == "publication_blocked"
    )
    case = _form_case(c, form)
    v = case["version"]
    r = _save(c, src, funding_case_id=v["case_id"], funding_case_version=1)
    assert r.status_code == 201, r.text
    pub = r.json()["publication"]
    ctx = pub["context"]
    assert ctx["opportunity_basis"] == "funding_case"
    assert ctx["opportunity_id"] == case["opportunity"]["opportunity_id"]
    assert ctx["binding"]["funding_case_version"] == 1
    assert ctx["binding"]["funding_case_digest"] == case["version_digest"]
    assert pub["question_set"]["opportunity_id"] == ctx["opportunity_id"]
    assert len(pub["question_set"]["questions"]) == 2
    assert pub["intake"]["input"]["capture"]["capture_id"] == form["capture_id"]  # lineage kept
    # The capture record itself is unchanged (no mutation, no reviewed relabel).
    assert c.get(f"/api/funding/captures/{form['capture_id']}").json() == form


def test_bnd26_mismatched_unlinked_stale_or_incomplete_context_is_held(c: TestClient) -> None:
    form = capture(c, FORM_PAGE)
    src = _html_source(form)
    other_doc = capture(c)
    unlinked = _form_case(c, other_doc)
    r = _save(c, src, funding_case_id=unlinked["version"]["case_id"], funding_case_version=1)
    assert r.status_code == 409 and r.json()["details"]["reason"] == "context_conflict"
    declared = capture(c, FORM_PAGE, opportunity_id="opp-somewhere-else")
    mism = _form_case(c, declared)
    r = _save(
        c,
        _html_source(declared),
        funding_case_id=mism["version"]["case_id"],
        funding_case_version=1,
    )
    assert r.status_code == 409
    assert any("opp-somewhere-else" in x for x in r.json()["details"]["conflicts"])
    case = _form_case(c, form)
    cid = case["version"]["case_id"]
    rev = {
        "idempotency_key": key(),
        "expected_version": 1,
        "context": FULL_CONTEXT,
        "capture_links": [{"capture_id": form["capture_id"]}],
    }
    assert c.post(f"/api/funding/cases/{cid}/revisions", json=rev).status_code == 201
    r = _save(c, src, funding_case_id=cid, funding_case_version=1)
    assert r.status_code == 409 and r.json()["details"]["reason"] == "context_changed"
    draft = create_case(
        c,
        {
            "idempotency_key": key(),
            "context": {"funder_label": "F"},
            "capture_links": [{"capture_id": form["capture_id"]}],
        },
    )
    r = _save(c, src, funding_case_id=draft["version"]["case_id"], funding_case_version=1)
    assert r.status_code == 422 and r.json()["details"]["reason"] == "context_incomplete"
    assert set(r.json()["details"]["missing"]) == {"stream", "cycle"}


def test_bnd27_saved_publication_survives_removal_of_producer_blob(
    settings: Settings, c: TestClient
) -> None:
    form = capture(c, FORM_PAGE)
    case = _form_case(c, form)
    pub = _save(
        c, _html_source(form), funding_case_id=case["version"]["case_id"], funding_case_version=1
    ).json()["publication"]
    shutil.rmtree(next(settings.funding_capture_store_dir.glob("org-*")) / "blobs")
    r = c.get(f"/api/automation/question-sets/{pub['question_set_id']}")
    assert r.status_code == 200
    again = r.json()
    assert again["integrity"]["raw_input_sha256"] == pub["integrity"]["raw_input_sha256"]
    assert again["intake"]["input"]["capture"]["capture_id"] == form["capture_id"]
    # A new import of the same capture now fails closed (the producer bytes are gone).
    assert c.post("/api/automation/intake", json={"source": _html_source(form)}).status_code == 409


# ------------------------------------------------------------------- BND-39/40


def test_bnd39_scenario_pass_never_confirms_eligibility(c: TestClient, settings: Settings) -> None:
    env = review(c, create_case(c, standard_case_body(c, capture(c))))
    report = evaluate(
        c,
        env,
        clock="2026-02-01T12:00:00-05:00",
        inputs={
            "request_amount": {
                "amount": "50000",
                "currency": "CAD",
                "provenance": "staff_asserted",
            },
            "region": {"value": "demo-region-north", "provenance": "staff_asserted"},
            "invitation": {
                "status": "invited",
                "provenance": "simulated",
                "evidence_note": "FIXTURE invitation letter",
            },
        },
    )
    assert report["eligibility_group_outcome"] == "met"
    assert report["scenario_summary"].startswith(
        "These encoded rules are met using these inputs; funder eligibility is not confirmed."
    )
    assert report["reliance_status"] == "not_confirmed"
    assert "staff_asserted" in report["reliance_explanation"]
    after = c.get(f"/api/funding/cases/{env['version']['case_id']}").json()
    assert {x["evaluation"] for x in after["requirement_set"]["conditions"]} == {"unknown"}
    assert not list(settings.knowledge_artifact_store_dir.glob("**/*"))  # nothing written to A


def test_bnd40_reports_reproduce_from_exact_versions_clock_and_inputs(c: TestClient) -> None:
    env = review(c, create_case(c, standard_case_body(c, capture(c))))
    body = {
        "clock": "2026-03-01T09:00:00-05:00",
        "inputs": {
            "request_amount": {
                "amount": "120000",
                "currency": "CAD",
                "provenance": "staff_asserted",
            }
        },
    }
    a, b = evaluate(c, env, **body), evaluate(c, env, **body)
    assert a["evaluation_id"] != b["evaluation_id"]
    assert a["inputs_digest"] == b["inputs_digest"] and a["results"] == b["results"]
    assert a["case_digest"] == env["version_digest"] and a["clock_source"] == "request"
    amount = next(r for r in a["results"] if r["requirement_key"] == "standard-amount")
    assert amount["outcome"] == "not_met"
    assert "120,000 exceeds the maximum 100,000 by 20,000" in amount["found"]
    assert amount["support"][0]["quote"] == AMOUNT_QUOTE
    assert "staff scenario" in amount["uncertainty"]
    assert amount["inputs_used"] == ["request_amount=120000 CAD units (staff_asserted)"]
    assert amount["validation"]["rule_id"] == "ELG-03"
    assert amount["validation"]["outcome"] == "fail"
    history = c.get(f"/api/funding/cases/{env['version']['case_id']}/evaluations").json()
    assert len(history["items"]) == 2 and history["items"][0]["stale"] is False


def test_reader_factory_and_production_unconfigured(settings: Settings, c: TestClient) -> None:
    env = create_case(c, standard_case_body(c, capture(c)))
    reader = get_funding_case_reader(settings)
    assert isinstance(reader, FundingCaseReader)
    got = reader.get_version("demo-org", env["version"]["case_id"], 1)
    assert got.version_digest == env["version_digest"]
    with pytest.raises(FundingCaseNotFound):
        reader.get_current("other-org", env["version"]["case_id"])
    prod = build_funding_case_reader(Settings(_env_file=None, environment="production"))
    assert isinstance(prod, UnconfiguredFundingCaseReader)
    with pytest.raises(CapabilityUnavailable):
        prod.get_current("demo-org", env["version"]["case_id"])


def test_tampered_case_or_review_withholds_content(settings: Settings, c: TestClient) -> None:
    env = review(c, create_case(c, standard_case_body(c, capture(c))))
    cid = env["version"]["case_id"]
    path = next(settings.dev_b_store_dir.glob(f"org-*/case-reviews/{cid}.v1/v000001.json"))
    data = json.loads(path.read_text())
    data["record"]["version_digest"] = "0" * 64
    path.chmod(0o600)
    path.write_text(json.dumps(data))
    r = c.get(f"/api/funding/cases/{cid}")
    assert r.status_code == 409 and r.json()["details"]["reason"] == "integrity_failure"
    assert "standard" not in r.text
