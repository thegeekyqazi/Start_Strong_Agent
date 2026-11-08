"""DOCX and JSON audit export (engineering s16; APP-07, APP-08, POL-05; C3 spec s6).

``working`` exports always succeed and are labelled "WORKING DRAFT - NOT REVIEWED".
``reviewed`` exports are refused (no artifact is produced) unless every selected question's
latest version has a current, non-stale approval, a fresh reviewed-mode check shows no
``fail``, no unsupported marker remains and every ``needs_review`` item was acknowledged
by the approver. Simulated inputs keep the "SYNTHETIC DEMO DATA" label on every page
(POL-05). Status and findings use plain text labels (owner decision: no colour coding
until the U01 writing guide is supplied).
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from docx import Document

from strongstart_contracts import Question, SessionIdentity
from strongstart_contracts.answers import (
    AnswerFinding,
    ExportBlocker,
    ExportRequest,
    ExportResult,
)

from . import audit
from .approval import Context, stale_reason, to_contract
from .service import build_check_report
from .store import StoredExport, StoredVersion

LABEL_WORKING = "WORKING DRAFT - NOT REVIEWED"
LABEL_REVIEWED = "REVIEWED - EXACT APPROVED VERSIONS"
LABEL_SYNTHETIC = "SYNTHETIC DEMO DATA"
LABEL_FIXTURE_APPROVAL = "FIXTURE APPROVAL - NOT AUTHENTICATION"
OUTCOME_LABEL = {
    "fail": "[PROBLEM]",
    "needs_review": "[NEEDS REVIEW]",
    "pass": "[PASSED THIS CHECK ONLY]",
    "not_applicable": "[NOT APPLICABLE]",
}
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def validation_record_is_current(record: dict[str, Any]) -> bool:
    """APP-08: a validation record counts as current only with a rule version, an input
    snapshot hash, an evaluation time and a result payload."""
    inputs = record.get("inputs") or {}
    return bool(
        record.get("rule_version")
        and inputs.get("rendered_text_sha256")
        and record.get("evaluated_at")
        and record.get("outcome")
    )


def _status_label(state: str) -> str:
    return {
        "approved": "Approved (this exact version)",
        "stale": "Out of date - approval no longer applies",
        "rejected": "Rejected by reviewer",
        "needs_attention": "Needs attention - not approved",
        "ready_for_review": "Ready for review - not approved",
        "draft": "Draft - not reviewed",
    }.get(state, "Not reviewed")


def _finding_lines(findings: list[AnswerFinding]) -> list[str]:
    return [
        f"{OUTCOME_LABEL[f.result.outcome]} {f.result.rule_id}: {f.message}"
        for f in findings
        if f.result.outcome in ("fail", "needs_review")
    ]


def _blockers(
    ctx: Context, question: Question | None, question_id: str, latest: StoredVersion | None
) -> list[ExportBlocker]:
    def block(reason: str, message: str) -> list[ExportBlocker]:
        return [ExportBlocker(question_id=question_id, reason=reason, message=message)]

    if question is None:
        return block("unknown_question", "This question is not in the application.")
    if latest is None:
        return block("no_answer", "No answer version has been saved.")
    decision = ctx.store.decision_for(ctx.organization_id, latest.answer_version_id)
    if decision is None or decision.decision != "approve":
        return block("not_approved", "The latest version is not approved.")
    reason = stale_reason(ctx, latest)
    if reason is not None:
        return block("stale_approval", f"The approval is out of date ({reason}).")
    out: list[ExportBlocker] = []
    fresh = build_check_report(
        question=question,
        bundle=ctx.workspace_source.get(ctx.organization_id).evidence_bundle,
        text=latest.text,
        mode="reviewed",
        policy=ctx.policy,
    )
    if fresh.rendered.unsupported_markers:
        out += block("unsupported_claim", "The answer still marks a claim as unsupported.")
    if any(f.result.outcome == "fail" for f in fresh.findings):
        out += block("open_problem", "A deterministic check reports a problem.")
    if any(f.result.outcome == "needs_review" for f in fresh.findings) and not (
        decision.acknowledged_review_items
    ):
        out += block("unacknowledged_warning", "Open review items were not acknowledged.")
    return out


def build_export(ctx: Context, identity: SessionIdentity, body: ExportRequest) -> ExportResult:
    ws = ctx.workspace_source.get(ctx.organization_id)
    questions = {q.question_id: q for q in ws.question_set.questions}
    bundle = ws.evidence_bundle
    facts = {f.fact_id: f for f in bundle.facts}
    now = datetime.now(UTC)
    rows: list[tuple[str, Question | None, StoredVersion | None]] = []
    for qid in body.question_ids:
        versions = ctx.store.versions(ctx.organization_id, qid) if qid in questions else []
        rows.append((qid, questions.get(qid), versions[-1] if versions else None))

    blockers: list[ExportBlocker] = []
    if body.mode == "reviewed":
        for qid, question, latest in rows:
            blockers += _blockers(ctx, question, qid, latest)

    simulated = (
        ctx.store.is_fixture
        or ws.is_fixture
        or any(f.provenance.is_simulated for f in bundle.facts)
        or any(r.provenance.is_simulated for q in questions.values() for r in q.source_refs)
    )
    labels = [LABEL_REVIEWED if body.mode == "reviewed" else LABEL_WORKING]
    if simulated:
        labels.append(LABEL_SYNTHETIC)
    fixture_approved = any(
        (d := ctx.store.decision_for(ctx.organization_id, latest.answer_version_id)) is not None
        and d.decision == "approve"
        and d.reviewer_is_fixture_identity
        for _, _, latest in rows
        if latest is not None
    )
    if fixture_approved:
        labels.append(LABEL_FIXTURE_APPROVAL)

    if blockers:
        audit.record(
            ctx.store,
            ctx.settings,
            organization_id=ctx.organization_id,
            actor_id=identity.actor_id,
            action="export_blocked",
            object_type="export",
            object_id="none",
            object_version=body.mode,
            decision="blocked",
            details={"reasons": ",".join(sorted({b.reason for b in blockers}))},
        )
        return ExportResult(
            export_id=None,
            mode=body.mode,
            blocked=True,
            blocked_by=blockers,
            labels=labels,
            docx_sha256=None,
            audit_sha256=None,
            created_at=now,
        )

    export_id = "exp-" + uuid.uuid4().hex[:24]
    docx_bytes = _docx(ctx, rows, facts, labels, body.mode)
    audit_bytes = _audit_json(ctx, identity, export_id, body.mode, rows, facts, labels, now)
    result = ExportResult(
        export_id=export_id,
        mode=body.mode,
        blocked=False,
        blocked_by=[],
        labels=labels,
        docx_sha256=hashlib.sha256(docx_bytes).hexdigest(),
        audit_sha256=hashlib.sha256(audit_bytes).hexdigest(),
        created_at=now,
    )
    ctx.store.add_export(
        ctx.organization_id,
        StoredExport(
            organization_id=ctx.organization_id, result=result, docx=docx_bytes, audit=audit_bytes
        ),
    )
    audit.record(
        ctx.store,
        ctx.settings,
        organization_id=ctx.organization_id,
        actor_id=identity.actor_id,
        action="export_created",
        object_type="export",
        object_id=export_id,
        object_version=body.mode,
        decision="created",
        details={
            "docx_sha256": result.docx_sha256 or "",
            "audit_sha256": result.audit_sha256 or "",
        },
    )
    return result


def _state_of(ctx: Context, version: StoredVersion) -> str:
    latest = ctx.store.versions(ctx.organization_id, version.question_id)[-1]
    return to_contract(ctx, version, latest.answer_version_id).state


def _docx(
    ctx: Context,
    rows: list[tuple[str, Question | None, StoredVersion | None]],
    facts: dict[str, Any],
    labels: list[str],
    mode: Literal["working", "reviewed"],
) -> bytes:
    doc = Document()
    header = doc.sections[0].header.paragraphs[0]
    header.text = " | ".join(labels)  # on every page (POL-05)
    doc.add_heading("Strong Start application export", level=1)
    doc.add_paragraph(" | ".join(labels))
    doc.add_paragraph(
        "Working exports may contain placeholders such as XXX."
        if mode == "working"
        else "Every answer below is the exact approved version."
    )
    for qid, question, latest in rows:
        doc.add_heading(question.original_text if question else qid, level=2)
        if question is not None and question.limit is not None:
            doc.add_paragraph(
                f"Limit: {question.limit.maximum} {question.limit.unit} "
                "(as stated in the question data)"
            )
        if latest is None:
            doc.add_paragraph("No answer saved yet.")
            continue
        doc.add_paragraph(
            f"Answer version {latest.answer_version} (fingerprint {latest.content_sha256[:12]}): "
            f"{_status_label(_state_of(ctx, latest))}"
        )
        doc.add_paragraph(latest.rendered.text)
        app01 = next((f for f in latest.check.findings if f.result.rule_id == "APP-01"), None)
        if app01 is not None:
            doc.add_paragraph(f"Count: {app01.message}")
        findings = latest.check.findings
        if mode == "working" and question is not None:
            # Working drafts may be incomplete with visible markers (s9.2): use working-mode
            # outcomes, so a placeholder reads [NEEDS REVIEW] rather than [PROBLEM].
            findings = build_check_report(
                question=question,
                bundle=ctx.workspace_source.get(ctx.organization_id).evidence_bundle,
                text=latest.text,
                mode="working",
                policy=ctx.policy,
            ).findings
        for line in _finding_lines(findings):
            doc.add_paragraph(line)
        if latest.rendered.bindings:
            doc.add_paragraph("Sources:")
            for b in latest.rendered.bindings:
                fact = facts.get(b.fact_id)
                if fact is None:
                    continue
                ref = fact.supporting_refs[0]
                provenance = (
                    "simulated"
                    if fact.provenance.is_simulated
                    else fact.provenance.provenance_class
                )
                doc.add_paragraph(
                    f"{b.rendered_text}: fact {fact.fact_id}; source {ref.source_id} "
                    f"({ref.source_version_id}); location {ref.locator or 'unknown'}; "
                    f"status {fact.status}; provenance {provenance}",
                    style="List Bullet",
                )
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _audit_json(
    ctx: Context,
    identity: SessionIdentity,
    export_id: str,
    mode: str,
    rows: list[tuple[str, Question | None, StoredVersion | None]],
    facts: dict[str, Any],
    labels: list[str],
    now: datetime,
) -> bytes:
    entries: list[dict[str, Any]] = []
    for qid, question, latest in rows:
        if latest is None:
            entries.append({"question_id": qid, "answer": None})
            continue
        decision = ctx.store.decision_for(ctx.organization_id, latest.answer_version_id)
        checks: list[dict[str, Any]] = []
        for f in latest.check.findings:
            record: dict[str, Any] = {
                "rule_id": f.result.rule_id,
                "rule_version": f.result.rule_version,
                "outcome": f.result.outcome,
                "inputs": f.result.inputs,
                "reasons": f.result.reasons,
                "evaluated_at": latest.checked_at.isoformat(),
            }
            record["counts_as_current"] = validation_record_is_current(record)
            checks.append(record)
        entries.append(
            {
                "question_id": qid,
                "question_version": question.question_version if question else None,
                "answer_version_id": latest.answer_version_id,
                "answer_version": latest.answer_version,
                "content_sha256": latest.content_sha256,
                "snapshot_sha256": latest.snapshot_sha256,
                "rendered_text_sha256": latest.rendered.text_sha256,
                "dependencies": [d.model_dump() for d in latest.dependencies],
                "fact_ids": [b.fact_id for b in latest.rendered.bindings],
                "sources": [
                    {
                        "fact_id": b.fact_id,
                        "source_id": facts[b.fact_id].supporting_refs[0].source_id,
                        "source_version_id": facts[b.fact_id].supporting_refs[0].source_version_id,
                        "locator": facts[b.fact_id].supporting_refs[0].locator,
                        "is_simulated": facts[b.fact_id].provenance.is_simulated,
                    }
                    for b in latest.rendered.bindings
                    if b.fact_id in facts
                ],
                "approval": None
                if decision is None
                else {
                    "approval_id": decision.approval_id,
                    "decision": decision.decision,
                    "reviewer_id": decision.reviewer_id,
                    "reviewer_is_fixture_identity": decision.reviewer_is_fixture_identity,
                    "decided_at": decision.decided_at.isoformat(),
                    "stale_reason": stale_reason(ctx, latest),
                },
                "checks": checks,
            }
        )
    payload = {
        "export_id": export_id,
        "mode": mode,
        "labels": labels,
        "created_at": now.isoformat(),
        "actor_id": identity.actor_id,
        "organization_id": ctx.organization_id,
        "store_is_fixture": ctx.store.is_fixture,
        "answers": entries,
    }
    return json.dumps(payload, sort_keys=True, indent=2).encode("utf-8")
