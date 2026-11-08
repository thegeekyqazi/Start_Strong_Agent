"""DISC-18: the Funding page drives the real API process (fixture/injected providers).

Starts uvicorn (real app, fixture identity, FIXTURE funding providers, temp store) and a
tiny same-origin server that serves the built web app (apps/web/dist) and proxies /api
and /health. Requires `npm run build` first (make browser-smoke does this).
Feature acceptance evidence only; not a numbered truth rule.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import REPO_ROOT

pytestmark = pytest.mark.browser
DIST = REPO_ROOT / "apps/web/dist"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def stack(
    tmp_path: Path, *, app_factory: str = "strongstart_api.app:app_factory", **env: str
) -> Iterator[str]:
    if not (DIST / "index.html").exists():
        pytest.fail("apps/web/dist is missing; run `npm run build` (make browser-smoke does)")
    api_port = _free_port()
    proc_env = {
        **{k: v for k, v in os.environ.items() if not k.startswith("STRONGSTART_")},
        "STRONGSTART_ENVIRONMENT": "local",
        "STRONGSTART_FUNDING_CAPTURE_STORE_DIR": str(tmp_path / "captures"),
        **env,
    }
    proc = subprocess.Popen(  # noqa: S603 - fixed argv
        [
            sys.executable,
            "-m",
            "uvicorn",
            "--factory",
            app_factory,
            "--host",
            "127.0.0.1",
            "--port",
            str(api_port),
        ],
        cwd=tmp_path,  # no repo .env is read; only the env above applies
        env=proc_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    api = f"http://127.0.0.1:{api_port}"

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a: Any, **kw: Any) -> None:
            super().__init__(*a, directory=str(DIST), **kw)

        def log_message(self, *args: object) -> None:
            return

        def _proxy(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else None
            req = urllib.request.Request(  # noqa: S310 - fixed local API origin
                api + self.path,
                data=body,
                method=self.command,
                headers={"Content-Type": self.headers.get("Content-Type", "application/json")},
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
                    status, data, ctype = r.status, r.read(), r.headers.get("Content-Type")
            except urllib.error.HTTPError as e:
                status, data, ctype = e.code, e.read(), e.headers.get("Content-Type")
            self.send_response(status)
            self.send_header("Content-Type", ctype or "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:
            if self.path.startswith(("/api/", "/health/")):
                return self._proxy()
            return super().do_GET()

        def do_POST(self) -> None:
            return self._proxy()

    web = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=web.serve_forever, daemon=True).start()
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen(api + "/health/live", timeout=1)  # noqa: S310
                break
            except OSError:
                time.sleep(0.1)
        else:
            pytest.fail("API did not start")
        yield f"http://127.0.0.1:{web.server_address[1]}"
    finally:
        web.shutdown()
        web.server_close()
        proc.terminate()
        proc.wait(timeout=10)


FIXTURE_ENV = {
    "STRONGSTART_ANSWER_STORE_BACKEND": "memory",
    "STRONGSTART_AUTH_MODE": "fixture",
    "STRONGSTART_FUNDING_SEARCH_MODE": "fixture",
    "STRONGSTART_FUNDING_CAPTURE_MODE": "fixture",
}


def test_funding_page_fixture_flow_against_real_api(tmp_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    with stack(tmp_path, **FIXTURE_ENV) as base, sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            external: list[str] = []
            page.on(
                "request",
                lambda r: (
                    external.append(r.url)
                    if not r.url.startswith(base) and not r.url.startswith("data:")
                    else None
                ),
            )
            page.goto(f"{base}/#/funding")
            page.get_by_text("LOCAL FIXTURE identity").wait_for()
            assert page.get_by_text("FIXTURE (synthetic)").count() >= 2
            page.get_by_label("Geography (optional)", exact=True).fill("Demo Region")
            page.get_by_role("button", name="Search", exact=True).click()
            page.get_by_text(
                "FIXTURE Demo Funder - Community Grants Program", exact=True
            ).wait_for()
            assert page.get_by_text("Eligibility: unassessed").count() == 3
            assert page.get_by_text("Duplicates collapsed: 1").is_visible()
            page.get_by_role("button", name="Capture this page").first.click()
            page.get_by_text("Coverage: complete").wait_for()
            assert page.get_by_text("provider_html, provider_raw_html").is_visible()
            page.get_by_role("button", name="Show provider_raw_html as text").click()
            pre = page.get_by_test_id("capture-content")
            pre.wait_for()
            assert "<script>window.__fixtureScriptRan" in pre.inner_text()
            assert page.evaluate("() => window.__fixtureScriptRan === undefined")
            assert page.locator("main script, main img").count() == 0
            # Unsafe manual destination and empty extraction are distinct states.
            page.get_by_label("Public http(s) URL").fill("http://169.254.169.254/latest/")
            page.get_by_role("button", name="Capture", exact=True).click()
            page.get_by_text("Destination denied").wait_for()
            page.get_by_label("Public http(s) URL").fill("https://demo-funder.example/empty")
            page.get_by_role("button", name="Capture", exact=True).click()
            page.get_by_text("Empty extraction").wait_for()
            assert external == [], external  # no tracker/remote resource was fetched
        finally:
            browser.close()


def test_funding_page_live_mode_without_keys(tmp_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    with stack(tmp_path, STRONGSTART_AUTH_MODE="fixture") as base, sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(f"{base}/#/funding")
            page.get_by_text("STRONGSTART_TAVILY_API_KEY not set", exact=False).wait_for()
            assert page.get_by_text("Mode: live").count() >= 2
            page.get_by_role("button", name="Search", exact=True).click()
            page.get_by_text("Provider unavailable (missing credentials)", exact=False).wait_for()
            assert page.get_by_text("FIXTURE Demo Funder").count() == 0
        finally:
            browser.close()


def test_funding_page_without_identity(tmp_path: Path) -> None:
    from playwright.sync_api import sync_playwright

    with (
        stack(tmp_path, **{**FIXTURE_ENV, "STRONGSTART_AUTH_MODE": "none"}) as base,
        sync_playwright() as p,
    ):
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(f"{base}/#/funding")
            page.get_by_text("Not signed in: search and capture will be denied.").wait_for()
            page.get_by_role("button", name="Search", exact=True).click()
            page.get_by_role("alert").filter(has_text="Not signed in").wait_for()
        finally:
            browser.close()
