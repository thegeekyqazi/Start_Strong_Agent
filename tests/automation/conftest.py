"""Shared helpers for B2-AUTO-001 automation tests (intake, capture seam, inspection)."""

from __future__ import annotations

import hashlib
import json
import socket
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.automation import router as automation_router
from strongstart_api.features.automation.registry import FIXTURE_DIR

DEFINITION_PATH = FIXTURE_DIR / "definitions/rep-portal-definition-v1.json"
PORTAL_PATH = FIXTURE_DIR / "portal/rep-portal-v1.html"
CAPTURE_DIR = FIXTURE_DIR / "captures"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


_STORE = Path(tempfile.mkdtemp(prefix="b2-test-b1-store-"))


def make_client(**settings: Any) -> TestClient:
    # Isolated (empty) B1 capture store: never read or write the shared .local-data dir.
    settings.setdefault("funding_capture_store_dir", _STORE)
    return TestClient(create_app(Settings(_env_file=None, **settings)))


@pytest.fixture
def fixture_client() -> TestClient:
    return make_client(auth_mode="fixture")


def definition() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(DEFINITION_PATH.read_text(encoding="utf-8"))
    return data


def intake_json(client: TestClient, content: str) -> Any:
    return client.post(
        "/api/automation/intake", json={"source": {"mode": "structured_json", "content": content}}
    )


def by_id(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {q["question_id"]: q for q in result["questions"]}


def codes(result: dict[str, Any], question_id: str | None = None) -> set[str]:
    return {
        f["code"]
        for f in result["findings"]
        if question_id is None or f.get("question_id") == question_id
    }


@pytest.fixture
def no_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[Any]]:
    """Fail loudly if code under test opens any outbound socket or resolves a name."""
    attempts: list[Any] = []

    def deny_connect(self: socket.socket, address: Any) -> None:
        attempts.append(address)
        raise AssertionError(f"unexpected network connect to {address!r}")

    def deny_resolve(*args: Any, **kwargs: Any) -> Any:
        attempts.append(args[:2])
        raise AssertionError("unexpected DNS resolution")

    monkeypatch.setattr(socket.socket, "connect", deny_connect)
    monkeypatch.setattr(socket, "getaddrinfo", deny_resolve)
    yield attempts


__all__ = [
    "CAPTURE_DIR",
    "DEFINITION_PATH",
    "PORTAL_PATH",
    "Path",
    "automation_router",
]
