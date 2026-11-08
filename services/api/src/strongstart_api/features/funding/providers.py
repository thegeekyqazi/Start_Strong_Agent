"""Search/capture provider ports and adapters (B1-DISC-001 s4-s6).

Live adapters: Tavily Search (``POST https://api.tavily.com/search``) and Firecrawl
single-page scrape (``POST https://api.firecrawl.dev/v2/scrape``). Request fields
were checked against the official API reference pages on 2026-11-07.

Budgets enforced here (project budgets, not vendor limits): one provider HTTP request
per explicit operation, **no automatic retries**, hard client timeouts, a byte cap on
the response body and no redirect following. A timeout is reported as an uncertain
outcome; it is not evidence that the vendor cancelled the work or charged nothing.
API keys are only placed in the Authorization header and never logged or returned.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from importlib import resources
from typing import Any, Protocol

import httpx

from strongstart_contracts.discovery import FundingErrorReason

from .normalize import normalize_url

TAVILY_ENDPOINT = "https://api.tavily.com/search"
FIRECRAWL_ENDPOINT = "https://api.firecrawl.dev/v2/scrape"
MAX_SEARCH_RESPONSE_BYTES = 1_000_000


class ProviderError(Exception):
    def __init__(
        self,
        reason: FundingErrorReason,
        message: str,
        *,
        provider_http_status: int | None = None,
        outcome_uncertain: bool = False,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.provider_http_status = provider_http_status
        self.outcome_uncertain = outcome_uncertain


@dataclass(frozen=True)
class RawSearchResult:
    title: str
    url: str
    content: str
    score: str | None
    published_date: str | None


@dataclass(frozen=True)
class ProviderSearchResponse:
    results: list[RawSearchResult | None]  # None = malformed item (kept for omission report)
    requested_params: dict[str, str | int | bool]
    http_status: int | None
    request_id: str | None = None
    response_time: str | None = None
    usage_credits: str | None = None


@dataclass(frozen=True)
class ProviderCaptureResponse:
    markdown: str | None
    html: str | None
    raw_html: str | None
    metadata: dict[str, str | int | None]
    warning: str | None
    requested_params: dict[str, str | int | bool | list[str]]
    request_id: str | None = None


class SearchProvider(Protocol):
    name: str
    mode: str
    is_fixture: bool

    def search(self, query: str, max_results: int, timeout_s: float) -> ProviderSearchResponse: ...


class CaptureProvider(Protocol):
    name: str
    mode: str
    is_fixture: bool

    def is_registered_fixture_url(self, url: str) -> bool: ...

    def capture(self, url: str, timeout_s: float, max_bytes: int) -> ProviderCaptureResponse: ...


# ----------------------------------------------------------------------------- HTTP


def _bounded_post(
    url: str,
    payload: dict[str, Any],
    api_key: str,
    timeout_s: float,
    max_bytes: int,
    transport: httpx.BaseTransport | None,
    *,
    timeout_reason: FundingErrorReason,
) -> tuple[int, Any]:
    deadline = time.monotonic() + timeout_s
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        with (
            httpx.Client(
                transport=transport, timeout=httpx.Timeout(timeout_s), follow_redirects=False
            ) as client,
            client.stream("POST", url, json=payload, headers=headers) as response,
        ):
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > max_bytes:
                    raise ProviderError(
                        FundingErrorReason.PROVIDER_ERROR,
                        "provider response exceeded the size limit",
                        provider_http_status=response.status_code,
                    )
                if time.monotonic() > deadline:
                    raise httpx.ReadTimeout("deadline exceeded")
            status = response.status_code
    except httpx.TimeoutException:
        raise ProviderError(
            timeout_reason,
            "provider request timed out; the outcome (and any charge) is unknown",
            outcome_uncertain=True,
        ) from None
    except httpx.HTTPError:
        raise ProviderError(
            FundingErrorReason.PROVIDER_ERROR, "provider could not be reached"
        ) from None
    try:
        data = json.loads(bytes(body)) if body else None
    except ValueError:
        data = None
    return status, data


def _map_status(status: int) -> ProviderError:
    if status in (401, 403):
        return ProviderError(
            FundingErrorReason.PROVIDER_AUTH_REJECTED,
            "provider rejected the configured credentials",
            provider_http_status=status,
        )
    if status == 429:
        return ProviderError(
            FundingErrorReason.RATE_LIMITED, "provider rate limit reached", provider_http_status=429
        )
    if status in (402, 432, 433):
        return ProviderError(
            FundingErrorReason.QUOTA_EXCEEDED,
            "provider plan/usage limit reached",
            provider_http_status=status,
        )
    return ProviderError(
        FundingErrorReason.PROVIDER_ERROR,
        f"provider returned HTTP {status}",
        provider_http_status=status,
    )


def _decimal_string(value: Any) -> str | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        dec = Decimal(str(value))
    except InvalidOperation:
        return None
    if not dec.is_finite():
        return None
    text = format(dec.normalize(), "f")
    return "0" if text in ("-0", "") else text


def _str_or_none(value: Any, limit: int = 2048) -> str | None:
    return value[:limit] if isinstance(value, str) and value else None


# ----------------------------------------------------------------------------- Tavily


@dataclass
class TavilySearchProvider:
    api_key: str
    transport: httpx.BaseTransport | None = None
    name: str = "tavily"
    mode: str = "live"
    is_fixture: bool = False

    def search(self, query: str, max_results: int, timeout_s: float) -> ProviderSearchResponse:
        params: dict[str, str | int | bool] = {
            "search_depth": "basic",
            "topic": "general",
            "max_results": max_results,
            "chunks_per_source": 2,
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
            "include_image_descriptions": False,
            "include_favicon": False,
            "include_published_date": True,
            "auto_parameters": False,
            "include_usage": True,
        }
        status, data = _bounded_post(
            TAVILY_ENDPOINT,
            {"query": query, **params},
            self.api_key,
            timeout_s,
            MAX_SEARCH_RESPONSE_BYTES,
            self.transport,
            timeout_reason=FundingErrorReason.TIMEOUT,
        )
        if status != 200:
            raise _map_status(status)
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise ProviderError(
                FundingErrorReason.PROVIDER_ERROR,
                "provider returned a malformed search response",
                provider_http_status=status,
            )
        results: list[RawSearchResult | None] = []
        for item in data["results"][:max_results]:
            if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                results.append(None)
                continue
            results.append(
                RawSearchResult(
                    title=_str_or_none(item.get("title"), 500) or "(untitled)",
                    url=item["url"][:2048],
                    content=_str_or_none(item.get("content"), 4000) or "",
                    score=_decimal_string(item.get("score")),
                    published_date=_str_or_none(item.get("published_date"), 100),
                )
            )
        usage = data.get("usage")
        return ProviderSearchResponse(
            results=results,
            requested_params=params,
            http_status=status,
            request_id=_str_or_none(data.get("request_id"), 100),
            response_time=_str_or_none(str(data.get("response_time") or ""), 32),
            usage_credits=_decimal_string(usage.get("credits"))
            if isinstance(usage, dict)
            else None,
        )


# -------------------------------------------------------------------------- Firecrawl

SAFE_METADATA_KEYS = ("title", "language", "sourceURL", "url", "statusCode", "contentType", "error")


@dataclass
class FirecrawlCaptureProvider:
    api_key: str
    transport: httpx.BaseTransport | None = None
    name: str = "firecrawl"
    mode: str = "live"
    is_fixture: bool = False

    def is_registered_fixture_url(self, url: str) -> bool:
        return False

    def capture(self, url: str, timeout_s: float, max_bytes: int) -> ProviderCaptureResponse:
        provider_timeout_ms = max(1000, int((timeout_s - 3) * 1000))
        params: dict[str, str | int | bool | list[str]] = {
            "formats": ["markdown", "html", "rawHtml"],
            "onlyMainContent": True,
            "maxAge": 0,
            "storeInCache": False,
            "proxy": "basic",
            "blockAds": True,
            "removeBase64Images": True,
            "parsers": [],
            "timeout": provider_timeout_ms,
        }
        status, data = _bounded_post(
            FIRECRAWL_ENDPOINT,
            {"url": url, **params},
            self.api_key,
            timeout_s,
            max_bytes * 4 + 200_000,
            self.transport,
            timeout_reason=FundingErrorReason.OUTCOME_UNKNOWN,
        )
        if status != 200:
            raise _map_status(status)
        if not isinstance(data, dict) or data.get("success") is not True:
            raise ProviderError(
                FundingErrorReason.PROVIDER_ERROR,
                "provider reported an unsuccessful or malformed scrape",
                provider_http_status=status,
            )
        body = data.get("data")
        if not isinstance(body, dict):
            raise ProviderError(
                FundingErrorReason.PROVIDER_ERROR, "provider scrape response had no data"
            )
        raw_meta = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        assert isinstance(raw_meta, dict)
        metadata: dict[str, str | int | None] = {}
        for key in SAFE_METADATA_KEYS:
            value = raw_meta.get(key)
            if isinstance(value, bool):
                continue
            if isinstance(value, int):
                metadata[key] = value
            elif isinstance(value, str):
                metadata[key] = value[:2048]
        return ProviderCaptureResponse(
            markdown=body.get("markdown") if isinstance(body.get("markdown"), str) else None,
            html=body.get("html") if isinstance(body.get("html"), str) else None,
            raw_html=body.get("rawHtml") if isinstance(body.get("rawHtml"), str) else None,
            metadata=metadata,
            warning=_str_or_none(body.get("warning"), 1000),
            requested_params=params,
            request_id=_str_or_none(raw_meta.get("scrapeId"), 100),
        )


# ---------------------------------------------------------------------------- Fixture

FIXTURE_PACKAGE = "strongstart_api.features.funding.fixture_data"


def _fixture_json(name: str) -> Any:
    return json.loads(resources.files(FIXTURE_PACKAGE).joinpath(name).read_text("utf-8"))


@dataclass
class FixtureSearchProvider:
    """FIXTURE: synthetic, deterministic results. Never used as a live fallback."""

    name: str = "fixture-search"
    mode: str = "fixture"
    is_fixture: bool = True
    calls: list[dict[str, Any]] = field(default_factory=list)

    def search(self, query: str, max_results: int, timeout_s: float) -> ProviderSearchResponse:
        self.calls.append({"query": query, "max_results": max_results})
        data = _fixture_json("search_results.json")
        results: list[RawSearchResult | None] = []
        for item in data["results"][:max_results]:
            if not isinstance(item.get("url"), str):
                results.append(None)
                continue
            results.append(
                RawSearchResult(
                    title=item["title"],
                    url=item["url"],
                    content=item["content"],
                    score=_decimal_string(item.get("score")),
                    published_date=item.get("published_date"),
                )
            )
        return ProviderSearchResponse(
            results=results,
            requested_params={"max_results": max_results, "fixture": True},
            http_status=None,
            request_id="fixture",
        )


@dataclass
class FixtureCaptureProvider:
    """FIXTURE: returns synthetic pages only for registered fixture URLs."""

    name: str = "fixture-capture"
    mode: str = "fixture"
    is_fixture: bool = True

    def _catalog(self) -> dict[str, dict[str, Any]]:
        data = _fixture_json("capture_catalog.json")
        return {normalize_url(entry["url"]): entry for entry in data["pages"]}

    def is_registered_fixture_url(self, url: str) -> bool:
        return normalize_url(url) in self._catalog()

    def capture(self, url: str, timeout_s: float, max_bytes: int) -> ProviderCaptureResponse:
        entry = self._catalog().get(normalize_url(url))
        if entry is None:
            raise ProviderError(
                FundingErrorReason.INVALID_INPUT,
                "fixture mode can capture only registered fixture URLs",
            )
        files = resources.files(FIXTURE_PACKAGE).joinpath("pages")

        def read(name: str | None) -> str | None:
            return files.joinpath(name).read_text("utf-8") if name else None

        return ProviderCaptureResponse(
            markdown=read(entry.get("markdown_file")),
            html=read(entry.get("html_file")),
            raw_html=read(entry.get("raw_html_file")),
            metadata=dict(entry["metadata"]),
            warning=entry.get("warning"),
            requested_params={"fixture": True},
            request_id="fixture",
        )
