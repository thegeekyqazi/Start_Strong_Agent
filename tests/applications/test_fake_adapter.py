"""FakeAdapter is deterministic and never emits raw numbers (C1 spec s4, s8)."""

from __future__ import annotations

import asyncio
import re

from strongstart_api.features.applications.models.base import StructuredTask
from strongstart_api.features.applications.models.fake import FakeAdapter
from strongstart_api.features.applications.models.validation import (
    SLOT_TOKEN,
    validate_draft_output,
)

from .conftest import DRAFT_BODY, DRAFT_URL, FACT, make_client


def _task() -> StructuredTask:
    return StructuredTask(
        task_id="t",
        operation="draft_answer",
        instructions="x",
        payload={"allowed_facts": [{"fact_id": FACT}]},
        output_schema={},
    )


def test_identical_across_calls_and_instances() -> None:
    a = asyncio.run(FakeAdapter().complete(_task()))
    b = asyncio.run(FakeAdapter().complete(_task()))
    c = asyncio.run(FakeAdapter().complete(_task()))
    assert a == b == c


def test_identical_across_api_requests() -> None:
    client = make_client(auth_mode="fixture")
    first = client.post(DRAFT_URL, json=DRAFT_BODY)
    second = client.post(DRAFT_URL, json=DRAFT_BODY)
    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    body = first.json()
    assert body["provider"] == {
        "adapter": "fake",
        "model": "fake-deterministic-v1",
        "is_fixture": True,
    }
    assert body["provenance"]["is_simulated"] is True
    assert {"kind": "fact_slot", "fact_id": FACT} in body["segments"]


def test_output_has_no_digits_outside_slots_and_validates() -> None:
    raw = asyncio.run(FakeAdapter().complete(_task()))
    draft = validate_draft_output(raw, frozenset({FACT}))
    assert draft.fact_ids == (FACT,)
    assert not re.search(r"\d", SLOT_TOKEN.sub("", draft.text))


def test_no_allowed_facts_means_no_slots() -> None:
    task = StructuredTask("t", "draft_answer", "x", {"allowed_facts": []}, {})
    draft = validate_draft_output(asyncio.run(FakeAdapter().complete(task)), frozenset())
    assert draft.fact_ids == () and "{{" not in draft.text
