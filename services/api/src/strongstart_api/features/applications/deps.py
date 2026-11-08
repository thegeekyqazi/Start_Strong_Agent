"""Dependency providers and error mapping shared by the applications routers (owner C).

``router.py`` re-exports these exact objects, so ``app.dependency_overrides`` keys stay the
same for tests and for other lanes.
"""

from __future__ import annotations

from typing import Annotated, NoReturn

from fastapi import Depends, Request

from strongstart_contracts import CapabilityUnavailable, ErrorCode

from ...config import Settings, get_settings
from ...errors import ApiError
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
from .service import EvidenceBundleNotFound, QuestionNotFound, QuestionVersionConflict
from .store import AnswerStore, InMemoryAnswerStore, UnconfiguredAnswerStore
from .workspace import (
    FixtureWorkspaceSource,
    UnconfiguredWorkspaceSource,
    WorkspaceNotFound,
    WorkspaceSource,
)


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


def get_answer_store(
    request: Request, settings: Annotated[Settings, Depends(get_settings)]
) -> AnswerStore:
    """C3 persistence. Until Dev A sequences the C3 answers/approvals migration, only a
    labelled in-memory FIXTURE store exists (fixture mode, one per app instance, lost on
    restart)."""
    if not settings.fixture_mode:
        return UnconfiguredAnswerStore()
    store: AnswerStore | None = getattr(request.app.state, "c3_answer_store", None)
    if store is None:
        store = InMemoryAnswerStore()
        request.app.state.c3_answer_store = store
    return store


def lookup_error(exc: Exception) -> ApiError:
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


LOOKUP_ERRORS = (
    QuestionNotFound,
    WorkspaceNotFound,
    EvidenceBundleNotFound,
    QuestionVersionConflict,
)


def model_error(exc: ModelError) -> ApiError:
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
