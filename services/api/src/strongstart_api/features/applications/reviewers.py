"""Reviewer roles (engineering s8.1; C3 spec s5; owner decision: deferred from C2 to C3).

The numerical reviewer receives the original fact values/periods and the claim bindings;
the meaning reviewer receives the rendered answer and the scoped policy. Each role runs
through the SEC-12 coordinator and its output is validated strictly. The result is a
``ReviewerProposal``: concerns for a human, never an approval, state change or verdict.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from strongstart_contracts import Provenance, ProvenanceClass, SessionIdentity
from strongstart_contracts.answers import (
    ModelRunInfo,
    ReviewerFinding,
    ReviewerProposal,
    ReviewerProposalRequest,
)

from . import audit
from .approval import Context
from .coordinator import run_role
from .models.base import DataClassNotPermitted, ModelAdapter, ModelOutputRejected, StructuredTask
from .models.validation import parse_model_json
from .workspace import load_workspace

_Id = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._:-]{0,127}$")]

INSTRUCTIONS = {
    "numerical_reviewer": (
        "You are a numerical reviewer. Inspect the original fact values and the bound claims. "
        "Return only JSON {findings:[{concern, span_start, span_end, fact_ids}]} listing "
        "concerns for a human. Do not compute totals; code does arithmetic. Never approve."
    ),
    "meaning_reviewer": (
        "You are a meaning/policy reviewer. Compare the answer with the scoped rules. Return "
        "only JSON {findings:[{concern, span_start, span_end, fact_ids}]} listing possible "
        "meaning changes or unsupported statements. Never approve or set any status."
    ),
}
OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "concern": {"type": "string"},
                    "span_start": {"type": "integer", "nullable": True},
                    "span_end": {"type": "integer", "nullable": True},
                    "fact_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["concern", "span_start", "span_end", "fact_ids"],
            },
        }
    },
    "required": ["findings"],
}


class _FindingOut(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    concern: str = Field(min_length=1, max_length=500)
    span_start: int | None = Field(ge=0)
    span_end: int | None = Field(ge=0)
    fact_ids: list[_Id] = Field(max_length=20)


class _ReviewOut(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    findings: list[_FindingOut] = Field(max_length=30)


def validate_review_output(
    raw: str, text_length: int, bound_fact_ids: frozenset[str]
) -> list[ReviewerFinding]:
    data = parse_model_json(raw)  # SEC-14/SEC-12 key scan, depth and size bounds
    try:
        parsed = _ReviewOut.model_validate(data)
    except ValidationError as exc:
        raise ModelOutputRejected(
            issues=["schema", *sorted({str(e["type"]) for e in exc.errors()})]
        ) from None
    out = []
    for f in parsed.findings:
        if (f.span_start is None) != (f.span_end is None):
            raise ModelOutputRejected(issues=["bad_span"])
        if (
            f.span_start is not None
            and f.span_end is not None
            and not (f.span_start <= f.span_end <= text_length)
        ):
            raise ModelOutputRejected(issues=["bad_span"])
        if any(fid not in bound_fact_ids for fid in f.fact_ids):
            raise ModelOutputRejected(issues=["unknown_fact_id"])
        out.append(
            ReviewerFinding(
                concern=f.concern,
                span_start=f.span_start,
                span_end=f.span_end,
                fact_ids=list(f.fact_ids),
            )
        )
    return out


async def propose(
    ctx: Context,
    identity: SessionIdentity,
    adapter: ModelAdapter,
    body: ReviewerProposalRequest,
    timeout_seconds: float,
) -> ReviewerProposal:
    version = ctx.store.get_version(ctx.organization_id, body.answer_version_id)
    ws = load_workspace(ctx.workspace_source, ctx.organization_id, version.question_set_id)
    facts = {f.fact_id: f for f in ws.evidence_bundle.facts}
    bound = [b for b in version.rendered.bindings if b.fact_id in facts]
    caps = adapter.capabilities()
    classes = frozenset(facts[b.fact_id].provenance.provenance_class for b in bound)
    if not classes <= caps.permitted_data_classes:
        raise DataClassNotPermitted()
    operation: Literal["numerical_review", "meaning_review"] = (
        "numerical_review" if body.role == "numerical_reviewer" else "meaning_review"
    )
    payload: dict[str, Any] = {"answer_text": version.rendered.text}
    if body.role == "numerical_reviewer":
        # The numerical reviewer inspects original values first (s8.1).
        payload["bindings"] = [
            {
                "fact_id": b.fact_id,
                "span_start": b.span_start,
                "span_end": b.span_end,
                "rendered_text": b.rendered_text,
                "original_value": facts[b.fact_id].value,
                "unit": facts[b.fact_id].unit,
                "reporting_period": facts[b.fact_id].reporting_period,
                "population": facts[b.fact_id].population,
            }
            for b in bound
        ]
    elif ctx.policy is not None:
        payload["policy_rules"] = [r.model_dump() for r in ctx.policy.terminology_rules]
    task = StructuredTask(
        task_id=f"review:{body.role}:{version.answer_version_id}",
        operation=operation,
        instructions=INSTRUCTIONS[body.role],
        payload=payload,
        output_schema=OUTPUT_SCHEMA,
        data_classes=classes,
    )
    raw = await run_role(adapter, task, timeout_seconds)
    findings = validate_review_output(
        raw, len(version.rendered.text), frozenset(b.fact_id for b in bound)
    )
    simulated = caps.is_fixture or any(facts[b.fact_id].provenance.is_simulated for b in bound)
    proposal = ctx.store.add_proposal(
        ctx.organization_id,
        ReviewerProposal(
            proposal_id="rp-" + uuid.uuid4().hex[:24],
            answer_version_id=version.answer_version_id,
            role=body.role,
            findings=findings,
            reviewer=ModelRunInfo(
                adapter=caps.adapter, model=caps.model, is_fixture=caps.is_fixture
            ),
            provenance=Provenance(
                provenance_class=ProvenanceClass.SIMULATED if simulated else ProvenanceClass.PUBLIC,
                is_simulated=simulated,
                note="Reviewer proposal only; not an approval or a verified finding.",
            ),
            created_at=datetime.now(UTC),
        ),
    )
    audit.record(
        ctx.store,
        ctx.settings,
        organization_id=ctx.organization_id,
        actor_id=identity.actor_id,
        action="reviewer_proposal_added",
        object_type="answer_version",
        object_id=version.answer_version_id,
        object_version=str(version.answer_version),
        decision=f"proposal:{body.role}",
        details={"proposal_id": proposal.proposal_id, "findings": str(len(findings))},
    )
    return proposal
