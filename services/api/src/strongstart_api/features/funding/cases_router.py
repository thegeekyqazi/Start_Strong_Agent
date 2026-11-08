"""Funding case routes (DEV-B-BUNDLE-002 M3/M4). Included by the funding router.

- POST /api/funding/cases                                   create (201; 200 replay)
- POST /api/funding/cases/{case_id}/revisions               new immutable version
- GET  /api/funding/cases                                   bounded list
- GET  /api/funding/cases/{case_id}                         current envelope
- GET  /api/funding/cases/{case_id}/versions/{version}      exact envelope
- POST /api/funding/cases/{case_id}/versions/{version}/review   "Review these requirements"
- POST /api/funding/cases/{case_id}/evaluations             deterministic report (saved)
- GET  /api/funding/cases/{case_id}/evaluations             history with staleness

Identity is resolved before any body is read or any store is touched.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request, Response

from strongstart_contracts import ErrorCode
from strongstart_contracts.funding_review import (
    MAX_ANCHORS,
    MAX_CAPTURE_LINKS,
    MAX_REQUIREMENTS,
    EvaluateCommand,
    EvaluationList,
    EvaluationReport,
    FundingCaseCommand,
    FundingCaseEnvelope,
    FundingCaseIntegrityError,
    FundingCaseList,
    FundingCaseNotFound,
    ReviewCommand,
)

from ...config import Settings, get_settings
from ...errors import ApiError
from ...identity import Identity
from ..dev_b_store import (
    HistoryLimit,
    IdempotencyReused,
    IntegrityFailure,
    NotFound,
    StoreBusy,
    StoreUnavailable,
    TooLarge,
    VersionConflict,
)
from .cases import CaseCommandError, FundingCaseRepository
from .public import build_funding_case_repository
from .strict_body import read_strict

router = APIRouter(prefix="/cases", tags=["funding"])  # mounted under /api/funding
CASE_ID = r"^case-[0-9a-f]{26}$"
COUNTS = {
    "requirements": MAX_REQUIREMENTS,
    "anchors": MAX_ANCHORS,
    "capture_links": MAX_CAPTURE_LINKS,
}


def get_case_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> FundingCaseRepository | None:
    return build_funding_case_repository(settings)


RepoDep = Annotated[FundingCaseRepository | None, Depends(get_case_repository)]
CaseIdPath = Annotated[str, Path()]
VersionPath = Annotated[int, Path(ge=1, le=20)]


def _err(status: int, reason: str, message: str, **details: Any) -> ApiError:
    code = {
        404: ErrorCode.FORBIDDEN,
        409: ErrorCode.VERSION_CONFLICT,
        503: ErrorCode.CAPABILITY_UNAVAILABLE,
    }.get(status, ErrorCode.VALIDATION_FAILED)
    return ApiError(status, code, message, {"reason": reason, **details})


def map_error(exc: Exception) -> ApiError:
    if isinstance(exc, ApiError):
        return exc
    if isinstance(exc, CaseCommandError):
        return _err(exc.status, exc.reason, exc.message, **exc.details)
    if isinstance(exc, FundingCaseNotFound | NotFound):
        return _err(404, "case_not_found", "funding case not found")
    if isinstance(exc, FundingCaseIntegrityError | IntegrityFailure):
        return _err(409, "integrity_failure", "stored case failed verification; content withheld")
    if isinstance(exc, VersionConflict):
        return _err(
            409,
            "version_conflict",
            "the case changed; reload and revise the current version",
            current_version=exc.current_version,
        )
    if isinstance(exc, IdempotencyReused):
        return _err(409, "idempotency_key_reused", "idempotency key reused for another command")
    if isinstance(exc, HistoryLimit):
        return _err(413, "history_limit", "version history limit reached")
    if isinstance(exc, TooLarge):
        return _err(413, "too_large", "record exceeds its size budget")
    if isinstance(exc, StoreBusy):
        return _err(503, "store_busy", "store is busy; retry later")
    if isinstance(exc, StoreUnavailable):
        return _err(503, exc.reason, "funding case store unavailable")
    if isinstance(exc, OSError):
        return _err(503, "store_write_failed", "the store could not complete the write")
    raise exc


def _repo(repo: FundingCaseRepository | None) -> FundingCaseRepository:
    if repo is None:
        raise _err(503, "store_unavailable", "no funding case repository in this environment")
    return repo


def _case_id(case_id: str) -> str:
    import re

    if not re.fullmatch(CASE_ID, case_id):
        raise _err(404, "case_not_found", "funding case not found")
    return case_id


@router.post("", response_model=FundingCaseEnvelope, status_code=201)
async def create_case(
    request: Request, response: Response, identity: Identity, repo: RepoDep
) -> FundingCaseEnvelope:
    store = _repo(repo)
    cmd = await read_strict(request, FundingCaseCommand, counts=COUNTS)
    if cmd.expected_version is not None:
        raise _err(422, "invalid_input", "use /revisions to revise an existing case")
    try:
        env, replayed = store.save(identity.organization_id, identity.actor_id, None, cmd)
    except Exception as exc:
        raise map_error(exc) from None
    if replayed:
        response.status_code = 200
    return env


@router.post("/{case_id}/revisions", response_model=FundingCaseEnvelope, status_code=201)
async def revise_case(
    case_id: CaseIdPath, request: Request, response: Response, identity: Identity, repo: RepoDep
) -> FundingCaseEnvelope:
    store = _repo(repo)
    cmd = await read_strict(request, FundingCaseCommand, counts=COUNTS)
    if cmd.expected_version is None:
        raise _err(422, "invalid_input", "a revision needs expected_version")
    try:
        env, replayed = store.save(
            identity.organization_id, identity.actor_id, _case_id(case_id), cmd
        )
    except Exception as exc:
        raise map_error(exc) from None
    if replayed:
        response.status_code = 200
    return env


@router.get("", response_model=FundingCaseList)
def list_cases(
    identity: Identity,
    repo: RepoDep,
    cursor: Annotated[str | None, Query(pattern=CASE_ID)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> FundingCaseList:
    try:
        return _repo(repo).list(identity.organization_id, cursor, limit)
    except Exception as exc:
        raise map_error(exc) from None


@router.get("/{case_id}", response_model=FundingCaseEnvelope)
def get_case(case_id: CaseIdPath, identity: Identity, repo: RepoDep) -> FundingCaseEnvelope:
    try:
        return _repo(repo).get_current(identity.organization_id, _case_id(case_id))
    except Exception as exc:
        raise map_error(exc) from None


@router.get("/{case_id}/versions/{version}", response_model=FundingCaseEnvelope)
def get_case_version(
    case_id: CaseIdPath, version: VersionPath, identity: Identity, repo: RepoDep
) -> FundingCaseEnvelope:
    try:
        return _repo(repo).get_version(identity.organization_id, _case_id(case_id), version)
    except Exception as exc:
        raise map_error(exc) from None


@router.post(
    "/{case_id}/versions/{version}/review", response_model=FundingCaseEnvelope, status_code=201
)
async def review_case(
    case_id: CaseIdPath,
    version: VersionPath,
    request: Request,
    response: Response,
    identity: Identity,
    repo: RepoDep,
) -> FundingCaseEnvelope:
    store = _repo(repo)
    cmd = await read_strict(request, ReviewCommand)
    try:
        env, replayed = store.review(
            identity.organization_id, identity.actor_id, _case_id(case_id), version, cmd
        )
    except Exception as exc:
        raise map_error(exc) from None
    if replayed:
        response.status_code = 200
    return env


@router.post("/{case_id}/evaluations", response_model=EvaluationReport, status_code=201)
async def evaluate_case(
    case_id: CaseIdPath, request: Request, response: Response, identity: Identity, repo: RepoDep
) -> EvaluationReport:
    store = _repo(repo)
    cmd = await read_strict(request, EvaluateCommand)
    try:
        report, replayed = store.evaluate(
            identity.organization_id, identity.actor_id, _case_id(case_id), cmd
        )
    except Exception as exc:
        raise map_error(exc) from None
    if replayed:
        response.status_code = 200
    return report


@router.get("/{case_id}/evaluations", response_model=EvaluationList)
def list_evaluations(
    case_id: CaseIdPath,
    identity: Identity,
    repo: RepoDep,
    cursor: Annotated[str | None, Query(pattern=r"^eval-[0-9a-f]{26}$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EvaluationList:
    try:
        return _repo(repo).list_evaluations(
            identity.organization_id, _case_id(case_id), cursor, limit
        )
    except Exception as exc:
        raise map_error(exc) from None
