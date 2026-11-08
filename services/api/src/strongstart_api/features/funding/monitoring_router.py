"""Saved searches and source rechecks (DEV-B-BUNDLE-002 M5). Mounted under /api/funding.

- POST /searches                                  save a public profile (201; 200 replay)
- POST /searches/{profile_id}/revisions           new profile version
- GET  /searches  |  GET /searches/{profile_id}   bounded list / current version
- POST /searches/{profile_id}/runs                "Run search now" (one provider request)
- GET  /searches/{profile_id}/runs                run history (failures included)
- GET  /searches/{profile_id}/runs/{run_id}/compare?base={run_id}
- POST /captures/{capture_id}/recheck             "Capture again and compare"
- GET  /captures/{capture_id}/observations        change observations for a capture

No scheduling, notifications or durable jobs. Identity is resolved first.
"""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from strongstart_contracts.funding_review import (
    ChangeObservation,
    ChangeObservationList,
    RecheckCommand,
    RunComparison,
    RunSearchCommand,
    SearchProfileCommand,
    SearchProfileList,
    SearchProfileVersion,
    SearchRunList,
    SearchRunRecord,
)

from ...config import Settings, get_settings
from ...identity import Identity
from ..dev_b_store.factory import local_store
from .cases_router import _err, map_error
from .deps import get_capture_provider, get_capture_store, get_resolver, get_search_provider
from .monitoring import MonitoringRepository
from .providers import CaptureProvider, SearchProvider
from .public import build_funding_case_repository
from .service import load_seed
from .store import LocalCaptureStore
from .strict_body import read_strict
from .url_policy import Resolver

router = APIRouter(tags=["funding"])
PROFILE_ID = re.compile(r"^prof-[0-9a-f]{26}$")
RUN_ID = r"^run-[0-9a-f]{26}$"
CAPTURE_ID = re.compile(r"^cap-[0-9a-f]{32}$")
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_monitoring_repository(settings: SettingsDep) -> MonitoringRepository | None:
    store, cases = local_store(settings), build_funding_case_repository(settings)
    if store is None or cases is None:
        return None
    return MonitoringRepository(store, cases)


RepoDep = Annotated[MonitoringRepository | None, Depends(get_monitoring_repository)]


def _repo(repo: MonitoringRepository | None) -> MonitoringRepository:
    if repo is None:
        raise _err(503, "store_unavailable", "no saved-research repository in this environment")
    return repo


def _profile(profile_id: str) -> str:
    if not PROFILE_ID.fullmatch(profile_id):
        raise _err(404, "profile_not_found", "saved search not found")
    return profile_id


def _not_found_as(reason: str, message: str, exc: Exception) -> Exception:
    from ..dev_b_store import NotFound

    return _err(404, reason, message) if isinstance(exc, NotFound) else map_error(exc)


@router.post("/searches", response_model=SearchProfileVersion, status_code=201)
async def create_profile(
    request: Request, response: Response, identity: Identity, repo: RepoDep, settings: SettingsDep
) -> SearchProfileVersion:
    store = _repo(repo)
    cmd = await read_strict(request, SearchProfileCommand)
    if cmd.expected_version is not None:
        raise _err(422, "invalid_input", "use /revisions to revise a saved search")
    try:
        prof, replayed = store.save_profile(
            identity.organization_id,
            identity.actor_id,
            None,
            cmd,
            list(settings.funding_query_fields),
        )
    except Exception as exc:
        raise map_error(exc) from None
    if replayed:
        response.status_code = 200
    return prof


@router.post(
    "/searches/{profile_id}/revisions", response_model=SearchProfileVersion, status_code=201
)
async def revise_profile(
    profile_id: str,
    request: Request,
    response: Response,
    identity: Identity,
    repo: RepoDep,
    settings: SettingsDep,
) -> SearchProfileVersion:
    store = _repo(repo)
    cmd = await read_strict(request, SearchProfileCommand)
    if cmd.expected_version is None:
        raise _err(422, "invalid_input", "a revision needs expected_version")
    try:
        prof, replayed = store.save_profile(
            identity.organization_id,
            identity.actor_id,
            _profile(profile_id),
            cmd,
            list(settings.funding_query_fields),
        )
    except Exception as exc:
        raise map_error(exc) from None
    if replayed:
        response.status_code = 200
    return prof


@router.get("/searches", response_model=SearchProfileList)
def list_profiles(
    identity: Identity,
    repo: RepoDep,
    cursor: Annotated[str | None, Query(pattern=r"^prof-[0-9a-f]{26}$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SearchProfileList:
    try:
        return _repo(repo).list_profiles(identity.organization_id, cursor, limit)
    except Exception as exc:
        raise map_error(exc) from None


@router.get("/searches/{profile_id}", response_model=SearchProfileVersion)
def get_profile(profile_id: str, identity: Identity, repo: RepoDep) -> SearchProfileVersion:
    try:
        return _repo(repo).get_profile(identity.organization_id, _profile(profile_id))
    except Exception as exc:
        raise _not_found_as("profile_not_found", "saved search not found", exc) from None


@router.post("/searches/{profile_id}/runs", response_model=SearchRunRecord, status_code=201)
async def run_profile(
    profile_id: str,
    request: Request,
    response: Response,
    identity: Identity,
    repo: RepoDep,
    settings: SettingsDep,
    provider: Annotated[SearchProvider | None, Depends(get_search_provider)],
    capture_provider: Annotated[CaptureProvider | None, Depends(get_capture_provider)],
) -> SearchRunRecord:
    store = _repo(repo)
    cmd = await read_strict(request, RunSearchCommand)
    try:
        run, replayed = store.run(
            identity.organization_id,
            identity.actor_id,
            _profile(profile_id),
            cmd,
            provider,
            max_results=settings.funding_max_results,
            timeout_s=settings.funding_search_timeout_seconds,
            allowed_fields=list(settings.funding_query_fields),
            seed=load_seed(settings.funding_search_mode, settings.funding_source_seed_path),
            capture_check=capture_provider,
        )
    except Exception as exc:
        raise _not_found_as("profile_not_found", "saved search not found", exc) from None
    if replayed:
        response.status_code = 200
    return run


@router.get("/searches/{profile_id}/runs", response_model=SearchRunList)
def list_runs(
    profile_id: str,
    identity: Identity,
    repo: RepoDep,
    cursor: Annotated[str | None, Query(pattern=RUN_ID)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SearchRunList:
    try:
        return _repo(repo).list_runs(identity.organization_id, _profile(profile_id), cursor, limit)
    except Exception as exc:
        raise _not_found_as("profile_not_found", "saved search not found", exc) from None


@router.get("/searches/{profile_id}/runs/{run_id}/compare", response_model=RunComparison)
def compare_runs(
    profile_id: str,
    run_id: str,
    identity: Identity,
    repo: RepoDep,
    base: Annotated[str, Query(pattern=RUN_ID)],
) -> RunComparison:
    if not re.fullmatch(RUN_ID, run_id):
        raise _err(404, "run_not_found", "search run not found")
    try:
        return _repo(repo).compare(identity.organization_id, _profile(profile_id), base, run_id)
    except Exception as exc:
        raise _not_found_as("run_not_found", "search run not found", exc) from None


@router.post("/captures/{capture_id}/recheck", response_model=ChangeObservation, status_code=201)
async def recheck_capture(
    capture_id: str,
    request: Request,
    response: Response,
    identity: Identity,
    repo: RepoDep,
    settings: SettingsDep,
    provider: Annotated[CaptureProvider | None, Depends(get_capture_provider)],
    capture_store: Annotated[LocalCaptureStore | None, Depends(get_capture_store)],
    resolver: Annotated[Resolver, Depends(get_resolver)],
) -> ChangeObservation:
    store = _repo(repo)
    cmd = await read_strict(request, RecheckCommand)
    if not CAPTURE_ID.fullmatch(capture_id):
        raise _err(404, "capture_not_found", "capture not found")
    try:
        obs, replayed = store.recheck(
            identity.organization_id,
            identity.actor_id,
            capture_id,
            cmd,
            provider=provider,
            capture_store=capture_store,
            resolver=resolver,
            timeout_s=settings.funding_capture_timeout_seconds,
            max_bytes=settings.funding_max_capture_bytes,
            seed=load_seed(settings.funding_capture_mode, settings.funding_source_seed_path),
        )
    except Exception as exc:
        raise map_error(exc) from None
    if replayed:
        response.status_code = 200
    return obs


@router.get("/captures/{capture_id}/observations", response_model=ChangeObservationList)
def list_observations(
    capture_id: str,
    identity: Identity,
    repo: RepoDep,
    cursor: Annotated[str | None, Query(pattern=r"^obs-[0-9a-f]{26}$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ChangeObservationList:
    if not CAPTURE_ID.fullmatch(capture_id):
        raise _err(404, "capture_not_found", "capture not found")
    try:
        return _repo(repo).list_observations(identity.organization_id, capture_id, cursor, limit)
    except Exception as exc:
        raise map_error(exc) from None
