"""Knowledge feature router (owner: A).

Registered in strongstart_api.features during INIT-001 so the owner's first task does
not need to edit the shared app entry point. Every operation is explicitly
unavailable until its feature spec is implemented; nothing here fabricates success.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from strongstart_contracts import (
    ActivatePackRequest,
    ActivePackState,
    Capability,
    DependencyRegistrationRequest,
    DependencyTargetState,
    ErrorCode,
    EvidenceBundle,
    KnowledgeAvailability,
    KnowledgeRetrievalResult,
    KnowledgeSnapshot,
    PackActivationReport,
    PackManifest,
    PackManifestRequest,
    PdfSourceImportRequest,
    PdfSourceImportResult,
    TextSourceImportRequest,
    TextSourceImportResult,
)

from ...config import Settings, get_settings
from ...errors import ApiError
from ...identity import Identity, require_identity
from .deps import (
    get_knowledge_repository,
    get_pack_service,
    get_pdf_ingestion_service,
    get_text_ingestion_service,
)
from .ingestion import TextIngestionError, TextIngestionService
from .packs import PackConflictError, PackManifestError, PackNotFoundError, PackService
from .pdf_ingestion import PdfIngestionService
from .repository import (
    KnowledgeIntegrityError,
    KnowledgeNotFoundError,
    PostgresKnowledgeRepository,
)

FEATURE = "knowledge"
router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

CAPABILITIES: list[Capability] = [
    Capability(
        feature="knowledge",
        owner="A",
        status="not_implemented",
        detail="Packs, ingestion and retrieval are planned (Dev A specs).",
    ),
]


def capabilities_for(settings: Settings) -> list[Capability]:
    if not settings.database_url:
        return CAPABILITIES
    return [
        Capability(
            feature=FEATURE,
            owner="A1",
            status="fixture_only" if settings.fixture_mode else "available",
            detail=(
                "Source/fact reads, local text/PDF ingestion and lexical retrieval "
                "and transactional pack replacement/invalidation are implemented; "
                "OCR remains planned."
            ),
        )
    ]


@router.get("/status", response_model=list[Capability])
def status(settings: Annotated[Settings, Depends(get_settings)]) -> list[Capability]:
    return capabilities_for(settings)


@router.get("/availability", response_model=KnowledgeAvailability)
def availability(settings: Annotated[Settings, Depends(get_settings)]) -> KnowledgeAvailability:
    try:
        identity = require_identity(settings)
        authenticated, fixture = True, identity.is_fixture
    except ApiError:
        authenticated, fixture = False, False
    configured = bool(settings.database_url)
    return KnowledgeAvailability(
        authenticated=authenticated,
        identity_is_fixture=fixture,
        environment=settings.environment,
        storage="postgresql" if configured else "unconfigured",
        status=(
            "fixture_only"
            if configured and fixture
            else "available"
            if configured
            else "unavailable"
        ),
        detail=(
            "PostgreSQL knowledge storage is configured; readiness is reported separately."
            if configured
            else "STRONGSTART_DATABASE_URL is not configured."
        ),
    )


def _require_repository(
    repository: PostgresKnowledgeRepository | None,
) -> PostgresKnowledgeRepository:
    if repository is None:
        raise ApiError(
            503,
            ErrorCode.CAPABILITY_UNAVAILABLE,
            "knowledge storage is not configured",
        )
    return repository


def _integrity_failure() -> ApiError:
    return ApiError(
        500,
        ErrorCode.INTERNAL_ERROR,
        "stored source failed integrity verification; knowledge content was withheld",
        {"reason": "integrity_failure"},
    )


@router.post("/sources/import-text", response_model=TextSourceImportResult, status_code=201)
def import_text_source(
    request: TextSourceImportRequest,
    identity: Identity,
    service: Annotated[TextIngestionService | None, Depends(get_text_ingestion_service)],
) -> TextSourceImportResult:
    if service is None:
        raise ApiError(
            503,
            ErrorCode.CAPABILITY_UNAVAILABLE,
            "text ingestion storage is not configured for this environment",
        )
    try:
        return service.ingest(
            identity.organization_id,
            request.title,
            request.text,
            is_fixture=identity.is_fixture,
        )
    except TextIngestionError as exc:
        raise ApiError(
            422,
            ErrorCode.VALIDATION_FAILED,
            str(exc),
            {"reason": "invalid_text_source"},
        ) from None


@router.post("/sources/import-pdf", response_model=PdfSourceImportResult, status_code=201)
def import_pdf_source(
    request: PdfSourceImportRequest,
    identity: Identity,
    service: Annotated[PdfIngestionService | None, Depends(get_pdf_ingestion_service)],
) -> PdfSourceImportResult:
    if service is None:
        raise ApiError(
            503,
            ErrorCode.CAPABILITY_UNAVAILABLE,
            "PDF ingestion storage is not configured for this environment",
        )
    try:
        return service.ingest(
            identity.organization_id,
            request.title,
            request.content_base64,
            is_fixture=identity.is_fixture,
        )
    except TextIngestionError as exc:
        raise ApiError(
            422,
            ErrorCode.VALIDATION_FAILED,
            str(exc),
            {"reason": "invalid_pdf_source"},
        ) from None


@router.get("/retrieve", response_model=KnowledgeRetrievalResult)
def retrieve_passages(
    identity: Identity,
    repository: Annotated[PostgresKnowledgeRepository | None, Depends(get_knowledge_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
    query: Annotated[str, Query(min_length=2, max_length=200)],
    limit: Annotated[int | None, Query(ge=1, le=25)] = None,
) -> KnowledgeRetrievalResult:
    try:
        return _require_repository(repository).retrieve(
            identity.organization_id,
            query,
            limit=min(
                limit or settings.knowledge_retrieval_limit, settings.knowledge_retrieval_limit
            ),
        )
    except KnowledgeIntegrityError:
        raise _integrity_failure() from None


@router.get("/snapshot", response_model=KnowledgeSnapshot)
def snapshot(
    identity: Identity,
    repository: Annotated[PostgresKnowledgeRepository | None, Depends(get_knowledge_repository)],
) -> KnowledgeSnapshot:
    try:
        return _require_repository(repository).get_snapshot(
            identity.organization_id, is_fixture=identity.is_fixture
        )
    except KnowledgeIntegrityError:
        raise _integrity_failure() from None


@router.get("/evidence/{pack_version_id}", response_model=EvidenceBundle)
def evidence_bundle(
    identity: Identity,
    pack_version_id: str,
    repository: Annotated[PostgresKnowledgeRepository | None, Depends(get_knowledge_repository)],
    pack_service: Annotated[PackService | None, Depends(get_pack_service)],
) -> EvidenceBundle:
    try:
        if pack_service is not None:
            try:
                manifest = pack_service.get_manifest(
                    identity.organization_id, pack_version_id
                )
            except PackNotFoundError:
                manifest = None
            if manifest is not None:
                pack_service.require_active(
                    identity.organization_id,
                    manifest.request.application_context,
                    pack_version_id,
                )
        return _require_repository(repository).get_bundle(identity.organization_id, pack_version_id)
    except PackConflictError:
        raise _pack_conflict() from None
    except KnowledgeNotFoundError:
        raise ApiError(
            404,
            ErrorCode.FORBIDDEN,
            "evidence pack not found or not accessible",
            {"reason": "evidence_not_found"},
        ) from None
    except KnowledgeIntegrityError:
        raise _integrity_failure() from None


def _require_pack_service(service: PackService | None) -> PackService:
    if service is None:
        raise ApiError(503, ErrorCode.CAPABILITY_UNAVAILABLE, "pack storage is not configured")
    return service


def _pack_hidden() -> ApiError:
    return ApiError(
        404,
        ErrorCode.FORBIDDEN,
        "pack object not found or not accessible",
        {"reason": "pack_object_not_found"},
    )


def _pack_conflict() -> ApiError:
    return ApiError(
        409,
        ErrorCode.STALE_SNAPSHOT,
        "pack state changed; refresh the active snapshot",
        {"reason": "pack_snapshot_conflict"},
    )


@router.post("/packs/import", response_model=PackManifest, status_code=201)
@router.post("/packs/manifests", response_model=PackManifest, status_code=201)
def create_pack_manifest(
    request: PackManifestRequest,
    identity: Identity,
    service: Annotated[PackService | None, Depends(get_pack_service)],
) -> PackManifest:
    try:
        return _require_pack_service(service).create_manifest(
            identity.organization_id, identity.actor_id, request
        )
    except PackNotFoundError:
        raise _pack_hidden() from None
    except PackConflictError:
        raise ApiError(
            409,
            ErrorCode.VERSION_CONFLICT,
            "pack version or bundle identity already exists",
            {"reason": "immutable_pack_identity_conflict"},
        ) from None
    except PackManifestError as exc:
        raise ApiError(
            422,
            ErrorCode.VALIDATION_FAILED,
            "pack manifest failed validation",
            {"reason": exc.reason},
        ) from None


@router.get("/packs/manifests/{pack_version_id}", response_model=PackManifest)
def get_pack_manifest(
    pack_version_id: str,
    identity: Identity,
    service: Annotated[PackService | None, Depends(get_pack_service)],
) -> PackManifest:
    try:
        return _require_pack_service(service).get_manifest(
            identity.organization_id, pack_version_id
        )
    except PackNotFoundError:
        raise _pack_hidden() from None


@router.post(
    "/packs/contexts/{application_context}/activate/{pack_version_id}",
    response_model=PackActivationReport,
)
def activate_pack(
    application_context: str,
    pack_version_id: str,
    request: ActivatePackRequest,
    identity: Identity,
    service: Annotated[PackService | None, Depends(get_pack_service)],
) -> PackActivationReport:
    try:
        return _require_pack_service(service).activate(
            identity.organization_id,
            identity.actor_id,
            application_context,
            pack_version_id,
            request.expected_active_pack_version_id,
        )
    except PackNotFoundError:
        raise _pack_hidden() from None
    except PackConflictError:
        raise _pack_conflict() from None


@router.get("/packs/contexts/{application_context}/active", response_model=ActivePackState)
def active_pack(
    application_context: str,
    identity: Identity,
    service: Annotated[PackService | None, Depends(get_pack_service)],
) -> ActivePackState:
    try:
        return _require_pack_service(service).active_state(
            identity.organization_id, application_context
        )
    except PackNotFoundError:
        raise _pack_hidden() from None


@router.get("/packs/contexts/{application_context}/evidence", response_model=EvidenceBundle)
def active_evidence_bundle(
    application_context: str,
    identity: Identity,
    service: Annotated[PackService | None, Depends(get_pack_service)],
    repository: Annotated[PostgresKnowledgeRepository | None, Depends(get_knowledge_repository)],
) -> EvidenceBundle:
    try:
        state = _require_pack_service(service).active_state(
            identity.organization_id, application_context
        )
        return _require_repository(repository).get_bundle(
            identity.organization_id, state.pack_version_id
        )
    except (PackNotFoundError, KnowledgeNotFoundError):
        raise _pack_hidden() from None
    except KnowledgeIntegrityError:
        raise _integrity_failure() from None


@router.post("/dependencies/targets", response_model=DependencyTargetState)
def register_dependency_target(
    request: DependencyRegistrationRequest,
    identity: Identity,
    service: Annotated[PackService | None, Depends(get_pack_service)],
) -> DependencyTargetState:
    try:
        return _require_pack_service(service).register_target(identity.organization_id, request)
    except PackConflictError:
        raise _pack_conflict() from None
    except PackManifestError as exc:
        raise ApiError(
            422,
            ErrorCode.VALIDATION_FAILED,
            "dependency registration failed validation",
            {"reason": exc.reason},
        ) from None


@router.get(
    "/dependencies/targets/{target_kind}/{target_id}",
    response_model=DependencyTargetState,
)
def dependency_target(
    target_kind: str,
    target_id: str,
    identity: Identity,
    service: Annotated[PackService | None, Depends(get_pack_service)],
) -> DependencyTargetState:
    try:
        return _require_pack_service(service).get_target(
            identity.organization_id, target_kind, target_id
        )
    except PackNotFoundError:
        raise _pack_hidden() from None
