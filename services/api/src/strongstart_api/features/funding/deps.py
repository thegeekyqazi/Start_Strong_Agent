"""Injectable funding dependencies (override with ``app.dependency_overrides`` in tests)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from ...config import Settings, get_settings
from .providers import (
    CaptureProvider,
    FirecrawlCaptureProvider,
    FixtureCaptureProvider,
    FixtureSearchProvider,
    SearchProvider,
    TavilySearchProvider,
)
from .store import LocalCaptureStore
from .url_policy import Resolver, system_resolver


def get_search_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SearchProvider | None:
    if settings.funding_search_mode == "fixture":
        return FixtureSearchProvider()
    key = settings.tavily_api_key.get_secret_value() if settings.tavily_api_key else ""
    return TavilySearchProvider(api_key=key) if key else None


def get_capture_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CaptureProvider | None:
    if settings.funding_capture_mode == "fixture":
        return FixtureCaptureProvider()
    key = settings.firecrawl_api_key.get_secret_value() if settings.firecrawl_api_key else ""
    return FirecrawlCaptureProvider(api_key=key) if key else None


def get_capture_store(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LocalCaptureStore | None:
    if settings.environment == "production":
        return None  # development-only store; no supported production store yet (Dev A)
    return LocalCaptureStore(settings.funding_capture_store_dir)


def get_resolver() -> Resolver:
    return system_resolver
