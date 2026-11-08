"""Authorized A3 validation routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from strongstart_contracts import (
    Capability,
    ErrorCode,
    NumericValidationReport,
    NumericValidationRequest,
    RuleCapability,
    SourceValidationReport,
    SourceValidationRequest,
)

from ...config import Settings
from ...errors import ApiError
from ...identity import Identity
from .deps import (
    get_numeric_validation_service,
    get_source_validation_service,
    get_validation_repository,
)
from .numeric_rules import capabilities as numeric_capabilities
from .registry import capabilities
from .repository import (
    SourceValidationRepository,
    ValidationReceiptNotFoundError,
    ValidationSubjectNotFoundError,
)
from .service import NumericValidationService, SourceValidationService

router = APIRouter(prefix="/api/validation", tags=["validation"])
CAPABILITIES = [
    Capability(
        feature="validation.source",
        owner="A3",
        status="not_implemented",
        detail="Source validation requires configured PostgreSQL storage.",
    )
]


def capabilities_for(settings: Settings) -> list[Capability]:
    return [
        Capability(
            feature="validation.source",
            owner="A3",
            status="available" if settings.database_url else "unavailable",
            detail=(
                "SRC-01 through SRC-10 deterministic evaluation and immutable receipts."
                if settings.database_url
                else "PostgreSQL validation storage is not configured."
            ),
        )
    ]


def _unavailable() -> ApiError:
    return ApiError(
        503,
        ErrorCode.CAPABILITY_UNAVAILABLE,
        "validation storage is not configured",
    )


def _hidden() -> ApiError:
    return ApiError(
        404,
        ErrorCode.FORBIDDEN,
        "validation subject or receipt not found or not accessible",
        {"reason": "validation_object_not_found"},
    )


@router.get("/rules", response_model=list[RuleCapability])
def rules(identity: Identity) -> list[RuleCapability]:
    del identity
    return capabilities() + numeric_capabilities()


@router.post("/source", response_model=SourceValidationReport, status_code=201)
def validate_source(
    request: SourceValidationRequest,
    identity: Identity,
    service: Annotated[SourceValidationService | None, Depends(get_source_validation_service)],
) -> SourceValidationReport:
    if service is None:
        raise _unavailable()
    try:
        return service.evaluate(identity.organization_id, identity.actor_id, request)
    except ValidationSubjectNotFoundError:
        raise _hidden() from None


@router.post("/numeric", response_model=NumericValidationReport, status_code=201)
def validate_numeric(
    request: NumericValidationRequest,
    identity: Identity,
    service: Annotated[NumericValidationService | None, Depends(get_numeric_validation_service)],
) -> NumericValidationReport:
    if service is None:
        raise _unavailable()
    try:
        return service.evaluate(identity.organization_id, identity.actor_id, request)
    except ValidationSubjectNotFoundError:
        raise _hidden() from None


@router.get("/receipts/{evaluation_id}", response_model=SourceValidationReport)
def receipt(
    evaluation_id: str,
    identity: Identity,
    repository: Annotated[SourceValidationRepository | None, Depends(get_validation_repository)],
) -> SourceValidationReport:
    if repository is None:
        raise _unavailable()
    try:
        return repository.get_receipt(identity.organization_id, evaluation_id)
    except ValidationReceiptNotFoundError:
        raise _hidden() from None


@router.get("/numeric/receipts/{evaluation_id}", response_model=NumericValidationReport)
def numeric_receipt(
    evaluation_id: str,
    identity: Identity,
    repository: Annotated[SourceValidationRepository | None, Depends(get_validation_repository)],
) -> NumericValidationReport:
    if repository is None:
        raise _unavailable()
    try:
        return repository.get_numeric_receipt(identity.organization_id, evaluation_id)
    except ValidationReceiptNotFoundError:
        raise _hidden() from None
