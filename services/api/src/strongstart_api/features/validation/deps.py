from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from ...config import Settings, get_settings
from ...db import get_engine
from ..knowledge.artifacts import LocalArtifactStore
from .repository import SourceValidationRepository
from .service import SourceValidationService


def get_validation_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SourceValidationRepository | None:
    if not settings.database_url:
        return None
    artifacts = (
        None
        if settings.environment == "production"
        else LocalArtifactStore(settings.knowledge_artifact_store_dir)
    )
    return SourceValidationRepository(
        get_engine(settings.database_url, settings.db_connect_timeout_seconds), artifacts
    )


def get_source_validation_service(
    repository: Annotated[SourceValidationRepository | None, Depends(get_validation_repository)],
) -> SourceValidationService | None:
    return SourceValidationService(repository) if repository is not None else None
