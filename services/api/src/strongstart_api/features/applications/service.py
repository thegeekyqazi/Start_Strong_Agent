"""Draft service: workspace lookup, data-class routing, timeout, validation (C1 spec s4-s6).

The service never trusts adapter output. It builds a typed task from the authorized
workspace, refuses data classes the adapter does not permit (before any call), bounds
the call with a deadline, validates the raw text and only then builds a
``DraftProposal``. Nothing here writes state or approves anything (SEC-14).
"""

from __future__ import annotations

import asyncio
import hashlib

from strongstart_contracts import Provenance, ProvenanceClass
from strongstart_contracts.answers import DraftProposal, DraftRequest, ModelRunInfo

from .models.base import DataClassNotPermitted, ModelAdapter, ModelTimeout, StructuredTask
from .models.validation import OUTPUT_JSON_SCHEMA, validate_draft_output
from .workspace import WorkspaceSource

INSTRUCTIONS = (
    "You draft one grant answer as a proposal for staff review. Return only JSON with keys "
    "text, fact_ids and uncertainties. Never write numbers in text: reference a figure only "
    "as {{fact:ID}} using an ID from allowed_facts, and list every referenced ID in fact_ids. "
    "Do not include approval, status or decision fields. If evidence is insufficient, say so "
    "in uncertainties instead of inventing content."
)


class QuestionNotFound(Exception):
    pass


class EvidenceBundleNotFound(Exception):
    pass


class QuestionVersionConflict(Exception):
    def __init__(self, current: int) -> None:
        super().__init__(f"current version {current}")
        self.current = current


async def draft_answer(
    *,
    source: WorkspaceSource,
    adapter: ModelAdapter,
    organization_id: str,
    question_id: str,
    request: DraftRequest,
    timeout_seconds: float,
) -> DraftProposal:
    workspace = source.get(organization_id)
    question = next(
        (q for q in workspace.question_set.questions if q.question_id == question_id), None
    )
    if question is None:
        raise QuestionNotFound()
    if question.question_version != request.question_version:
        raise QuestionVersionConflict(question.question_version)
    bundle = workspace.evidence_bundle
    if bundle.bundle_id != request.evidence_bundle_id:
        raise EvidenceBundleNotFound()

    caps = adapter.capabilities()  # CapabilityUnavailable propagates; no fallback (s17)
    allowed = frozenset(bundle.allowed_fact_ids)
    facts = [f for f in bundle.facts if f.fact_id in allowed]
    classes = frozenset(
        [f.provenance.provenance_class for f in facts]
        + [r.provenance.provenance_class for r in question.source_refs]
    )
    if not classes <= caps.permitted_data_classes:
        raise DataClassNotPermitted()

    task = StructuredTask(
        task_id=f"draft:{question.question_id}:{question.question_version}",
        operation="draft_answer",
        instructions=INSTRUCTIONS,
        payload={
            "question": {
                "question_id": question.question_id,
                "original_text": question.original_text,
                "limit": question.limit.model_dump(mode="json", include={"maximum", "unit"})
                if question.limit
                else None,
            },
            # Values are deliberately withheld: the server renders them from slots (s8.2).
            "allowed_facts": [
                {
                    "fact_id": f.fact_id,
                    "metric_id": f.metric_id,
                    "unit": f.unit,
                    "scope": f.scope,
                    "population": f.population,
                    "reporting_period": f.reporting_period,
                }
                for f in facts
            ],
        },
        output_schema=OUTPUT_JSON_SCHEMA,
        data_classes=classes,
    )
    try:
        raw = await asyncio.wait_for(adapter.complete(task), timeout=timeout_seconds)
    except TimeoutError:
        raise ModelTimeout() from None

    draft = validate_draft_output(raw, allowed)
    template_sha = hashlib.sha256(draft.text.encode("utf-8")).hexdigest()
    identity = "|".join(
        [
            question.question_id,
            str(question.question_version),
            bundle.bundle_id,
            caps.model,
            template_sha,
        ]
    )
    simulated = caps.is_fixture or any(f.provenance.is_simulated for f in facts)
    return DraftProposal(
        proposal_id="draft-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24],
        question_id=question.question_id,
        question_version=question.question_version,
        evidence_bundle_id=bundle.bundle_id,
        pack_version_id=bundle.pack_version_id,
        template_text=draft.text,
        template_sha256=template_sha,
        segments=list(draft.segments),
        fact_ids=list(draft.fact_ids),
        uncertainties=list(draft.uncertainties),
        provider=ModelRunInfo(adapter=caps.adapter, model=caps.model, is_fixture=caps.is_fixture),
        provenance=Provenance(
            provenance_class=ProvenanceClass.SIMULATED if simulated else ProvenanceClass.PUBLIC,
            is_simulated=simulated,
            note=(
                "Deterministic fake-adapter proposal over synthetic inputs; not model-written."
                if caps.is_fixture
                else "Model proposal; inputs carry their own provenance labels."
            ),
        ),
    )
