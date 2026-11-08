from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from ...config import Settings, get_settings
from ...db import get_engine
from .repository import PostgresKnowledgeRepository


def get_knowledge_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> PostgresKnowledgeRepository | None:
    if not settings.database_url:
        return None
    return PostgresKnowledgeRepository(
        get_engine(settings.database_url, settings.db_connect_timeout_seconds)
    )
