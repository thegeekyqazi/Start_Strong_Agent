"""B1-B2 capture seam: B2's consumer port for captured documents (launch agreement s3).

``CaptureSource`` is the small port B2's importer depends on. It receives the
*server-derived* organization ID, never a client value, and returns the semantic v1
captured-document record plus the exact stored bytes of one artifact. B2 verifies the
artifact hash itself; it never trusts client-attested metadata and never refetches a URL.

Implementations:

- ``UnconfiguredCaptureSource``: default; raises ``CapabilityUnavailable`` (fail closed).
- ``InMemoryCaptureSource``: records + bytes held in memory. Used by the B2 fixture
  producer and by integration tests that feed a B1-serialized record through the real
  importer (``parse_capture_record`` is the adapter for B1's JSON).
- ``FixtureCaptureSource``: loads the B2 fixture producer records shipped under
  ``fixtures/captures`` (labelled fixture; synthetic ``.invalid`` URLs).

B1's real producer (B1-DISC-001) is pending. When its contract is published, map its
serialized record onto ``parse_capture_record`` (field mapping in the B2 handoff) or
add an adapter implementing ``CaptureSource`` over B1's authorized read operation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from strongstart_contracts.common import Provenance, Sha256Hex, StableId
from strongstart_contracts.discovery import CapturedDocument, CapturedDocumentReader
from strongstart_contracts.discovery import CaptureIntegrityError as B1CaptureIntegrity
from strongstart_contracts.discovery import CaptureNotFoundError as B1CaptureNotFound
from strongstart_contracts.ports import CapabilityUnavailable

CAPTURE_DIR = Path(__file__).parent / "fixtures" / "captures"


class CaptureNotFound(Exception):
    """Unknown capture/artifact, or one outside the caller's organization (no existence leak)."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CaptureArtifact(_Strict):
    artifact_id: StableId
    representation_type: str = Field(max_length=64)
    media_type: str = Field(max_length=128)
    byte_size: int = Field(ge=0)
    sha256: Sha256Hex
    content_file: str | None = Field(default=None, description="fixture-internal only")


class CaptureUrls(_Strict):
    original: str | None = None
    requested: str | None = None
    final: str | None = None
    final_status: Literal["known", "provider_reported", "unknown"]


class CaptureExtraction(_Strict):
    coverage: Literal["complete", "partial", "empty", "unknown"]
    warnings: list[str] = Field(default_factory=list, max_length=50)


class CaptureRecord(_Strict):
    """B2's consumer view of the semantic v1 captured-document record (launch s3)."""

    schema_version: Literal["capture-record/1"]
    capture_id: StableId
    source_id: StableId
    source_version_id: StableId
    organization_id: StableId
    opportunity_id: StableId | None = None
    stream_id: StableId | None = None
    cycle_id: StableId | None = None
    urls: CaptureUrls
    provider: str | None = None
    captured_at: datetime | None = None
    artifacts: list[CaptureArtifact] = Field(min_length=1, max_length=20)
    extraction: CaptureExtraction
    provenance: Provenance
    authority_review_status: str = Field(max_length=64)
    # Additive fields for the real B1 producer (CapturedDocument v1). ``None`` = not stated.
    supported_import_representations: list[str] | None = None
    producer_is_fixture: bool = False
    producer: str = "b2-fixture-producer"
    source_reference_hash: Sha256Hex | None = None


class CaptureIntegrity(Exception):
    """Stored bytes failed the producer's hash verification."""


def parse_capture_record(data: dict[str, Any]) -> CaptureRecord:
    """Adapter for a serialized semantic-v1 record. Raises ValueError on mismatch."""
    try:
        return CaptureRecord.model_validate(data)
    except ValidationError as exc:
        raise ValueError(
            f"capture record does not match capture-record/1: {exc.error_count()} issue(s)"
        ) from None


class CaptureSource(Protocol):
    is_fixture: bool

    def get_record(self, organization_id: str, capture_id: str) -> CaptureRecord: ...

    def read_artifact(self, organization_id: str, capture_id: str, artifact_id: str) -> bytes: ...

    def list_records(self, organization_id: str) -> list[CaptureRecord]: ...


class UnconfiguredCaptureSource:
    is_fixture = False

    def get_record(self, organization_id: str, capture_id: str) -> CaptureRecord:
        raise CapabilityUnavailable("AutomationCaptureSource", "no capture producer configured")

    def read_artifact(self, organization_id: str, capture_id: str, artifact_id: str) -> bytes:
        raise CapabilityUnavailable("AutomationCaptureSource", "no capture producer configured")

    def list_records(self, organization_id: str) -> list[CaptureRecord]:
        return []


@dataclass(frozen=True)
class _Stored:
    record: CaptureRecord
    contents: dict[str, bytes]


class InMemoryCaptureSource:
    """Organization-scoped in-memory capture source. Bytes are copied on the way in."""

    def __init__(self, items: list[tuple[CaptureRecord, dict[str, bytes]]], *, is_fixture: bool):
        self.is_fixture = is_fixture
        self._items: dict[str, _Stored] = {}
        for record, contents in items:
            if record.capture_id in self._items:
                raise ValueError(f"duplicate capture_id {record.capture_id}")
            self._items[record.capture_id] = _Stored(
                record, {k: bytes(v) for k, v in contents.items()}
            )

    def _scoped(self, organization_id: str, capture_id: str) -> _Stored:
        item = self._items.get(capture_id)
        if item is None or item.record.organization_id != organization_id:
            raise CaptureNotFound(capture_id)
        return item

    def get_record(self, organization_id: str, capture_id: str) -> CaptureRecord:
        return self._scoped(organization_id, capture_id).record

    def read_artifact(self, organization_id: str, capture_id: str, artifact_id: str) -> bytes:
        item = self._scoped(organization_id, capture_id)
        if artifact_id not in item.contents:
            raise CaptureNotFound(artifact_id)
        return item.contents[artifact_id]

    def list_records(self, organization_id: str) -> list[CaptureRecord]:
        return [
            s.record for s in self._items.values() if s.record.organization_id == organization_id
        ]


def _confined(directory: Path, name: str) -> Path:
    if "/" in name or "\\" in name or name.startswith(".") or not name:
        raise ValueError("fixture content file must be a plain file name")
    path = (directory / name).resolve()
    if path.parent != directory.resolve() or not path.is_file():
        raise ValueError("fixture content file escapes the fixture directory")
    return path


def load_fixture_capture_source(directory: Path = CAPTURE_DIR) -> InMemoryCaptureSource:
    """B2 fixture producer. Content files are resolved inside ``directory`` only."""
    doc = json.loads((directory / "records.json").read_text(encoding="utf-8"))
    items: list[tuple[CaptureRecord, dict[str, bytes]]] = []
    for raw in doc["records"]:
        record = parse_capture_record(raw).model_copy(update={"producer_is_fixture": True})
        contents: dict[str, bytes] = {}
        for art in record.artifacts:
            if art.content_file:
                contents[art.artifact_id] = _confined(directory, art.content_file).read_bytes()
        items.append((record, contents))
    return InMemoryCaptureSource(items, is_fixture=True)


# --------------------------------------------------------------------------- B1 adapter


def record_from_captured_document(doc: CapturedDocument) -> CaptureRecord:
    """Map B1's ``CapturedDocument`` (schema "1") onto B2's consumer view, field for field.

    Nothing is inferred: B1's ``final_url_status`` ("provider_reported"/"unknown"), the
    source reference IDs, every artifact hash/representation, coverage, warnings,
    authority review and provenance are carried over verbatim.
    """
    ref = doc.source_reference
    return CaptureRecord(
        schema_version="capture-record/1",
        capture_id=doc.capture_id,
        source_id=ref.source_id,
        source_version_id=ref.source_version_id,
        organization_id=doc.organization_id,
        opportunity_id=doc.opportunity_id,
        stream_id=doc.stream_id,
        cycle_id=doc.cycle_id,
        urls=CaptureUrls(
            original=doc.normalized_url,
            requested=doc.requested_url,
            final=doc.final_url,
            final_status=doc.final_url_status,
        ),
        provider=f"{doc.provider} ({doc.provider_mode})",
        captured_at=doc.captured_at,
        artifacts=[
            CaptureArtifact(
                artifact_id=a.artifact_id,
                representation_type=a.representation,
                media_type=a.media_type,
                byte_size=a.size_bytes,
                sha256=a.sha256,
            )
            for a in doc.artifacts
        ],
        extraction=CaptureExtraction(coverage=doc.coverage, warnings=list(doc.warnings)[:50]),
        provenance=doc.provenance,
        authority_review_status=doc.authority_review,
        supported_import_representations=list(doc.supported_import_representations),
        producer_is_fixture=doc.provider_mode == "fixture" or doc.provenance.is_simulated,
        producer="b1-capture-store",
        source_reference_hash=ref.content_hash,
    )


class B1CaptureSource:
    """``CaptureSource`` over B1's org-scoped ``CapturedDocumentReader`` (no URL refetch)."""

    is_fixture = False  # per-record fixture status comes from ``producer_is_fixture``

    def __init__(self, reader: CapturedDocumentReader) -> None:
        self._reader = reader

    def get_record(self, organization_id: str, capture_id: str) -> CaptureRecord:
        try:
            return record_from_captured_document(
                self._reader.get_record(organization_id, capture_id)
            )
        except B1CaptureNotFound:
            raise CaptureNotFound(capture_id) from None

    def read_artifact(self, organization_id: str, capture_id: str, artifact_id: str) -> bytes:
        try:
            return self._reader.read_artifact(organization_id, capture_id, artifact_id).content
        except B1CaptureNotFound:
            raise CaptureNotFound(artifact_id) from None
        except B1CaptureIntegrity:
            raise CaptureIntegrity(artifact_id) from None

    def list_records(self, organization_id: str) -> list[CaptureRecord]:
        return []  # B1's reader port has no listing; staff paste the capture reference


class ChainedCaptureSource:
    """Try each source in order; unknown in one source falls through to the next."""

    is_fixture = False

    def __init__(self, sources: list[CaptureSource]) -> None:
        self._sources = sources

    def _owner(self, organization_id: str, capture_id: str) -> tuple[CaptureSource, CaptureRecord]:
        for src in self._sources:
            try:
                return src, src.get_record(organization_id, capture_id)
            except (CaptureNotFound, CapabilityUnavailable):
                continue
        raise CaptureNotFound(capture_id)

    def get_record(self, organization_id: str, capture_id: str) -> CaptureRecord:
        return self._owner(organization_id, capture_id)[1]

    def read_artifact(self, organization_id: str, capture_id: str, artifact_id: str) -> bytes:
        return self._owner(organization_id, capture_id)[0].read_artifact(
            organization_id, capture_id, artifact_id
        )

    def list_records(self, organization_id: str) -> list[CaptureRecord]:
        return [r for s in self._sources for r in s.list_records(organization_id)]
