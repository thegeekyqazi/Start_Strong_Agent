"""AUTO2 real Chromium through B's API; approvals are an explicit TEST provider, not C3."""

from __future__ import annotations

import importlib
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from strongstart_api.features.automation.inspector import FixtureServer
from strongstart_api.features.automation.prefill_deps import PrefillBrowserConfig
from tests.automation.prefill_support import (
    Harness,
    approve,
    execute,
    fields,
    harness,
    key,
    plan,
    save_definition,
    sha,
)

prefill_browser = importlib.import_module("strongstart_api.features.automation.prefill_browser")
prefill_runner = importlib.import_module("strongstart_api.features.automation.prefill_runner")
pytestmark = pytest.mark.browser


@pytest.fixture
def h(tmp_path: Path) -> Harness:
    return harness(tmp_path)


@pytest.fixture
def resources(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Any]]:
    """Observe only this execution's actual sessions; never kill unrelated browsers."""
    sessions: list[Any] = []
    servers: list[FixtureServer] = []
    server_enter = FixtureServer.__enter__

    def entered(server: FixtureServer) -> FixtureServer:
        servers.append(server)
        return server_enter(server)

    monkeypatch.setattr(FixtureServer, "__enter__", entered)
    original = prefill_browser._session

    @contextmanager
    def tracked(*args: Any, **kwargs: Any) -> Iterator[Any]:
        with original(*args, **kwargs) as session:
            sessions.append(session)
            yield session

    monkeypatch.setattr(prefill_browser, "_session", tracked)
    yield sessions
    for server in servers:
        assert not server._thread.is_alive()
        assert server._server.socket.fileno() == -1
    for s in sessions:
        assert not s.browser.is_connected()
        assert s.page.is_closed()
        assert not s.server._thread.is_alive()
        assert s.server._server.socket.fileno() == -1


def prepare(h: Harness, portal: str = "rep-prefill-v1", **texts: str) -> dict[str, Any]:
    pub = save_definition(h.client)
    selections = [
        (f"pf-{name.replace('_', '-')}", approve(h, pub, f"pf-{name.replace('_', '-')}", text))
        for name, text in texts.items()
    ]
    r = plan(h, pub, selections, portal)
    assert r.status_code == 201, r.text
    assert r.json()["executable"], r.text
    return dict(r.json())


def run(h: Harness, p: dict[str, Any]) -> dict[str, Any]:
    r = execute(h, p)
    assert r.status_code == 201, r.text
    return dict(r.json()["run"]["run"])


def test_auto2_16_18_live_values_final_reread_and_idempotent_receipt(
    h: Harness, resources: list[Any]
) -> None:
    name = "  L'été 🦎 <img src=x onerror=alert(1)>  "
    summary = "  First line\r\nSecond line — café 🧑🏽‍💻\nLast line  "
    p = prepare(h, org_name=name, summary=summary)
    idem = key("browser-exec")
    r = execute(h, p, idem)
    assert r.status_code == 201, r.text
    body = r.json()
    receipt = body["run"]["run"]
    assert receipt["outcome"] == "selected_fields_verified"
    assert receipt["final_reread"] == "all_match" and receipt["browser_version"]
    got = fields(body)
    assert got["org-name-field"]["actual_value"] == name
    assert got["org-name-field"]["actual_sha256"] == sha(name)
    assert got["summary-field"]["actual_value"] == summary.replace("\r\n", "\n")
    assert got["summary-field"]["comparison"] == "b2-readback-textarea-crlf/1"
    for f in got.values():
        assert f["result"] == "match"
        assert f["compared_actual_sha256"] == f["compared_intended_sha256"]
    assert receipt["activity"]["operations_performed"] == [
        "fill:org-name-field",
        "fill:summary-field",
    ]
    assert receipt["submitted"] is False
    assert len(resources) == 1
    replay = execute(h, p, idem)
    assert replay.status_code == 200 and replay.json()["replayed"]
    assert replay.json()["run"]["run"] == receipt
    assert len(resources) == 1


@pytest.mark.parametrize(
    "portal,field,state",
    [
        ("rep-prefill-v1-truncating", "org-name-field", "mismatch"),
        ("rep-prefill-v1-replacing", "summary-field", "mismatch"),
        ("rep-prefill-v1-overwrite", "org-name-field", "overwritten_after_verify"),
    ],
)
def test_auto2_17_scripts_truncate_replace_and_overwrite(
    h: Harness, resources: list[Any], portal: str, field: str, state: str
) -> None:
    p = prepare(h, portal, org_name="Approved organization name", summary="Exact approved summary")
    if "overwrite" in portal:
        pub = save_definition(h.client)
        a = approve(h, pub, "pf-org-name", "Approved organization name")
        b = approve(h, pub, "pf-service-area", "region", typed=["region"])
        p = plan(h, pub, [("pf-org-name", a), ("pf-service-area", b)], portal).json()
    r = execute(h, p)
    assert r.status_code == 201, r.text
    receipt = r.json()["run"]["run"]
    f = fields(r.json())[field]
    assert receipt["outcome"] == "stopped_with_partial_entry"
    assert f["state"] == state and f["result"] == "mismatch"
    assert f["actual_sha256"] != f["intended_sha256"]
    assert len(receipt["activity"]["operations_performed"]) <= 2  # no repair or retry
    if state == "overwritten_after_verify":
        assert receipt["final_reread"] == "mismatch"
    if "truncating" in portal:
        assert fields(r.json())["summary-field"]["state"] == "not_attempted"


@pytest.mark.parametrize(
    "mutation", ["page", "missing", "duplicate", "type", "options", "required"]
)
def test_auto2_07_changed_execution_document_has_zero_writes(
    h: Harness, resources: list[Any], monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    p = prepare(h, org_name="Approved organization")
    if mutation == "page":
        read = prefill_runner.prefill_page
        monkeypatch.setattr(
            prefill_runner, "prefill_page", lambda portal: read(portal) + b"<!--changed-->"
        )
        expected = "page_hash_changed"
    else:
        # Initial bytes/hash are unchanged. Script mutates the live DOM after readiness.
        original = prefill_browser._session

        @contextmanager
        def changed(*args: Any, **kwargs: Any) -> Iterator[Any]:
            with original(*args, **kwargs) as s:
                changes = {
                    "missing": "document.querySelector('#org-name').remove()",
                    "duplicate": (
                        "document.querySelector('#org-name').after("
                        "document.querySelector('#org-name').cloneNode(true))"
                    ),
                    "type": "document.querySelector('#org-name').type = 'password'",
                    "options": (
                        "document.querySelector('#service-area').options[1].value = 'unregistered'"
                    ),
                    "required": (
                        "document.querySelector('#rep-prefill-v1').insertAdjacentHTML("
                        "'beforeend', '<input required name=unexpected>')"
                    ),
                }
                s.page.evaluate(changes[mutation])
                yield s

        monkeypatch.setattr(prefill_browser, "_session", changed)
        expected = "fingerprint_changed"
    receipt = run(h, p)
    assert receipt["outcome"] == "blocked_before_entry"
    assert receipt["outcome_reason"] == expected
    assert receipt["activity"]["operations_performed"] == []
    assert all(f["state"] == "not_attempted" for f in receipt["fields"])


def test_auto2_19_20_choices_reveal_and_remap_conditional_child(
    h: Harness, resources: list[Any]
) -> None:
    pub = save_definition(h.client)
    selections = []
    for original, text, typed in [
        ("pf-org-name", "Org", None),
        ("pf-summary", "Project", None),
        ("pf-service-area", "region", ["region"]),
        ("pf-languages", "en,fr", ["en", "fr"]),
        ("pf-has-partners", "yes", ["yes"]),
        ("pf-partnership", "Partner's exact approved role", None),
        ("pf-request-amount", "25000", None),
    ]:
        selections.append((original, approve(h, pub, original, text, typed=typed)))
    r = plan(h, pub, selections)
    assert r.status_code == 201, r.text
    receipt = run(h, r.json())
    assert receipt["outcome"] == "selected_fields_verified"
    assert len(receipt["fields"]) == 7 and receipt["final_reread"] == "all_match"
    assert all(f["state"] == "entered_verified" for f in receipt["fields"])
    assert {f["field_id"]: f["actual_value"] for f in receipt["fields"]}["partnership-field"] == (
        "Partner's exact approved role"
    )
    assert "check:has-partners-field" in receipt["activity"]["operations_performed"]


def test_auto2_20_unexpected_branch_structure_stops_child(
    h: Harness, resources: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original = prefill_browser._session

    @contextmanager
    def branch(*args: Any, **kwargs: Any) -> Iterator[Any]:
        with original(*args, **kwargs) as s:
            s.page.evaluate("""() => document.querySelector('#has-partners-yes')
              .addEventListener('change', () => document.querySelector('#summary').remove())""")
            yield s

    monkeypatch.setattr(prefill_browser, "_session", branch)
    pub = save_definition(h.client)
    a = approve(h, pub, "pf-has-partners", "yes", typed=["yes"])
    b = approve(h, pub, "pf-partnership", "Approved child")
    r = plan(h, pub, [("pf-has-partners", a), ("pf-partnership", b)])
    receipt = run(h, r.json())
    assert receipt["outcome"] == "stopped_with_partial_entry"
    assert receipt["outcome_reason"] == "structure_changed"
    assert receipt["fields"][1]["state"] == "blocked_before_write"


def test_auto2_17_invalid_number_rejection_without_repair(
    h: Harness, resources: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    # The planner normally holds invalid numeric strings; inject the browser's native
    # rejection at the operation boundary too, without altering planner authorization.
    from playwright.sync_api import Locator

    original = Locator.fill

    def invalid(locator: Locator, value: str, **kwargs: Any) -> None:
        original(locator, "not-a-number" if value == "25000" else value, **kwargs)

    monkeypatch.setattr(Locator, "fill", invalid)
    p = prepare(h, request_amount="25000")
    receipt = run(h, p)
    assert receipt["outcome"] == "stopped_with_partial_entry"
    assert receipt["fields"][0]["state"] == "write_failed"
    assert receipt["fields"][0]["reason"] == "operation_rejected_by_browser"
    assert len(receipt["activity"]["operations_performed"]) == 1


@pytest.fixture
def canary() -> Iterator[tuple[str, list[str]]]:
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
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", hits
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
        assert not thread.is_alive()


def test_auto2_23_24_hostile_input_cannot_submit_or_reach_canary(
    h: Harness,
    resources: list[Any],
    canary: tuple[str, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url, hits = canary
    read = prefill_runner.prefill_page

    # Replace hostile destinations with an actual listening service; approval/content
    # still comes solely from the explicit test reader. Exact page hash is plan-bound.
    def hostile(portal: Any) -> bytes:
        page = bytes(read(portal))
        for host in [
            b"https://exfil.example.invalid",
            b"https://beacon.example.invalid",
            b"http://10.0.0.1",
            b"https://popup.example.invalid",
            b"https://nav.example.invalid",
        ]:
            page = page.replace(host, url.encode())
        page = page.replace(b"wss://ws.example.invalid", url.replace("http", "ws").encode())
        return page

    from strongstart_api.features.automation import prefill_plan

    monkeypatch.setattr(prefill_plan, "prefill_page", hostile)
    monkeypatch.setattr(prefill_runner, "prefill_page", hostile)
    p = prepare(h, "rep-prefill-v1-hostile", org_name="Approved canary secret", summary="Later")
    receipt = run(h, p)
    assert receipt["outcome"] != "selected_fields_verified"
    activity = receipt["activity"]
    assert hits == []
    assert activity["fixture_server_mutation_hits"] == 0
    assert activity["mutation_requests_blocked"] >= 2
    assert activity["websockets_blocked"] >= 1
    # A denied initial popup navigation can be stopped before Chromium emits a Page
    # event; popup/download event handling is independently exercised below without a
    # competing top-level navigation.
    assert activity["navigations_blocked"] >= 1
    assert any("169.254.169.254" in e["target"] for e in activity["blocked_log"])
    assert all(
        op.startswith(("fill:", "check:", "select_option:"))
        for op in activity["operations_performed"]
    )
    assert receipt["fields"][1]["state"] == "not_attempted"
    assert receipt["submitted"] is False


def test_auto2_24_redirect_hop_never_reaches_canary(
    h: Harness,
    resources: list[Any],
    canary: tuple[str, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url, hits = canary
    original = prefill_browser._session

    @contextmanager
    def redirected(*args: Any, **kwargs: Any) -> Iterator[Any]:
        kwargs.update(extra_pages={"/redirect": b""}, redirects={"/redirect": url + "/hop"})
        with original(*args, **kwargs) as s:
            s.page.evaluate("fetch('/redirect').catch(() => {})")
            yield s

    monkeypatch.setattr(prefill_browser, "_session", redirected)
    p = prepare(h, org_name="Approved")
    receipt = run(h, p)
    assert hits == []
    assert any(
        e["reason"] == "redirect_or_oversize_refused" for e in receipt["activity"]["blocked_log"]
    )


def test_auto2_25_26_timeout_after_possible_write_is_unknown_and_closes(
    h: Harness, resources: list[Any]
) -> None:
    h.browser[0] = PrefillBrowserConfig(execution_timeout_ms=5000, operation_timeout_ms=500)
    p = prepare(h, "rep-prefill-v1-stalling", org_name="Approved", summary="Possible write")
    start = time.monotonic()
    receipt = run(h, p)
    assert time.monotonic() - start < 12
    assert receipt["outcome"] == "outcome_unknown"
    assert receipt["fields"][1]["state"] == "outcome_unknown"
    assert len(receipt["activity"]["operations_performed"]) == 2


def test_auto2_25_missing_browser_has_no_writes(h: Harness, resources: list[Any]) -> None:
    h.browser[0] = PrefillBrowserConfig(executable_path="/nonexistent/b2-only-chromium")
    p = prepare(h, org_name="Approved")
    response = execute(h, p)
    assert response.status_code == 503
    assert response.json()["details"]["reason"] == "browser_unavailable"
    run_id = response.json()["details"]["run_id"]
    stored = h.client.get(f"/api/automation/prefill-runs/{run_id}")
    assert stored.status_code == 200
    receipt = stored.json()["run"]
    assert receipt["outcome"] == "blocked_before_entry"
    assert receipt["outcome_reason"] == "browser_unavailable"
    assert receipt["activity"]["operations_performed"] == []
    assert resources == []


def test_auto2_27_32_ui_real_api_process_selected_fields_receipt(tmp_path: Path) -> None:
    """Actual web UI → HTTP API → restricted Chromium; explicit TEST approvals, not C3/G2."""
    import json

    from playwright.sync_api import sync_playwright

    from tests.browser.test_funding_e2e import FIXTURE_ENV, stack
    from tests.conftest import REPO_ROOT

    with (
        stack(
            tmp_path,
            app_factory="tests.browser.prefill_app:app_factory",
            **FIXTURE_ENV,
            STRONGSTART_DEV_B_STORE_DIR=str(tmp_path / "dev-b"),
            PYTHONPATH=str(REPO_ROOT),
        ) as base,
        sync_playwright() as p,
    ):
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            ids = json.loads((tmp_path / "prefill-test-ids.json").read_text())
            page.goto(base + "/#/automation")
            page.get_by_label("Exact saved question-set ID").fill(ids["question_set_id"])
            page.get_by_role("button", name="Load prefill questions").click()
            page.get_by_label("Approval ID for pf-org-name", exact=False).fill(ids["org"])
            page.get_by_label("Approval ID for pf-summary", exact=False).fill(ids["summary"])
            page.get_by_role("button", name="Prepare selected-field plan (no entry)").click()
            page.get_by_text("Exact approved plan preview", exact=True).wait_for()
            assert page.locator("pre").filter(has_text="Approved organization").text_content() == (
                "  Approved organization 🦎  "
            )
            page.get_by_role("button", name="Fill these approved fields").dblclick()
            page.get_by_role("heading", name="Selected fields verified").wait_for()
            assert (
                page.get_by_label("Read-back receipt")
                .get_by_text("Final reread: all_match.", exact=False)
                .is_visible()
            )
            assert page.get_by_role("button", name="Fill these approved fields").is_disabled()
            page.reload()
            assert page.get_by_label("Read-back receipt").count() == 0
            page.get_by_role("button", name="Check stored receipt").click()
            page.get_by_role("heading", name="Selected fields verified").wait_for()
            assert errors == []
        finally:
            browser.close()


def test_auto2_26_hook_failure_stops_and_closes_owned_resources(
    h: Harness, resources: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    from strongstart_api.features.automation.prefill_store import PrefillRepository

    original = PrefillRepository.record_step

    def fail_after_readback(self: Any, org: str, run_id: str, receipt: Any) -> None:
        if receipt.state == "entered_verified":
            raise RuntimeError("test-only post-write persistence failure")
        original(self, org, run_id, receipt)

    monkeypatch.setattr(PrefillRepository, "record_step", fail_after_readback)
    p = prepare(h, org_name="Possible write", summary="Must not write")
    receipt = run(h, p)
    assert receipt["outcome"] == "outcome_unknown"
    assert receipt["fields"][0]["state"] == "outcome_unknown"
    assert receipt["fields"][1]["state"] == "not_attempted"
    assert len(resources) == 1


def test_auto2_24_popup_and_download_events_are_closed_without_navigation_race(
    h: Harness, resources: list[Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original = prefill_browser._session

    @contextmanager
    def hostile_events(*args: Any, **kwargs: Any) -> Iterator[Any]:
        with original(*args, **kwargs) as s:
            s.page.evaluate("""() => {
              document.querySelector('#org-name').addEventListener('input', () => {
                window.open('about:blank');
                const a = document.createElement('a');
                a.href = 'data:text/plain,fixture-only'; a.download = 'fixture.txt';
                document.body.appendChild(a); a.click();
              });
            }""")
            yield s

    monkeypatch.setattr(prefill_browser, "_session", hostile_events)
    p = prepare(h, org_name="Approved fixture text", summary="Approved summary")
    receipt = run(h, p)
    activity = receipt["activity"]
    assert activity["popups_blocked"] >= 1
    assert activity["downloads_blocked"] >= 1
    assert activity["fixture_server_mutation_hits"] == 0
    assert any(e["reason"] == "popup_not_allowed" for e in activity["blocked_log"])
    assert any(e["reason"] == "download_not_allowed" for e in activity["blocked_log"])
