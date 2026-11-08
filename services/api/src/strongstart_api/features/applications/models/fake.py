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
        if task.operation == "plan_application":
            return self._plan(task)
        if task.operation in ("numerical_review", "meaning_review"):
            return self._review(task)
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

    @staticmethod
    def _plan(task: StructuredTask) -> str:
        """Deterministic planner: all allowed facts go to the first question; every other
        question gets an explicit missing-input note. Nothing is invented (s7)."""
        questions: list[dict[str, Any]] = list(task.payload.get("questions", []))
        fact_ids = sorted(str(f["fact_id"]) for f in task.payload.get("allowed_facts", []))
        items = []
        for n, q in enumerate(questions):
            assigned = fact_ids if n == 0 else []
            items.append(
                {
                    "question_id": q["question_id"],
                    "evidence_fact_ids": assigned,
                    "missing_inputs": []
                    if assigned
                    else ["No evidence in this bundle answers this question; staff input needed."],
                    "repeated_with": [],
                }
            )
        return json.dumps({"items": items}, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _review(task: StructuredTask) -> str:
        """Deterministic reviewer proposals (s8.1). Concerns only; never a verdict."""
        bindings: list[dict[str, Any]] = list(task.payload.get("bindings", []))
        if task.operation == "numerical_review":
            findings = [
                {
                    "concern": "Confirm this linked figure answers the question for the period "
                    "and population it covers.",
                    "span_start": b["span_start"],
                    "span_end": b["span_end"],
                    "fact_ids": [b["fact_id"]],
                }
                for b in bindings
            ]
        else:
            findings = [
                {
                    "concern": "Check that the wording keeps the meaning of approved material "
                    "and makes no claim the evidence does not support.",
                    "span_start": None,
                    "span_end": None,
                    "fact_ids": [],
                }
            ]
        return json.dumps({"findings": findings}, sort_keys=True, separators=(",", ":"))
