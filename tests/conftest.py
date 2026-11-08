from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = REPO_ROOT / "tests/fixtures/demo/demo-bundle-v1.json"


@pytest.fixture
def bundle_json() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    return data


pytest_plugins = ["tests.integration.a4_support"]
