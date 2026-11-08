"""Server-built prefill plans (B2-AUTO-002 s5.2, s6, s9). Pure planning: no DOM, no writes.

The planner joins four server-side sources and never trusts the client for any of them:

1. the exact saved publication named by ``question_set_id`` (ApplicationDefinitionReader);
2. a registered prefill portal (trusted registry: selectors, control types, options);
3. the publication's original-to-published ID mapping (never wording or position);
4. approved content per approval ID from the configured ``ApprovedPrefillReader``.

Approval does not resolve B's own holds. Unresolved intake requirements, word limits
(C owns the counter), unconfirmed character conventions, non-conforming numbers,
prose-as-choice and unsupported conditions all stay held, each with a reason.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from strongstart_contracts import CapabilityUnavailable, Provenance, ProvenanceClass
from strongstart_contracts.application_publication import (
    PublishedApplicationVersion,
    QuestionIdMapping,
)
from strongstart_contracts.automation_intake import IntakeQuestion
from strongstart_contracts.automation_prefill import (
    PLAN_TTL_SECONDS,
    ApprovedPrefillContent,
    ApprovedPrefillReader,
    AttachmentChecklistItem,
    AttachmentEvidenceReader,
    BoundField,
    HeldField,
    HeldReason,
    PlanCondition,
    PlanDefinitionRef,
    PlannedFieldAction,
    PortalBinding,
    PrefillBudgets,
    PrefillDependencyCurrentness,
    PrefillPlan,
    PrefillSelection,
    ProducerLabel,
    ReadbackComparison,
    TrustedAttachmentRecord,
    UnselectedRequirement,
)
from strongstart_contracts.fixture_adapters import ApprovalNotUsable

from ..dev_b_store.core import canonical_json, sha256_hex
from .registry import (
    INTAKE_FIXTURES,
    PREFILL_FORM_VERSIONS,
    PrefillControl,
    PrefillPortal,
    prefill_page,
    read_fixture_bytes,
)

UTF16_CONVENTIONS = {"html-maxlength-utf16-code-units"}
TOKEN = re.compile(r"\{\{\s*(?:fact|unsupported)\s*:")
WHOLE_NUMBER = re.compile(r"^(?:0|[1-9][0-9]*)$")
MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
SCOPE_NOTE = (
    "Selected fields only. This plan is not the application's completeness, eligibility or "
    "submission readiness. Held fields, unselected required questions and attachments remain "
    "outstanding; nothing is submitted or signed."
)
PLAN_PROVENANCE = Provenance(
    provenance_class=ProvenanceClass.ENGINEERING_DERIVED,
    is_simulated=True,
    note="B2-AUTO-002 prefill plan for a registered local fixture portal (not a funder site).",
)


class PlanRejected(Exception):
    """The command itself cannot produce a plan (422/409 with a safe reason)."""

    def __init__(self, status: int, reason: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.reason = reason
        self.message = message


def sha_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha_choices(values: list[str]) -> str:
    return sha256_hex(canonical_json(values))


def utf16_len(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def plan_hash(plan_body: dict[str, object]) -> str:
    body = {k: v for k, v in plan_body.items() if k != "plan_sha256"}
    return sha256_hex(canonical_json(body))


def content_problem(
    content: ApprovedPrefillContent,
    *,
    organization_id: str,
    selection: PrefillSelection,
    mapping: QuestionIdMapping,
    question_set_id: str,
) -> tuple[HeldReason, str] | None:
    """Check C's envelope independently (s5.1). ``None`` means the content is usable."""
    a = content.approval
    if content.organization_id != organization_id:
        return "approval_identity_mismatch", "approval belongs to another organization scope"
    if a.approval_snapshot_id != selection.approval_snapshot_id:
        return "approval_identity_mismatch", "reader returned a different approval"
    if content.question_id != selection.published_question_id:
        return (
            "approval_identity_mismatch",
            f"approval names question '{content.question_id}', not the selected published "
            f"question '{selection.published_question_id}'; IDs are never substituted",
        )
    if content.question_set_id != question_set_id:
        return "approval_identity_mismatch", "approval names a different question set version"
    if content.question_version != mapping.question_version:
        return "approval_identity_mismatch", "approval names a different question version"
    if content.answer_version_id != a.answer_snapshot_id:
        return "approval_integrity_mismatch", "answer version differs from the approval snapshot"
    template = sha_text(content.template_text)
    if template != content.template_sha256 or template != a.content_sha256:
        return "approval_integrity_mismatch", "template text does not match the approved hash"
    if sha_text(content.rendered_text) != content.rendered_sha256:
        return "approval_integrity_mismatch", "rendered text does not match its rendered hash"
    if [d.model_dump() for d in content.dependencies] != [d.model_dump() for d in a.dependencies]:
        return "approval_integrity_mismatch", "dependency list differs from the approval snapshot"
    if content.unresolved_marker_count != 0 or TOKEN.search(content.rendered_text):
        return "unresolved_fact_token", "rendered text still contains an unresolved fact slot"
    return None


def comparison_for(control: str) -> ReadbackComparison:
    if control == "textarea":
        return "b2-readback-textarea-crlf/1"
    if control in ("select", "radio", "checkbox"):
        return "b2-readback-choice-exact/1"
    return "b2-readback-exact/1"


def _decimal(v: str | None) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(v)
    except InvalidOperation:
        return None


@dataclass
class _Requirements:
    holds: list[tuple[HeldReason, str]]
    constraints: list[str]
    refs: list[str]
    max_utf16: list[int]
    amount_ranges: list[tuple[Decimal | None, Decimal | None]]


def requirements_for(
    q: IntakeQuestion, control: PrefillControl, stream: str | None
) -> _Requirements:
    r = _Requirements([], [], [], [], [])
    if q.action_state == "held_unresolved_requirement":
        r.holds.append(("held_unresolved_requirement", "; ".join(q.hold_reasons)))
    for lim in q.limits:
        r.refs.append(lim.limit_id)
        if lim.unit == "words":
            r.holds.append(
                (
                    "held_counter_unavailable",
                    f"{lim.maximum} words: C owns word counting (APP-01) and exposes no "
                    "public counter; B does not invent a convention",
                )
            )
        elif lim.unit in ("characters", "utf16_code_units"):
            if lim.counting_convention in UTF16_CONVENTIONS and lim.maximum is not None:
                r.max_utf16.append(int(Decimal(lim.maximum)))
                r.constraints.append(f"max {lim.maximum} UTF-16 code units ({lim.limit_id})")
            else:
                r.holds.append(
                    (
                        "held_unconfirmed_convention",
                        f"{lim.maximum} characters with convention '{lim.counting_convention}'",
                    )
                )
        elif lim.unit == "amount":
            if lim.applies_to_stream in (None, stream):
                r.amount_ranges.append((_decimal(lim.minimum), _decimal(lim.maximum)))
                r.constraints.append(f"amount {lim.minimum}..{lim.maximum} ({lim.limit_id})")
    if control.native_max_length is not None:
        r.max_utf16.append(control.native_max_length)
        r.constraints.append(f"native maxlength {control.native_max_length} (UTF-16 code units)")
    if control.minimum is not None or control.maximum is not None:
        r.amount_ranges.append((_decimal(control.minimum), _decimal(control.maximum)))
        r.constraints.append(f"native range {control.minimum}..{control.maximum}, whole numbers")
    if control.control == "file":
        r.holds.append(
            ("held_attachment_upload_disabled", "file upload is not enabled in this slice")
        )
    if q.answer_kind in ("group", "unsupported"):
        r.holds.append(("held_unsupported_control", f"answer kind '{q.answer_kind}'"))
    return r


@dataclass
class _Value:
    operation: str
    value: str | None
    choices: list[str]


def value_for(
    control: PrefillControl, q: IntakeQuestion, content: ApprovedPrefillContent, req: _Requirements
) -> _Value | tuple[HeldReason, str]:
    if control.control in ("text", "textarea"):
        text = content.rendered_text
        if text == "":
            return "held_value_empty", "the approved rendered text is empty"
        n = utf16_len(text)
        for limit in req.max_utf16:
            if n > limit:
                return "held_value_too_long", f"{n} UTF-16 code units exceed the limit of {limit}"
        return _Value("fill", text, [])
    if control.control == "number":
        text = content.rendered_text
        if not WHOLE_NUMBER.fullmatch(text):
            return (
                "held_value_format",
                "the approved text is not a whole number in digits only; it is never "
                "stripped, rounded or translated",
            )
        amount = Decimal(text)
        for lo, hi in req.amount_ranges:
            if (lo is not None and amount < lo) or (hi is not None and amount > hi):
                return "held_value_format", f"{text} is outside the confirmed range {lo}..{hi}"
        return _Value("fill", text, [])
    # select / radio / checkbox: only a C-authorized typed value, never prose
    if content.typed_value is None:
        return (
            "held_choice_value_unavailable",
            "no C-authorized typed choice value; prose is never mapped to an option",
        )
    values = list(content.typed_value.values)
    source = {c.value for c in q.choices}
    registered = [o for o in control.options if o != ""]
    if len(values) != len(set(values)) or any(
        v not in registered or v not in source for v in values
    ):
        return "held_choice_not_registered", f"typed value {values} is not a registered option"
    if control.control in ("select", "radio") and len(values) != 1:
        return "held_choice_not_registered", "a single-choice control needs exactly one value"
    ordered = [o for o in registered if o in values]
    op = "select_option" if control.control == "select" else "check"
    return _Value(op, None, ordered)


def _attachments(
    pub: PublishedApplicationVersion,
    mapping: dict[str, QuestionIdMapping],
    reader: AttachmentEvidenceReader,
    organization_id: str,
) -> tuple[list[AttachmentChecklistItem], str]:
    questions = [q for q in pub.intake.questions if q.answer_kind == "file"]
    if not questions:
        return [], "unavailable"
    records: list[TrustedAttachmentRecord] | None
    try:
        records = reader.list_for(organization_id, pub.question_set_id)
    except CapabilityUnavailable:
        records = None
    items: list[AttachmentChecklistItem] = []
    for q in questions:
        spec = q.attachment
        accepted = spec.accepted_types if spec else None
        max_size = spec.max_size_bytes if spec else None
        max_count = spec.max_count if spec else None
        common = {
            "original_question_id": q.question_id,
            "published_question_id": mapping[q.question_id].published_question_id,
            "required_status": q.required_status,
            "accepted_types": accepted,
            "max_size_bytes": max_size,
            "max_count": max_count,
        }
        if records is None:
            items.append(
                AttachmentChecklistItem(
                    **common,
                    status="needs_review_unavailable",
                    findings=["No authorized artifact reader is configured; needs review."],
                    evidence_basis="unavailable",
                )
            )
            continue
        mine = [r for r in records if r.original_question_id == q.question_id]
        findings: list[str] = []
        if not mine and q.required_status == "required":
            findings.append("Required attachment is missing.")
        for r in mine:
            if not r.exists:
                findings.append(f"{r.artifact_id}: the artifact does not exist.")
                continue
            if accepted is None:
                findings.append("Accepted types are not stated; needs review.")
            else:
                allowed = {MEDIA_TYPES.get(t.lower()) for t in accepted}
                if r.detected_media_type not in allowed:
                    findings.append(
                        f"{r.artifact_id}: detected type {r.detected_media_type} is not accepted."
                    )
            if max_size is None:
                findings.append("Maximum size is not stated; needs review.")
            elif r.size_bytes > max_size:
                findings.append(f"{r.artifact_id}: {r.size_bytes} bytes exceeds {max_size}.")
        if max_count is not None and len(mine) > max_count:
            findings.append(f"{len(mine)} artifacts exceed the maximum count of {max_count}.")
        items.append(
            AttachmentChecklistItem(
                **common,
                status="findings" if findings else "matches_trusted_record",
                findings=findings,
                artifact_ids=[r.artifact_id for r in mine],
                evidence_basis=", ".join(sorted({r.basis for r in mine})) or "no records",
            )
        )
    basis = "explicit_test_provider" if records is not None else "unavailable"
    return items, basis


def allowed_input_hashes(portal: PrefillPortal) -> set[str]:
    out = {sha256_hex(prefill_page(portal))}
    fixture = INTAKE_FIXTURES.get(portal.definition_fixture_id)
    if fixture is not None:
        out.add(sha256_hex(read_fixture_bytes(fixture.relative_path)))
    return out


def binding_for(
    pub: PublishedApplicationVersion, portal: PrefillPortal, mapping: dict[str, QuestionIdMapping]
) -> PortalBinding:
    fields = [
        BoundField(
            original_question_id=c.original_question_id,
            published_question_id=mapping[c.original_question_id].published_question_id,
            question_version=mapping[c.original_question_id].question_version,
            field_id=c.field_id,
            control=c.control,
            options=list(c.options),
            native_max_length=c.native_max_length,
            minimum=c.minimum,
            maximum=c.maximum,
        )
        for c in portal.controls
        if c.original_question_id in mapping
    ]
    return PortalBinding(
        portal_fixture_id=portal.fixture_id,
        form_id=portal.form_id,
        form_version=portal.form_version,
        page_sha256=sha256_hex(prefill_page(portal)),
        expected_fingerprint=PREFILL_FORM_VERSIONS[portal.form_id][portal.form_version],
        logical_origin=portal.origin_label,
        fields=fields,
    )


def build_plan(
    *,
    plan_id: str,
    pub: PublishedApplicationVersion,
    portal: PrefillPortal,
    selections: list[PrefillSelection],
    reader: ApprovedPrefillReader,
    attachment_reader: AttachmentEvidenceReader,
    currentness: PrefillDependencyCurrentness | None,
    organization_id: str,
    actor_id: str,
    now: datetime,
    runtime_epoch: str,
    approval_reader_label: str,
) -> PrefillPlan:
    if pub.intake.input.sha256 not in allowed_input_hashes(portal):
        raise PlanRejected(
            422,
            "portal_definition_mismatch",
            "this saved definition was not imported from the selected portal's registered "
            "source, so its question IDs cannot be bound to that portal",
        )
    mapping = {m.original_question_id: m for m in pub.id_mapping}
    by_published = {m.published_question_id: m for m in pub.id_mapping}
    questions = {q.question_id: q for q in pub.intake.questions}
    controls = {c.original_question_id: c for c in portal.controls}
    for sel in selections:
        if sel.published_question_id not in by_published:
            raise PlanRejected(
                422,
                "question_not_in_definition",
                f"'{sel.published_question_id}' is not a published question of this exact "
                "question set (source and C fixture IDs are not substitutes)",
            )
    ordered = sorted(
        selections,
        key=lambda s: questions[by_published[s.published_question_id].original_question_id].order,
    )
    actions: list[PlannedFieldAction] = []
    held: list[HeldField] = []
    planned_by_original: dict[str, PlannedFieldAction] = {}

    def hold(sel: PrefillSelection, reason: HeldReason, detail: str, field: str | None) -> None:
        held.append(
            HeldField(
                published_question_id=sel.published_question_id,
                original_question_id=by_published[sel.published_question_id].original_question_id,
                field_id=field,
                approval_snapshot_id=sel.approval_snapshot_id,
                reason=reason,
                detail=detail,
            )
        )

    for sel in ordered:
        m = by_published[sel.published_question_id]
        q = questions[m.original_question_id]
        control = controls.get(m.original_question_id)
        if control is None:
            hold(sel, "mapping_missing", "the registered portal has no control for it", None)
            continue
        req = requirements_for(q, control, pub.intake.stream_id)
        if req.holds:
            reason, detail = req.holds[0]
            hold(sel, reason, detail, control.field_id)
            continue
        try:
            content = reader.resolve_for_prefill(organization_id, sel.approval_snapshot_id)
        except ApprovalNotUsable as exc:
            hold(sel, "approval_not_usable", exc.reason, control.field_id)
            continue
        problem = content_problem(
            content,
            organization_id=organization_id,
            selection=sel,
            mapping=m,
            question_set_id=pub.question_set_id,
        )
        if problem is not None:
            hold(sel, problem[0], problem[1], control.field_id)
            continue
        value = value_for(control, q, content, req)
        if isinstance(value, tuple):
            hold(sel, value[0], value[1], control.field_id)
            continue
        condition: PlanCondition | None = None
        if q.conditions or control.condition is not None:
            supported = [
                c
                for c in q.conditions
                if c.basis == "structured_definition"
                and c.status == "declared_unverified"
                and c.depends_on_question_id is not None
                and c.expected_value is not None
            ]
            if (
                len(q.conditions) != 1
                or len(supported) != 1
                or control.condition is None
                or control.reveal_selector is None
                or (supported[0].depends_on_question_id, supported[0].expected_value)
                != control.condition
            ):
                hold(
                    sel,
                    "held_condition_unsupported",
                    "the condition is not a single supported structured predicate that matches "
                    "the registry; source condition strings are never executed",
                    control.field_id,
                )
                continue
            parent = planned_by_original.get(control.condition[0])
            if parent is None or parent.intended_choices != [control.condition[1]]:
                hold(
                    sel,
                    "held_parent_not_selected",
                    f"needs the approved parent choice {control.condition[0]} = "
                    f"'{control.condition[1]}' earlier in this plan",
                    control.field_id,
                )
                continue
            condition = PlanCondition(
                parent_published_question_id=parent.published_question_id,
                expected_value=control.condition[1],
                basis="structured_definition_and_registry",
            )
        intended_sha = (
            sha_text(value.value) if value.value is not None else sha_choices(value.choices)
        )
        action = PlannedFieldAction(
            action_index=len(actions),
            published_question_id=sel.published_question_id,
            original_question_id=m.original_question_id,
            question_version=m.question_version,
            field_id=control.field_id,
            control=control.control,
            operation=value.operation,
            approval_snapshot_id=sel.approval_snapshot_id,
            answer_version_id=content.answer_version_id,
            producer_id=content.producer_id,
            producer_epoch=content.producer_epoch,
            template_sha256=content.template_sha256,
            rendered_sha256=content.rendered_sha256,
            dependency_snapshot_sha256=content.dependency_snapshot_sha256,
            dependencies=list(content.dependencies),
            intended_value=value.value,
            intended_choices=value.choices,
            intended_sha256=intended_sha,
            intended_length_utf16=utf16_len(value.value) if value.value is not None else None,
            comparison=comparison_for(control.control),
            constraints=req.constraints,
            requirement_refs=req.refs,
            condition=condition,
            approval_provenance=content.provenance,
        )
        actions.append(action)
        planned_by_original[m.original_question_id] = action

    selected = {s.published_question_id for s in selections}
    unselected = [
        UnselectedRequirement(
            published_question_id=mapping[q.question_id].published_question_id,
            original_question_id=q.question_id,
            required_status=q.required_status,
            answer_kind=q.answer_kind,
        )
        for q in pub.intake.questions
        if mapping[q.question_id].published_question_id not in selected
        and q.required_status in ("required", "conditional", "unknown")
        and q.answer_kind != "file"
    ]
    attachments, attachment_basis = _attachments(pub, mapping, attachment_reader, organization_id)
    binding = pub.context.binding
    draft = {
        "plan_id": plan_id,
        "plan_sha256": "0" * 64,
        "organization_id": organization_id,
        "created_by": actor_id,
        "created_at": now,
        "expires_at": now + timedelta(seconds=PLAN_TTL_SECONDS),
        "runtime_epoch": runtime_epoch,
        "definition": PlanDefinitionRef(
            definition_id=pub.definition_id,
            definition_version=pub.version,
            question_set_id=pub.question_set_id,
            publication_digest=pub.integrity.normalized_digest,
            input_sha256=pub.intake.input.sha256,
            funding_case_id=binding.funding_case_id if binding else None,
            funding_case_version=binding.funding_case_version if binding else None,
            funding_case_digest=binding.funding_case_digest if binding else None,
        ),
        "portal": binding_for(pub, portal, mapping),
        "actions": actions,
        "held": held,
        "unselected_requirements": unselected,
        "attachments": attachments,
        "executable": bool(actions),
        "not_executable_reasons": [] if actions else ["no_eligible_selected_fields"],
        "scope_note": SCOPE_NOTE,
        "producers": ProducerLabel(
            approval_reader=approval_reader_label,
            approval_reader_is_fixture=reader.is_fixture,
            dependency_currentness="not_integrated"
            if currentness is None
            else "explicit_test_provider",
            attachment_evidence=attachment_basis,
        ),
        "budgets": PrefillBudgets(),
        "provenance": PLAN_PROVENANCE,
        "is_fixture": True,
        "mode_label": (
            "FIXTURE prefill demo: registered local fixture portal; approvals from "
            + ("an explicit test provider" if approval_reader_label != "c_reader" else "C")
            + "; nothing is submitted."
        ),
    }
    plan = PrefillPlan.model_validate(draft)
    digest = plan_hash(plan.model_dump(mode="json"))
    return PrefillPlan.model_validate({**plan.model_dump(), "plan_sha256": digest})
