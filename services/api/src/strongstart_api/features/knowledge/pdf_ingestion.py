"""Bounded PDF text extraction with exact page provenance."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4

import pypdf
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import Engine

from strongstart_contracts import PdfSourceImportResult, Provenance

from ...db import knowledge_passages, knowledge_source_versions, knowledge_sources
from .artifacts import ArtifactStore
from .ingestion import TextIngestionError


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class PdfExtraction:
    pages: list[ExtractedPage]
    page_count: int
    warnings: list[str]


class BoundedPdfParser:
    def __init__(self, max_bytes: int, max_pages: int, max_chars: int) -> None:
        self.max_bytes = max_bytes
        self.max_pages = max_pages
        self.max_chars = max_chars

    def decode(self, encoded: str) -> bytes:
        try:
            content = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            raise TextIngestionError("content_base64 is not strict standard base64") from None
        if len(content) > self.max_bytes:
            raise TextIngestionError(f"PDF exceeds the {self.max_bytes}-byte limit")
        if not content.startswith(b"%PDF-"):
            raise TextIngestionError("content does not have a PDF signature")
        return content

    def extract(self, content: bytes) -> PdfExtraction:
        try:
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted:
                raise TextIngestionError("encrypted PDFs are not supported")
            page_count = len(reader.pages)
            if page_count == 0:
                raise TextIngestionError("PDF contains no pages")
            if page_count > self.max_pages:
                raise TextIngestionError(f"PDF exceeds the {self.max_pages}-page limit")
            pages: list[ExtractedPage] = []
            warnings: list[str] = []
            total_chars = 0
            for index, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                if not text.strip():
                    warnings.append(f"page {index} has no extractable text; OCR not performed")
                    continue
                total_chars += len(text)
                if total_chars > self.max_chars:
                    raise TextIngestionError(
                        f"PDF extraction exceeds the {self.max_chars}-character limit"
                    )
                pages.append(ExtractedPage(index, text))
        except TextIngestionError:
            raise
        except (PdfReadError, OSError, ValueError, KeyError) as exc:
            raise TextIngestionError(f"PDF could not be parsed ({type(exc).__name__})") from None
        if not pages:
            raise TextIngestionError("PDF has no extractable text; OCR is required")
        return PdfExtraction(pages=pages, page_count=page_count, warnings=warnings)


class PdfIngestionService:
    def __init__(self, engine: Engine, artifacts: ArtifactStore, parser: BoundedPdfParser) -> None:
        self.engine = engine
        self.artifacts = artifacts
        self.parser = parser

    def ingest(
        self, organization_id: str, title: str, encoded: str, *, is_fixture: bool
    ) -> PdfSourceImportResult:
        normalized_title = title.strip()
        if not normalized_title:
            raise TextIngestionError("title must contain non-whitespace text")
        content = self.parser.decode(encoded)
        extraction = self.parser.extract(content)
        artifact = self.artifacts.put(organization_id, content)
        suffix = uuid4().hex
        source_id = f"src-{suffix}"
        version_id = f"srcv-{suffix}"
        passage_ids = [f"pass-{suffix}-p{page.page_number}" for page in extraction.pages]
        captured_at = datetime.now(UTC)
        provenance_class = "simulated" if is_fixture else "supplied"
        note = (
            "Imported through fixture identity; not real organizational evidence."
            if is_fixture
            else None
        )
        status = "complete" if len(extraction.pages) == extraction.page_count else "partial"
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
                    media_type="application/pdf",
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
                    parser_name="pypdf",
                    parser_version=pypdf.__version__,
                    parser_warnings=json.dumps(extraction.warnings),
                    page_count=extraction.page_count,
                    processed_pages=len(extraction.pages),
                    extraction_status=status,
                )
            )
            conn.execute(
                knowledge_passages.insert(),
                [
                    {
                        "id": passage_id,
                        "source_version_id": version_id,
                        "locator": f"page:{page.page_number}",
                        "exact_text": page.text,
                    }
                    for passage_id, page in zip(passage_ids, extraction.pages, strict=True)
                ],
            )
        return PdfSourceImportResult(
            source_id=source_id,
            source_version_id=version_id,
            artifact_key=artifact.artifact_key,
            content_sha256=artifact.content_sha256,
            size_bytes=artifact.size_bytes,
            media_type="application/pdf",
            parser_name="pypdf",
            parser_version=pypdf.__version__,
            warnings=extraction.warnings,
            page_count=extraction.page_count,
            processed_pages=len(extraction.pages),
            passage_ids=passage_ids,
            provenance=Provenance(
                provenance_class=provenance_class, is_simulated=is_fixture, note=note
            ),
        )
