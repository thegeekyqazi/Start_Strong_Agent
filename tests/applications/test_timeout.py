"""A slow model returns a typed timeout, not a hang (C1 spec s6)."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from strongstart_api.features.applications.models.fake import FakeAdapter

from .conftest import DRAFT_BODY, DRAFT_URL, make_client


class HangingAdapter:
    is_fixture = True

    def capabilities(self) -> Any:
        return FakeAdapter().capabilities()

    async def complete(self, task: Any) -> str:
        await asyncio.sleep(30)
        return "{}"


def test_hanging_adapter_times_out_quickly_with_typed_envelope() -> None:
    client = make_client(HangingAdapter(), auth_mode="fixture", model_timeout_seconds=0.05)
    start = time.monotonic()
    r = client.post(DRAFT_URL, json=DRAFT_BODY)
    assert time.monotonic() - start < 2
    assert r.status_code == 504
    body = r.json()
    assert body["code"] == "dependency_unavailable"
    assert body["details"] == {"reason": "model_timeout"}
