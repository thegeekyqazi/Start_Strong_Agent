from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from ...config import Settings, get_settings
from ...db import configured_engine
from ..knowledge.artifacts import LocalArtifactStore
from .repository import SourceValidationRepository
from .service import NumericValidationService, SourceValidationService


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
    return SourceValidationRepository(configured_engine(settings), artifacts)


def get_source_validation_service(
    repository: Annotated[SourceValidationRepository | None, Depends(get_validation_repository)],
) -> SourceValidationService | None:
    return SourceValidationService(repository) if repository is not None else None


def get_numeric_validation_service(
    repository: Annotated[SourceValidationRepository | None, Depends(get_validation_repository)],
) -> NumericValidationService | None:
    return NumericValidationService(repository) if repository is not None else None
