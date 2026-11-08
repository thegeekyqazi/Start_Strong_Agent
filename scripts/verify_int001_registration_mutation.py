"""Run the real PostgreSQL race with registration locks removed, then restore exactly.

Requires STRONGSTART_DATABASE_URL. Never edits activation or test assertions. Bounded
subprocesses and finally restoration protect the worktree even if the audit fails.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "services/api/src/strongstart_api/features/knowledge/packs.py"
TEST = (
    "tests/smoke/test_int001_a4.py::"
    "test_registration_lock_serializes_replacement_and_prevents_stale_registration"
)


def run() -> int:
    original = SOURCE.read_bytes()
    digest = hashlib.sha256(original).hexdigest()
    text = original.decode()
    start = text.index("    def register_browser_target(")
    end = text.index("    def get_target(", start)
    section = text[start:end]
    assert section.count(".with_for_update()") == 3
    mutant = section.replace(".with_for_update()", "")
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
            or "stale_registration: replacement missed the new target" not in output
        ):
            raise RuntimeError("mutation was not caught for the intended stale-registration reason")
    finally:
        SOURCE.write_bytes(original)
        assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == digest
        print("Exact source restored; SHA-256:", digest)
    restored = subprocess.run(command, cwd=ROOT, timeout=90, check=False)  # noqa: S603
    return restored.returncode


if __name__ == "__main__":
    raise SystemExit(run())
