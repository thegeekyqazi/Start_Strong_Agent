"""Read-only Playwright inspector for the registered local representative portal.

Scope (B2-AUTO-001 s6): registered-local-fixture, read-only inspection only. This is
not arbitrary-site isolation. Controls:

- an ephemeral, server-owned HTTP fixture server on 127.0.0.1 with a random port that
  serves only registered pages (GET) and denies every mutation method with 403;
- a fresh Chromium context: no storage state, cookies or credentials; service workers
  blocked; downloads refused; popups closed;
- ``context.route('**/*')``: only GET requests to the fixture origin's registered paths
  continue; everything else (other origins, loopback/private/metadata, non-GET) is
  aborted and logged; WebSockets are intercepted and never connected;
- the DOM is read by the fixed ``ENUMERATE_JS`` below (trusted application code). No
  imported or model-generated script is ever evaluated. No fill/click/upload/submit;
- finite time/field/text budgets; context, browser, Playwright and the fixture server
  are closed on every exit path (``finally``).

Request interception is one layer (Playwright documents its limits, e.g. service
workers); it is not network isolation for hostile third-party sites.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlsplit

from strongstart_contracts.automation_intake import NetworkLogEntry

PORTAL_PATH = "/portal"
MAX_LOG = 100
MAX_RESOURCE_BYTES = 2 * 1024 * 1024

ENUMERATE_JS = r"""
(limits) => {
  const clip = (s) => (s == null ? null : String(s).slice(0, limits.maxText));
  const text = (el) => (el ? clip((el.textContent || '').trim()) : null);
  const sel = 'input, textarea, select, button, [contenteditable], [role="textbox"],'
    + ' [role="combobox"], [role="listbox"], [role="slider"], [role="spinbutton"]';
  const all = Array.from(document.querySelectorAll(sel));
  const nodes = all.slice(0, limits.maxFields);
  const fields = nodes.map((el) => {
    const tag = el.tagName.toLowerCase();
    const formControl = ['input', 'textarea', 'select', 'button'].includes(tag);
    const labels = formControl && el.labels ? Array.from(el.labels).map(text) : [];
    const fs = el.closest('fieldset');
    const legend = fs ? fs.querySelector(':scope > legend') : null;
    const describedBy = (el.getAttribute('aria-describedby') || '').split(/\s+/)
      .filter(Boolean).slice(0, 10).map((id) => text(document.getElementById(id)))
      .filter((t) => t !== null);
    const groupFs = fs && fs.getAttribute('aria-describedby')
      ? fs.getAttribute('aria-describedby').split(/\s+/).filter(Boolean).slice(0, 10)
          .map((id) => text(document.getElementById(id))).filter((t) => t !== null)
      : [];
    const declared = {};
    for (const a of Array.from(el.attributes)) {
      if (a.name.startsWith('data-fixture-')) declared[a.name] = clip(a.value);
    }
    const cond = el.closest('[data-fixture-condition]');
    if (cond) {
      declared['data-fixture-condition'] = clip(cond.getAttribute('data-fixture-condition'));
    }
    if (fs && fs.hasAttribute('data-fixture-question-id')) {
      declared['data-fixture-group-question-id'] =
        clip(fs.getAttribute('data-fixture-question-id'));
    }
    const type = tag === 'input' ? (el.getAttribute('type') || 'text').toLowerCase()
      : tag === 'button' ? (el.getAttribute('type') || 'submit').toLowerCase() : null;
    const options = tag === 'select'
      ? Array.from(el.options).slice(0, limits.maxOptions).map((o) => ({
          value: clip(o.value),
          label: clip(o.label || o.textContent || ''),
          disabled: !!o.disabled,
        }))
      : [];
    const visible = typeof el.checkVisibility === 'function'
      ? el.checkVisibility()
      : !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
    const ml = el.getAttribute('maxlength');
    return {
      tag, type, id: el.id || null, name: el.getAttribute('name'), role: el.getAttribute('role'),
      contentEditable: !!el.isContentEditable,
      label: labels.length ? labels.join(' | ') : null, legend: text(legend),
      describedBy: describedBy.concat(groupFs),
      required: el.hasAttribute('required') || el.getAttribute('aria-required') === 'true',
      disabled: !!el.disabled || el.getAttribute('aria-disabled') === 'true',
      readonly: el.hasAttribute('readonly'),
      maxLength: ml !== null && /^\d+$/.test(ml) ? Number(ml) : null,
      min: el.getAttribute('min'), max: el.getAttribute('max'), step: el.getAttribute('step'),
      accept: el.getAttribute('accept'), multiple: el.hasAttribute('multiple'),
      optionValue: (type === 'radio' || type === 'checkbox')
        ? clip(el.getAttribute('value')) : null,
      options, visible, declared,
    };
  });
  return { fields, truncated: all.length > limits.maxFields };
}
"""


READY_JS = "(selector) => document.querySelector(selector) !== null"


class InspectionFailure(Exception):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class InspectorConfig:
    timeout_ms: int = 15_000
    max_fields: int = 300
    max_text_chars: int = 2_000
    max_options: int = 200
    executable_path: str | None = None  # tests point this at a missing binary


@dataclass
class ActivityLog:
    allowed: int = 0
    blocked: int = 0
    mutation_blocked: int = 0
    popups: int = 0
    downloads: int = 0
    navigations_blocked: int = 0
    websockets_blocked: int = 0
    entries: list[NetworkLogEntry] = field(default_factory=list)
    truncated: bool = False

    def block(self, method: str, url: str, resource_type: str, reason: str) -> None:
        self.blocked += 1
        if len(self.entries) >= MAX_LOG:
            self.truncated = True
            return
        self.entries.append(
            NetworkLogEntry(
                method=method[:16],
                target=sanitize_url(url),
                resource_type=resource_type[:32],
                decision="blocked",
                reason=reason,
            )
        )


def sanitize_url(url: str) -> str:
    try:
        parts = urlsplit(url)
    except ValueError:
        return "<unparseable>"
    if parts.scheme in ("http", "https", "ws", "wss"):
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
        return f"{parts.scheme}://{host}{port}{parts.path}"[:300]
    return f"{parts.scheme}:"[:40]


@dataclass
class RawInspection:
    fields: list[dict[str, Any]]
    truncated: bool
    activity: ActivityLog
    fixture_server_mutation_hits: int
    browser_version: str


class FixtureServer:
    """Ephemeral loopback server for registered fixture pages. Mutations are denied (403)."""

    def __init__(self, pages: dict[str, bytes], redirects: dict[str, str] | None = None) -> None:
        self.pages = dict(pages)
        self.redirects = dict(redirects or {})
        self.mutation_hits = 0
        self.get_hits = 0
        self._lock = threading.Lock()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                return

            def _path(self) -> str:
                return urlsplit(self.path).path

            def do_GET(self) -> None:
                with owner._lock:
                    owner.get_hits += 1
                path = self._path()
                if path in owner.redirects:
                    self.send_response(302)
                    self.send_header("Location", owner.redirects[path])
                    self.end_headers()
                    return
                body = owner.pages.get(path)
                if body is None:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _deny(self) -> None:
                with owner._lock:
                    owner.mutation_hits += 1
                msg = b"denied: the automation principal has no submit/sign/write permission"
                self.send_response(403)
                self.send_header("Content-Type", "text/plain")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)

            do_POST = do_PUT = do_PATCH = do_DELETE = _deny  # noqa: N815

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._server.daemon_threads = True
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def __enter__(self) -> FixtureServer:
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=5)


@contextmanager
def _deadline(timeout_ms: int) -> Iterator[Callable[[], float]]:
    end = time.monotonic() + timeout_ms / 1000

    def remaining() -> float:
        left = (end - time.monotonic()) * 1000
        if left <= 0:
            raise InspectionFailure("timeout", "inspection time budget exhausted")
        return left

    yield remaining


@dataclass
class RestrictedSession:
    """One live restricted fixture document (shared by read-only inspection and prefill)."""

    page: Any
    browser: Any
    log: ActivityLog
    server: FixtureServer
    remaining: Callable[[], float]
    playwright_error: type[Exception]
    playwright_timeout: type[Exception]


@contextmanager
def restricted_fixture_session(
    page_html: bytes,
    *,
    ready_selector: str,
    timeout_ms: int,
    executable_path: str | None = None,
    extra_pages: dict[str, bytes] | None = None,
    redirects: dict[str, str] | None = None,
    observer: Callable[[Any], None] | None = None,
) -> Iterator[RestrictedSession]:
    """Serve one registered page from an ephemeral loopback server, open it in a fresh
    restricted Chromium context, wait for the declared readiness and yield the live page.

    Context, browser, Playwright and the fixture server are closed on every exit path.
    """
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise InspectionFailure("browser_unavailable", "Playwright is not installed") from None

    pages = {PORTAL_PATH: page_html, **(extra_pages or {})}
    log = ActivityLog()
    with FixtureServer(pages, redirects) as server, _deadline(timeout_ms) as remaining:
        allowed_paths = set(pages)
        origin = server.origin

        def on_route(route: Any) -> None:
            req = route.request
            parts = urlsplit(req.url)
            same_origin = f"{parts.scheme}://{parts.netloc}" == origin
            is_nav = req.is_navigation_request()
            if same_origin and req.method == "GET" and parts.path in allowed_paths:
                # Fetch without following redirects: Playwright does not re-run route handlers
                # for redirect hops, so a 3xx must never be handed to the browser to follow.
                try:
                    resp = route.fetch(max_redirects=0, timeout=min(5_000.0, remaining()))
                except (PlaywrightError, InspectionFailure):
                    log.block(req.method, req.url, req.resource_type, "fixture_fetch_failed")
                    route.abort("failed")
                    return
                if 300 <= resp.status < 400 or len(resp.body()) > MAX_RESOURCE_BYTES:
                    log.block(
                        req.method, req.url, req.resource_type, "redirect_or_oversize_refused"
                    )
                    if is_nav:
                        log.navigations_blocked += 1
                        route.fulfill(status=204, body="")
                    else:
                        route.abort("blockedbyclient")
                    return
                log.allowed += 1
                route.fulfill(response=resp)
                return
            reason = "not_registered_fixture_resource"
            if req.method not in ("GET", "HEAD"):
                log.mutation_blocked += 1
                reason = "mutation_method_denied"
            elif not same_origin:
                reason = "origin_not_allowed"
            log.block(req.method, req.url, req.resource_type, reason)
            if is_nav:
                # A 204 response is not committed as a navigation: the fixture document stays
                # in place instead of being replaced by an error page. Nothing leaves the host.
                log.navigations_blocked += 1
                route.fulfill(status=204, body="")
                return
            route.abort("blockedbyclient")

        def on_websocket(ws: Any) -> None:
            # Never call connect_to_server(): a routed WebSocket that is not connected never
            # reaches the network. (Calling close() inside this sync handler deadlocks.)
            log.websockets_blocked += 1
            log.block("WS", ws.url, "websocket", "websocket_not_allowed")

        pw = sync_playwright().start()
        try:
            try:
                browser = pw.chromium.launch(
                    headless=True,
                    executable_path=executable_path,
                    timeout=remaining(),
                    args=["--disable-background-networking", "--no-first-run"],
                )
            except PlaywrightError:
                raise InspectionFailure(
                    "browser_unavailable", "Chromium could not be launched"
                ) from None
            if observer is not None:
                observer(browser)
            context = None
            try:
                context = browser.new_context(
                    service_workers="block",
                    accept_downloads=False,
                    java_script_enabled=True,
                    storage_state=None,
                    permissions=[],
                )
                context.route("**/*", on_route)
                context.route_web_socket("**/*", on_websocket)

                seen_popups: set[int] = set()

                def on_popup(p: Any) -> None:
                    if id(p) in seen_popups:
                        return
                    seen_popups.add(id(p))
                    log.popups += 1
                    log.block("GET", p.url or "about:blank", "popup", "popup_not_allowed")
                    try:
                        p.close()
                    except PlaywrightError:
                        pass

                page = context.new_page()
                context.on("page", on_popup)
                page.on("popup", on_popup)

                def on_download(d: Any) -> None:
                    log.downloads += 1
                    log.block("GET", d.url, "download", "download_not_allowed")
                    try:
                        d.cancel()
                    except PlaywrightError:
                        pass

                page.on("download", on_download)
                try:
                    # Observe the initial document commit, then the registered readiness
                    # predicate. A hostile script may start a denied navigation before the
                    # initial DOMContentLoaded waiter settles; that lifecycle event must not
                    # become our readiness authority or consume the whole time budget.
                    page.goto(origin + PORTAL_PATH, wait_until="commit", timeout=remaining())
                    # Poll the declared readiness condition with trusted code. (wait_for_selector
                    # would wait on a blocked, never-committed navigation started by the page.)
                    while not page.evaluate(READY_JS, ready_selector):
                        page.wait_for_timeout(min(50.0, remaining()))
                except PlaywrightTimeout:
                    raise InspectionFailure(
                        "timeout", "fixture readiness condition was not met within the budget"
                    ) from None
                except PlaywrightError:
                    raise InspectionFailure("timeout", "fixture page did not load") from None
                yield RestrictedSession(
                    page=page,
                    browser=browser,
                    log=log,
                    server=server,
                    remaining=remaining,
                    playwright_error=PlaywrightError,
                    playwright_timeout=PlaywrightTimeout,
                )
            finally:
                if context is not None:
                    try:
                        context.close()
                    except PlaywrightError:
                        pass
                try:
                    browser.close()
                except PlaywrightError:
                    pass
        finally:
            pw.stop()


def inspect_page(
    page_html: bytes,
    *,
    ready_selector: str,
    config: InspectorConfig,
    extra_pages: dict[str, bytes] | None = None,
    redirects: dict[str, str] | None = None,
    observer: Callable[[Any], None] | None = None,
) -> RawInspection:
    """Open the fixture page in a fresh restricted context and read its controls."""
    with restricted_fixture_session(
        page_html,
        ready_selector=ready_selector,
        timeout_ms=config.timeout_ms,
        executable_path=config.executable_path,
        extra_pages=extra_pages,
        redirects=redirects,
        observer=observer,
    ) as session:
        raw = session.page.evaluate(
            ENUMERATE_JS,
            {
                "maxFields": config.max_fields,
                "maxText": config.max_text_chars,
                "maxOptions": config.max_options,
            },
        )
        version = session.browser.version
    return RawInspection(
        fields=list(raw["fields"]),
        truncated=bool(raw["truncated"]),
        activity=session.log,
        fixture_server_mutation_hits=session.server.mutation_hits,
        browser_version=str(version),
    )
