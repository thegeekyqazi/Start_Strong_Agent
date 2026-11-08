"""Supported C integration factories. B never imports C's private store/router."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from ...config import Settings, get_settings
from .approval import Context
from .deps import get_answer_store, get_policy, get_workspace_source
from .resolver import StoreApprovedAnswerResolver
from .rules.policy import WritingPolicy
from .store import AnswerStore
from .workspace import WorkspaceSource


def get_approved_prefill_reader(
    store: Annotated[AnswerStore, Depends(get_answer_store)],
    source: Annotated[WorkspaceSource, Depends(get_workspace_source)],
    policy: Annotated[WritingPolicy | None, Depends(get_policy)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StoreApprovedAnswerResolver:
    return StoreApprovedAnswerResolver(
        lambda org: Context(store, source, policy, settings, org), store.is_fixture
    )
