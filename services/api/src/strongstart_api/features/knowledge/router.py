"""Knowledge feature router (owner: A).

Registered in strongstart_api.features during INIT-001 so the owner's first task does
not need to edit the shared app entry point. Every operation is explicitly
unavailable until its feature spec is implemented; nothing here fabricates success.
"""

from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends

from strongstart_contracts import (
    Capability,
    ErrorCode,
    EvidenceBundle,
    KnowledgeAvailability,
    KnowledgeSnapshot,
)

from ...config import Settings, get_settings
from ...errors import ApiError, not_implemented
from ...identity import Identity, require_identity
from .deps import get_knowledge_repository
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
            detail="Source/fact reads implemented; ingestion and pack replacement remain planned.",
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
) -> EvidenceBundle:
    try:
        return _require_repository(repository).get_bundle(identity.organization_id, pack_version_id)
    except KnowledgeNotFoundError:
        raise ApiError(
            404,
            ErrorCode.FORBIDDEN,
            "evidence pack not found or not accessible",
            {"reason": "evidence_not_found"},
        ) from None
    except KnowledgeIntegrityError:
        raise _integrity_failure() from None


@router.post("/packs/import", status_code=202, response_model=None)
def placeholder_operation(identity: Identity) -> NoReturn:
    """Protected placeholder: denies without identity, else reports not_implemented."""
    raise not_implemented(FEATURE, "packs/import")
