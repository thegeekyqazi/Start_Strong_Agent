"""Safe bounded text ingestion into immutable artifacts and PostgreSQL provenance."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Engine

from strongstart_contracts import Provenance, TextSourceImportResult

from ...db import knowledge_passages, knowledge_source_versions, knowledge_sources
from .artifacts import ArtifactStore


class TextIngestionError(ValueError):
    pass


class TextIngestionService:
    def __init__(self, engine: Engine, artifacts: ArtifactStore, max_bytes: int) -> None:
        self.engine = engine
        self.artifacts = artifacts
        self.max_bytes = max_bytes

    def ingest(
        self, organization_id: str, title: str, text: str, *, is_fixture: bool
    ) -> TextSourceImportResult:
        normalized_title = title.strip()
        if not normalized_title:
            raise TextIngestionError("title must contain non-whitespace text")
        if "\x00" in text:
            raise TextIngestionError("text contains a forbidden NUL character")
        content = text.encode("utf-8")
        if not content or not text.strip():
            raise TextIngestionError("text must contain non-whitespace content")
        if len(content) > self.max_bytes:
            raise TextIngestionError(f"text exceeds the {self.max_bytes}-byte limit")

        artifact = self.artifacts.put(organization_id, content)
        suffix = uuid4().hex
        source_id = f"src-{suffix}"
        version_id = f"srcv-{suffix}"
        passage_id = f"pass-{suffix}"
        captured_at = datetime.now(UTC)
        provenance_class = "simulated" if is_fixture else "supplied"
        note = (
            "Imported through fixture identity; not real organizational evidence."
            if is_fixture
            else None
        )
        warnings: list[str] = []
        locator = f"char:0-{len(text)}"

        with self.engine.begin() as conn:
            conn.execute(
                knowledge_sources.insert().values(
                    id=source_id,
                    organization_id=organization_id,
                    title=normalized_title,
                    provenance_class=provenance_class,
                    is_simulated=is_fixture,
                    provenance_note=note,
                )
            )
            conn.execute(
                knowledge_source_versions.insert().values(
                    id=version_id,
                    source_id=source_id,
                    organization_id=organization_id,
                    media_type="text/plain; charset=utf-8",
                    content_bytes=None,
                    storage_backend="local_artifact",
                    artifact_key=artifact.artifact_key,
                    content_sha256=artifact.content_sha256,
                    size_bytes=artifact.size_bytes,
                    captured_at=captured_at,
                    publication_status="unknown",
                    publication_date=None,
                    reporting_period=None,
                    verification_status="unverified",
                    parser_name="plain_text_utf8",
                    parser_version="1",
                    parser_warnings=json.dumps(warnings),
                )
            )
            conn.execute(
                knowledge_passages.insert().values(
                    id=passage_id,
                    source_version_id=version_id,
                    locator=locator,
                    exact_text=text,
                )
            )

        return TextSourceImportResult(
            source_id=source_id,
            source_version_id=version_id,
            passage_id=passage_id,
            artifact_key=artifact.artifact_key,
            content_sha256=artifact.content_sha256,
            size_bytes=artifact.size_bytes,
            media_type="text/plain; charset=utf-8",
            parser_name="plain_text_utf8",
            parser_version="1",
            warnings=warnings,
            locator=locator,
            provenance=Provenance(
                provenance_class=provenance_class, is_simulated=is_fixture, note=note
            ),
        )
