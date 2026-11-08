"""Organization-scoped immutable artifact storage for Dev A knowledge sources."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ArtifactNotFoundError(Exception):
    """Artifact is absent or not available to the organization."""


class ArtifactIntegrityError(Exception):
    """Stored bytes differ from their immutable identity."""


@dataclass(frozen=True)
class StoredArtifact:
    artifact_key: str
    content_sha256: str
    size_bytes: int


class ArtifactStore(Protocol):
    def put(self, organization_id: str, content: bytes) -> StoredArtifact: ...

    def read(self, organization_id: str, artifact_key: str) -> bytes: ...


_KEY = re.compile(r"^sha256-[0-9a-f]{64}$")


class LocalArtifactStore:
    """Development/test adapter; paths are derived only from hashes."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    @staticmethod
    def _org_namespace(organization_id: str) -> str:
        return hashlib.sha256(organization_id.encode("utf-8")).hexdigest()

    def _path(self, organization_id: str, artifact_key: str) -> Path:
        if not _KEY.fullmatch(artifact_key):
            raise ArtifactNotFoundError
        path = self.root / self._org_namespace(organization_id) / artifact_key
        resolved = path.resolve()
        if self.root not in resolved.parents:
            raise ArtifactNotFoundError
        return resolved

    def put(self, organization_id: str, content: bytes) -> StoredArtifact:
        digest = hashlib.sha256(content).hexdigest()
        artifact = StoredArtifact(f"sha256-{digest}", digest, len(content))
        destination = self._path(organization_id, artifact.artifact_key)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            self._verify(destination, artifact)
            return artifact
        descriptor, temporary_name = tempfile.mkstemp(dir=destination.parent, prefix=".pending-")
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, destination)
            except FileExistsError:
                pass
            self._verify(destination, artifact)
        finally:
            temporary.unlink(missing_ok=True)
        return artifact

    @staticmethod
    def _verify(path: Path, expected: StoredArtifact) -> bytes:
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            raise ArtifactNotFoundError from None
        if (
            len(content) != expected.size_bytes
            or hashlib.sha256(content).hexdigest() != expected.content_sha256
        ):
            raise ArtifactIntegrityError("artifact integrity verification failed")
        return content

    def read(self, organization_id: str, artifact_key: str) -> bytes:
        path = self._path(organization_id, artifact_key)
        digest = artifact_key.removeprefix("sha256-")
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            raise ArtifactNotFoundError from None
        return self._verify(path, StoredArtifact(artifact_key, digest, size))
