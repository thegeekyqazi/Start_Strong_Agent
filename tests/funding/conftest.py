"""Funding test helpers. Every client uses a per-test temp capture store (no shared data)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.funding import deps as funding_router

PUBLIC_RESOLVER: Callable[[str], Iterable[str]] = lambda host: ["93.184.215.14"]  # noqa: E731

ClientFactory = Callable[..., TestClient]


@pytest.fixture
def make_client(tmp_path: Path) -> ClientFactory:
    def factory(
        *,
        search_provider: Any = "default",
        capture_provider: Any = "default",
        resolver: Callable[[str], Iterable[str]] = PUBLIC_RESOLVER,
        **settings_overrides: Any,
    ) -> TestClient:
        settings_overrides.setdefault("auth_mode", "fixture")
        settings_overrides.setdefault("funding_capture_store_dir", tmp_path / "captures")
        settings = Settings(_env_file=None, **settings_overrides)
        app = create_app(settings)
        if search_provider != "default":
            app.dependency_overrides[funding_router.get_search_provider] = lambda: search_provider
        if capture_provider != "default":
            app.dependency_overrides[funding_router.get_capture_provider] = lambda: capture_provider
        app.dependency_overrides[funding_router.get_resolver] = lambda: resolver
        return TestClient(app)

    return factory


FIXTURE_MODES = {"funding_search_mode": "fixture", "funding_capture_mode": "fixture"}
PROFILE = {"profile": {"interests": ["early learning"], "geography": "Demo Region"}}
GRANT_URL = "https://demo-funder.example/programs/community-grants"
