"""SEC-06 canary: a dummy Gemini key never appears in responses or the web bundle.

A clean scan catches known canaries/patterns only; it is not proof that no secret exists.
"""

from __future__ import annotations

import httpx
from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.applications.models.gemini import GeminiAdapter
from strongstart_api.features.applications.router import get_model_adapter
from tests.conftest import REPO_ROOT

from .conftest import DRAFT_BODY, DRAFT_URL, recording_transport

CANARY = "AIza" + "CANARY0canary0CANARY0canary0CANARY0c"[:35]


def _client(status: int) -> TestClient:
    settings = Settings(
        _env_file=None,
        auth_mode="fixture",
        model_provider="gemini",
        gemini_api_key=CANARY,
        gemini_model="demo-model",
    )
    # Provider echoes the key back in its error body: it must not reach our response.
    transport, _ = recording_transport(lambda r: httpx.Response(status, text=f"bad key {CANARY}"))
    app = create_app(settings)
    app.dependency_overrides[get_model_adapter] = lambda: GeminiAdapter(
        settings.gemini_api_key, settings.gemini_model, 5, transport
    )
    return TestClient(app)


def test_canary_absent_from_every_applications_response() -> None:
    for status in (200, 401, 429, 500):
        c = _client(status)
        responses = [
            c.post(DRAFT_URL, json=DRAFT_BODY),
            c.get("/api/applications/workspace"),
            c.get("/api/applications/status"),
            c.get("/api/capabilities"),
            c.get("/api/session"),
            c.get("/openapi.json"),
        ]
        for r in responses:
            assert CANARY not in r.text
            assert all(CANARY not in v for v in r.headers.values())


def test_canary_absent_from_web_source_and_any_built_bundle() -> None:
    # dist/ exists only after `make build`; a fresh checkout scans source only.
    web = REPO_ROOT / "apps/web"
    files = [*web.glob("src/**/*.ts*"), *web.glob("dist/**/*.js"), *web.glob("dist/**/*.html")]
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert CANARY not in text, path
