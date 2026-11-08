"""Supported C integration factories. B never imports C's private store/router."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Request

from strongstart_contracts.answers import (
    ApplicationWorkspace,
    CheckReport,
    CheckRequest,
    DraftProposal,
    DraftRequest,
)

from ...config import Settings, get_settings
from .approval import Context, can_approve
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
from .postgres_store import PostgresAnswerStore
from .resolver import StoreApprovedAnswerResolver
from .rules.policy import WritingPolicy
from .service import check_answer, draft_answer
from .store import AnswerStore
from .workspace import WorkspaceSource, load_workspace


def get_approved_prefill_reader(
    store: Annotated[AnswerStore, Depends(get_answer_store)],
    source: Annotated[WorkspaceSource, Depends(get_workspace_source)],
    policy: Annotated[WritingPolicy | None, Depends(get_policy)],
    settings: Annotated[Settings, Depends(get_settings)],
    request: Request,
) -> StoreApprovedAnswerResolver:
    selected = getattr(request.app.state, "c3_answer_store", None)

    def store_current() -> bool:
        current = getattr(request.app.state, "c3_answer_store", None)
        if isinstance(store, PostgresAnswerStore) and isinstance(current, PostgresAnswerStore):
            return current.engine.url == store.engine.url
        return current is store

    return StoreApprovedAnswerResolver(
        lambda org: Context(store, source, policy, settings, org),
        store.is_fixture,
        store_current=store_current if selected is store else None,
    )


# C4-SKL-001: narrow, public draft-preview port. Skills supplies a resolved practice as
# finite policy records plus guidance text; this port reuses C's real workspace, model,
# render and check pipeline. It never persists, approves, exports or prefills.
PREVIEW_LOOKUP_ERRORS = LOOKUP_ERRORS
preview_lookup_error = lookup_error
preview_model_error = model_error
PreviewModelError = ModelError


@dataclass(frozen=True)
class PracticePreviewPort:
    source: WorkspaceSource
    adapter: ModelAdapter
    base_policy: WritingPolicy | None
    timeout_seconds: float

    def workspace(self, organization_id: str, question_set_id: str | None) -> ApplicationWorkspace:
        return load_workspace(self.source, organization_id, question_set_id)

    async def draft(
        self,
        organization_id: str,
        question_id: str,
        request: DraftRequest,
        policy: WritingPolicy | None,
        practice_guidance: str | None,
    ) -> DraftProposal:
        return await draft_answer(
            source=self.source,
            adapter=self.adapter,
            organization_id=organization_id,
            question_id=question_id,
            request=request,
            timeout_seconds=self.timeout_seconds,
            policy=policy,
            practice_guidance=practice_guidance,
        )

    def check(
        self,
        organization_id: str,
        question_id: str,
        request: CheckRequest,
        policy: WritingPolicy | None,
    ) -> CheckReport:
        return check_answer(
            source=self.source,
            organization_id=organization_id,
            question_id=question_id,
            request=request,
            policy=policy,
        )


def get_practice_preview_port(
    source: Annotated[WorkspaceSource, Depends(get_workspace_source)],
    adapter: Annotated[ModelAdapter, Depends(get_model_adapter)],
    policy: Annotated[WritingPolicy | None, Depends(get_policy)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> PracticePreviewPort:
    return PracticePreviewPort(source, adapter, policy, settings.model_timeout_seconds)


# C4-SKL-001: staff decision rule shared with C3 (fixture identity in fixture mode only).
staff_can_decide = can_approve
