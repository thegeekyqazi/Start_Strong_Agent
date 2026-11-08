"""C4-SKL-001 routes under /api/skills (owner C). One router registration.

Identity resolves before any read or provider call. Other-organization and unknown IDs are
indistinguishable (404). Durable state uses the DATA-001 PostgreSQL engine; there is no memory
fallback. Preview responses are working-only and cannot approve, export or prefill.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.exc import IntegrityError, OperationalError

from strongstart_contracts import Capability, CapabilityUnavailable, ErrorCode
from strongstart_contracts.skills import (
    CompiledPracticePackage,
    PracticeActivateRequest,
    PracticeCandidate,
    PracticeGenerateRequest,
    PracticeOverview,
    PracticePreview,
    PracticePreviewRequest,
    PracticeRelease,
    PracticeReviewRequest,
    PracticeRevokeRequest,
    PracticeSourceCreate,
    PracticeSourceVersion,
)

from ...config import Settings, get_settings
from ...errors import ApiError
from ...identity import Identity
from ..applications.postgres_store import PostgresAnswerStore
from ..applications.public import (
    PREVIEW_LOOKUP_ERRORS,
    PracticePreviewPort,
    PreviewModelError,
    get_practice_preview_port,
    preview_lookup_error,
    preview_model_error,
    staff_can_decide,
)
from .demo import DEMO_CONTEXT, DEMO_SOURCES
from .repository import PracticeRepository, ScopeConflict
from .service import SkillError, SkillsService

router = APIRouter(prefix="/api/skills", tags=["skills"])

CAPABILITIES = [
    Capability(
        feature="skills",
        owner="C",
        status="unavailable",
        detail="Practice skills need fixture mode and the PostgreSQL answer store.",
    )
]


def capabilities_for(settings: Settings) -> list[Capability]:
    usable = settings.fixture_mode and settings.answer_store_backend == "postgres"
    return [
        Capability(
            feature="skills",
            owner="C",
            status="fixture_only" if usable else "unavailable",
            detail=(
                "Thin C4 practice slice: SYNTHETIC source authority, finite rules, scans, "
                "screening signal, exact-hash activation and a working-only draft preview."
                if usable
                else CAPABILITIES[0].detail
            ),
        )
    ]


def get_skills_service(
    request: Request,
    identity: Identity,
    settings: Annotated[Settings, Depends(get_settings)],
    port: Annotated[PracticePreviewPort, Depends(get_practice_preview_port)],
) -> SkillsService:
    store = getattr(request.app.state, "c3_answer_store", None)
    if not isinstance(store, PostgresAnswerStore):
        raise ApiError(
            503,
            ErrorCode.CAPABILITY_UNAVAILABLE,
            "practice skills need the durable PostgreSQL store",
            {"reason": "practice_store_unavailable"},
        )
    return SkillsService(
        repo=PracticeRepository(store.engine),
        port=port,
        context=DEMO_CONTEXT,
        org=identity.organization_id,
        actor=identity.actor_id,
        can_decide=staff_can_decide(identity, settings),
        fixture_mode=settings.fixture_mode,
    )


Service = Annotated[SkillsService, Depends(get_skills_service)]


def _map(exc: Exception) -> ApiError:
    if isinstance(exc, SkillError):
        status = exc.status
        code = {
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.VALIDATION_FAILED,
            409: ErrorCode.VERSION_CONFLICT,
        }.get(status, ErrorCode.VALIDATION_FAILED)
        return ApiError(status, code, exc.message, {"reason": exc.reason, **exc.details})
    if isinstance(exc, PREVIEW_LOOKUP_ERRORS):
        return preview_lookup_error(exc)
    if isinstance(exc, PreviewModelError):
        return preview_model_error(exc)
    if isinstance(exc, ScopeConflict):
        return ApiError(
            409, ErrorCode.VERSION_CONFLICT, "practice scope changed", {"reason": exc.reason}
        )
    if isinstance(exc, IntegrityError):
        return ApiError(
            409,
            ErrorCode.VERSION_CONFLICT,
            "write conflict; reload and retry",
            {"reason": "write_conflict"},
        )
    return ApiError(
        503,
        ErrorCode.DEPENDENCY_UNAVAILABLE,
        "practice store unavailable",
        {"reason": "practice_store_unavailable"},
    )


_HANDLED = (
    SkillError,
    ScopeConflict,
    IntegrityError,
    OperationalError,
    PreviewModelError,
    *PREVIEW_LOOKUP_ERRORS,
)


def _run[R](fn: Callable[[], R]) -> R:
    try:
        return fn()
    except CapabilityUnavailable:
        raise
    except _HANDLED as exc:
        raise _map(exc) from None


async def _arun[R](fn: Callable[[], Awaitable[R]]) -> R:
    try:
        return await fn()
    except CapabilityUnavailable:
        raise
    except _HANDLED as exc:
        raise _map(exc) from None


def _screening_live(svc: SkillsService) -> bool:
    try:
        return not svc.port.adapter.capabilities().is_fixture
    except CapabilityUnavailable:
        return False


@router.get("", response_model=PracticeOverview)
def overview(svc: Service) -> PracticeOverview:
    return _run(lambda: svc.overview(_screening_live(svc)))


@router.post("/sources", response_model=PracticeSourceVersion, status_code=201)
def create_source(body: PracticeSourceCreate, svc: Service) -> PracticeSourceVersion:
    return _run(
        lambda: svc.create_source(
            body.title,
            body.text,
            "administrator_authored",
            body.expected_current_source_version_id,
            check_cas=True,
        )
    )


@router.post("/fixture-sources/{key}", response_model=PracticeSourceVersion, status_code=201)
def create_fixture_source(key: str, svc: Service) -> PracticeSourceVersion:
    if not svc.fixture_mode or key not in DEMO_SOURCES:
        raise ApiError(
            404,
            ErrorCode.VALIDATION_FAILED,
            "unknown fixture source",
            {"reason": "unknown_fixture_source"},
        )
    title, text = DEMO_SOURCES[key]
    return _run(lambda: svc.create_source(title, text, "synthetic_demo", None, check_cas=False))


@router.post("/sources/{source_version_id}/authority", response_model=PracticeSourceVersion)
def approve_authority(source_version_id: str, svc: Service) -> PracticeSourceVersion:
    return _run(lambda: svc.approve_authority(source_version_id))


@router.post("/candidates", response_model=PracticeCandidate, status_code=201)
async def generate(body: PracticeGenerateRequest, svc: Service) -> PracticeCandidate:
    return await _arun(lambda: svc.generate(body.source_version_id))


@router.get("/candidates/{candidate_id}", response_model=PracticeCandidate)
def read_candidate(candidate_id: str, svc: Service) -> PracticeCandidate:
    return _run(lambda: svc.candidate(candidate_id))


@router.get("/candidates/{candidate_id}/package", response_model=CompiledPracticePackage)
def export_package(candidate_id: str, svc: Service) -> CompiledPracticePackage:
    return _run(lambda: svc.package_export(candidate_id))


@router.post("/candidates/{candidate_id}/screening", response_model=PracticeCandidate)
async def run_screening(candidate_id: str, svc: Service) -> PracticeCandidate:
    return await _arun(lambda: svc.run_screening(candidate_id))


@router.post("/candidates/{candidate_id}/review", response_model=PracticeCandidate)
def review(candidate_id: str, body: PracticeReviewRequest, svc: Service) -> PracticeCandidate:
    return _run(lambda: svc.review(candidate_id, body))


@router.post("/candidates/{candidate_id}/activate", response_model=PracticeRelease)
def activate(candidate_id: str, body: PracticeActivateRequest, svc: Service) -> PracticeRelease:
    return _run(lambda: svc.activate(candidate_id, body))


@router.post("/releases/revoke", response_model=PracticeRelease)
def revoke(body: PracticeRevokeRequest, svc: Service) -> PracticeRelease:
    return _run(lambda: svc.revoke(body.release_id, body.reason))


@router.post("/preview", response_model=PracticePreview)
async def preview(body: PracticePreviewRequest, svc: Service) -> PracticePreview:
    return await _arun(lambda: svc.preview(body))


__all__: list[Any] = ["CAPABILITIES", "capabilities_for", "router"]
