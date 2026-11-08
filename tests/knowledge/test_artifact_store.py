from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from strongstart_api.features.knowledge.artifacts import (
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    LocalArtifactStore,
)


def test_local_store_round_trip_is_content_addressed(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    content = b"Strong Start evidence\n"
    first = store.put("org-a", content)
    second = store.put("org-a", content)

    assert first == second
    assert first.content_sha256 == hashlib.sha256(content).hexdigest()
    assert first.size_bytes == len(content)
    assert store.read("org-a", first.artifact_key) == content


def test_cross_org_and_malformed_keys_are_hidden(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    artifact = store.put("org-a", b"private")

    with pytest.raises(ArtifactNotFoundError):
        store.read("org-b", artifact.artifact_key)
    with pytest.raises(ArtifactNotFoundError):
        store.read("org-a", "../../private")


def test_tampered_artifact_fails_integrity_check(tmp_path: Path) -> None:
    store = LocalArtifactStore(tmp_path)
    artifact = store.put("org-a", b"original")
    path = tmp_path / hashlib.sha256(b"org-a").hexdigest() / artifact.artifact_key
    path.write_bytes(b"tampered")

    with pytest.raises(ArtifactIntegrityError):
        store.read("org-a", artifact.artifact_key)
    with pytest.raises(ArtifactIntegrityError):
        store.put("org-a", b"original")
