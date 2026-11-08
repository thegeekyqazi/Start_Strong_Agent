"""Deterministic FIXTURE model adapter (C1 spec s4). Default for local/test only.

Returns canned JSON whose prose contains no digits: any figure appears only as a
``{{fact:ID}}`` slot referencing an allowed fact from the task payload (s8.2). The
same task always yields byte-identical output. Settings reject this adapter in
production.
"""

from __future__ import annotations

import json
from typing import Any

from strongstart_contracts import ProvenanceClass

from .base import ModelCapabilities, StructuredTask

FAKE_MODEL = "fake-deterministic-v1"


class FakeAdapter:
    is_fixture = True

    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            adapter="fake",
            model=FAKE_MODEL,
            structured_output=True,
            max_context_tokens=None,
            max_output_tokens=None,
            permitted_data_classes=frozenset(ProvenanceClass),
            is_fixture=True,
        )

    async def complete(self, task: StructuredTask) -> str:
        facts: list[dict[str, Any]] = list(task.payload.get("allowed_facts", []))
        fact_ids = sorted(str(f["fact_id"]) for f in facts)[:1]
        text = (
            "SYNTHETIC FIXTURE DRAFT: Demo Org supports early learning for families in "
            "its community."
        )
        if fact_ids:
            text += f" Linked evidence: {{{{fact:{fact_ids[0]}}}}}."
        body = {
            "text": text,
            "fact_ids": fact_ids,
            "uncertainties": [
                "Fixture output from the deterministic fake adapter; not written by a model.",
                "Linked facts must be checked by staff before this text is used.",
            ],
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":"))
