"""Application service: plan, draft and check (C1 spec s4-s6; C2 spec s4-s6).

The service never trusts adapter output. It builds typed tasks from the authorized
workspace, refuses data classes the adapter does not permit (before any call), runs each
role through the SEC-12 coordinator with a deadline, validates the raw text, renders
fact slots on the server (s8.2) and runs the deterministic rules. Nothing here persists,
writes state or approves anything (SEC-14); C2 is stateless (owner decision).
"""

from __future__ import annotations

import hashlib

from strongstart_contracts import EvidenceBundle, Fact, Provenance, ProvenanceClass, Question
from strongstart_contracts.answers import (
    AnswerPlan,
    ApplicationWorkspace,
    CheckReport,
    CheckRequest,
    DraftProposal,
    DraftRequest,
    ModelRunInfo,
    PlanItem,
    PlanRequest,
)

from .coordinator import run_role
from .models.base import DataClassNotPermitted, ModelAdapter, ModelCapabilities, StructuredTask
from .models.validation import (
    OUTPUT_JSON_SCHEMA,
    PLAN_JSON_SCHEMA,
    validate_draft_output,
    validate_plan_output,
)
from .rules.checks import CheckContext, Mode, run_checks, sha256_text
from .rules.policy import WritingPolicy
from .rules.render import render
from .workspace import WorkspaceSource, load_workspace

INSTRUCTIONS = (
    "You draft one grant answer as a proposal for staff review. Return only JSON with keys "
    "text, fact_ids and uncertainties. Never write numbers in text: reference a figure only "
    "as {{fact:ID}} using an ID from allowed_facts, and list every referenced ID in fact_ids. "
    "If a claim has no evidence, write {{unsupported:short-reason}} instead of inventing it. "
    "Do not include approval, status, permission or decision fields."
)
PLAN_INSTRUCTIONS = (
    "You plan answers for every listed question. Return only JSON with key items: one item "
    "per question with question_id, evidence_fact_ids (only IDs from allowed_facts), "
    "missing_inputs (what staff must supply) and repeated_with (question_ids asking for the "
    "same content). Never invent a funding request, spending plan, figures or consequences."
)


class QuestionNotFound(Exception):
    pass


class EvidenceBundleNotFound(Exception):
    pass


class QuestionVersionConflict(Exception):
    def __init__(self, current: int) -> None:
        super().__init__(f"current version {current}")
        self.current = current


def _bundle(workspace: ApplicationWorkspace, evidence_bundle_id: str) -> EvidenceBundle:
    bundle = workspace.evidence_bundle
    if bundle.bundle_id != evidence_bundle_id:
        raise EvidenceBundleNotFound()
    return bundle


def _question(workspace: ApplicationWorkspace, question_id: str, version: int) -> Question:
    question = next(
        (q for q in workspace.question_set.questions if q.question_id == question_id), None
    )
    if question is None:
        raise QuestionNotFound()
    if question.question_version != version:
        raise QuestionVersionConflict(question.question_version)
    return question


def _allowed_facts(bundle: EvidenceBundle) -> list[Fact]:
    allowed = frozenset(bundle.allowed_fact_ids)
    return [f for f in bundle.facts if f.fact_id in allowed]


def _require_data_classes(
    caps: ModelCapabilities, facts: list[Fact], questions: list[Question]
) -> frozenset[ProvenanceClass]:
    classes = frozenset(
        [f.provenance.provenance_class for f in facts]
        + [r.provenance.provenance_class for q in questions for r in q.source_refs]
    )
    if not classes <= caps.permitted_data_classes:
        raise DataClassNotPermitted()
    return classes


def _facts_payload(facts: list[Fact]) -> list[dict[str, object]]:
    # Values are deliberately withheld: the server renders them from slots (s8.2).
    return [
        {
            "fact_id": f.fact_id,
            "metric_id": f.metric_id,
            "unit": f.unit,
            "scope": f.scope,
            "population": f.population,
            "reporting_period": f.reporting_period,
        }
        for f in facts
    ]


def _provenance(caps: ModelCapabilities, facts: list[Fact], fake_note: str) -> Provenance:
    simulated = caps.is_fixture or any(f.provenance.is_simulated for f in facts)
    return Provenance(
        provenance_class=ProvenanceClass.SIMULATED if simulated else ProvenanceClass.PUBLIC,
        is_simulated=simulated,
        note=fake_note
        if caps.is_fixture
        else "Model proposal; inputs carry their own provenance labels.",
    )


def build_check_report(
    *,
    question: Question,
    bundle: EvidenceBundle,
    text: str,
    mode: Mode,
    policy: WritingPolicy | None,
) -> CheckReport:
    rendered, unresolved, facts = render(text, bundle)
    findings = run_checks(
        CheckContext(
            question=question,
            rendered=rendered,
            unresolved=unresolved,
            facts=facts,
            mode=mode,
            policy=policy,
        )
    )
    return CheckReport(
        question_id=question.question_id,
        question_version=question.question_version,
        evidence_bundle_id=bundle.bundle_id,
        mode=mode,
        submitted_text_sha256=sha256_text(text),
        rendered=rendered,
        findings=findings,
    )


def check_answer(
    *,
    source: WorkspaceSource,
    organization_id: str,
    question_id: str,
    request: CheckRequest,
    policy: WritingPolicy | None,
) -> CheckReport:
    workspace = load_workspace(source, organization_id, request.question_set_id)
    question = _question(workspace, question_id, request.question_version)
    bundle = _bundle(workspace, request.evidence_bundle_id)
    return build_check_report(
        question=question, bundle=bundle, text=request.text, mode=request.mode, policy=policy
    )


async def draft_answer(
    *,
    source: WorkspaceSource,
    adapter: ModelAdapter,
    organization_id: str,
    question_id: str,
    request: DraftRequest,
    timeout_seconds: float,
    policy: WritingPolicy | None = None,
) -> DraftProposal:
    workspace = load_workspace(source, organization_id, request.question_set_id)
    question = _question(workspace, question_id, request.question_version)
    bundle = _bundle(workspace, request.evidence_bundle_id)

    caps = adapter.capabilities()  # CapabilityUnavailable propagates; no fallback (s17)
    facts = _allowed_facts(bundle)
    classes = _require_data_classes(caps, facts, [question])
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
            "allowed_facts": _facts_payload(facts),
        },
        output_schema=OUTPUT_JSON_SCHEMA,
        data_classes=classes,
    )
    raw = await run_role(adapter, task, timeout_seconds)
    draft = validate_draft_output(raw, frozenset(bundle.allowed_fact_ids))
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
        provenance=_provenance(
            caps,
            facts,
            "Deterministic fake-adapter proposal over synthetic inputs; not model-written.",
        ),
        # Closes the C1 gap: raw numbers in model text now surface as APP-03 findings.
        check=build_check_report(
            question=question, bundle=bundle, text=draft.text, mode="working", policy=policy
        ),
    )


async def plan_application(
    *,
    source: WorkspaceSource,
    adapter: ModelAdapter,
    organization_id: str,
    request: PlanRequest,
    timeout_seconds: float,
) -> AnswerPlan:
    workspace = load_workspace(source, organization_id, request.question_set_id)
    bundle = _bundle(workspace, request.evidence_bundle_id)
    questions = sorted(workspace.question_set.questions, key=lambda q: q.order)
    caps = adapter.capabilities()
    facts = _allowed_facts(bundle)
    classes = _require_data_classes(caps, facts, questions)
    task = StructuredTask(
        task_id=f"plan:{workspace.question_set.question_set_id}:{bundle.bundle_id}",
        operation="plan_application",
        instructions=PLAN_INSTRUCTIONS,
        payload={
            "questions": [
                {"question_id": q.question_id, "original_text": q.original_text} for q in questions
            ],
            "allowed_facts": _facts_payload(facts),
        },
        output_schema=PLAN_JSON_SCHEMA,
        data_classes=classes,
    )
    raw = await run_role(adapter, task, timeout_seconds)
    items = validate_plan_output(
        raw, tuple(q.question_id for q in questions), frozenset(bundle.allowed_fact_ids)
    )
    versions = {q.question_id: q.question_version for q in questions}
    plan_key = "|".join([task.task_id, caps.model, raw])
    return AnswerPlan(
        plan_id="plan-" + hashlib.sha256(plan_key.encode("utf-8")).hexdigest()[:24],
        question_set_id=workspace.question_set.question_set_id,
        evidence_bundle_id=bundle.bundle_id,
        items=[
            PlanItem(
                question_id=i.question_id,
                question_version=versions[i.question_id],
                evidence_fact_ids=list(i.evidence_fact_ids),
                missing_inputs=list(i.missing_inputs),
                repeated_with=list(i.repeated_with),
            )
            for i in items
        ],
        planner=ModelRunInfo(adapter=caps.adapter, model=caps.model, is_fixture=caps.is_fixture),
        provenance=_provenance(
            caps, facts, "Deterministic fake-adapter plan over synthetic inputs; not model-written."
        ),
    )
