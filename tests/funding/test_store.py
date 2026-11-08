"""LocalCaptureStore unit behaviour (store-boundary coverage only)."""

from __future__ import annotations

from pathlib import Path

import pytest

from strongstart_api.features.funding.store import CaptureStoreError, LocalCaptureStore
from strongstart_contracts.discovery import (
    CapturedDocument,
    CaptureIntegrityError,
    CaptureNotFoundError,
)
from tests.conftest import REPO_ROOT

SAMPLE = REPO_ROOT / "tests/fixtures/funding/sample-capture-v1"


def _load(store: LocalCaptureStore) -> CapturedDocument:
    record = CapturedDocument.model_validate_json((SAMPLE / "record.json").read_bytes())
    blobs = {
        a.sha256: (SAMPLE / "artifacts" / a.artifact_id).read_bytes() for a in record.artifacts
    }
    store.save(record, blobs)
    return record


def test_records_are_immutable(tmp_path: Path) -> None:
    store = LocalCaptureStore(tmp_path)
    record = _load(store)
    with pytest.raises(CaptureStoreError):
        _load(store)
    assert store.get_record(record.organization_id, record.capture_id) == record


def test_mismatched_bytes_refused_on_save(tmp_path: Path) -> None:
    record = CapturedDocument.model_validate_json((SAMPLE / "record.json").read_bytes())
    blobs = {a.sha256: b"wrong" for a in record.artifacts}
    with pytest.raises(CaptureIntegrityError):
        LocalCaptureStore(tmp_path).save(record, blobs)


def test_missing_blob_and_unknown_ids(tmp_path: Path) -> None:
    store = LocalCaptureStore(tmp_path)
    record = _load(store)
    for blob in tmp_path.rglob("blobs/*"):
        blob.unlink()
    with pytest.raises(CaptureIntegrityError):
        store.read_artifact(
            record.organization_id, record.capture_id, record.artifacts[0].artifact_id
        )
    with pytest.raises(CaptureNotFoundError):
        store.get_record("other-org", record.capture_id)
    with pytest.raises(CaptureNotFoundError):
        store.get_record(record.organization_id, "../../etc/passwd")


def test_no_temp_files_left_and_paths_confined(tmp_path: Path) -> None:
    store = LocalCaptureStore(tmp_path)
    _load(store)
    files = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert files and not any(p.name.startswith(".tmp-") for p in files)
    assert all(tmp_path.resolve() in p.resolve().parents for p in files)
