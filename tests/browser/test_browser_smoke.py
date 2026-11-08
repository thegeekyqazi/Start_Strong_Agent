"""Browser is actually usable (AUT-03 boundary only): open local fixture, read value back.

This is readiness evidence, not approved prefill. No submit/sign action exists.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import pytest

from tests.conftest import REPO_ROOT

pytestmark = pytest.mark.browser
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/browser"


@pytest.fixture
def fixture_server() -> Iterator[str]:
    handler = partial(SimpleHTTPRequestHandler, directory=str(FIXTURE_DIR))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def test_chromium_reads_fixture_values_back(fixture_server: str) -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(f"{fixture_server}/demo-form.html")
            assert "FIXTURE" in page.title()
            assert page.input_value("#mission") == "FIXTURE preset mission value"
            # maxlength truncation is observable on read-back, never silently accepted.
            page.fill("#pending", "0123456789ABC")
            assert page.input_value("#pending") == "0123456789"
            print(f"chromium version: {browser.version}")
        finally:
            browser.close()
