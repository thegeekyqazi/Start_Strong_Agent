"""B1-DISC-001 acceptance matrix through the real API (injected/fixture providers)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError

from strongstart_api.config import Settings
from strongstart_api.features.funding.providers import (
    FixtureCaptureProvider,
    ProviderCaptureResponse,
    ProviderSearchResponse,
    RawSearchResult,
)
from strongstart_api.features.funding.store import LocalCaptureStore
from strongstart_api.identity import require_identity
from strongstart_contracts import SessionIdentity
from strongstart_contracts.discovery import CapturedDocument
from tests.funding.conftest import FIXTURE_MODES, GRANT_URL, PROFILE, ClientFactory


@dataclass
class SpySearch:
    name: str = "spy-search"
    mode: str = "live"
    is_fixture: bool = False
    calls: list[tuple[str, int]] = field(default_factory=list)
    results: list[RawSearchResult | None] = field(default_factory=list)

    def search(self, query: str, max_results: int, timeout_s: float) -> ProviderSearchResponse:
        self.calls.append((query, max_results))
        return ProviderSearchResponse(
            results=self.results[:max_results],
            requested_params={"max_results": max_results},
            http_status=200,
        )


@dataclass
class SpyCapture:
    response: ProviderCaptureResponse
    name: str = "spy-capture"
    mode: str = "live"
    is_fixture: bool = False
    calls: list[str] = field(default_factory=list)

    def is_registered_fixture_url(self, url: str) -> bool:
        return False

    def capture(self, url: str, timeout_s: float, max_bytes: int) -> ProviderCaptureResponse:
        self.calls.append(url)
        return self.response


def page(**kw: Any) -> ProviderCaptureResponse:
    base: dict[str, Any] = dict(
        markdown="# Grants\n\nText",
        html="<main><h1>Grants</h1></main>",
        raw_html="<html><body><main><h1>Grants</h1></main></body></html>",
        metadata={
            "url": "https://example.org/grants",
            "statusCode": 200,
            "contentType": "text/html",
        },
        warning=None,
        requested_params={"formats": ["markdown"]},
    )
    base.update(kw)
    return ProviderCaptureResponse(**base)


# DISC-01 ------------------------------------------------------------------------------
def test_disc01_missing_identity_401_before_provider_or_store(make_client: ClientFactory) -> None:
    spy, cap = SpySearch(), SpyCapture(page())
    c = make_client(auth_mode="none", search_provider=spy, capture_provider=cap)
    for method, path, body in [
        ("post", "/api/funding/search", PROFILE),
        ("post", "/api/funding/search", {"garbage": True}),
        ("post", "/api/funding/captures", {"url": "https://example.org/grants"}),
        ("get", "/api/funding/captures/cap-" + "0" * 32, None),
        ("get", f"/api/funding/captures/cap-{'0' * 32}/artifacts/x/content", None),
    ]:
        r = c.request(method, path, json=body)
        assert r.status_code == 401, path
        assert r.json()["code"] == "unauthenticated"
    assert spy.calls == [] and cap.calls == []


# DISC-02 ------------------------------------------------------------------------------
def test_disc02_missing_keys_unavailable_without_fixture_substitution(
    make_client: ClientFactory,
) -> None:
    c = make_client()  # live modes, no keys
    r = c.post("/api/funding/search", json=PROFILE)
    assert r.status_code == 503 and r.json()["details"]["reason"] == "provider_unavailable"
    assert "FIXTURE" not in r.text
    r = c.post("/api/funding/captures", json={"url": "https://example.org/grants"})
    assert r.status_code == 503 and r.json()["details"]["reason"] == "provider_unavailable"
    av = c.get("/api/funding/availability").json()
    assert [p["status"] for p in av["providers"]][:2] == ["unavailable", "unavailable"]
    assert all(p["live_verified"] is False for p in av["providers"])


def test_disc02_configured_key_is_never_exposed(make_client: ClientFactory) -> None:
    canary = "tvly-" + "CANARY" * 4
    c = make_client(tavily_api_key=SecretStr(canary), firecrawl_api_key=SecretStr(canary))
    for path in [
        "/api/funding/availability",
        "/api/funding/status",
        "/api/capabilities",
        "/openapi.json",
    ]:
        assert canary not in c.get(path).text
    av = c.get("/api/funding/availability").json()
    assert av["providers"][0]["status"] == "available"
    assert "not live-verified" in av["providers"][0]["detail"]


# DISC-03 ------------------------------------------------------------------------------
def test_disc03_fixture_mode_is_conspicuous(make_client: ClientFactory) -> None:
    c = make_client(**FIXTURE_MODES)
    r = c.post("/api/funding/search", json=PROFILE).json()
    assert r["query"]["mode"] == "fixture" and r["warnings"][0].startswith("FIXTURE MODE")
    assert all(x["provenance"]["is_simulated"] for x in r["candidates"])
    cap = c.post("/api/funding/captures", json={"url": GRANT_URL}).json()
    assert cap["provider_mode"] == "fixture" and cap["provenance"]["is_simulated"] is True
    assert cap["warnings"][0].startswith("FIXTURE MODE")


@pytest.mark.parametrize(
    "overrides",
    [
        {"funding_search_mode": "fixture"},
        {"funding_capture_mode": "fixture"},
        {"auth_mode": "fixture"},
    ],
)
def test_disc03_production_rejects_fixture_configuration(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", **overrides)


def test_disc03_production_disables_development_store(make_client: ClientFactory) -> None:
    c = make_client(environment="production", auth_mode="none")
    store = c.get("/api/funding/availability").json()["providers"][2]
    assert store["status"] == "unavailable" and store["mode"] == "disabled"


# DISC-04 ------------------------------------------------------------------------------
def test_disc04_limits_enforced_before_provider(make_client: ClientFactory) -> None:
    spy = SpySearch(
        results=[
            RawSearchResult("t", f"https://example.org/{i}", "c", None, None) for i in range(10)
        ]
    )
    c = make_client(search_provider=spy, funding_max_results=3)
    bad = [
        {"profile": {"interests": ["x" * 200]}},
        {"profile": {"interests": []}},
        {"profile": {"interests": ["ok"]}, "max_results": 50},
        {"query": "raw query"},
    ]
    for body in bad:
        assert c.post("/api/funding/search", json=body).status_code == 422
    assert spy.calls == []
    r = c.post("/api/funding/search", json={**PROFILE, "max_results": 5}).json()
    assert spy.calls[-1][1] == 3 and len(r["candidates"]) == 3


# DISC-05 ------------------------------------------------------------------------------
def test_disc05_provider_payload_contains_selected_public_fields_only(
    make_client: ClientFactory,
) -> None:
    spy = SpySearch()
    c = make_client(search_provider=spy, funding_query_fields=["interests"])
    c.post(
        "/api/funding/search",
        json={
            "profile": {
                "interests": ["early learning"],
                "geography": "Demo Region",
                "program_context": "family literacy",
            }
        },
    )
    assert spy.calls == [("early learning grant funding", 5)]
    r = c.post(
        "/api/funding/search",
        json={"profile": {"interests": ["early learning"]}, "organization_facts": "private"},
    )
    assert r.status_code == 422


# DISC-06 ------------------------------------------------------------------------------
def test_disc06_duplicates_collapse_but_cycles_stay_distinct(make_client: ClientFactory) -> None:
    r = make_client(**FIXTURE_MODES).post("/api/funding/search", json=PROFILE).json()
    urls = [c["normalized_url"] for c in r["candidates"]]
    assert urls.count("https://demo-funder.example/programs/community-grants") == 1
    assert "https://demo-funder.example/programs/community-grants?cycle=2025" in urls
    first = r["candidates"][0]
    assert r["duplicates_collapsed"] == 1
    assert first["original_url"].endswith("#apply")  # displayed original preserved
    assert first["duplicates"][0]["original_url"].startswith("https://DEMO-FUNDER")


# DISC-07 / DISC-08 ----------------------------------------------------------------------
def test_disc07_08_candidates_never_become_eligible_or_dated(make_client: ClientFactory) -> None:
    r = make_client(**FIXTURE_MODES).post("/api/funding/search", json=PROFILE).json()
    for cand in r["candidates"]:
        assert cand["eligibility_status"] == "unassessed"
        assert cand["cycle_status"] == "unknown"
        assert cand["deadline"] == {"status": "unknown", "value": None}
    announcement = next(c for c in r["candidates"] if "awards-announced" in c["normalized_url"])
    assert announcement["authority"] == "unreviewed"
    assert any("award announcement" in w for w in r["warnings"])
    assert any("not a likelihood of award" in w for w in r["warnings"])
    dated = next(c for c in r["candidates"] if c["provider_date_hint"])
    assert "deadline" not in json.dumps(
        {k: v for k, v in dated.items() if k == "provider_date_hint"}
    )


def test_disc07_no_results_state(make_client: ClientFactory) -> None:
    r = make_client(search_provider=SpySearch()).post("/api/funding/search", json=PROFILE).json()
    assert r["candidates"] == [] and any("No usable results" in w for w in r["warnings"])


def test_disc08_capture_time_is_not_a_deadline(make_client: ClientFactory) -> None:
    cap = make_client(**FIXTURE_MODES).post("/api/funding/captures", json={"url": GRANT_URL}).json()
    assert cap["source_reference"]["publication_date"] == {"status": "unknown", "value": None}
    assert cap["source_reference"]["reporting_period"] is None
    assert "deadline" not in cap and cap["captured_at"]


# DISC-09 / DISC-10 / DISC-16 --------------------------------------------------------------
def test_disc09_10_16_hashes_lineage_restart_and_tamper(
    make_client: ClientFactory, tmp_path: Path
) -> None:
    c = make_client(**FIXTURE_MODES)
    cap = c.post("/api/funding/captures", json={"url": GRANT_URL, "candidate_id": "cand-1"}).json()
    rec = CapturedDocument.model_validate(cap)
    assert rec.source_reference.source_version_id == rec.capture_id
    assert rec.capture_pipeline_version and rec.provider and rec.captured_at
    # Restart: a brand-new client/app over the same directory reopens it with integrity.
    c2 = make_client(**FIXTURE_MODES)
    html = next(a for a in rec.artifacts if a.representation == "provider_raw_html")
    content = c2.get(f"/api/funding/captures/{rec.capture_id}/artifacts/{html.artifact_id}/content")
    assert content.status_code == 200 and content.json()["integrity_verified"] is True
    assert c2.get(f"/api/funding/captures/{rec.capture_id}").json() == cap
    # Tamper one byte of the stored blob: trusted read is refused.
    blob = next((tmp_path / "captures").rglob(html.sha256))
    data = bytearray(blob.read_bytes())
    data[0] ^= 1
    blob.write_bytes(bytes(data))
    bad = c2.get(f"/api/funding/captures/{rec.capture_id}/artifacts/{html.artifact_id}/content")
    assert bad.status_code == 500 and bad.json()["details"]["reason"] == "integrity_failure"
    assert "FIXTURE" not in bad.text


def test_disc10_same_bytes_two_urls_share_blob_keep_origins(
    make_client: ClientFactory, tmp_path: Path
) -> None:
    same = page()
    spy = SpyCapture(same)
    c = make_client(capture_provider=spy)
    a = c.post("/api/funding/captures", json={"url": "https://example.org/grants"}).json()
    b = c.post("/api/funding/captures", json={"url": "https://mirror.example.org/grants"}).json()
    assert a["capture_id"] != b["capture_id"]
    assert a["requested_url"] != b["requested_url"]
    assert [x["sha256"] for x in a["artifacts"]] == [x["sha256"] for x in b["artifacts"]]
    blobs = list((tmp_path / "captures").rglob("blobs/*"))
    assert len(blobs) == 3  # three representations, stored once each


# DISC-11 ------------------------------------------------------------------------------
def test_disc11_empty_and_partial_extraction(make_client: ClientFactory) -> None:
    c = make_client(**FIXTURE_MODES)
    empty = c.post("/api/funding/captures", json={"url": "https://demo-funder.example/empty"})
    assert empty.status_code == 422
    body = empty.json()
    assert body["details"]["reason"] == "extraction_empty"
    rec = c.get(f"/api/funding/captures/{body['details']['capture_id']}").json()
    assert rec["coverage"] == "empty" and rec["artifacts"] == []
    partial = c.post("/api/funding/captures", json={"url": GRANT_URL + "?cycle=2025"}).json()
    assert partial["coverage"] == "partial"
    assert partial["supported_import_representations"] == []


def test_disc11_whitespace_only_and_oversize_representations(make_client: ClientFactory) -> None:
    spy = SpyCapture(page(html="   \n", raw_html="x" * 20_000))
    c = make_client(capture_provider=spy, funding_max_capture_bytes=10_000)
    rec = c.post("/api/funding/captures", json={"url": "https://example.org/grants"}).json()
    assert rec["coverage"] == "partial"
    assert [a["representation"] for a in rec["artifacts"]] == ["provider_markdown"]
    assert any("exceeds" in w for w in rec["warnings"])


@pytest.mark.parametrize(
    ("meta", "reason"),
    [
        ({"statusCode": 404}, "source_http_error"),
        ({"statusCode": 200, "contentType": "application/pdf"}, "unsupported_content"),
    ],
)
def test_disc11_source_errors_not_stored(
    make_client: ClientFactory, tmp_path: Path, meta: dict[str, Any], reason: str
) -> None:
    c = make_client(capture_provider=SpyCapture(page(metadata=meta)))
    r = c.post("/api/funding/captures", json={"url": "https://example.org/grants"})
    assert r.json()["details"]["reason"] == reason
    assert not list((tmp_path / "captures").rglob("*.json"))


# DISC-12 (API level) --------------------------------------------------------------------
@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd",
        "https://u:p@example.org/",
        "https://example.org:8080/",
    ],
)
def test_disc12_unsafe_capture_destinations(make_client: ClientFactory, url: str) -> None:
    spy = SpyCapture(page())
    r = make_client(capture_provider=spy).post("/api/funding/captures", json={"url": url})
    assert r.status_code == 422 and r.json()["details"]["reason"] == "unsafe_destination"
    assert spy.calls == []


def test_disc12_dns_to_private_and_unsafe_final_destination(make_client: ClientFactory) -> None:
    spy = SpyCapture(page())
    c = make_client(capture_provider=spy, resolver=lambda h: ["10.0.0.7"])
    r = c.post("/api/funding/captures", json={"url": "https://example.org/grants"})
    assert r.json()["details"]["reason"] == "unsafe_destination" and spy.calls == []
    spy2 = SpyCapture(page(metadata={"url": "http://192.168.0.10/", "statusCode": 200}))
    r = make_client(capture_provider=spy2).post(
        "/api/funding/captures", json={"url": "https://example.org/grants"}
    )
    assert r.json()["details"]["reason"] == "unsafe_destination"
    fx = make_client(**FIXTURE_MODES).post(
        "/api/funding/captures", json={"url": "https://demo-funder.example/redirect-internal"}
    )
    assert fx.json()["details"]["reason"] == "unsafe_destination"


def test_disc12_unsafe_search_results_are_omitted_not_capturable(
    make_client: ClientFactory,
) -> None:
    r = make_client(**FIXTURE_MODES).post("/api/funding/search", json=PROFILE).json()
    assert any(o["original_url"] == "http://127.0.0.1/admin" for o in r["omitted"])
    assert all("127.0.0.1" not in c["normalized_url"] for c in r["candidates"])


# DISC-13 ------------------------------------------------------------------------------
def test_disc13_cross_org_and_traversal_reads_rejected(make_client: ClientFactory) -> None:
    c = make_client(**FIXTURE_MODES)
    cap = c.post("/api/funding/captures", json={"url": GRANT_URL}).json()
    other = SessionIdentity(
        actor_id="x", organization_id="other-org", roles=[], is_fixture=True, label="test"
    )
    c.app.dependency_overrides[require_identity] = lambda: other  # type: ignore[attr-defined]
    art = cap["artifacts"][0]["artifact_id"]
    for path in [
        f"/api/funding/captures/{cap['capture_id']}",
        f"/api/funding/captures/{cap['capture_id']}/artifacts/{art}/content",
    ]:
        r = c.get(path, headers={"X-Org-Id": "demo-org"})
        assert r.status_code == 404 and r.json()["details"]["reason"] == "capture_not_found"
    c.app.dependency_overrides.pop(require_identity)  # type: ignore[attr-defined]
    for bad in ["..%2F..%2Fetc%2Fpasswd", "cap-..", "CAP-" + "0" * 32, "%2Ftmp%2Fx"]:
        r = c.get(f"/api/funding/captures/{bad}")
        assert r.status_code == 404, bad
    r = c.get(f"/api/funding/captures/{cap['capture_id']}/artifacts/..%2F..%2Fx/content")
    assert r.status_code == 404
    assert "/" not in json.dumps(cap["artifacts"]).replace("text/", "")  # no local paths
    assert "captures" not in json.dumps(cap).split("supported_import")[0].lower()


# DISC-14 ------------------------------------------------------------------------------
def test_disc14_errors_safe_and_not_retried(make_client: ClientFactory) -> None:
    from strongstart_api.features.funding.providers import ProviderError
    from strongstart_contracts.discovery import FundingErrorReason

    calls: list[int] = []

    @dataclass
    class Failing:
        name: str = "failing"
        mode: str = "live"
        is_fixture: bool = False

        def search(self, query: str, max_results: int, timeout_s: float) -> Any:
            calls.append(1)
            raise ProviderError(
                FundingErrorReason.OUTCOME_UNKNOWN, "timed out", outcome_uncertain=True
            )

    r = make_client(search_provider=Failing()).post("/api/funding/search", json=PROFILE)
    assert r.status_code == 504 and calls == [1]
    d = r.json()["details"]
    assert d["reason"] == "outcome_unknown" and d["outcome_uncertain"] is True
    assert d["retried"] is False


# DISC-15 ------------------------------------------------------------------------------
def test_disc15_page_text_is_data_and_no_secrets_leak(
    make_client: ClientFactory, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    canary = "fc-" + "CANARY" * 5
    c = make_client(
        firecrawl_api_key=SecretStr(canary),
        tavily_api_key=SecretStr(canary),
        capture_provider=FixtureCaptureProvider(),
        funding_search_mode="fixture",
    )
    cap = c.post("/api/funding/captures", json={"url": GRANT_URL}).json()
    raw = next(a for a in cap["artifacts"] if a["representation"] == "provider_raw_html")
    content = c.get(
        f"/api/funding/captures/{cap['capture_id']}/artifacts/{raw['artifact_id']}/content"
    )
    body = content.json()
    assert content.headers["content-type"].startswith("application/json")
    assert "<script>" in body["text"]  # preserved verbatim as data, served as a JSON string
    assert cap["authority_review"] == "unreviewed"  # page text never promotes authority
    stored = "".join(
        p.read_text(errors="ignore") for p in (tmp_path / "captures").rglob("*") if p.is_file()
    )
    for text in (json.dumps(cap), content.text, stored, caplog.text):
        assert canary not in text and "Bearer" not in text


# DISC-17 ------------------------------------------------------------------------------
def test_disc17_serialized_record_resolves_exact_html_for_b2(
    make_client: ClientFactory, tmp_path: Path
) -> None:
    from html.parser import HTMLParser

    c = make_client(**FIXTURE_MODES)
    cap = c.post("/api/funding/captures", json={"url": GRANT_URL}).json()
    serialized = json.dumps(cap)
    # --- consumer side (contract-level stand-in for B2's importer; no URL refetch) ---
    record = CapturedDocument.model_validate_json(serialized)
    reader = LocalCaptureStore(tmp_path / "captures")
    assert record.supported_import_representations == ["provider_html", "provider_raw_html"]
    art = next(a for a in record.artifacts if a.representation == "provider_html")
    verified = reader.read_artifact(record.organization_id, record.capture_id, art.artifact_id)
    assert verified.artifact.sha256 == art.sha256 == record.source_reference.content_hash

    class Fields(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.names: list[str] = []

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag == "textarea":
                self.names.append(dict(attrs)["name"] or "")

    parser = Fields()
    parser.feed(verified.content.decode("utf-8"))
    assert parser.names == ["mission", "services"]
    lineage = (record.capture_id, record.source_reference.source_id, art.sha256, art.representation)
    assert all(lineage)
