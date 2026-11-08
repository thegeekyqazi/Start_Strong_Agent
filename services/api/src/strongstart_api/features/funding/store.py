"""LocalCaptureStore: DEVELOPMENT-ONLY persistent capture storage (B1-DISC-001 s5).

Used because no supported shared store exists yet (the default ``CaptureStore`` is
``UnconfiguredCaptureStore``). Dev A owns the real artifact store; until it exists this
store's capability is ``development_local_store`` and it is disabled in production.

Properties:
- organization namespaces are derived from the server identity and hashed into the
  directory name; no client-supplied path, filename or organization is used for I/O;
- capture IDs are server-generated (``cap-<uuid4 hex>``) and strictly validated on read;
- capture records are immutable (never overwritten); artifact bytes are content-addressed
  per organization, so identical bytes captured from two URLs share one blob while each
  capture keeps its own origin record (SRC-06);
- writes are atomic and no-clobber (temp file + fsync + ``os.link``; DEV-B-BUNDLE-002 s6),
  so two concurrent captures can never overwrite each other's record; reads re-hash bytes
  and fail closed on mismatch (SRC-02);
- durability follows the Dev B platform policy: POSIX full (file + directory fsync);
  Windows only with an explicit reduced-durability opt-in; otherwise writes are refused
  before success (``StoreUnavailable``);
- a catalog index (``catalog/<captured_at ms>-<capture_id>``) is created atomically after
  each record so staff can list captures without scanning blobs; older records without an
  index entry are backfilled in bounded steps and reported as pending until complete.

It does not implement the shared ``CaptureStore.put/get`` protocol, because that
signature has no organization scope; B2 consumes ``CapturedDocumentReader`` instead.
"""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from pydantic import ValidationError

from strongstart_contracts.discovery import (
    CaptureCatalogPage,
    CapturedDocument,
    CaptureIntegrityError,
    CaptureNotFoundError,
    CaptureSummary,
    ImportableArtifactRef,
    VerifiedArtifact,
)

from ..dev_b_store.core import (
    MAX_SCAN_ENTRIES,
    Durability,
    StoreUnavailable,
    atomic_create,
    durability_mode,
)

CAPTURE_ID_PATTERN = re.compile(r"^cap-[0-9a-f]{32}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
CATALOG_KEY = re.compile(r"^([0-9]{13})-(cap-[0-9a-f]{32})$")
BACKFILL_PER_CALL = 50

__all__ = ["CaptureStoreError", "LocalCaptureStore", "StoreUnavailable"]


class CaptureStoreError(Exception):
    pass


class LocalCaptureStore:
    is_fixture = False
    capability = "development_local_store"

    def __init__(
        self, root: Path, *, allow_reduced_durability: bool = False, os_name: str | None = None
    ) -> None:
        self.root = root.resolve()
        self.allow_reduced_durability = allow_reduced_durability
        self._os_name = os_name

    def durability(self) -> Durability:
        return durability_mode(self.allow_reduced_durability, self._os_name)

    # -- paths ---------------------------------------------------------------------

    def _org_dir(self, organization_id: str) -> Path:
        digest = hashlib.sha256(organization_id.encode("utf-8")).hexdigest()[:32]
        return self._confined(self.root / f"org-{digest}")

    def _confined(self, path: Path) -> Path:
        resolved = path.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise CaptureStoreError("path escapes the capture store root")
        return resolved

    def _record_path(self, organization_id: str, capture_id: str) -> Path:
        if not CAPTURE_ID_PATTERN.match(capture_id):
            raise CaptureNotFoundError(capture_id)
        return self._confined(self._org_dir(organization_id) / "records" / f"{capture_id}.json")

    def _blob_path(self, organization_id: str, sha256: str) -> Path:
        if not SHA256_PATTERN.match(sha256):
            raise CaptureIntegrityError("invalid artifact hash")
        return self._confined(self._org_dir(organization_id) / "blobs" / sha256)

    def _catalog_dir(self, organization_id: str) -> Path:
        return self._confined(self._org_dir(organization_id) / "catalog")

    @staticmethod
    def catalog_key(record: CapturedDocument) -> str:
        ms = int(record.captured_at.timestamp() * 1000)
        return f"{ms:013d}-{record.capture_id}"

    # -- writes --------------------------------------------------------------------

    def save(self, record: CapturedDocument, blobs: dict[str, bytes]) -> None:
        durability = self.durability()  # refuse unsupported platforms before any write
        org = record.organization_id
        record_path = self._record_path(org, record.capture_id)
        if record_path.exists():
            raise CaptureStoreError("capture records are immutable")
        for artifact in record.artifacts:
            data = blobs[artifact.sha256]
            if (
                hashlib.sha256(data).hexdigest() != artifact.sha256
                or len(data) != artifact.size_bytes
            ):
                raise CaptureIntegrityError("artifact bytes do not match their metadata")
            blob_path = self._blob_path(org, artifact.sha256)
            if not atomic_create(blob_path, data, durability):
                if hashlib.sha256(blob_path.read_bytes()).hexdigest() != artifact.sha256:
                    raise CaptureIntegrityError("existing blob failed integrity verification")
        data = record.model_dump_json(indent=2).encode("utf-8")
        if not atomic_create(record_path, data, durability):
            raise CaptureStoreError("capture records are immutable")
        self._index(org, record, durability)

    def _index(
        self, organization_id: str, record: CapturedDocument, durability: Durability
    ) -> None:
        path = self._confined(self._catalog_dir(organization_id) / self.catalog_key(record))
        atomic_create(path, record.capture_id.encode("ascii"), durability)

    # -- reads (CapturedDocumentReader) ----------------------------------------------

    def get_record(self, organization_id: str, capture_id: str) -> CapturedDocument:
        path = self._record_path(organization_id, capture_id)
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            raise CaptureNotFoundError(capture_id) from None
        try:
            record = CapturedDocument.model_validate_json(raw)
        except ValidationError:
            raise CaptureIntegrityError("stored capture record is corrupt") from None
        if record.organization_id != organization_id or record.capture_id != capture_id:
            raise CaptureNotFoundError(capture_id)
        return record

    def read_artifact(
        self, organization_id: str, capture_id: str, artifact_id: str
    ) -> VerifiedArtifact:
        record = self.get_record(organization_id, capture_id)
        artifact = next((a for a in record.artifacts if a.artifact_id == artifact_id), None)
        if artifact is None:
            raise CaptureNotFoundError(artifact_id)
        try:
            data = self._blob_path(organization_id, artifact.sha256).read_bytes()
        except FileNotFoundError:
            raise CaptureIntegrityError("artifact bytes are missing") from None
        if len(data) != artifact.size_bytes or hashlib.sha256(data).hexdigest() != artifact.sha256:
            raise CaptureIntegrityError("artifact bytes failed integrity verification")
        return VerifiedArtifact(artifact=artifact, content=data)

    # -- catalog (CaptureCatalogReader) ----------------------------------------------

    @staticmethod
    def _bounded_names(directory: Path) -> tuple[list[str], bool]:
        names: list[str] = []
        try:
            with os.scandir(directory) as it:
                for n, entry in enumerate(it):
                    if n >= MAX_SCAN_ENTRIES:
                        return names, True
                    if not entry.is_symlink() and entry.is_file():
                        names.append(entry.name)
        except FileNotFoundError:
            pass
        return names, False

    def _backfill(self, organization_id: str, indexed: set[str]) -> tuple[str, int]:
        """Index up to BACKFILL_PER_CALL older records; report what remains honestly."""
        names, truncated = self._bounded_names(self._org_dir(organization_id) / "records")
        missing = [
            n.removesuffix(".json")
            for n in names
            if n.endswith(".json")
            and CAPTURE_ID_PATTERN.match(n.removesuffix(".json"))
            and n.removesuffix(".json") not in indexed
        ]
        done = 0
        durability: Durability | None = None
        for capture_id in missing[:BACKFILL_PER_CALL]:
            try:
                record = self.get_record(organization_id, capture_id)
            except (CaptureNotFoundError, CaptureIntegrityError):
                continue  # corrupt records stay unindexed; never hidden as complete
            try:
                durability = durability or self.durability()
            except StoreUnavailable:
                break
            self._index(organization_id, record, durability)
            done += 1
        pending = len(missing) - done
        if truncated:
            return "incomplete_scan", pending
        return ("complete" if pending == 0 else "pending"), pending

    def list_captures(
        self, organization_id: str, cursor: str | None, limit: int
    ) -> CaptureCatalogPage:
        if cursor is not None and not CATALOG_KEY.fullmatch(cursor):
            raise CaptureNotFoundError("invalid cursor")
        catalog_dir = self._catalog_dir(organization_id)
        names, _ = self._bounded_names(catalog_dir)
        indexed = {m.group(2) for n in names if (m := CATALOG_KEY.fullmatch(n))}
        backfill, pending = self._backfill(organization_id, indexed)
        names, catalog_truncated = self._bounded_names(catalog_dir)  # includes new entries
        keys = sorted({n for n in names if CATALOG_KEY.fullmatch(n)}, reverse=True)
        if cursor is not None:
            keys = [k for k in keys if k < cursor]
        page, more = keys[:limit], len(keys) > limit
        items = [self._summary(organization_id, k) for k in page]
        return CaptureCatalogPage(
            items=items,
            next_cursor=page[-1] if more and page else None,
            more=more,
            incomplete=catalog_truncated,
            backfill_status=backfill,
            backfill_pending=pending,
            limit=limit,
        )

    def _summary(self, organization_id: str, key: str) -> CaptureSummary:
        match = CATALOG_KEY.fullmatch(key)
        if match is None:  # pragma: no cover - keys are filtered by the caller
            raise CaptureNotFoundError(key)
        capture_id = match.group(2)
        try:
            r = self.get_record(organization_id, capture_id)
        except (CaptureNotFoundError, CaptureIntegrityError):
            return CaptureSummary(
                capture_id=capture_id,
                status="corrupt",
                detail="The stored record is missing or failed validation; no content shown.",
            )
        return CaptureSummary(
            capture_id=r.capture_id,
            status="ok",
            page_title=r.page_title,
            requested_url=r.requested_url,
            final_url=r.final_url,
            captured_at=r.captured_at,
            provider=r.provider,
            provider_mode=r.provider_mode,
            coverage=r.coverage,
            representation_count=len(r.artifacts),
            importable_artifacts=[
                ImportableArtifactRef(
                    artifact_id=a.artifact_id,
                    representation=a.representation,
                    intake_reference=f"{r.capture_id}:{a.artifact_id}",
                )
                for a in r.artifacts
                if a.representation in r.supported_import_representations
            ],
            authority_review=r.authority_review,
            is_simulated=r.provenance.is_simulated,
        )
