"""Applications, review and skills feature router (owner: C; C1 spec s6).

C1 adds the fixture application workspace and a synchronous draft-proposal route
(deviation D1: no JobStore exists yet). Identity resolves before any source or model
access. Review and skills remain explicitly not implemented.
"""

from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends

from strongstart_contracts import Capability, CapabilityUnavailable, ErrorCode
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
from .models.base import (
    DataClassNotPermitted,
    ModelAdapter,
    ModelError,
    ModelOutputRejected,
    ModelTimeout,
    ModelTransportError,
    StructuredTask,
)
from .models.fake import FakeAdapter
from .models.gemini import GeminiAdapter
from .rules.policy import WritingPolicy, fixture_policy
from .service import (
    EvidenceBundleNotFound,
    QuestionNotFound,
    QuestionVersionConflict,
    check_answer,
    draft_answer,
    plan_application,
)
from .workspace import (
    FixtureWorkspaceSource,
    UnconfiguredWorkspaceSource,
    WorkspaceNotFound,
    WorkspaceSource,
)

FEATURE = "applications"
router = APIRouter(prefix="/api/applications", tags=["applications"])

_REVIEW = Capability(
    feature="review",
    owner="C",
    status="not_implemented",
    detail="Review and exact-version approval planned (C3).",
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
    _REVIEW,
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
    return [workspace, _model_capability(settings), _REVIEW, _SKILLS]


def get_workspace_source(settings: Annotated[Settings, Depends(get_settings)]) -> WorkspaceSource:
    return FixtureWorkspaceSource() if settings.fixture_mode else UnconfiguredWorkspaceSource()


class _FixtureAdapterForbidden:
    """Production with model_provider=fake: explicitly unavailable, never a fixture draft."""

    is_fixture = False

    def capabilities(self) -> NoReturn:
        raise CapabilityUnavailable("ModelAdapter.fake", "fixture adapter disabled in production")

    async def complete(self, task: StructuredTask) -> NoReturn:
        raise CapabilityUnavailable("ModelAdapter.fake", "fixture adapter disabled in production")


def get_model_adapter(settings: Annotated[Settings, Depends(get_settings)]) -> ModelAdapter:
    if settings.model_provider == "gemini":
        return GeminiAdapter(
            settings.gemini_api_key, settings.gemini_model, settings.model_timeout_seconds
        )
    if settings.environment == "production":
        return _FixtureAdapterForbidden()
    return FakeAdapter()


def get_policy(settings: Annotated[Settings, Depends(get_settings)]) -> WritingPolicy | None:
    """Synthetic demo policy in fixture mode only; otherwise none (POL rules say so)."""
    return fixture_policy() if settings.fixture_mode else None


def _lookup_error(exc: Exception) -> ApiError:
    if isinstance(exc, EvidenceBundleNotFound):
        return ApiError(
            404,
            ErrorCode.VALIDATION_FAILED,
            "unknown evidence bundle",
            {"reason": "unknown_evidence_bundle"},
        )
    if isinstance(exc, QuestionVersionConflict):
        return ApiError(
            409,
            ErrorCode.VERSION_CONFLICT,
            "question version changed",
            {"current_question_version": exc.current},
        )
    return ApiError(
        404, ErrorCode.VALIDATION_FAILED, "unknown question", {"reason": "unknown_question"}
    )


_LOOKUP_ERRORS = (
    QuestionNotFound,
    WorkspaceNotFound,
    EvidenceBundleNotFound,
    QuestionVersionConflict,
)


def _model_error(exc: ModelError) -> ApiError:
    details: dict[str, object] = {"reason": exc.reason}
    if isinstance(exc, ModelOutputRejected):
        details["issues"] = exc.issues
        return ApiError(502, ErrorCode.VALIDATION_FAILED, "model output rejected", details)
    if isinstance(exc, ModelTimeout):
        return ApiError(504, ErrorCode.DEPENDENCY_UNAVAILABLE, "model call timed out", details)
    if isinstance(exc, DataClassNotPermitted):
        return ApiError(403, ErrorCode.FORBIDDEN, "data class not permitted for adapter", details)
    if isinstance(exc, ModelTransportError) and exc.reason == "rate_limited":
        return ApiError(429, ErrorCode.DEPENDENCY_UNAVAILABLE, "model provider busy", details)
    return ApiError(502, ErrorCode.DEPENDENCY_UNAVAILABLE, "model provider error", details)


@router.get("/status", response_model=list[Capability])
def status(settings: Annotated[Settings, Depends(get_settings)]) -> list[Capability]:
    return capabilities_for(settings)


@router.get("/workspace", response_model=ApplicationWorkspace)
def workspace(
    identity: Identity, source: Annotated[WorkspaceSource, Depends(get_workspace_source)]
) -> ApplicationWorkspace:
    try:
        return source.get(identity.organization_id)
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
