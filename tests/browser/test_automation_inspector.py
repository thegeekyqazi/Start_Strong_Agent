"""Real-Chromium read-only inspection of the representative fixture portal (B2-AUTO-001).

AUTO-07..AUTO-12. These use the installed Playwright Chromium; nothing is mocked.
"""

from __future__ import annotations

import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.automation.inspection import fingerprint, observed_fields
from strongstart_api.features.automation.inspector import (
    FixtureServer,
    InspectionFailure,
    InspectorConfig,
    inspect_page,
)
from strongstart_api.features.automation.registry import FORM_VERSIONS, PORTAL_FIXTURES, portal_page
from strongstart_api.features.automation.router import get_inspector_config

pytestmark = pytest.mark.browser
READY = 'body[data-fixture-ready="true"]'


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(
        create_app(Settings(_env_file=None, answer_store_backend="memory", auth_mode="fixture"))
    )


def inspect(client: TestClient, fixture_id: str, **extra: Any) -> dict[str, Any]:
    r = client.post("/api/automation/inspect-fixture", json={"fixture_id": fixture_id, **extra})
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def statuses(body: dict[str, Any]) -> dict[str, str]:
    return {m["question_id"]: m["status"] for m in body["mappings"]}


@pytest.fixture
def canary() -> Iterator[tuple[str, list[str]]]:
    """Another local service the fixture must never reach."""
    hits: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            hits.append(self.path)
            self.send_response(200)
            self.end_headers()

        do_POST = do_GET  # noqa: N815

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", hits
    finally:
        server.shutdown()
        server.server_close()


def test_auto07_chromium_reads_representative_fields_after_readiness(client: TestClient) -> None:
    body = inspect(client, "rep-portal-v1")
    assert body["is_fixture"] is True and body["prefill_permitted"] is False
    assert body["browser_name"] == "chromium" and body["browser_version"]
    assert body["fingerprint_status"] == "matches_expected"
    assert body["fingerprint"] == FORM_VERSIONS["rep-portal"][1]
    assert body["map_status"] == "valid"
    assert set(statuses(body).values()) == {"matched"}
    fields = {f["field_key"]: f for f in body["fields"]}
    assert fields["id:mission"]["tag"] == "textarea" and fields["id:mission"]["required"]
    assert fields["id:mission"]["max_length"] == 2000
    assert fields["id:mission"]["described_by_text"] == ["Maximum 50 words."]
    assert fields["id:pending-applications"]["max_length"] == 250
    assert fields["id:request-amount"]["input_type"] == "number"
    assert (fields["id:request-amount"]["min"], fields["id:request-amount"]["max"]) == (
        "20000",
        "100000",
    )
    assert fields["id:financial-statement"]["accept"] == [".pdf", ".docx"]
    assert fields["id:partnership"]["visible"] is False  # hidden conditional section
    assert fields["id:partnership"]["declared_fixture_metadata"]["data-fixture-condition"] == (
        "rp-has-partners == yes"
    )
    radios = [f for f in body["fields"] if f["name"] == "service_area"]
    assert [r["option_value"] for r in radios] == ["city", "region", "province"]
    assert fields["id:fixture-submit"]["disabled"] is True
    fm = body["form_map"]
    assert fm["origin"] == "fixture://rep-portal.local" and fm["fingerprint"] == body["fingerprint"]
    assert {f["question_id"] for f in fm["fields"]} == {m["question_id"] for m in body["mappings"]}
    # held questions are flagged on their mappings
    held = {m["question_id"] for m in body["mappings"] if m["requirement_hold"]}
    assert held == {"rp-partnership", "rp-other-funding"}


def test_auto07_dynamic_content_requires_the_declared_wait(client: TestClient) -> None:
    body = inspect(client, "rep-portal-v1-dynamic")
    assert body["map_status"] == "valid" and statuses(body)["rp-partnership"] == "matched"
    # Enumerating immediately (no readiness wait) would miss the inserted section.
    raw = inspect_page(
        portal_page(PORTAL_FIXTURES["rep-portal-v1-dynamic"]),
        ready_selector="body",
        config=InspectorConfig(),
    )
    early = observed_fields(raw.fields)
    assert not any(f.dom_id == "partnership" for f in early)
    assert fingerprint(early) != FORM_VERSIONS["rep-portal"][1]


def test_auto08_duplicate_missing_unsupported_never_first_match(client: TestClient) -> None:
    dup = inspect(client, "rep-portal-v1-duplicate")
    assert statuses(dup)["rp-services"] == "ambiguous"
    assert (
        next(m for m in dup["mappings"] if m["question_id"] == "rp-services")["observed_count"] == 2
    )
    assert dup["map_status"] == "invalid" and dup["form_map"] is None
    alt = inspect(client, "rep-portal-v1-altered")
    assert statuses(alt)["rp-mission"] == "missing"
    assert alt["map_status"] == "invalid" and alt["form_map"] is None
    assert any(f["code"] == "unexpected_required_field" for f in alt["findings"])
    widget = inspect(client, "rep-portal-v1-unsupported-widget")
    assert statuses(widget)["rp-services"] == "unsupported"
    assert widget["form_map"] is None
    label = inspect(client, "rep-portal-v1-missing-label")
    assert any(
        f["code"] == "missing_label" and f["field_id"] == "id:other-funding"
        for f in label["findings"]
    )


def test_auto09_changed_fingerprint_or_version_is_never_silently_reused(
    client: TestClient,
) -> None:
    alt = inspect(client, "rep-portal-v1-altered")
    assert alt["fingerprint_status"] == "changed"
    assert alt["findings"][0]["code"] == "fingerprint_changed"
    stale = "0" * 64
    same_form = inspect(client, "rep-portal-v1", expected_fingerprint=stale)
    assert same_form["map_status"] == "invalid" and same_form["form_map"] is None
    assert any(f["code"] == "mapping_changed" for f in same_form["findings"])
    r = client.post(
        "/api/automation/inspect-fixture",
        json={"fixture_id": "rep-portal-v1", "expected_form_version": 2},
    )
    assert r.status_code == 422 and r.json()["details"]["reason"] == "unknown_form_version"


def test_auto10_fixture_exception_cannot_reach_other_local_services(
    canary: tuple[str, list[str]],
) -> None:
    url, hits = canary
    page = f"""<html><body>
      <img src="{url}/img"><iframe src="{url}/frame"></iframe>
      <link rel="stylesheet" href="{url}/css">
      <img src="/redirect-to-canary">
      <form action="{url}/submit" method="post"><input id="x" name="x"></form>
      <script>
        fetch('{url}/fetch').catch(function () {{}});
        fetch('{url}/post', {{ method: 'POST', body: 'a=1' }}).catch(function () {{}});
        var ws; try {{ ws = new WebSocket('{url.replace("http", "ws")}/ws') }} catch (e) {{}}
        setTimeout(function () {{ location.href = '{url}/navigate' }}, 10);
        setTimeout(function () {{ document.body.setAttribute('data-fixture-ready', 'true') }}, 400);
      </script></body></html>""".encode()
    raw = inspect_page(
        page,
        ready_selector=READY,
        config=InspectorConfig(),
        extra_pages={"/redirect-to-canary": b""},
        redirects={"/redirect-to-canary": f"{url}/redirected"},
    )
    assert hits == []
    targets = {e.target for e in raw.activity.entries}
    for path in ("/img", "/frame", "/css", "/fetch", "/post", "/navigate"):
        assert f"{url}{path}" in targets, path
    assert raw.activity.mutation_blocked >= 1
    assert raw.fixture_server_mutation_hits == 0


def test_auto11_inspector_performs_no_writes_and_submit_is_denied(client: TestClient) -> None:
    body = inspect(client, "rep-portal-v1-hostile")
    act = body["activity"]
    assert act["inspector_actions"] == []
    assert act["fixture_server_mutation_hits"] == 0
    assert act["mutation_requests_blocked"] >= 1
    assert act["requests_allowed"] == 1  # only the registered portal document
    reasons = {(e["method"], e["reason"]) for e in act["blocked_log"]}
    assert ("POST", "mutation_method_denied") in reasons
    assert act["navigations_blocked"] >= 1
    assert any("169.254.169.254" in e["target"] for e in act["blocked_log"])
    assert body["map_status"] == "valid"  # hostile behaviour is observed, not obeyed
    # The fixture submit endpoint itself denies the automation principal.
    with FixtureServer({"/portal": b"x"}) as server:
        req = urllib.request.Request(f"{server.origin}/fixture-submit", data=b"a=1", method="POST")  # noqa: S310
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=5)  # noqa: S310
        assert exc.value.code == 403
        assert server.mutation_hits == 1


def test_auto12_missing_browser_is_unavailable_not_faked() -> None:
    client = TestClient(
        create_app(Settings(_env_file=None, answer_store_backend="memory", auth_mode="fixture"))
    )
    client.app.dependency_overrides[get_inspector_config] = lambda: InspectorConfig(  # type: ignore[attr-defined]
        executable_path="/nonexistent/chromium-for-b2-test"
    )
    r = client.post("/api/automation/inspect-fixture", json={"fixture_id": "rep-portal-v1"})
    assert r.status_code == 503
    assert r.json()["details"]["reason"] == "browser_unavailable"
    assert "Traceback" not in r.text and "/nonexistent" not in r.text


def test_auto12_timeout_is_bounded_and_browser_closes() -> None:
    seen: list[Any] = []
    with pytest.raises(InspectionFailure) as exc:
        inspect_page(
            portal_page(PORTAL_FIXTURES["rep-portal-v1-never-ready"]),
            ready_selector=READY,
            config=InspectorConfig(timeout_ms=1500),
            observer=seen.append,
        )
    assert exc.value.reason == "timeout"
    assert len(seen) == 1 and seen[0].is_connected() is False
    client = TestClient(
        create_app(Settings(_env_file=None, answer_store_backend="memory", auth_mode="fixture"))
    )
    client.app.dependency_overrides[get_inspector_config] = lambda: InspectorConfig(timeout_ms=1500)  # type: ignore[attr-defined]
    r = client.post(
        "/api/automation/inspect-fixture", json={"fixture_id": "rep-portal-v1-never-ready"}
    )
    assert r.status_code == 504 and r.json()["details"]["reason"] == "timeout"
    assert r.json()["details"]["elapsed_ms"] < 5000


def test_export_with_inspection_carries_form_map(client: TestClient) -> None:
    r = client.post(
        "/api/automation/export-definition",
        json={
            "source": {"mode": "fixture", "fixture_id": "rep-portal-definition-v1"},
            "inspect_fixture_id": "rep-portal-v1",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["form_map"]["fingerprint"] == FORM_VERSIONS["rep-portal"][1]
    assert body["inspection"]["map_status"] == "valid"
    assert body["approval_status"] == "not_approved" and body["prefill_permitted"] is False
    qs_ids = {q["question_id"] for q in body["question_set"]["questions"]}
    assert {f["question_id"] for f in body["form_map"]["fields"]} <= qs_ids
