"""GeminiAdapter: disabled without key/model, no fallback, key only in header (C1 spec s4)."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from pydantic import SecretStr

from strongstart_api.features.applications.models.base import (
    ModelTimeout,
    ModelTransportError,
    StructuredTask,
)
from strongstart_api.features.applications.models.gemini import GeminiAdapter
from strongstart_contracts import CapabilityUnavailable

from .conftest import DRAFT_BODY, DRAFT_URL, FACT, gemini_response, make_client, recording_transport

KEY = SecretStr("test-dummy-key-not-real")
VALID = json.dumps(
    {"text": f"Served {{{{fact:{FACT}}}}}.", "fact_ids": [FACT], "uncertainties": []}
)


def _task() -> StructuredTask:
    return StructuredTask("t", "draft_answer", "x", {"allowed_facts": []}, {})


def _never_called(_: httpx.Request) -> httpx.Response:
    raise AssertionError("no network call expected")


@pytest.mark.parametrize(("key", "model"), [(None, "m"), (SecretStr(""), "m"), (KEY, None)])
def test_unconfigured_is_capability_unavailable_without_network(
    key: SecretStr | None, model: str | None
) -> None:
    transport, seen = recording_transport(_never_called)
    adapter = GeminiAdapter(key, model, 5, transport)
    with pytest.raises(CapabilityUnavailable):
        adapter.capabilities()
    with pytest.raises(CapabilityUnavailable):
        asyncio.run(adapter.complete(_task()))
    assert seen == []


def test_app_starts_with_gemini_and_no_key_and_never_falls_back() -> None:
    client = make_client(auth_mode="fixture", model_provider="gemini")
    assert client.get("/health/live").status_code == 200
    caps = {c["feature"]: c for c in client.get("/api/capabilities").json()["capabilities"]}
    assert caps["applications.model"]["status"] == "unavailable"
    r = client.post(DRAFT_URL, json=DRAFT_BODY)
    assert r.status_code == 503
    assert r.json()["code"] == "capability_unavailable"
    assert "fake" not in r.text  # no silent fake fallback


def test_key_sent_in_header_not_url_and_output_validated() -> None:
    transport, seen = recording_transport(
        lambda _: httpx.Response(200, json=gemini_response(VALID))
    )
    adapter = GeminiAdapter(KEY, "demo-model", 5, transport)
    client = make_client(adapter, auth_mode="fixture", model_provider="gemini")
    r = client.post(DRAFT_URL, json=DRAFT_BODY)
    assert r.status_code == 200, r.text
    assert r.json()["provider"] == {"adapter": "gemini", "model": "demo-model", "is_fixture": False}
    assert len(seen) == 1
    request = seen[0]
    assert request.headers["x-goog-api-key"] == KEY.get_secret_value()
    assert KEY.get_secret_value() not in str(request.url)
    sent = json.loads(request.content)
    assert sent["generationConfig"]["responseMimeType"] == "application/json"
    assert '"value"' not in sent["contents"][0]["parts"][0]["text"]  # fact values withheld


def test_invalid_gemini_output_is_rejected() -> None:
    bad = json.dumps({"text": "x", "fact_ids": [], "uncertainties": [], "approved": True})
    transport, _ = recording_transport(lambda _: httpx.Response(200, json=gemini_response(bad)))
    client = make_client(GeminiAdapter(KEY, "m", 5, transport), auth_mode="fixture")
    r = client.post(DRAFT_URL, json=DRAFT_BODY)
    assert r.status_code == 502 and r.json()["details"]["issues"] == ["sec14_forbidden_field"]


@pytest.mark.parametrize(
    ("status", "reason", "http"),
    [
        (401, "auth_rejected", 502),
        (403, "auth_rejected", 502),
        (429, "rate_limited", 429),
        (500, "provider_error", 502),
    ],
)
def test_provider_http_errors_are_typed(status: int, reason: str, http: int) -> None:
    transport, seen = recording_transport(lambda _: httpx.Response(status, text="provider body"))
    adapter = GeminiAdapter(KEY, "m", 5, transport)
    with pytest.raises(ModelTransportError) as exc:
        asyncio.run(adapter.complete(_task()))
    assert exc.value.reason == reason
    r = make_client(adapter, auth_mode="fixture").post(DRAFT_URL, json=DRAFT_BODY)
    assert r.status_code == http and r.json()["details"]["reason"] == reason
    assert "provider body" not in r.text
    assert len(seen) == 2  # exactly one attempt per call, no retries


def test_malformed_provider_envelope_is_provider_error() -> None:
    transport, _ = recording_transport(lambda _: httpx.Response(200, json={"candidates": []}))
    with pytest.raises(ModelTransportError):
        asyncio.run(GeminiAdapter(KEY, "m", 5, transport).complete(_task()))


def test_httpx_timeout_maps_to_model_timeout() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    transport, _ = recording_transport(boom)
    with pytest.raises(ModelTimeout):
        asyncio.run(GeminiAdapter(KEY, "m", 5, transport).complete(_task()))


def test_supplied_data_is_denied_before_network() -> None:
    from strongstart_api.features.applications.router import get_workspace_source
    from strongstart_api.features.applications.workspace import FixtureWorkspaceSource
    from strongstart_contracts import ProvenanceClass

    real = FixtureWorkspaceSource().get("demo-org")
    bundle = real.evidence_bundle
    fact = bundle.facts[0]
    supplied = fact.model_copy(
        update={
            "provenance": fact.provenance.model_copy(
                update={"provenance_class": ProvenanceClass.SUPPLIED}
            )
        }
    )
    ws = real.model_copy(
        update={"evidence_bundle": bundle.model_copy(update={"facts": [supplied]})}
    )

    class Source:
        is_fixture = True

        def get(self, organization_id: str) -> object:
            return ws

    transport, seen = recording_transport(_never_called)
    client = make_client(GeminiAdapter(KEY, "m", 5, transport), auth_mode="fixture")
    client.app.dependency_overrides[get_workspace_source] = lambda: Source()  # type: ignore[attr-defined]
    r = client.post(DRAFT_URL, json=DRAFT_BODY)
    assert r.status_code == 403 and r.json()["details"]["reason"] == "data_class_not_permitted"
    assert seen == []


def test_production_never_serves_fake_drafts() -> None:
    client = make_client(environment="production", model_provider="fake")
    caps = {c["feature"]: c for c in client.get("/api/capabilities").json()["capabilities"]}
    assert caps["applications.model"]["status"] == "unavailable"

    from strongstart_api.config import Settings
    from strongstart_api.features.applications.router import get_model_adapter

    adapter = get_model_adapter(Settings(_env_file=None, environment="production"))
    with pytest.raises(CapabilityUnavailable):
        adapter.capabilities()
