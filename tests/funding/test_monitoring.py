"""DEV-B-BUNDLE-002 M5: saved searches, manual reruns and source rechecks (BND-41..BND-48).

Provider doubles are injected for deterministic variation; they are HTTP-free test doubles,
not live Tavily/Firecrawl evidence.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from strongstart_api.config import Settings
from strongstart_api.features.funding import deps, providers
from strongstart_api.features.funding.providers import (
    ProviderCaptureResponse,
    ProviderError,
    ProviderSearchResponse,
    RawSearchResult,
)
from strongstart_contracts.discovery import FundingErrorReason

from .case_helpers import (
    OTHER,
    anchor,
    capture,
    client_for,
    create_case,
    evaluate,
    key,
    make_settings,
    review,
    standard_case_body,
)

UPDATES = "https://demo-funder.example/programs/community-grants/updates"
PROFILE = {"interests": ["early learning"], "geography": "Demo Region"}


@pytest.fixture(autouse=True)
def _reset_rotation() -> Iterator[None]:
    providers._FIXTURE_ROTATION.clear()
    yield
    providers._FIXTURE_ROTATION.clear()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def c(settings: Settings) -> TestClient:
    return client_for(settings)


@dataclass
class SearchDouble:
    batches: list[list[str]]
    name: str = "search-double"
    mode: str = "fixture"
    is_fixture: bool = True
    queries: list[str] = field(default_factory=list)
    fail_with: FundingErrorReason | None = None

    def search(self, query: str, max_results: int, timeout_s: float) -> ProviderSearchResponse:
        self.queries.append(query)
        if self.fail_with is not None:
            raise ProviderError(self.fail_with, "TEST provider failure")
        urls = self.batches[min(len(self.queries) - 1, len(self.batches) - 1)]
        return ProviderSearchResponse(
            results=[
                RawSearchResult(
                    title=f"FIXTURE {u}",
                    url=u,
                    content="FIXTURE grant funding",
                    score=None,
                    published_date=None,
                )
                for u in urls
            ],
            requested_params={"double": True},
            http_status=None,
        )


@dataclass
class CaptureDouble:
    pages: list[tuple[str | None, str | None]]
    params: dict[str, Any] = field(default_factory=lambda: {"double": True})
    name: str = "capture-double"
    mode: str = "fixture"
    is_fixture: bool = True
    calls: int = 0

    def is_registered_fixture_url(self, url: str) -> bool:
        return True

    def capture(self, url: str, timeout_s: float, max_bytes: int) -> ProviderCaptureResponse:
        md, html = self.pages[min(self.calls, len(self.pages) - 1)]
        self.calls += 1
        return ProviderCaptureResponse(
            markdown=md,
            html=html,
            raw_html=html,
            metadata={"url": url, "statusCode": 200, "contentType": "text/html"},
            warning=None,
            requested_params=dict(self.params),
        )


def with_providers(c: TestClient, search: Any = None, capture_provider: Any = None) -> None:
    app = c.app
    if search is not None:
        app.dependency_overrides[deps.get_search_provider] = lambda: search  # type: ignore[attr-defined]
    if capture_provider is not None:
        app.dependency_overrides[deps.get_capture_provider] = lambda: capture_provider  # type: ignore[attr-defined]


def profile(c: TestClient, **over: Any) -> dict[str, Any]:
    r = c.post(
        "/api/funding/searches",
        json={"idempotency_key": key("prof"), "label": "FIXTURE label", "profile": PROFILE, **over},
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()
    return data


def run(c: TestClient, prof: dict[str, Any], version: int = 1, k: str | None = None) -> Any:
    return c.post(
        f"/api/funding/searches/{prof['profile_id']}/runs",
        json={"idempotency_key": k or key("run"), "profile_version": version},
    )


def recheck(c: TestClient, capture_id: str, **extra: Any) -> Any:
    return c.post(
        f"/api/funding/captures/{capture_id}/recheck",
        json={"idempotency_key": key("recheck"), **extra},
    )


# ------------------------------------------------------------------- BND-41/42


def test_bnd41_profile_keeps_public_fields_only_and_previews_the_query(
    c: TestClient,
) -> None:
    bad = c.post(
        "/api/funding/searches",
        json={
            "idempotency_key": key(),
            "label": "x",
            "profile": {**PROFILE, "organization_facts": "120 children served"},
        },
    )
    assert bad.status_code == 422
    prof = profile(c, label="FIXTURE <script>x</script> label")
    assert prof["query_preview"] == "early learning Demo Region grant funding"
    assert prof["public_fields_used"] == ["interests", "geography"]
    double = SearchDouble([["https://a.example/grants"]])
    with_providers(c, search=double)
    # Private case/scenario data exists in the org but never flows into the query.
    env = review(c, create_case(c, standard_case_body(c, capture(c))))
    evaluate(
        c, env, inputs={"region": {"value": "demo-region-north", "provenance": "staff_asserted"}}
    )
    assert run(c, prof).status_code == 201
    assert double.queries == [prof["query_preview"]]
    assert "script" not in double.queries[0] and "demo-region-north" not in double.queries[0]


def test_bnd42_one_provider_call_failures_stay_failures_and_replay_is_free(
    settings: Settings,
) -> None:
    c = client_for(settings)
    prof = profile(c)
    double = SearchDouble([["https://a.example/grants"]])
    with_providers(c, search=double)
    k = key("run")
    first, again = run(c, prof, k=k), run(c, prof, k=k)
    assert (first.status_code, again.status_code) == (201, 200)
    assert len(double.queries) == 1  # the replay did not call the provider
    double.fail_with = FundingErrorReason.RATE_LIMITED
    failed = run(c, prof).json()
    assert failed["outcome"] == "failed" and failed["error_reason"] == "rate_limited"
    assert failed["result"] is None and failed["normalized_urls"] == []
    assert len(double.queries) == 2  # exactly one request, no automatic retry
    live = client_for(settings.model_copy(update={"funding_search_mode": "live"}))
    live_prof = profile(live)
    unavailable = run(live, live_prof).json()
    assert unavailable["outcome"] == "unavailable"
    assert unavailable["error_reason"] == "provider_unavailable" and unavailable["result"] is None
    history = live.get(f"/api/funding/searches/{live_prof['profile_id']}/runs").json()["items"]
    assert [h["outcome"] for h in history] == ["unavailable"]  # failure kept in history


# ------------------------------------------------------------------- BND-43/44


def test_bnd43_same_version_comparison_by_normalized_url(c: TestClient) -> None:
    prof = profile(c)
    with_providers(
        c,
        search=SearchDouble(
            [
                ["https://a.example/grants?utm_source=x", "https://b.example/fund"],
                ["https://B.example:443/fund#apply", "https://c.example/new"],
            ]
        ),
    )
    r1, r2 = run(c, prof).json(), run(c, prof).json()
    cmp = c.get(
        f"/api/funding/searches/{prof['profile_id']}/runs/{r2['run_id']}/compare",
        params={"base": r1["run_id"]},
    ).json()
    assert cmp["newly_seen"] == ["https://c.example/new"]
    assert cmp["seen_again"] == ["https://b.example/fund"]
    assert cmp["not_seen_in_this_result_set"] == ["https://a.example/grants"]
    assert "not a removed opportunity or a closed grant" in cmp["note"]


def test_bnd44_versions_and_failures_are_not_compared(c: TestClient) -> None:
    prof = profile(c)
    double = SearchDouble([["https://a.example/grants"]])
    with_providers(c, search=double)
    r1 = run(c, prof).json()
    rev = c.post(
        f"/api/funding/searches/{prof['profile_id']}/revisions",
        json={
            "idempotency_key": key(),
            "expected_version": 1,
            "label": "v2",
            "profile": {"interests": ["family literacy"]},
        },
    )
    assert rev.status_code == 201 and rev.json()["version"] == 2
    stale = run(c, prof, version=1)
    assert stale.status_code == 409 and stale.json()["details"]["current_version"] == 2
    r2 = run(c, prof, version=2).json()
    base = f"/api/funding/searches/{prof['profile_id']}/runs"
    cmp = c.get(f"{base}/{r2['run_id']}/compare", params={"base": r1["run_id"]})
    assert cmp.status_code == 409 and cmp.json()["details"]["reason"] == "not_comparable"
    double.fail_with = FundingErrorReason.TIMEOUT
    r3 = run(c, prof, version=2).json()
    assert r3["outcome"] == "failed"
    cmp = c.get(f"{base}/{r3['run_id']}/compare", params={"base": r2["run_id"]})
    assert cmp.status_code == 409


def test_bnd44_other_org_profile_and_runs_look_unknown(settings: Settings, c: TestClient) -> None:
    prof = profile(c)
    other = client_for(settings, OTHER)
    a = other.get(f"/api/funding/searches/{prof['profile_id']}")
    b = other.get(f"/api/funding/searches/prof-{'0' * 26}")
    assert a.status_code == b.status_code == 404 and a.json()["details"] == b.json()["details"]
    assert run(other, prof).status_code == 404
    assert other.get("/api/funding/searches").json()["items"] == []


# ------------------------------------------------------------------- BND-45/46


def _blob_hashes(settings: Settings) -> dict[str, str]:
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in settings.funding_capture_store_dir.glob("org-*/blobs/*")
    }


def test_bnd45_recheck_creates_new_capture_keeps_old_bytes_and_obeys_url_policy(
    settings: Settings, c: TestClient
) -> None:
    old = capture(c, UPDATES)
    before = _blob_hashes(settings)
    obs = recheck(c, old["capture_id"]).json()
    assert obs["new_capture_id"] and obs["new_capture_id"] != old["capture_id"]
    assert obs["overall"] == "unchanged"
    after = _blob_hashes(settings)
    assert all(after[k] == v for k, v in before.items())  # old bytes untouched
    assert c.get(f"/api/funding/captures/{old['capture_id']}").json() == old
    live = settings.model_copy(update={"funding_capture_mode": "live"})
    lc = client_for(live)
    double = CaptureDouble([("# FIXTURE", "<p>FIXTURE</p>")], mode="live", is_fixture=False)
    with_providers(lc, capture_provider=double)
    first = capture(lc, "https://grants.example/program")
    lc.app.dependency_overrides[deps.get_resolver] = lambda: lambda host: ["10.0.0.5"]  # type: ignore[attr-defined]
    denied = recheck(lc, first["capture_id"]).json()
    assert denied["overall"] == "failed" and denied["failure_reason"] == "unsafe_destination"
    assert double.calls == 1  # the private destination was refused before any provider call


def test_bnd46_match_change_missing_and_not_comparable(c: TestClient) -> None:
    old = capture(c, UPDATES)
    unchanged = recheck(c, old["capture_id"]).json()
    changed = recheck(c, old["capture_id"]).json()
    partial = recheck(c, old["capture_id"]).json()
    assert unchanged["overall"] == "unchanged"
    assert {x["outcome"] for x in unchanged["comparisons"]} == {"match"}
    assert changed["overall"] == "changed"
    assert "+Standard stream requests: 20,000 to 90,000 CAD per award." in changed["text_diff"]
    assert "not by itself a policy change" in changed["explanation"]
    assert partial["overall"] == "partial"
    assert "missing_in_new" in {x["outcome"] for x in partial["comparisons"]}
    double = CaptureDouble([("# FIXTURE", "<p>x</p>")], params={"formats": "other"})
    with_providers(c, capture_provider=double)
    different = recheck(c, old["capture_id"]).json()
    assert different["overall"] == "not_comparable" and different["comparisons"] == []
    history = c.get(f"/api/funding/captures/{old['capture_id']}/observations").json()
    assert len(history["items"]) == 4


# ------------------------------------------------------------------- BND-47/48


def test_bnd47_linked_change_requires_re_review_and_stales_history(c: TestClient) -> None:
    doc = capture(c, UPDATES)
    body = {
        "idempotency_key": key(),
        "context": {
            "funder_label": "F",
            "stream_label": "standard",
            "cycle_label": "2026",
            "stage": "full_application",
        },
        "capture_links": [{"capture_id": doc["capture_id"]}],
    }
    body["anchors"] = [
        anchor(c, doc, "Standard stream requests: 20,000 to 100,000 CAD per award.", "amount")
    ]
    body["requirements"] = [
        {
            "requirement_key": "cap",
            "spec": {
                "kind": "amount_range",
                "limit_kind": "per_award",
                "maximum": "100000",
                "currency": "CAD",
            },
            "anchor_keys": ["amount"],
            "interpretation": "FIXTURE per-award max",
        }
    ]
    env = review(c, create_case(c, body))
    cid = env["version"]["case_id"]
    report = evaluate(
        c,
        env,
        inputs={
            "request_amount": {"amount": "50000", "currency": "CAD", "provenance": "staff_asserted"}
        },
    )
    assert report["results"][0]["outcome"] == "met"
    unchanged = recheck(c, doc["capture_id"], funding_case_id=cid, funding_case_version=1).json()
    assert unchanged["overall"] == "unchanged"
    assert c.get(f"/api/funding/cases/{cid}").json()["source_status"] == "current"
    changed = recheck(c, doc["capture_id"], funding_case_id=cid, funding_case_version=1).json()
    assert changed["overall"] == "changed"
    assert any("requires re-review" in e for e in changed["downstream_effects"])
    now = c.get(f"/api/funding/cases/{cid}").json()
    assert now["source_status"] == "requires_re_review"
    assert now["readiness"] == "requires_re_review"
    assert now["source_findings"][0]["observation_id"] == changed["observation_id"]
    history = c.get(f"/api/funding/cases/{cid}/evaluations").json()["items"]
    assert history[0]["stale"] is True
    assert history[0]["report"] == report  # the old evaluation is kept unchanged
    blocked = evaluate(
        c,
        env,
        inputs={
            "request_amount": {"amount": "50000", "currency": "CAD", "provenance": "staff_asserted"}
        },
    )
    assert blocked["results"][0]["outcome"] == "unknown"
    assert "requires re-review" in blocked["results"][0]["found"]


def test_bnd47_unlinked_capture_cannot_be_linked_to_a_case(c: TestClient) -> None:
    doc = capture(c, UPDATES)
    env = create_case(c, standard_case_body(c, capture(c)))
    r = recheck(
        c, doc["capture_id"], funding_case_id=env["version"]["case_id"], funding_case_version=1
    )
    assert r.status_code == 422


def test_bnd48_observation_never_rewrites_rules_or_claims_downstream_invalidation(
    c: TestClient,
) -> None:
    doc = capture(c, UPDATES)
    env = create_case(
        c,
        {
            "idempotency_key": key(),
            "context": {"funder_label": "F"},
            "capture_links": [{"capture_id": doc["capture_id"]}],
        },
    )
    cid = env["version"]["case_id"]
    recheck(c, doc["capture_id"], funding_case_id=cid, funding_case_version=1)
    obs = recheck(c, doc["capture_id"], funding_case_id=cid, funding_case_version=1).json()
    assert obs["overall"] == "changed"
    after = c.get(f"/api/funding/cases/{cid}").json()
    assert after["version"] == env["version"] and after["version_digest"] == env["version_digest"]
    assert after["current_version"] == 1  # no automatic new rules or versions
    assert any("A4" in e and "C3" in e for e in obs["downstream_effects"])
    assert any(
        "no answers, approvals or rules were changed" in e for e in obs["downstream_effects"]
    )
