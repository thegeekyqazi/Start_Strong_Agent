"""Applications, review and skills feature router (owner: C; C1 spec s6).

C1 adds the fixture application workspace and a synchronous draft-proposal route
(deviation D1: no JobStore exists yet). Identity resolves before any source or model
access. Review and skills remain explicitly not implemented.
"""

from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Query

from strongstart_contracts import Capability, ErrorCode
from strongstart_contracts.answers import (
    AnswerPlan,
    ApplicationWorkspace,
    CheckReport,
    CheckRequest,
    DraftProposal,
    DraftRequest,
    PlanRequest,
)

from ...config import Settings, get_settings
from ...errors import ApiError, not_implemented
from ...identity import Identity
from .deps import (
    LOOKUP_ERRORS,
    get_answer_store,
    get_model_adapter,
    get_policy,
    get_workspace_source,
    lookup_error,
    model_error,
)
from .models.base import ModelAdapter, ModelError
from .review_router import review_router
from .rules.policy import WritingPolicy
from .service import check_answer, draft_answer, plan_application
from .workspace import (
    QuestionSetIntegrityError,
    QuestionSetNotFound,
    WorkspaceNotFound,
    WorkspaceSource,
    load_workspace,
)

__all__ = [
    "CAPABILITIES",
    "capabilities_for",
    "get_answer_store",
    "get_model_adapter",
    "get_policy",
    "get_workspace_source",
    "router",
]

FEATURE = "applications"
router = APIRouter(prefix="/api/applications", tags=["applications"])

_REVIEW_STATIC = Capability(
    feature="review",
    owner="C",
    status="unavailable",
    detail="Review needs an answer store (fixture mode only until the C3 migration is sequenced).",
)
_SKILLS = Capability(
    feature="skills",
    owner="C",
    status="not_implemented",
    detail="Practice-skill generation planned (C4).",
)

# Static fallback kept for features.FEATURE_CAPABILITIES (pre-hook consumers).
CAPABILITIES: list[Capability] = [
    Capability(
        feature="applications",
        owner="C",
        status="unavailable",
        detail="Workspace needs a configured question/evidence producer.",
    ),
    _REVIEW_STATIC,
    _SKILLS,
]


def _model_capability(settings: Settings) -> Capability:
    if settings.model_provider == "fake" and settings.environment == "production":
        return Capability(
            feature="applications.model",
            owner="C",
            status="unavailable",
            detail="Fake adapter selected but disabled in production; no fallback.",
        )
    if settings.model_provider == "fake":
        return Capability(
            feature="applications.model",
            owner="C",
            status="fixture_only",
            detail="Deterministic fake adapter: canned drafts with fact slots, not a model.",
        )
    configured = bool(settings.gemini_api_key and settings.gemini_api_key.get_secret_value())
    configured = configured and bool(settings.gemini_model)
    return Capability(
        feature="applications.model",
        owner="C",
        status="available" if configured else "unavailable",
        detail=(
            "Gemini adapter configured; live behaviour not verified by C1."
            if configured
            else "Gemini selected but key or model name is not configured; no fallback."
        ),
    )


def capabilities_for(settings: Settings) -> list[Capability]:
    workspace = Capability(
        feature="applications",
        owner="C",
        status="fixture_only" if settings.fixture_mode else "unavailable",
        detail=(
            "Fixture workspace over demo-bundle@1: plan, draft and deterministic checks "
            "(APP-01/02/03, POL-01/02/03) with a synthetic demo policy."
            if settings.fixture_mode
            else "Workspace needs a configured question/evidence producer."
        ),
    )
    review = Capability(
        feature="review",
        owner="C",
        status="fixture_only" if settings.fixture_mode else "unavailable",
        detail=(
            "Saved versions, exact-version approval, staleness, resolver and DOCX/audit export "
            "over an in-memory FIXTURE store (C3 migration pending Dev A)."
            if settings.fixture_mode
            else _REVIEW_STATIC.detail
        ),
    )
    return [workspace, _model_capability(settings), review, _SKILLS]


_lookup_error = lookup_error
_model_error = model_error
_LOOKUP_ERRORS = LOOKUP_ERRORS


@router.get("/status", response_model=list[Capability])
def status(settings: Annotated[Settings, Depends(get_settings)]) -> list[Capability]:
    return capabilities_for(settings)


@router.get("/workspace", response_model=ApplicationWorkspace)
def workspace(
    identity: Identity,
    source: Annotated[WorkspaceSource, Depends(get_workspace_source)],
    question_set_id: Annotated[
        str | None, Query(pattern=r"^[a-z0-9][a-z0-9._:-]{0,127}$", max_length=128)
    ] = None,
) -> ApplicationWorkspace:
    """Demo fixture questions by default; with ``question_set_id``, that exact Dev B saved
    question set read server-side (C2b). Errors are surfaced; there is no fallback."""
    try:
        return load_workspace(source, identity.organization_id, question_set_id)
    except (QuestionSetNotFound, QuestionSetIntegrityError) as exc:
        raise lookup_error(exc) from None
    except WorkspaceNotFound:
        raise ApiError(
            404, ErrorCode.VALIDATION_FAILED, "no workspace", {"reason": "unknown_workspace"}
        ) from None


@router.post("/questions/{question_id}/draft", response_model=DraftProposal)
async def draft(
    question_id: str,
    body: DraftRequest,
    identity: Identity,
    settings: Annotated[Settings, Depends(get_settings)],
    source: Annotated[WorkspaceSource, Depends(get_workspace_source)],
    adapter: Annotated[ModelAdapter, Depends(get_model_adapter)],
    policy: Annotated[WritingPolicy | None, Depends(get_policy)],
) -> DraftProposal:
    try:
        return await draft_answer(
            source=source,
            adapter=adapter,
            organization_id=identity.organization_id,
            question_id=question_id,
            request=body,
            timeout_seconds=settings.model_timeout_seconds,
            policy=policy,
        )
    except _LOOKUP_ERRORS as exc:
        raise _lookup_error(exc) from None
    except ModelError as exc:
        raise _model_error(exc) from None


@router.post("/questions/{question_id}/check", response_model=CheckReport)
def check(
    question_id: str,
    body: CheckRequest,
    identity: Identity,
    source: Annotated[WorkspaceSource, Depends(get_workspace_source)],
    policy: Annotated[WritingPolicy | None, Depends(get_policy)],
) -> CheckReport:
    """Deterministic findings for the exact submitted text. Stateless; no approval."""
    try:
        return check_answer(
            source=source,
            organization_id=identity.organization_id,
            question_id=question_id,
            request=body,
            policy=policy,
        )
    except _LOOKUP_ERRORS as exc:
        raise _lookup_error(exc) from None


@router.post("/plan", response_model=AnswerPlan)
async def plan(
    body: PlanRequest,
    identity: Identity,
    settings: Annotated[Settings, Depends(get_settings)],
    source: Annotated[WorkspaceSource, Depends(get_workspace_source)],
    adapter: Annotated[ModelAdapter, Depends(get_model_adapter)],
) -> AnswerPlan:
    try:
        return await plan_application(
            source=source,
            adapter=adapter,
            organization_id=identity.organization_id,
            request=body,
            timeout_seconds=settings.model_timeout_seconds,
        )
    except _LOOKUP_ERRORS as exc:
        raise _lookup_error(exc) from None
    except ModelError as exc:
        raise _model_error(exc) from None


@router.post("/draft-jobs", status_code=202, response_model=None)
def placeholder_operation(identity: Identity) -> NoReturn:
    """Durable draft jobs need a JobStore (engineering s14); still not implemented."""
    raise not_implemented(FEATURE, "draft-jobs")


router.include_router(review_router)
