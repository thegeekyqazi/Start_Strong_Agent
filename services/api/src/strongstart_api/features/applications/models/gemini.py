"""Gemini adapter behind the ModelAdapter interface (C1 spec s4; engineering s17, s23.1).

Disabled by default. Unusable configuration (no key, no model name) raises
``CapabilityUnavailable`` before any network call; there is no fallback to another
provider. The key is sent only in the ``x-goog-api-key`` header (never the URL) and no
error carries a provider body. Permitted data classes exclude ``supplied`` partner
material until the maintainer approves that routing.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import SecretStr

from strongstart_contracts import CapabilityUnavailable, ProvenanceClass

from .base import ModelCapabilities, ModelTimeout, ModelTransportError, StructuredTask

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
MAX_OUTPUT_TOKENS = 1024
GEMINI_DATA_CLASSES = frozenset(
    {ProvenanceClass.SIMULATED, ProvenanceClass.ENGINEERING_DERIVED, ProvenanceClass.PUBLIC}
)


class GeminiAdapter:
    is_fixture = False

    def __init__(
        self,
        api_key: SecretStr | None,
        model: str | None,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._transport = transport

    def _usable(self) -> tuple[str, str]:
        key = self._key.get_secret_value() if self._key is not None else ""
        if not key:
            raise CapabilityUnavailable("ModelAdapter.gemini", "STRONGSTART_GEMINI_API_KEY not set")
        if not self._model:
            raise CapabilityUnavailable("ModelAdapter.gemini", "STRONGSTART_GEMINI_MODEL not set")
        return key, self._model

    def capabilities(self) -> ModelCapabilities:
        _, model = self._usable()
        return ModelCapabilities(
            adapter="gemini",
            model=model,
            structured_output=True,
            max_context_tokens=None,  # not assumed; confirm per model (s17, s23.1)
            max_output_tokens=MAX_OUTPUT_TOKENS,
            permitted_data_classes=GEMINI_DATA_CLASSES,
            is_fixture=False,
        )

    async def complete(self, task: StructuredTask) -> str:
        key, model = self._usable()
        body: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": task.instructions}]},
            "contents": [
                {"role": "user", "parts": [{"text": json.dumps(task.payload, sort_keys=True)}]}
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": task.output_schema,
                "maxOutputTokens": MAX_OUTPUT_TOKENS,
            },
        }
        url = f"{GEMINI_BASE_URL}/models/{model}:generateContent"
        try:
            async with httpx.AsyncClient(
                transport=self._transport, timeout=self._timeout, follow_redirects=False
            ) as client:
                res = await client.post(url, json=body, headers={"x-goog-api-key": key})
        except httpx.TimeoutException:
            raise ModelTimeout() from None
        except httpx.HTTPError:
            raise ModelTransportError("provider_error") from None
        if res.status_code in (401, 403):
            raise ModelTransportError("auth_rejected")
        if res.status_code == 429:
            raise ModelTransportError("rate_limited")
        if res.status_code != 200:
            raise ModelTransportError("provider_error")
        try:
            text = res.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (ValueError, KeyError, IndexError, TypeError):
            raise ModelTransportError("provider_error") from None
        if not isinstance(text, str):
            raise ModelTransportError("provider_error")
        return text
