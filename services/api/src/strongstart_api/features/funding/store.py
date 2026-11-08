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
- writes are atomic (temp file + fsync + rename); reads re-hash bytes and fail closed
  on mismatch (SRC-02).

It does not implement the shared ``CaptureStore.put/get`` protocol, because that
signature has no organization scope; B2 consumes ``CapturedDocumentReader`` instead.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

from strongstart_contracts.discovery import (
    CapturedDocument,
    CaptureIntegrityError,
    CaptureNotFoundError,
    VerifiedArtifact,
)

CAPTURE_ID_PATTERN = re.compile(r"^cap-[0-9a-f]{32}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class CaptureStoreError(Exception):
    pass


class LocalCaptureStore:
    is_fixture = False
    capability = "development_local_store"

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

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

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    # -- writes --------------------------------------------------------------------

    def save(self, record: CapturedDocument, blobs: dict[str, bytes]) -> None:
        org = record.organization_id
        for artifact in record.artifacts:
            data = blobs[artifact.sha256]
            if (
                hashlib.sha256(data).hexdigest() != artifact.sha256
                or len(data) != artifact.size_bytes
            ):
                raise CaptureIntegrityError("artifact bytes do not match their metadata")
            blob_path = self._blob_path(org, artifact.sha256)
            if blob_path.exists():
                if hashlib.sha256(blob_path.read_bytes()).hexdigest() != artifact.sha256:
                    raise CaptureIntegrityError("existing blob failed integrity verification")
            else:
                self._atomic_write(blob_path, data)
        record_path = self._record_path(org, record.capture_id)
        if record_path.exists():
            raise CaptureStoreError("capture records are immutable")
        self._atomic_write(record_path, record.model_dump_json(indent=2).encode("utf-8"))

    # -- reads (CapturedDocumentReader) ----------------------------------------------

    def get_record(self, organization_id: str, capture_id: str) -> CapturedDocument:
        path = self._record_path(organization_id, capture_id)
        try:
            raw = path.read_bytes()
        except FileNotFoundError:
            raise CaptureNotFoundError(capture_id) from None
        record = CapturedDocument.model_validate_json(raw)
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
