"""SEC-06 bootstrap boundary: provider keys stay out of the web source and repo files.

A clean scan is not proof that no secrets exist; it catches known patterns/canaries only.
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.conftest import REPO_ROOT

KEY_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),  # Google API key shape
    re.compile(r"\btvly-[0-9A-Za-z]{20,}"),
    re.compile(r"\bfc-[0-9a-f]{32}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{32,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
SKIP_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    ".bootstrap-input",
    "dist",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "__pycache__",
}
SKIP_FILES = {"package-lock.json", "uv.lock"}


def _files() -> list[Path]:
    out = []
    for path in REPO_ROOT.rglob("*"):
        if any(part in SKIP_DIRS for part in path.relative_to(REPO_ROOT).parts):
            continue
        if path.is_file() and path.name not in SKIP_FILES and path.name != ".env":
            out.append(path)
    return out


def test_no_known_key_patterns_in_repo_files() -> None:
    hits = []
    for path in _files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits += [f"{path}: {p.pattern}" for p in KEY_PATTERNS if p.search(text)]
    assert hits == []


def test_web_source_never_references_server_settings() -> None:
    web = REPO_ROOT / "apps/web"
    for path in [*web.glob("src/**/*.ts*"), *web.glob("*.ts"), *web.glob("dist/**/*.js")]:
        text = path.read_text(encoding="utf-8")
        assert "STRONGSTART_" not in text, path
        assert "API_KEY" not in text, path


def test_detector_catches_dummy_canary() -> None:
    canary = "AIza" + "A" * 35
    assert any(p.search(f"key={canary}") for p in KEY_PATTERNS)
