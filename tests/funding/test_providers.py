"""Live adapter request shapes and failure handling with injected HTTP (no network).

DISC-02 (no key -> no request), DISC-04 (limits), DISC-14 (safe errors, no retries),
DISC-15 (no key in errors/logs).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
import pytest

from strongstart_api.features.funding.providers import (
    FirecrawlCaptureProvider,
    ProviderError,
    TavilySearchProvider,
)
from strongstart_contracts.discovery import FundingErrorReason

KEY = "tvly-" + "CANARYKEY" * 3  # built at runtime: not a key-shaped literal


class Recorder:
    def __init__(self, status: int = 200, body: Any = None, exc: Exception | None = None):
        self.status, self.body, self.exc = status, body, exc
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.exc is not None:
            raise self.exc
        content = self.body if isinstance(self.body, bytes) else json.dumps(self.body).encode()
        return httpx.Response(self.status, content=content)


TAVILY_OK = {
    "query": "q",
    "results": [
        {
            "title": "T",
            "url": "https://example.org/a",
            "content": "c",
            "score": 0.81025416,
            "published_date": "Tue, 11 Mar 2025 17:00:00 GMT",
        },
        {"title": "no url"},
    ],
    "response_time": "1.67",
    "usage": {"credits": 1},
    "request_id": "req-1",
}


def test_tavily_request_is_bounded_and_explicit() -> None:
    rec = Recorder(body=TAVILY_OK)
    out = TavilySearchProvider(KEY, transport=httpx.MockTransport(rec)).search(
        "early learning", 5, 5
    )
    assert len(rec.requests) == 1
    req = rec.requests[0]
    assert str(req.url) == "https://api.tavily.com/search"
    assert req.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(req.content)
    assert body["query"] == "early learning" and body["max_results"] == 5
    assert body["include_answer"] is False and body["include_images"] is False
    assert body["auto_parameters"] is False and body["search_depth"] == "basic"
    assert body["include_raw_content"] is False
    assert out.results[0] is not None and out.results[0].score == "0.81025416"
    assert out.results[1] is None  # malformed item reported, not dropped silently
    assert out.usage_credits == "1" and out.request_id == "req-1"


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        (401, FundingErrorReason.PROVIDER_AUTH_REJECTED),
        (429, FundingErrorReason.RATE_LIMITED),
        (432, FundingErrorReason.QUOTA_EXCEEDED),
        (433, FundingErrorReason.QUOTA_EXCEEDED),
        (400, FundingErrorReason.PROVIDER_ERROR),
        (500, FundingErrorReason.PROVIDER_ERROR),
    ],
)
def test_tavily_errors_are_typed_single_attempt_and_secret_free(
    status: int, reason: FundingErrorReason, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    rec = Recorder(status=status, body={"detail": {"error": f"key {KEY} rejected"}})
    with pytest.raises(ProviderError) as info:
        TavilySearchProvider(KEY, transport=httpx.MockTransport(rec)).search("q", 5, 5)
    assert info.value.reason == reason
    assert len(rec.requests) == 1
    assert KEY not in info.value.message and KEY not in caplog.text


@pytest.mark.parametrize("body", [b"not json", {"results": "nope"}, {"other": 1}])
def test_tavily_malformed_response(body: Any) -> None:
    rec = Recorder(body=body)
    with pytest.raises(ProviderError) as info:
        TavilySearchProvider(KEY, transport=httpx.MockTransport(rec)).search("q", 5, 5)
    assert info.value.reason == FundingErrorReason.PROVIDER_ERROR


def test_tavily_timeout_is_reported_not_retried() -> None:
    rec = Recorder(exc=httpx.ReadTimeout("slow"))
    with pytest.raises(ProviderError) as info:
        TavilySearchProvider(KEY, transport=httpx.MockTransport(rec)).search("q", 5, 5)
    assert info.value.reason == FundingErrorReason.TIMEOUT and info.value.outcome_uncertain
    assert len(rec.requests) == 1


def test_oversized_provider_response_rejected() -> None:
    rec = Recorder(body=b"x" * 1_100_000)
    with pytest.raises(ProviderError, match="size limit"):
        TavilySearchProvider(KEY, transport=httpx.MockTransport(rec)).search("q", 5, 5)


FC_KEY = "fc-" + "0123456789abcdef" * 2
FC_OK = {
    "success": True,
    "data": {
        "markdown": "# Title\n\nbody",
        "html": "<main><h1>Title</h1></main>",
        "rawHtml": "<html><body><main><h1>Title</h1></main></body></html>",
        "metadata": {
            "title": "Title",
            "sourceURL": "https://example.org/a",
            "url": "https://example.org/a",
            "statusCode": 200,
            "contentType": "text/html",
            "scrapeId": "s-1",
            "cookie": "secret",
        },
    },
}


def test_firecrawl_request_is_single_page_no_actions_no_cache() -> None:
    rec = Recorder(body=FC_OK)
    out = FirecrawlCaptureProvider(FC_KEY, transport=httpx.MockTransport(rec)).capture(
        "https://example.org/a", 45, 2_000_000
    )
    assert len(rec.requests) == 1
    body = json.loads(rec.requests[0].content)
    assert str(rec.requests[0].url) == "https://api.firecrawl.dev/v2/scrape"
    assert body["formats"] == ["markdown", "html", "rawHtml"]
    assert "actions" not in body and body["parsers"] == []
    assert body["maxAge"] == 0 and body["storeInCache"] is False and body["proxy"] == "basic"
    assert 1000 <= body["timeout"] < 45_000
    assert out.markdown and out.raw_html and out.request_id == "s-1"
    assert "cookie" not in out.metadata  # only allowlisted metadata retained


@pytest.mark.parametrize(
    ("status", "body", "reason"),
    [
        (
            402,
            {"success": False, "code": "insufficient_credits"},
            FundingErrorReason.QUOTA_EXCEEDED,
        ),
        (429, {"success": False}, FundingErrorReason.RATE_LIMITED),
        (200, {"success": False, "error": "x"}, FundingErrorReason.PROVIDER_ERROR),
        (200, {"success": True}, FundingErrorReason.PROVIDER_ERROR),
    ],
)
def test_firecrawl_failures(status: int, body: Any, reason: FundingErrorReason) -> None:
    rec = Recorder(status=status, body=body)
    with pytest.raises(ProviderError) as info:
        FirecrawlCaptureProvider(FC_KEY, transport=httpx.MockTransport(rec)).capture(
            "https://example.org/a", 45, 2_000_000
        )
    assert info.value.reason == reason and len(rec.requests) == 1


def test_firecrawl_timeout_marks_outcome_unknown() -> None:
    rec = Recorder(exc=httpx.ReadTimeout("slow"))
    with pytest.raises(ProviderError) as info:
        FirecrawlCaptureProvider(FC_KEY, transport=httpx.MockTransport(rec)).capture(
            "https://example.org/a", 45, 2_000_000
        )
    assert info.value.reason == FundingErrorReason.OUTCOME_UNKNOWN
    assert info.value.outcome_uncertain and len(rec.requests) == 1
