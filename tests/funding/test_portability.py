"""DEV-B-BUNDLE-002 M2 portability fixes (BND-21).

- hash-sensitive fixtures are protected from end-of-line conversion at checkout;
- durability is platform-specific and refused (not silently weakened) where unsupported;
- capture records are created no-clobber under concurrent writers (cross-process).
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from strongstart_api.features.dev_b_store import core
from strongstart_api.features.dev_b_store.core import (
    LocalVersionStore,
    StoreUnavailable,
    durability_mode,
)
from strongstart_api.features.funding.store import CaptureStoreError, LocalCaptureStore
from strongstart_contracts.discovery import CapturedDocument
from tests.conftest import REPO_ROOT

SAMPLE = REPO_ROOT / "tests/fixtures/funding/sample-capture-v1"
PROTECTED = [
    "tests/fixtures/funding",
    "tests/fixtures/automation",
    "services/api/src/strongstart_api/features/funding/fixture_data",
    "services/api/src/strongstart_api/features/automation/fixtures",
]


def _record_and_blobs() -> tuple[CapturedDocument, dict[str, bytes]]:
    record = CapturedDocument.model_validate_json((SAMPLE / "record.json").read_bytes())
    blobs = {
        a.sha256: (SAMPLE / "artifacts" / a.artifact_id).read_bytes() for a in record.artifacts
    }
    return record, blobs


GIT = shutil.which("git")


@pytest.mark.skipif(GIT is None, reason="git not available")
def test_bnd21_hash_sensitive_fixtures_disable_eol_conversion() -> None:
    assert GIT is not None
    files = subprocess.run(  # noqa: S603 - fixed argv
        [GIT, "ls-files", *PROTECTED], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.split()
    files = [f for f in files if "__pycache__" not in f and not f.endswith(".py")]
    assert files
    attrs = subprocess.run(  # noqa: S603 - fixed argv
        [GIT, "check-attr", "text", "--", *files],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert all(line.endswith(": text: unset") for line in attrs), attrs


def test_bnd21_registered_hashes_match_exact_bytes_and_crlf_would_break_them() -> None:
    record, _ = _record_and_blobs()
    for a in record.artifacts:
        data = (SAMPLE / "artifacts" / a.artifact_id).read_bytes()
        assert hashlib.sha256(data).hexdigest() == a.sha256
        if b"\n" in data:  # why the attributes matter: a CRLF checkout changes the identity
            assert hashlib.sha256(data.replace(b"\n", b"\r\n")).hexdigest() != a.sha256
    records = json.loads(
        (
            REPO_ROOT
            / "services/api/src/strongstart_api/features/automation/fixtures/captures/records.json"
        ).read_text("utf-8")
    )["records"]
    directory = REPO_ROOT / "services/api/src/strongstart_api/features/automation/fixtures/captures"
    for raw in records:
        for art in raw["artifacts"]:
            if art.get("content_file") and raw["capture_id"] != "cap-fixture-tampered":
                data = (directory / art["content_file"]).read_bytes()
                assert hashlib.sha256(data).hexdigest() == art["sha256"], art["artifact_id"]


def test_bnd21_durability_policy_per_platform() -> None:
    assert durability_mode(False, "posix") == "full_posix"
    assert durability_mode(True, "nt") == "reduced_windows"
    with pytest.raises(StoreUnavailable) as exc:
        durability_mode(False, "nt")
    assert exc.value.reason == "platform_durability_unsupported"
    with pytest.raises(StoreUnavailable):
        durability_mode(True, "java")


def test_bnd21_unsupported_platform_refuses_before_any_write(tmp_path: Path) -> None:
    record, blobs = _record_and_blobs()
    with pytest.raises(StoreUnavailable):
        LocalCaptureStore(tmp_path / "c", os_name="nt").save(record, blobs)
    store = LocalVersionStore(tmp_path / "v", os_name="nt")
    with pytest.raises(StoreUnavailable):
        store.collection("demo-org", "definitions").commit(
            idempotency_key="k" * 8,
            command_hash="x",
            object_id=None,
            expected_version=0,
            build=lambda o, v, p: {},
            id_prefix="def",
        )
    assert not [p for p in tmp_path.rglob("*") if p.is_file()]


def test_bnd21_reduced_windows_mode_is_explicit_and_skips_only_dir_fsync(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[Path] = []
    monkeypatch.setattr(core, "_fsync_dir", lambda p: calls.append(p))
    record, blobs = _record_and_blobs()
    LocalCaptureStore(tmp_path / "w", allow_reduced_durability=True, os_name="nt").save(
        record, blobs
    )
    assert calls == []
    LocalCaptureStore(tmp_path / "p", os_name="posix").save(record, blobs)
    assert calls  # POSIX flushes the directory entry for every created file


def _save_variant(root: str, barrier: Any, warning: str, out: Any) -> None:
    record, blobs = _record_and_blobs()
    record = record.model_copy(update={"warnings": [*record.warnings, warning]})
    barrier.wait()
    try:
        LocalCaptureStore(Path(root)).save(record, blobs)
        out.put(("ok", warning))
    except CaptureStoreError:
        out.put(("immutable", warning))


def test_bnd21_concurrent_cross_process_captures_never_clobber(tmp_path: Path) -> None:
    ctx = multiprocessing.get_context("spawn")
    barrier, out = ctx.Barrier(2), ctx.Queue()
    procs = [
        ctx.Process(target=_save_variant, args=(str(tmp_path), barrier, f"writer-{i}", out))
        for i in range(2)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(30)
    results = [out.get(timeout=5) for _ in procs]
    winners = [w for status, w in results if status == "ok"]
    assert sorted(s for s, _ in results) == ["immutable", "ok"]
    record, _ = _record_and_blobs()
    stored = LocalCaptureStore(tmp_path).get_record(record.organization_id, record.capture_id)
    assert stored.warnings[-1] == winners[0]  # the loser did not overwrite the winner
    assert not [p for p in tmp_path.rglob(".tmp-*")]
