"""C2 deterministic rules through the real check route (APP-01/02/03, POL-01/02/03).

Positive, negative and boundary cases from the catalog's minimum fixtures. Each test calls
the API with the shared fixture workspace and the synthetic demo policy.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from strongstart_api.features.applications.router import get_workspace_source
from strongstart_api.features.applications.rules.counters import (
    code_points_v1,
    utf16_v1,
    words_v1,
)
from strongstart_api.features.applications.workspace import FixtureWorkspaceSource
from strongstart_contracts.answers import ApplicationWorkspace

from .conftest import FACT, make_client

BODY = {"question_version": 1, "evidence_bundle_id": "demo-evidence-a-v1"}


def check(
    text: str, question: str = "mission-q1", mode: str = "working", client: TestClient | None = None
) -> dict[str, Any]:
    c = client or make_client(auth_mode="fixture")
    r = c.post(
        f"/api/applications/questions/{question}/check", json={**BODY, "text": text, "mode": mode}
    )
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def outcomes(report: dict[str, Any], rule: str) -> list[str]:
    return [f["result"]["outcome"] for f in report["findings"] if f["result"]["rule_id"] == rule]


def findings(report: dict[str, Any], rule: str) -> list[dict[str, Any]]:
    return [f for f in report["findings"] if f["result"]["rule_id"] == rule]


# --- APP-03 (owner priority) -------------------------------------------------------------


def test_c1_gap_raw_number_is_flagged_and_blocks_review() -> None:
    working = check("We served 500 children in 2025.")
    reviewed = check("We served 500 children in 2025.", mode="reviewed")
    assert outcomes(working, "APP-03") == ["needs_review"]
    assert outcomes(reviewed, "APP-03") == ["fail"]
    f = findings(reviewed, "APP-03")[0]
    assert f["affected_text"] == "500" and f["result"]["observed"] == "500"


def test_bound_fact_renders_server_side_with_exact_span() -> None:
    report = check(f"We served {{{{fact:{FACT}}}}} last year.")
    rendered = report["rendered"]
    assert rendered["text"] == "We served 120 children (2025-09/2026-06) last year."
    b = rendered["bindings"][0]
    assert rendered["text"][b["span_start"] : b["span_end"]] == b["rendered_text"]
    assert b["pack_version_id"] == "demo-a-v1"
    # bound and verified? The fixture fact is needs_review: citation alone is not support.
    assert outcomes(report, "APP-03") == ["needs_review"]
    assert "not verified" in findings(report, "APP-03")[0]["message"]


def test_citation_present_but_raw_figure_still_unbound() -> None:
    report = check(f"We served 500 children {{{{fact:{FACT}}}}}.", mode="reviewed")
    assert "fail" in outcomes(report, "APP-03")
    assert any(f["affected_text"] == "500" for f in findings(report, "APP-03"))


def test_unknown_or_out_of_scope_fact_is_not_rendered_or_leaked() -> None:
    report = check("We served {{fact:other-org-secret-fact}}.")
    assert "other-org" not in report["rendered"]["text"]
    assert report["rendered"]["bindings"] == []
    assert outcomes(report, "APP-03") == ["fail"]


def test_unsupported_marker_allowed_in_working_blocks_in_reviewed() -> None:
    text = "Our waitlist doubled {{unsupported:no-waitlist-data}}."
    assert outcomes(check(text), "APP-03") == ["needs_review"]
    assert outcomes(check(text, mode="reviewed"), "APP-03") == ["fail"]


def test_clean_text_passes_only_its_predicate() -> None:
    report = check("Demo Org supports early learning in its community.")
    assert outcomes(report, "APP-03") == ["pass"]
    assert "this check only" in findings(report, "APP-03")[0]["message"]


# --- APP-01 ------------------------------------------------------------------------------


def test_counters_boundaries() -> None:
    assert words_v1("don't stop well-known") == 3
    assert words_v1("one\ntwo\r\nthree") == 3
    assert words_v1("a\u00a0b") == 2  # NBSP separates
    assert words_v1("a​b") == 1  # zero-width does not
    assert code_points_v1("😀") == 1 and utf16_v1("😀") == 2


def test_app01_n_and_n_plus_one_at_limit() -> None:
    at = check(" ".join(["word"] * 50))
    over = check(" ".join(["word"] * 51))
    assert outcomes(at, "APP-01") == ["needs_review"]  # convention unconfirmed: never pass
    assert outcomes(over, "APP-01") == ["fail"]
    assert "1 over" in findings(over, "APP-01")[0]["message"]


def test_app01_passes_when_convention_confirmed() -> None:
    real = FixtureWorkspaceSource().get("demo-org")
    qs = real.question_set
    q0 = qs.questions[0]
    limit = q0.limit
    assert limit is not None
    confirmed = q0.model_copy(
        update={"limit": limit.model_copy(update={"counting_convention": "words-v1"})}
    )
    ws = real.model_copy(
        update={"question_set": qs.model_copy(update={"questions": [confirmed, *qs.questions[1:]]})}
    )

    class Source:
        is_fixture = True

        def get(self, organization_id: str) -> ApplicationWorkspace:
            return ws

    c = make_client(auth_mode="fixture")
    c.app.dependency_overrides[get_workspace_source] = lambda: Source()  # type: ignore[attr-defined]
    assert outcomes(check(" ".join(["word"] * 50), client=c), "APP-01") == ["pass"]


def test_app01_conflict_and_unknown_unit_never_choose() -> None:
    conflict = check(" ".join(["w"] * 400), question="partnership-q3")
    assert outcomes(conflict, "APP-01") == ["needs_review"]  # over 350, under 500
    assert outcomes(check(" ".join(["w"] * 501), question="partnership-q3"), "APP-01") == ["fail"]
    unknown = check("x" * 301, question="pending-q4")  # 1 word, 301 characters
    assert outcomes(unknown, "APP-01") == ["needs_review"]
    assert findings(unknown, "APP-01")[0]["result"]["observed"] == {
        "words-v1": 1,
        "code-points-v1": 301,
    }


# --- APP-02 ------------------------------------------------------------------------------


def test_app02_required_status_map() -> None:
    assert outcomes(check(""), "APP-02") == ["fail"]  # mission-q1 required, empty
    assert outcomes(check("Answer."), "APP-02") == ["pass"]
    assert outcomes(check("Answer.", question="partnership-q3"), "APP-02") == [
        "needs_review"
    ]  # null


# --- POL ---------------------------------------------------------------------------------


def test_pol01_scoped_term_flagged_but_not_inside_quotes() -> None:
    flagged = check("The Demo Literacy Program pairs each child with a tutor.")
    assert outcomes(flagged, "POL-01") == ["fail"]
    assert "Volunteer Coach" in findings(flagged, "POL-01")[0]["message"]
    assert "synthetic demo policy" in findings(flagged, "POL-01")[0]["message"]
    quoted = check('The Demo Literacy Program parent said "my tutor changed everything".')
    assert outcomes(quoted, "POL-01") == ["pass"]
    out_of_scope = check("A tutor helped at the library.")
    assert outcomes(out_of_scope, "POL-01") == ["not_applicable"]


def test_pol02_first_use_expansion_and_protected_text() -> None:
    assert outcomes(check("DLP helps families. Demo Literacy Program grows."), "POL-02") == ["fail"]
    assert outcomes(check("Demo Literacy Program (DLP) helps. DLP grows."), "POL-02") == ["pass"]
    assert "fail" in outcomes(check("The demo literacy program helps."), "POL-02")


def test_pol03_placeholders_working_vs_reviewed() -> None:
    assert outcomes(check("We will serve XXX families."), "POL-03") == ["needs_review"]
    assert outcomes(check("We will serve XXX families.", mode="reviewed"), "POL-03") == ["fail"]
    assert outcomes(check("Budget TBD."), "POL-03") == ["needs_review"]
    assert outcomes(check("All done."), "POL-03") == ["pass"]


def test_policy_absent_means_needs_review_never_pass() -> None:
    from strongstart_api.features.applications.router import get_policy

    c = make_client(auth_mode="fixture")
    c.app.dependency_overrides[get_policy] = lambda: None  # type: ignore[attr-defined]
    report = check("Demo Literacy Program tutors.", client=c)
    assert outcomes(report, "POL-01") == ["needs_review"]
    assert outcomes(report, "POL-02") == ["needs_review"]


def test_report_binds_exact_text_and_carries_no_status() -> None:
    a, b = check("Answer one."), check("Answer two.")
    assert a["submitted_text_sha256"] != b["submitted_text_sha256"]
    assert not {"approved", "status", "state"} & set(a)
    for f in a["findings"]:
        assert f["result"]["rule_version"] == "c2-1"
        assert f["result"]["inputs"]["rendered_text_sha256"] == a["rendered"]["text_sha256"]
