"""Approved prefill routes (B2-AUTO-002 s10), included by the automation router.

- POST /api/automation/prefill-plans                  server-built plan; no DOM writes
- GET  /api/automation/prefill-plans/{plan_id}        the saved plan plus availability
- POST /api/automation/prefill-plans/{plan_id}/execute  explicit "Fill these approved fields"
- GET  /api/automation/prefill-runs/{run_id}          stored progress/receipt, read-time labels

Identity runs before any body, store, approval or browser access. Missing and
other-organization IDs return the same 404. Requests never carry content, selectors, URLs,
organization or approval flags.
"""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.concurrency import run_in_threadpool

from strongstart_contracts import CapabilityUnavailable, ErrorCode
from strongstart_contracts.application_publication import (
    ApplicationDefinitionIntegrityError,
    ApplicationDefinitionNotFound,
)
from strongstart_contracts.automation_prefill import (
    ApprovedPrefillReader,
    AttachmentEvidenceReader,
    ExecutePrefillRequest,
    ExecutePrefillResult,
    PrefillDependencyCurrentness,
    PrefillPlan,
    PrefillPlanView,
    PrefillRunView,
    PreparePrefillPlanRequest,
)

from ...config import Settings, get_settings
from ...errors import ApiError
from ...identity import Identity
from ..dev_b_store.core import (
    IdempotencyReused,
    IntegrityFailure,
    NotFound,
    StoreBusy,
    StoreUnavailable,
    new_object_id,
)
from ..funding.public import build_funding_case_reader
from .intake_errors import fixture_not_allowed, intake_error
from .prefill_deps import (
    Clock,
    PrefillBrowserConfig,
    get_approved_prefill_reader,
    get_attachment_evidence_reader,
    get_prefill_browser_config,
    get_prefill_clock,
    get_prefill_currentness,
    get_runtime_epoch,
)
from .prefill_plan import PlanRejected, build_plan
from .prefill_runner import ExecutionDeps, GrantRefused, execute, view_of
from .prefill_store import AlreadyClaimed, PrefillRepository, run_id_for
from .public import build_application_definition_reader, build_definition_repository
from .registry import PREFILL_PORTALS
from .service import fixtures_enabled

prefill_router = APIRouter()  # mounted under the automation router (/api/automation)
PLAN_ID = re.compile(r"^pfp-[0-9a-f]{26}$")
RUN_ID = re.compile(r"^pfr-[0-9a-f]{26}$")

SettingsDep = Annotated[Settings, Depends(get_settings)]
ReaderDep = Annotated[ApprovedPrefillReader, Depends(get_approved_prefill_reader)]
AttachDep = Annotated[AttachmentEvidenceReader, Depends(get_attachment_evidence_reader)]
CurrentDep = Annotated[PrefillDependencyCurrentness | None, Depends(get_prefill_currentness)]
ClockDep = Annotated[Clock, Depends(get_prefill_clock)]
EpochDep = Annotated[str, Depends(get_runtime_epoch)]
BrowserDep = Annotated[PrefillBrowserConfig, Depends(get_prefill_browser_config)]


def get_prefill_repository(settings: SettingsDep) -> PrefillRepository | None:
    store = build_definition_repository(settings)
    return PrefillRepository(store.store) if store is not None else None


RepoDep = Annotated[PrefillRepository | None, Depends(get_prefill_repository)]


def _not_found() -> ApiError:
    return intake_error(404, ErrorCode.FORBIDDEN, "not_found", "not found")


def _require(settings: Settings, repo: PrefillRepository | None) -> PrefillRepository:
    if not fixtures_enabled(settings):
        raise fixture_not_allowed("approved prefill is only available for local fixture portals")
    if repo is None:
        raise intake_error(
            503,
            ErrorCode.CAPABILITY_UNAVAILABLE,
            "store_unavailable",
            "no prefill repository is configured in this environment",
        )
    return repo


def _store_error(exc: Exception) -> ApiError:
    if isinstance(exc, NotFound):
        return _not_found()
    if isinstance(exc, IntegrityFailure):
        return intake_error(
            409, ErrorCode.VERSION_CONFLICT, "integrity_failure", "stored record failed integrity"
        )
    if isinstance(exc, IdempotencyReused):
        return intake_error(
            409,
            ErrorCode.VERSION_CONFLICT,
            "idempotency_key_reused",
            "this idempotency key was already used for a different command",
        )
    if isinstance(exc, StoreBusy):
        return intake_error(503, ErrorCode.DEPENDENCY_UNAVAILABLE, "store_busy", "store busy")
    if isinstance(exc, StoreUnavailable):
        return intake_error(503, ErrorCode.CAPABILITY_UNAVAILABLE, exc.reason, "store unavailable")
    raise exc


def _reader_label(reader: ApprovedPrefillReader) -> str:
    return "c_reader" if getattr(reader, "is_c_reader", False) is True else "explicit_test_provider"


def _deps(
    settings: Settings,
    repo: PrefillRepository,
    reader: ApprovedPrefillReader,
    currentness: PrefillDependencyCurrentness | None,
    clock: Clock,
    epoch: str,
    config: PrefillBrowserConfig,
) -> ExecutionDeps:
    return ExecutionDeps(
        repo=repo,
        definitions=build_application_definition_reader(settings),
        cases=build_funding_case_reader(settings),
        reader=reader,
        currentness=currentness,
        clock=clock,
        runtime_epoch=lambda: epoch,
        config=config,
    )


@prefill_router.post("/prefill-plans", response_model=PrefillPlan, status_code=201)
async def prepare_plan(
    request: Request,
    identity: Identity,
    settings: SettingsDep,
    repo: RepoDep,
    reader: ReaderDep,
    attachments: AttachDep,
    currentness: CurrentDep,
    clock: ClockDep,
    epoch: EpochDep,
) -> PrefillPlan:
    from .router import _read_bounded_json, _validated

    store = _require(settings, repo)
    body = _validated(PreparePrefillPlanRequest, await _read_bounded_json(request))
    portal = PREFILL_PORTALS.get(body.portal_fixture_id)
    if portal is None:
        raise intake_error(
            422,
            ErrorCode.VALIDATION_FAILED,
            "portal_not_registered",
            "the portal is not a registered prefill fixture (arbitrary portals are unsupported)",
        )

    def work() -> PrefillPlan:
        definitions = build_application_definition_reader(settings)
        try:
            pub = definitions.get_version(identity.organization_id, body.question_set_id)
        except ApplicationDefinitionNotFound:
            raise _not_found() from None
        except ApplicationDefinitionIntegrityError:
            raise intake_error(
                409, ErrorCode.VERSION_CONFLICT, "integrity_failure", "definition withheld"
            ) from None
        try:
            plan = build_plan(
                plan_id=new_object_id("pfp"),
                pub=pub,
                portal=portal,
                selections=list(body.selections),
                reader=reader,
                attachment_reader=attachments,
                currentness=currentness,
                organization_id=identity.organization_id,
                actor_id=identity.actor_id,
                now=clock(),
                runtime_epoch=epoch,
                approval_reader_label=_reader_label(reader),
            )
        except PlanRejected as exc:
            raise intake_error(
                exc.status, ErrorCode.VALIDATION_FAILED, exc.reason, exc.message
            ) from None
        except CapabilityUnavailable:
            raise intake_error(
                503,
                ErrorCode.CAPABILITY_UNAVAILABLE,
                "approval_reader_unavailable",
                "no approved-content reader is configured; nothing falls back to seeded data",
            ) from None
        try:
            store.save_plan(identity.organization_id, plan)
        except Exception as exc:
            raise _store_error(exc) from None
        return plan

    return await run_in_threadpool(work)


@prefill_router.get("/prefill-plans/{plan_id}", response_model=PrefillPlanView)
def get_plan(
    plan_id: str,
    identity: Identity,
    settings: SettingsDep,
    repo: RepoDep,
    clock: ClockDep,
    epoch: EpochDep,
) -> PrefillPlanView:
    store = _require(settings, repo)
    if not PLAN_ID.fullmatch(plan_id):
        raise _not_found()
    try:
        plan = store.get_plan(identity.organization_id, plan_id)
        run = store.run_for_plan(identity.organization_id, plan_id)
    except Exception as exc:
        raise _store_error(exc) from None
    if run is not None:
        availability = "claimed"
    elif not plan.executable:
        availability = "empty"
    elif plan.runtime_epoch != epoch:
        availability = "runtime_epoch_changed"
    elif clock() > plan.expires_at:
        availability = "expired"
    else:
        availability = "executable"
    return PrefillPlanView(
        plan=plan,
        availability=availability,
        run_id=run.run_id if run else None,
    )


@prefill_router.post(
    "/prefill-plans/{plan_id}/execute", response_model=ExecutePrefillResult, status_code=201
)
async def execute_plan(
    plan_id: str,
    request: Request,
    response: Response,
    identity: Identity,
    settings: SettingsDep,
    repo: RepoDep,
    reader: ReaderDep,
    currentness: CurrentDep,
    clock: ClockDep,
    epoch: EpochDep,
    config: BrowserDep,
) -> ExecutePrefillResult:
    from .router import _read_bounded_json, _validated

    store = _require(settings, repo)
    if not PLAN_ID.fullmatch(plan_id):
        raise _not_found()
    body = _validated(ExecutePrefillRequest, await _read_bounded_json(request))
    deps = _deps(settings, store, reader, currentness, clock, epoch, config)

    def work() -> ExecutePrefillResult:
        try:
            plan = store.get_plan(identity.organization_id, plan_id)
            return execute(deps, plan, body, identity.actor_id)
        except GrantRefused as exc:
            raise intake_error(
                409, ErrorCode.VERSION_CONFLICT, exc.reason, exc.message, **exc.details
            ) from None
        except AlreadyClaimed as exc:
            raise intake_error(
                409,
                ErrorCode.VERSION_CONFLICT,
                "plan_already_executed",
                "this plan was already claimed by another execute command; prepare a new plan",
                run_id=exc.run_id,
            ) from None
        except Exception as exc:
            raise _store_error(exc) from None

    result = await run_in_threadpool(work)
    if result.replayed:
        response.status_code = 200
    return result


@prefill_router.get("/prefill-runs/{run_id}", response_model=PrefillRunView)
def get_run(
    run_id: str,
    identity: Identity,
    settings: SettingsDep,
    repo: RepoDep,
    reader: ReaderDep,
    clock: ClockDep,
    epoch: EpochDep,
    config: BrowserDep,
) -> PrefillRunView:
    store = _require(settings, repo)
    if not RUN_ID.fullmatch(run_id):
        raise _not_found()
    deps = _deps(settings, store, reader, None, clock, epoch, config)
    try:
        return view_of(deps, store.latest_run(identity.organization_id, run_id))
    except Exception as exc:
        raise _store_error(exc) from None


__all__ = ["prefill_router", "run_id_for"]
