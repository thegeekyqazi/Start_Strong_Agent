"""Application intake and browser automation feature router (owner: B2). B2-AUTO-001.

Routes (all under /api/automation):

- GET  /status              granular capability list (public, static)
- GET  /availability        capabilities + import modes + browser readiness (+ fixtures)
- POST /intake              import a fixture / structured JSON / saved HTML / capture ref
- POST /inspect-fixture     read-only Playwright inspection of a registered fixture portal
- POST /export-definition   server-derived versioned JSON handoff (not approved)
- GET  /fixtures/portal/{fixture_id}  view the fixture portal (sandboxed, fixture mode only)

The identity dependency runs before any body is read, any fixture/capture byte is
accessed or a browser is launched. No route accepts org_id/approved/authorization from
the client, and no route fills, uploads, submits or signs anything.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ValidationError

from strongstart_contracts import Capability, ErrorCode
from strongstart_contracts.automation_intake import (
    ApplicationIntakeResult,
    AutomationAvailability,
    AutomationHandoffExport,
    ExportDefinitionRequest,
    FormInspectionResult,
    ImportApplicationRequest,
    ImportModeInfo,
    InspectFixtureRequest,
)

from ...config import Settings, get_settings
from ...identity import FIXTURE_IDENTITY, Identity
from . import html_form, structured
from .capture import CaptureSource, UnconfiguredCaptureSource, load_fixture_capture_source
from .inspector import InspectorConfig
from .intake_errors import fixture_not_allowed, intake_error, too_large
from .registry import PORTAL_FIXTURES, fixture_entries, portal_page
from .service import (
    MAX_CAPTURE_BYTES,
    build_export,
    capture_fixture_entries,
    fixtures_enabled,
    require_fixtures,
    run_inspection,
    run_intake,
)

FEATURE = "automation"
router = APIRouter(prefix="/api/automation", tags=["automation"])
MAX_REQUEST_BYTES = 2 * 1024 * 1024

CAPABILITIES: list[Capability] = [
    Capability(
        feature="automation",
        owner="B2",
        status="fixture_only",
        detail=(
            "Intake (structured JSON, saved HTML, capture reference) and read-only inspection "
            "of the local representative fixture portal. Prefill/submission not available."
        ),
    ),
    Capability(
        feature="automation.intake",
        owner="B2",
        status="available",
        detail="Bounded structured-JSON and saved-HTML import; nonpersistent; not approved.",
    ),
    Capability(
        feature="automation.capture_intake",
        owner="B2",
        status="fixture_only",
        detail="Consumes the B1-B2 capture record through a B2 fixture producer; real B1 "
        "producer pending.",
    ),
    Capability(
        feature="automation.browser_inspection",
        owner="B2",
        status="fixture_only",
        detail="Read-only Playwright inspection of the registered local representative portal "
        "only; not arbitrary-site isolation.",
    ),
    Capability(
        feature="automation.pdf_parsing",
        owner="B2",
        status="not_implemented",
        detail="Original PDF/scan/prose parsing is not implemented.",
    ),
    Capability(
        feature="automation.approved_prefill",
        owner="B2",
        status="not_implemented",
        detail="Planned for B2-AUTO-002; needs C's ApprovedAnswerResolver (unavailable here).",
    ),
    Capability(
        feature="automation.final_submission",
        owner="B2",
        status="unavailable",
        detail="No submit/sign capability exists; staff control final submission.",
    ),
]

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_capture_source(settings: SettingsDep) -> CaptureSource:
    if fixtures_enabled(settings):
        return load_fixture_capture_source()
    return UnconfiguredCaptureSource()


def get_inspector_config() -> InspectorConfig:
    return InspectorConfig()


CaptureDep = Annotated[CaptureSource, Depends(get_capture_source)]
InspectorDep = Annotated[InspectorConfig, Depends(get_inspector_config)]

_browser_cache: tuple[float, tuple[Any, str]] | None = None


def _browser_status(settings: Settings) -> tuple[Any, str]:
    """Checks the installed Chromium executable without launching it (cached 60 s)."""
    global _browser_cache
    if not fixtures_enabled(settings):
        return "disabled", "Browser inspection is only enabled in local fixture mode."
    now = time.monotonic()
    if _browser_cache is not None and now - _browser_cache[0] < 60:
        return _browser_cache[1]
    result: tuple[Any, str]
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            path = p.chromium.executable_path
        result = (
            ("installed_not_launched", "Chromium is installed; each inspection launches it fresh.")
            if Path(path).exists()
            else ("unavailable", "Playwright Chromium is not installed (make browser-install).")
        )
    except Exception:  # any driver failure means unavailable
        result = ("unavailable", "Playwright is not available in this environment.")
    _browser_cache = (now, result)
    return result


@router.get("/status", response_model=list[Capability])
def status() -> list[Capability]:
    return CAPABILITIES


@router.get("/availability", response_model=AutomationAvailability)
def availability(settings: SettingsDep, capture: CaptureDep) -> AutomationAvailability:
    enabled = fixtures_enabled(settings)
    browser_status, browser_detail = _browser_status(settings)
    # The fixture catalogue is server-registered metadata only (no bytes, no paths).
    fixtures = (
        fixture_entries(capture_fixture_entries(capture, FIXTURE_IDENTITY.organization_id))
        if enabled
        else []
    )
    return AutomationAvailability(
        capabilities=CAPABILITIES,
        import_modes=[
            ImportModeInfo(
                mode="fixture",
                status="fixture_only" if enabled else "unavailable",
                max_bytes=html_form.MAX_HTML_BYTES,
                detail="Server-registered engineering-derived fixtures.",
            ),
            ImportModeInfo(
                mode="structured_json",
                status="available",
                max_bytes=structured.MAX_JSON_BYTES,
                detail="strongstart-application-definition v1 JSON (strict).",
            ),
            ImportModeInfo(
                mode="html",
                status="available",
                max_bytes=html_form.MAX_HTML_BYTES,
                detail="Saved HTML form; parsed statically, never executed.",
            ),
            ImportModeInfo(
                mode="capture",
                status="fixture_only" if capture.is_fixture else "unavailable",
                max_bytes=MAX_CAPTURE_BYTES,
                detail="Captured document via the B1-B2 capture port.",
            ),
        ],
        browser_status=browser_status,
        browser_detail=browser_detail,
        fixture_mode=settings.fixture_mode,
        fixtures=fixtures,
    )


async def _read_bounded_json(request: Request) -> Any:
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_REQUEST_BYTES:
        raise too_large(MAX_REQUEST_BYTES, "request body")
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_REQUEST_BYTES:
            raise too_large(MAX_REQUEST_BYTES, "request body")
        chunks.append(chunk)
    try:
        return structured.decode_strict_json(b"".join(chunks), max_depth=8)
    except Exception:
        raise intake_error(
            422, ErrorCode.VALIDATION_FAILED, "malformed_request", "request body is not valid JSON"
        ) from None


def _validated[M: BaseModel](model: type[M], body: Any) -> M:
    try:
        return model.model_validate(body)
    except ValidationError as exc:
        issues = [{"loc": list(e.get("loc", ())), "type": e.get("type")} for e in exc.errors()[:50]]
        raise intake_error(
            422,
            ErrorCode.VALIDATION_FAILED,
            "malformed_request",
            "request does not match the schema",
            issues=issues,
        ) from None


@router.post("/intake", response_model=ApplicationIntakeResult)
async def intake(
    request: Request, identity: Identity, settings: SettingsDep, capture: CaptureDep
) -> ApplicationIntakeResult:
    body = _validated(ImportApplicationRequest, await _read_bounded_json(request))
    return await run_in_threadpool(run_intake, body.source, identity, settings, capture)


@router.post("/inspect-fixture", response_model=FormInspectionResult)
def inspect_fixture(
    body: InspectFixtureRequest,
    identity: Identity,
    settings: SettingsDep,
    capture: CaptureDep,
    config: InspectorDep,
) -> FormInspectionResult:
    return run_inspection(
        body.fixture_id,
        identity,
        settings,
        config,
        capture,
        expected_form_version=body.expected_form_version,
        client_expected_fingerprint=body.expected_fingerprint,
    )


@router.post("/export-definition", response_model=AutomationHandoffExport)
async def export_definition(
    request: Request,
    identity: Identity,
    settings: SettingsDep,
    capture: CaptureDep,
    config: InspectorDep,
) -> AutomationHandoffExport:
    body = _validated(ExportDefinitionRequest, await _read_bounded_json(request))

    def work() -> AutomationHandoffExport:
        result = run_intake(body.source, identity, settings, capture)
        inspection = None
        if body.inspect_fixture_id is not None:
            inspection = run_inspection(
                body.inspect_fixture_id,
                identity,
                settings,
                config,
                capture,
                client_expected_fingerprint=body.expected_fingerprint,
            )
        return build_export(result, inspection)

    return await run_in_threadpool(work)


PORTAL_CSP = (
    "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; "
    "style-src 'unsafe-inline'; img-src 'none'; form-action 'none'; base-uri 'none'"
)


@router.get("/fixtures/portal/{fixture_id}", response_class=HTMLResponse)
def view_portal(fixture_id: str, identity: Identity, settings: SettingsDep) -> HTMLResponse:
    """Staff view of the representative portal. Sandboxed (opaque origin, no forms/network)."""
    require_fixtures(settings)
    portal = PORTAL_FIXTURES.get(fixture_id)
    if portal is None:
        raise fixture_not_allowed(f"'{fixture_id}' is not a registered portal fixture")
    return HTMLResponse(
        portal_page(portal),
        headers={
            "Content-Security-Policy": PORTAL_CSP,
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
        },
    )
