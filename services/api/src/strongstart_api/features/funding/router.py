"""Find Funding feature router (owner: B1). B1-DISC-001 rev 1.0.

Endpoint mapping (spec s7 labels -> actual routes under the existing /api/funding prefix):
- availability -> GET  /api/funding/availability       (no provider calls; no secrets)
- search       -> POST /api/funding/search             (identity required)
- captures     -> POST /api/funding/captures           (identity required)
- metadata     -> GET  /api/funding/captures/{capture_id}
- content      -> GET  /api/funding/captures/{capture_id}/artifacts/{artifact_id}/content
- library        -> GET  /api/funding/captures?cursor=&limit=  (DEV-B-BUNDLE-002 M2; bounded)
- POST /api/funding/discovery-jobs stays an explicit 501: durable discovery jobs are
  future work (no JobStore); search/capture are bounded request operations instead.

The identity dependency is resolved before any provider, store or file access.
"""

from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Query

from strongstart_contracts import Capability, ErrorCode
from strongstart_contracts.discovery import (
    CaptureCatalogPage,
    CaptureContent,
    CapturedDocument,
    CaptureIntegrityError,
    CaptureNotFoundError,
    CaptureRequest,
    FundingAvailability,
    FundingErrorReason,
    ProviderAvailability,
    SearchRequest,
    SearchResult,
)

from ...config import Settings, get_settings
from ...errors import ApiError, not_implemented
from ...identity import Identity, require_identity
from .deps import get_capture_provider, get_capture_store, get_resolver, get_search_provider
from .providers import CaptureProvider, SearchProvider
from .service import FundingError, load_seed, run_capture, run_search
from .store import LocalCaptureStore
from .url_policy import Resolver

FEATURE = "funding"
router = APIRouter(prefix="/api/funding", tags=["funding"])

STATUS_BY_REASON: dict[FundingErrorReason, tuple[int, ErrorCode]] = {
    FundingErrorReason.INVALID_INPUT: (422, ErrorCode.VALIDATION_FAILED),
    FundingErrorReason.PROVIDER_UNAVAILABLE: (503, ErrorCode.CAPABILITY_UNAVAILABLE),
    FundingErrorReason.STORE_UNAVAILABLE: (503, ErrorCode.CAPABILITY_UNAVAILABLE),
    FundingErrorReason.PROVIDER_ERROR: (502, ErrorCode.DEPENDENCY_UNAVAILABLE),
    FundingErrorReason.PROVIDER_AUTH_REJECTED: (502, ErrorCode.DEPENDENCY_UNAVAILABLE),
    FundingErrorReason.RATE_LIMITED: (429, ErrorCode.DEPENDENCY_UNAVAILABLE),
    FundingErrorReason.QUOTA_EXCEEDED: (429, ErrorCode.DEPENDENCY_UNAVAILABLE),
    FundingErrorReason.TIMEOUT: (504, ErrorCode.DEPENDENCY_UNAVAILABLE),
    FundingErrorReason.OUTCOME_UNKNOWN: (504, ErrorCode.DEPENDENCY_UNAVAILABLE),
    FundingErrorReason.UNSAFE_DESTINATION: (422, ErrorCode.FORBIDDEN),
    FundingErrorReason.UNSUPPORTED_CONTENT: (422, ErrorCode.VALIDATION_FAILED),
    FundingErrorReason.SOURCE_HTTP_ERROR: (422, ErrorCode.VALIDATION_FAILED),
    FundingErrorReason.EXTRACTION_EMPTY: (422, ErrorCode.VALIDATION_FAILED),
    FundingErrorReason.CAPTURE_NOT_FOUND: (404, ErrorCode.FORBIDDEN),
    FundingErrorReason.INTEGRITY_FAILURE: (500, ErrorCode.INTERNAL_ERROR),
}


def _api_error(exc: FundingError) -> ApiError:
    status, code = STATUS_BY_REASON[exc.reason]
    details = {
        "reason": exc.reason.value,
        **{k: v for k, v in exc.details.items() if v is not None},
    }
    return ApiError(status, code, exc.message, details)


# ---------------------------------------------------------------------- availability


def _provider_availability(settings: Settings) -> list[ProviderAvailability]:
    search_fixture = settings.funding_search_mode == "fixture"
    capture_fixture = settings.funding_capture_mode == "fixture"
    tavily = bool(settings.tavily_api_key and settings.tavily_api_key.get_secret_value())
    firecrawl = bool(settings.firecrawl_api_key and settings.firecrawl_api_key.get_secret_value())
    store_ok = settings.environment != "production"
    if search_fixture:
        search_status, search_detail = "fixture_only", "FIXTURE: synthetic search results."
    elif tavily:
        search_status = "available"
        search_detail = "Tavily adapter configured; not live-verified by this service."
    else:
        search_status = "unavailable"
        search_detail = (
            "STRONGSTART_TAVILY_API_KEY not set; search unavailable (no fixture fallback)."
        )
    if capture_fixture:
        capture_status, capture_detail = "fixture_only", "FIXTURE: registered synthetic pages only."
    elif firecrawl:
        capture_status = "available"
        capture_detail = "Firecrawl adapter configured; not live-verified by this service."
    else:
        capture_status = "unavailable"
        capture_detail = "STRONGSTART_FIRECRAWL_API_KEY not set; capture is unavailable."
    return [
        ProviderAvailability(
            operation="search",
            provider="fixture-search" if search_fixture else "tavily",
            mode="fixture" if search_fixture else "live",
            status=search_status,
            configured=search_fixture or tavily,
            detail=search_detail,
        ),
        ProviderAvailability(
            operation="capture",
            provider="fixture-capture" if capture_fixture else "firecrawl",
            mode="fixture" if capture_fixture else "live",
            status=capture_status,
            configured=capture_fixture or firecrawl,
            detail=capture_detail,
        ),
        ProviderAvailability(
            operation="capture_store",
            provider="local-capture-store",
            mode="development_only" if store_ok else "disabled",
            status="fixture_only" if store_ok else "unavailable",
            configured=store_ok,
            detail=(
                "Development-only local file store (persists across restarts in this "
                "checkout). Not a supported deployment store."
                if store_ok
                else "Disabled in production: no supported capture store is configured."
            ),
        ),
    ]


def capabilities_for(settings: Settings) -> list[Capability]:
    providers = _provider_availability(settings)
    statuses = {p.status for p in providers}
    if "unavailable" in statuses:
        status = "unavailable"
    elif "fixture_only" in statuses:
        status = "fixture_only"
    else:
        status = "available"
    detail = "; ".join(f"{p.operation}={p.status}" for p in providers)
    local = settings.environment != "production"
    dev = "fixture_only" if local else "unavailable"
    where = (
        "development-only local repository (not a supported deployment store)"
        if local
        else "disabled in production (no supported repository)"
    )
    return [
        Capability(feature=FEATURE, owner="B1", status=status, detail=detail),
        Capability(
            feature="funding.capture_library",
            owner="B1",
            status=dev,
            detail=f"Saved capture catalog with bounded listing/backfill; {where}.",
        ),
        Capability(
            feature="funding.reviewed_requirements",
            owner="B1",
            status=dev,
            detail="Funding cases with server-verified evidence anchors and explicit, "
            f"version-bound staff review; {where}. Not funder certification.",
        ),
        Capability(
            feature="funding.saved_searches",
            owner="B1",
            status=dev,
            detail="Saved public search profiles with staff-triggered reruns, comparisons and "
            "explicit single-source rechecks. No scheduling or notifications (no JobStore).",
        ),
        Capability(
            feature="funding.evaluations",
            owner="B1",
            status=dev,
            detail="Deterministic deadline/eligibility rules over reviewed requirements and "
            "staff scenario inputs; reliance is never confirmed (no verified A facts).",
        ),
    ]


CAPABILITIES: list[Capability] = [
    Capability(
        feature=FEATURE,
        owner="B1",
        status="unavailable",
        detail="Static default; runtime status comes from capabilities_for(settings).",
    ),
]


@router.get("/status", response_model=list[Capability])
def status(settings: Annotated[Settings, Depends(get_settings)]) -> list[Capability]:
    return capabilities_for(settings)


@router.get("/availability", response_model=FundingAvailability)
def availability(settings: Annotated[Settings, Depends(get_settings)]) -> FundingAvailability:
    try:
        identity = require_identity(settings)
        authenticated, is_fixture = True, identity.is_fixture
    except ApiError:
        authenticated, is_fixture = False, False
    return FundingAvailability(
        authenticated=authenticated,
        identity_is_fixture=is_fixture,
        environment=settings.environment,
        providers=_provider_availability(settings),
        limits={
            "max_results": settings.funding_max_results,
            "search_timeout_seconds": settings.funding_search_timeout_seconds,
            "capture_timeout_seconds": settings.funding_capture_timeout_seconds,
            "max_capture_bytes_per_representation": settings.funding_max_capture_bytes,
            "provider_requests_per_operation": 1,
            "automatic_retries": 0,
        },
        notes=[
            "Search and capture are separate, staff-initiated, bounded operations.",
            "No eligibility, deadline or cycle status is assessed in this slice.",
        ],
    )


# ------------------------------------------------------------------------ operations


@router.post("/search", response_model=SearchResult)
def search(
    identity: Identity,
    body: SearchRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    provider: Annotated[SearchProvider | None, Depends(get_search_provider)],
    capture_provider: Annotated[CaptureProvider | None, Depends(get_capture_provider)],
) -> SearchResult:
    try:
        return run_search(
            body,
            provider,
            max_results_limit=settings.funding_max_results,
            timeout_s=settings.funding_search_timeout_seconds,
            allowed_fields=list(settings.funding_query_fields),
            seed=load_seed(settings.funding_search_mode, settings.funding_source_seed_path),
            fixture_capture_check=capture_provider,
        )
    except FundingError as exc:
        raise _api_error(exc) from None


@router.post("/captures", response_model=CapturedDocument, status_code=201)
def create_capture(
    identity: Identity,
    body: CaptureRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    provider: Annotated[CaptureProvider | None, Depends(get_capture_provider)],
    store: Annotated[LocalCaptureStore | None, Depends(get_capture_store)],
    resolver: Annotated[Resolver, Depends(get_resolver)],
) -> CapturedDocument:
    try:
        return run_capture(
            body,
            identity.organization_id,
            provider,
            store,
            resolver,
            timeout_s=settings.funding_capture_timeout_seconds,
            max_bytes=settings.funding_max_capture_bytes,
            seed=load_seed(settings.funding_capture_mode, settings.funding_source_seed_path),
        )
    except FundingError as exc:
        raise _api_error(exc) from None


def _require_store(store: LocalCaptureStore | None) -> LocalCaptureStore:
    if store is None:
        raise _api_error(
            FundingError(FundingErrorReason.STORE_UNAVAILABLE, "no capture store is available")
        )
    return store


def _not_found() -> ApiError:
    return _api_error(
        FundingError(FundingErrorReason.CAPTURE_NOT_FOUND, "capture not found or not accessible")
    )


@router.get("/captures", response_model=CaptureCatalogPage)
def list_captures(
    identity: Identity,
    store: Annotated[LocalCaptureStore | None, Depends(get_capture_store)],
    cursor: Annotated[str | None, Query(pattern=r"^[0-9]{13}-cap-[0-9a-f]{32}$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CaptureCatalogPage:
    try:
        return _require_store(store).list_captures(identity.organization_id, cursor, limit)
    except CaptureNotFoundError:
        raise _not_found() from None


@router.get("/captures/{capture_id}", response_model=CapturedDocument)
def get_capture(
    identity: Identity,
    capture_id: str,
    store: Annotated[LocalCaptureStore | None, Depends(get_capture_store)],
) -> CapturedDocument:
    try:
        return _require_store(store).get_record(identity.organization_id, capture_id)
    except CaptureNotFoundError:
        raise _not_found() from None
    except CaptureIntegrityError:
        raise _api_error(
            FundingError(
                FundingErrorReason.INTEGRITY_FAILURE,
                "stored capture record failed verification; content withheld",
            )
        ) from None


@router.get("/captures/{capture_id}/artifacts/{artifact_id}/content", response_model=CaptureContent)
def get_capture_content(
    identity: Identity,
    capture_id: str,
    artifact_id: str,
    store: Annotated[LocalCaptureStore | None, Depends(get_capture_store)],
) -> CaptureContent:
    try:
        verified = _require_store(store).read_artifact(
            identity.organization_id, capture_id, artifact_id
        )
    except CaptureNotFoundError:
        raise _not_found() from None
    except CaptureIntegrityError:
        raise _api_error(
            FundingError(
                FundingErrorReason.INTEGRITY_FAILURE,
                "stored artifact failed integrity verification; content withheld",
            )
        ) from None
    return CaptureContent(
        capture_id=capture_id,
        artifact=verified.artifact,
        text=verified.content.decode("utf-8", errors="replace"),
    )


@router.post("/discovery-jobs", status_code=202, response_model=None)
def placeholder_operation(identity: Identity) -> NoReturn:
    """Durable discovery jobs are future work; this stays explicitly not implemented."""
    raise not_implemented(FEATURE, "discovery-jobs")


# DEV-B-BUNDLE-002 M3/M4: funding case routes under /api/funding/cases.
from .cases_router import router as _cases_router  # noqa: E402
from .monitoring_router import router as _monitoring_router  # noqa: E402

router.include_router(_cases_router)
# DEV-B-BUNDLE-002 M5: saved searches, manual reruns and source rechecks.
router.include_router(_monitoring_router)
