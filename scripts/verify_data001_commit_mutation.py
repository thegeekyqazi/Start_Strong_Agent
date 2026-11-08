"""Disable only the C commit predicate, prove stale-export publication, restore exactly.

Requires STRONGSTART_DATABASE_URL. Never edits tests or other serialization guards. Bounded
subprocesses and finally restoration protect the worktree even if the audit fails.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "services/api/src/strongstart_api/features/applications/postgres_store.py"
TEST = "tests/smoke/test_data001_processes.py::test_commit_guard_rejects_stale_reviewed_export"


def run() -> int:
    original = SOURCE.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    text = original.decode()
    marker = "# DATA-001 COMMIT GUARD: mutation audit disables this predicate only."
    start = text.index(marker)
    end = text.index("                    yield", start)
    section = text[start:end]
    assert section.count("if expected is not None and (") == 1
    mutant = section.replace("if expected is not None and (", "if False and (")
    command = [sys.executable, "-m", "pytest", "-m", "db", "-q", TEST]
    try:
        SOURCE.write_text(text[:start] + mutant + text[end:])
        result = subprocess.run(  # noqa: S603 - fixed Python/pytest command, no user executable
            command,
            cwd=ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        output = result.stdout + result.stderr
        print(output)
        if (
            result.returncode == 0
            or "stale_export_publication: reviewed export committed" not in output
        ):
            raise RuntimeError("mutation was not caught for the intended stale-export reason")
    finally:
        SOURCE.write_bytes(original)
        assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == digest
        print("Exact source restored; SHA-256:", digest)
    restored = subprocess.run(command, cwd=ROOT, timeout=90, check=False)  # noqa: S603
    return restored.returncode


if __name__ == "__main__":
    raise SystemExit(run())
