"""Safely import the StrongStart agent repo kit ZIP into a target directory.

INIT-001 section 2 / bootstrap boundary of SEC-04 (not full upload/parser containment).

The archive is treated as untrusted data:
- every entry is listed and validated before anything is written;
- absolute paths, ``..`` traversal, drive letters, symlinks, special files,
  executable bits, unexpected paths and excessive sizes are rejected;
- entries are extracted into a staging directory first, then compared with
  existing target files; an existing file that differs is never overwritten
  (it is reported as a conflict for explicit reconciliation);
- nothing from the archive is executed.

Usage: python scripts/import_kit.py ARCHIVE TARGET_DIR [--expected-sha256 HEX] [--dry-run]
Exit status: 0 imported/identical, 1 rejected archive, 2 conflicts left for manual review.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import stat
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

EXPECTED_PATHS = frozenset(
    {
        "AGENTS.md",
        "CLAUDE.md",
        ".github/PULL_REQUEST_TEMPLATE.md",
        "docs/coordination/README.md",
        "docs/decisions/0001-agent-working-agreement.md",
        "docs/decisions/TEMPLATE.md",
        "docs/handoffs/TEMPLATE.md",
        "docs/specs/README.md",
        "docs/engineering/StrongStart_Engineering_Plan.md",
        "docs/engineering/StrongStart_Check_Catalog.json",
    }
)
ALLOWED_SUFFIXES = frozenset({".md", ".json"})
MAX_ENTRY_BYTES = 1_000_000
MAX_TOTAL_BYTES = 5_000_000
MAX_ENTRIES = 50
MAX_COMPRESSION_RATIO = 100


class ArchiveRejected(Exception):
    """The archive failed validation; nothing was written to the target."""


@dataclass
class ImportReport:
    archive_sha256: str
    sha256_matches: bool | None
    created: list[str] = field(default_factory=list)
    identical: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_name(name: str) -> str:
    if not name or "\x00" in name or "\\" in name:
        raise ArchiveRejected(f"invalid entry name: {name!r}")
    if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
        raise ArchiveRejected(f"absolute path rejected: {name!r}")
    parts = PurePosixPath(name).parts
    if any(part in ("..", ".") for part in parts) or not parts:
        raise ArchiveRejected(f"path traversal rejected: {name!r}")
    return str(PurePosixPath(*parts))


def validate_archive(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    """Return validated file entries or raise ArchiveRejected."""
    infos = zf.infolist()
    if len(infos) > MAX_ENTRIES:
        raise ArchiveRejected(f"too many entries: {len(infos)}")
    total = 0
    files: list[zipfile.ZipInfo] = []
    seen: set[str] = set()
    for info in infos:
        name = _validate_name(info.filename.rstrip("/") if info.is_dir() else info.filename)
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ArchiveRejected(f"symlink rejected: {name!r}")
        if mode and not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ArchiveRejected(f"special file rejected: {name!r}")
        if info.is_dir():
            continue
        if mode & 0o111:
            raise ArchiveRejected(f"executable entry rejected: {name!r}")
        if name not in EXPECTED_PATHS or PurePosixPath(name).suffix not in ALLOWED_SUFFIXES:
            raise ArchiveRejected(f"unexpected entry rejected: {name!r}")
        if name in seen:
            raise ArchiveRejected(f"duplicate entry rejected: {name!r}")
        seen.add(name)
        if info.file_size > MAX_ENTRY_BYTES:
            raise ArchiveRejected(f"entry too large: {name!r} ({info.file_size} bytes)")
        if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise ArchiveRejected(f"suspicious compression ratio: {name!r}")
        total += info.file_size
        if total > MAX_TOTAL_BYTES:
            raise ArchiveRejected("archive expands beyond the size limit")
        files.append(info)
    return files


def import_kit(
    archive: Path, target: Path, expected_sha256: str | None = None, dry_run: bool = False
) -> ImportReport:
    digest = sha256_file(archive)
    report = ImportReport(
        archive_sha256=digest,
        sha256_matches=None if expected_sha256 is None else digest == expected_sha256.lower(),
    )
    target = target.resolve()
    with zipfile.ZipFile(archive) as zf, tempfile.TemporaryDirectory() as staging_dir:
        staging = Path(staging_dir)
        for info in validate_archive(zf):
            dest = (staging / info.filename).resolve()
            if staging.resolve() not in dest.parents:
                raise ArchiveRejected(f"entry escapes staging: {info.filename!r}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, dest.open("wb") as out:
                copied = 0
                while chunk := src.read(65536):
                    copied += len(chunk)
                    if copied > MAX_ENTRY_BYTES:
                        raise ArchiveRejected(f"entry exceeded declared size: {info.filename!r}")
                    out.write(chunk)
        for staged in sorted(p for p in staging.rglob("*") if p.is_file()):
            rel = staged.relative_to(staging).as_posix()
            existing = target / rel
            if existing.is_symlink():
                report.conflicts.append(rel)
            elif existing.exists():
                if existing.read_bytes() == staged.read_bytes():
                    report.identical.append(rel)
                else:
                    report.conflicts.append(rel)
            else:
                report.created.append(rel)
                if not dry_run:
                    existing.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(staged, existing)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("archive", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = import_kit(args.archive, args.target, args.expected_sha256, args.dry_run)
    except (ArchiveRejected, zipfile.BadZipFile) as exc:
        print(f"REJECTED: {exc}", file=sys.stderr)
        return 1
    print(f"archive sha256: {report.archive_sha256}")
    if report.sha256_matches is False:
        print("WARNING: sha256 differs from the expected reference; inspect before trusting.")
    for label, items in (
        ("created", report.created),
        ("identical", report.identical),
        ("conflict", report.conflicts),
    ):
        for item in items:
            print(f"{label}: {item}")
    return 2 if report.conflicts else 0


if __name__ == "__main__":
    raise SystemExit(main())
