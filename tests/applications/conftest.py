"""Shared helpers for C1 tests (applications feature, owner C)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.applications.models.base import ModelAdapter
from strongstart_api.features.applications.router import get_model_adapter

DRAFT_URL = "/api/applications/questions/mission-q1/draft"
DRAFT_BODY = {"question_version": 1, "evidence_bundle_id": "demo-evidence-a-v1"}
FACT = "demo-fact-children-served"


def make_client(adapter: ModelAdapter | None = None, **overrides: Any) -> TestClient:
    overrides.setdefault(
        "answer_store_backend",
        "unconfigured" if overrides.get("environment") == "production" else "memory",
    )
    settings = Settings(_env_file=None, **overrides)
    app = create_app(settings)
    if adapter is not None:
        app.dependency_overrides[get_model_adapter] = lambda: adapter
    return TestClient(app)


def gemini_response(text: str) -> dict[str, Any]:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def recording_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    return httpx.MockTransport(wrapped), seen
