"""C3 routes: saved versions, exact-version approval, notes, reviewer roles, export, audit.

Included by ``router.router`` under ``/api/applications``. Identity resolves before any
store, workspace or model access. Every write is gated in code (C3 spec s4).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from strongstart_contracts import CapabilityUnavailable, ErrorCode
from strongstart_contracts.answers import (
    AnswerHistory,
    AnswerVersion,
    AnswerVersionCreate,
    ApprovalDecisionRequest,
    ApprovalRecord,
    AuditEvent,
    ExportRequest,
    ExportResult,
    ReviewerProposal,
    ReviewerProposalRequest,
    ReviewNote,
    ReviewNoteCreate,
)

from ...config import Settings, get_settings
from ...errors import ApiError
from ...identity import Identity
from .approval import (
    ApprovalForbidden,
    Context,
    GateBlocked,
    SnapshotConflict,
    add_note,
    apply_changes,
    decide,
    history,
    save_version,
)
from .deps import (
    LOOKUP_ERRORS,
    get_answer_store,
    get_model_adapter,
    get_policy,
    get_workspace_source,
    lookup_error,
    model_error,
)
from .exporter import DOCX_MEDIA_TYPE, build_export
from .models.base import ModelAdapter, ModelError
from .resolver import StoreApprovedAnswerResolver
from .reviewers import propose
from .rules.policy import WritingPolicy
from .store import AnswerStore, ExportTooLarge, NotFoundInStore, StaleExpectation
from .workspace import WorkspaceSource, fixture_change_set

review_router = APIRouter()

# Optional Dev B question-set selection (C2b); same pattern as StableId.
QuestionSetQuery = Annotated[
    str | None, Query(pattern=r"^[a-z0-9][a-z0-9._:-]{0,127}$", max_length=128)
]

StoreDep = Annotated[AnswerStore, Depends(get_answer_store)]
SourceDep = Annotated[WorkspaceSource, Depends(get_workspace_source)]
PolicyDep = Annotated[WritingPolicy | None, Depends(get_policy)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _ctx(
    store: AnswerStore,
    source: WorkspaceSource,
    policy: WritingPolicy | None,
    settings: Settings,
    organization_id: str,
) -> Context:
    return Context(
        store=store,
        workspace_source=source,
        policy=policy,
        settings=settings,
        organization_id=organization_id,
    )


def get_c_approved_answer_resolver(
    store: StoreDep, source: SourceDep, policy: PolicyDep, settings: SettingsDep
) -> StoreApprovedAnswerResolver:
    """C's real ApprovedAnswerResolver (ports.py contract) for Dev B's prefill. Wiring it
    into the shared ``strongstart_api.ports.get_approved_answer_resolver`` provider is a
    shared-host change left for owner/B coordination (C3 handoff)."""
    return StoreApprovedAnswerResolver(
        lambda org: _ctx(store, source, policy, settings, org), store.is_fixture
    )


def _not_found() -> ApiError:
    return ApiError(404, ErrorCode.VALIDATION_FAILED, "not found", {"reason": "not_found"})


def _conflict(reason: str, **extra: object) -> ApiError:
    return ApiError(
        409, ErrorCode.VERSION_CONFLICT, "version or snapshot conflict", {"reason": reason, **extra}
    )


@review_router.post("/answers/versions", response_model=AnswerVersion, status_code=201)
def create_version(
    body: AnswerVersionCreate,
    identity: Identity,
    store: StoreDep,
    source: SourceDep,
    policy: PolicyDep,
    settings: SettingsDep,
) -> AnswerVersion:
    try:
        return save_version(
            _ctx(store, source, policy, settings, identity.organization_id), identity, body
        )
    except StaleExpectation as exc:
        raise _conflict(exc.reason, current_answer_version=exc.current) from None
    except LOOKUP_ERRORS as exc:
        raise lookup_error(exc) from None


@review_router.get("/answers/{question_id}", response_model=AnswerHistory)
def answer_history(
    question_id: str,
    identity: Identity,
    store: StoreDep,
    source: SourceDep,
    policy: PolicyDep,
    settings: SettingsDep,
    question_set_id: QuestionSetQuery = None,
) -> AnswerHistory:
    try:
        return history(
            _ctx(store, source, policy, settings, identity.organization_id),
            question_id,
            question_set_id,
        )
    except LOOKUP_ERRORS as exc:
        raise lookup_error(exc) from None


@review_router.post("/answers/decisions", response_model=ApprovalRecord)
def approval_decision(
    body: ApprovalDecisionRequest,
    identity: Identity,
    store: StoreDep,
    source: SourceDep,
    policy: PolicyDep,
    settings: SettingsDep,
) -> ApprovalRecord:
    try:
        return decide(
            _ctx(store, source, policy, settings, identity.organization_id), identity, body
        )
    except ApprovalForbidden:
        raise ApiError(
            403, ErrorCode.FORBIDDEN, "not authorized to approve", {"reason": "not_an_approver"}
        ) from None
    except NotFoundInStore:
        raise _not_found() from None
    except (SnapshotConflict, StaleExpectation) as exc:
        raise _conflict(exc.reason) from None
    except GateBlocked as exc:
        raise ApiError(
            422,
            ErrorCode.VALIDATION_FAILED,
            "approval gate blocked",
            {"reason": exc.reason, "findings": [f.model_dump(mode="json") for f in exc.findings]},
        ) from None
    except LOOKUP_ERRORS as exc:
        raise lookup_error(exc) from None


@review_router.post("/answers/notes", response_model=ReviewNote, status_code=201)
def review_note(
    body: ReviewNoteCreate,
    identity: Identity,
    store: StoreDep,
    source: SourceDep,
    policy: PolicyDep,
    settings: SettingsDep,
) -> ReviewNote:
    try:
        return add_note(
            _ctx(store, source, policy, settings, identity.organization_id), identity, body
        )
    except NotFoundInStore:
        raise _not_found() from None
    except StaleExpectation as exc:
        raise _conflict(exc.reason) from None


@review_router.post("/answers/reviews", response_model=ReviewerProposal, status_code=201)
async def reviewer_proposal(
    body: ReviewerProposalRequest,
    identity: Identity,
    store: StoreDep,
    source: SourceDep,
    policy: PolicyDep,
    settings: SettingsDep,
    adapter: Annotated[ModelAdapter, Depends(get_model_adapter)],
) -> ReviewerProposal:
    try:
        return await propose(
            _ctx(store, source, policy, settings, identity.organization_id),
            identity,
            adapter,
            body,
            settings.model_timeout_seconds,
        )
    except NotFoundInStore:
        raise _not_found() from None
    except StaleExpectation as exc:
        raise _conflict(exc.reason) from None
    except LOOKUP_ERRORS as exc:
        raise lookup_error(exc) from None
    except ModelError as exc:
        raise model_error(exc) from None


@review_router.post("/exports", response_model=ExportResult)
def create_export(
    body: ExportRequest,
    identity: Identity,
    store: StoreDep,
    source: SourceDep,
    policy: PolicyDep,
    settings: SettingsDep,
) -> ExportResult:
    try:
        return build_export(
            _ctx(store, source, policy, settings, identity.organization_id), identity, body
        )
    except StaleExpectation as exc:
        raise _conflict(exc.reason) from None
    except ExportTooLarge:
        raise ApiError(
            422,
            ErrorCode.VALIDATION_FAILED,
            "export exceeds engineering byte budget",
            {"reason": "export_size_limit"},
        ) from None
    except LOOKUP_ERRORS as exc:
        raise lookup_error(exc) from None


@review_router.get("/exports/{export_id}/docx")
def export_docx(export_id: str, identity: Identity, store: StoreDep) -> Response:
    try:
        export = store.get_export(identity.organization_id, export_id)
    except NotFoundInStore:
        raise _not_found() from None
    except StaleExpectation as exc:
        raise _conflict(exc.reason) from None
    return Response(
        export.docx,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{export_id}.docx"'},
    )


@review_router.get("/exports/{export_id}/audit")
def export_audit(export_id: str, identity: Identity, store: StoreDep) -> Response:
    try:
        export = store.get_export(identity.organization_id, export_id)
    except NotFoundInStore:
        raise _not_found() from None
    except StaleExpectation as exc:
        raise _conflict(exc.reason) from None
    return Response(
        export.audit,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{export_id}-audit.json"'},
    )


@review_router.get("/audit-events", response_model=list[AuditEvent])
def audit_events(identity: Identity, store: StoreDep) -> list[AuditEvent]:
    """Restricted trace access: identity required, organization-scoped (SEC-10)."""
    return store.audit(identity.organization_id)


@review_router.post("/fixture/change-sets/{change_set_id}/apply", response_model=list[str])
def apply_fixture_change_set(
    change_set_id: str,
    identity: Identity,
    store: StoreDep,
    source: SourceDep,
    policy: PolicyDep,
    settings: SettingsDep,
) -> list[str]:
    """FIXTURE ONLY: simulates A's ChangeSet publisher (A4, not built) so staleness can be
    demonstrated. Disabled outside fixture mode."""
    if not settings.fixture_mode:
        raise CapabilityUnavailable("ChangeSetPublisher", "fixture change sets need fixture mode")
    change_set = fixture_change_set(change_set_id)
    if change_set is None:
        raise _not_found()
    try:
        return apply_changes(
            _ctx(store, source, policy, settings, identity.organization_id), identity, change_set
        )
    except StaleExpectation as exc:
        raise _conflict(exc.reason) from None
