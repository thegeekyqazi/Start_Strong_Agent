"""Archive extraction stays inside target (SEC-04 bootstrap boundary; SKL-03 principle)."""

from __future__ import annotations

import stat
import zipfile
from pathlib import Path

import pytest

from scripts.import_kit import ArchiveRejected, import_kit


def _zip(path: Path, entries: list[tuple[str, bytes, int]]) -> Path:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data, mode in entries:
            info = zipfile.ZipInfo(name)
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, data)
    return path


REG = stat.S_IFREG | 0o644


def test_ordinary_kit_files_import(tmp_path: Path) -> None:
    archive = _zip(
        tmp_path / "kit.zip", [("AGENTS.md", b"a", REG), ("docs/specs/README.md", b"s", REG)]
    )
    target = tmp_path / "repo"
    target.mkdir()
    report = import_kit(archive, target)
    assert sorted(report.created) == ["AGENTS.md", "docs/specs/README.md"]
    assert (target / "docs/specs/README.md").read_bytes() == b"s"


def test_existing_edits_are_not_overwritten(tmp_path: Path) -> None:
    archive = _zip(tmp_path / "kit.zip", [("AGENTS.md", b"kit", REG), ("CLAUDE.md", b"same", REG)])
    target = tmp_path / "repo"
    target.mkdir()
    (target / "AGENTS.md").write_bytes(b"owner edit")
    (target / "CLAUDE.md").write_bytes(b"same")
    report = import_kit(archive, target)
    assert report.conflicts == ["AGENTS.md"]
    assert report.identical == ["CLAUDE.md"]
    assert (target / "AGENTS.md").read_bytes() == b"owner edit"


@pytest.mark.parametrize(
    ("name", "mode"),
    [
        ("../escape.md", REG),
        ("/abs/AGENTS.md", REG),
        ("docs/../../x.md", REG),
        ("AGENTS.md", stat.S_IFLNK | 0o777),
        ("AGENTS.md", stat.S_IFREG | 0o755),
        ("docs/run.sh", REG),
        ("docs/unexpected.md", REG),
    ],
)
def test_hostile_entries_rejected_without_writing(tmp_path: Path, name: str, mode: int) -> None:
    archive = _zip(tmp_path / "bad.zip", [("CLAUDE.md", b"ok", REG), (name, b"x", mode)])
    target = tmp_path / "repo"
    target.mkdir()
    with pytest.raises(ArchiveRejected):
        import_kit(archive, target)
    assert list(target.iterdir()) == []
    assert not (tmp_path / "escape.md").exists()


def test_oversize_entry_rejected(tmp_path: Path) -> None:
    archive = _zip(tmp_path / "big.zip", [("AGENTS.md", b"\0" * 2_000_000, REG)])
    with pytest.raises(ArchiveRejected):
        import_kit(archive, tmp_path)


def test_sha256_mismatch_is_reported_not_hidden(tmp_path: Path) -> None:
    archive = _zip(tmp_path / "kit.zip", [("AGENTS.md", b"a", REG)])
    target = tmp_path / "repo"
    target.mkdir()
    report = import_kit(archive, target, expected_sha256="0" * 64, dry_run=True)
    assert report.sha256_matches is False
    assert not (target / "AGENTS.md").exists()
