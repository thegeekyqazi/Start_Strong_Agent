from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from ...config import Settings, get_settings
from ...db import get_engine
from .artifacts import LocalArtifactStore
from .ingestion import TextIngestionService
from .pdf_ingestion import BoundedPdfParser, PdfIngestionService
from .repository import PostgresKnowledgeRepository


def get_knowledge_repository(
    settings: Annotated[Settings, Depends(get_settings)],
) -> PostgresKnowledgeRepository | None:
    if not settings.database_url:
        return None
    artifacts = (
        None
        if settings.environment == "production"
        else LocalArtifactStore(settings.knowledge_artifact_store_dir)
    )
    return PostgresKnowledgeRepository(
        get_engine(settings.database_url, settings.db_connect_timeout_seconds), artifacts
    )


def get_text_ingestion_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> TextIngestionService | None:
    if not settings.database_url or settings.environment == "production":
        return None
    return TextIngestionService(
        get_engine(settings.database_url, settings.db_connect_timeout_seconds),
        LocalArtifactStore(settings.knowledge_artifact_store_dir),
        settings.knowledge_max_text_bytes,
    )


def get_pdf_ingestion_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> PdfIngestionService | None:
    if not settings.database_url or settings.environment == "production":
        return None
    return PdfIngestionService(
        get_engine(settings.database_url, settings.db_connect_timeout_seconds),
        LocalArtifactStore(settings.knowledge_artifact_store_dir),
        BoundedPdfParser(
            settings.knowledge_max_pdf_bytes,
            settings.knowledge_max_pdf_pages,
            settings.knowledge_max_extracted_chars,
        ),
    )
