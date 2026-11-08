"""Shared normalization for imported questions (normalization version ``b2-norm/1``).

Pure functions: no I/O. Turns parser-specific question drafts into typed
``IntakeQuestion`` records, keeps competing limits side by side, holds affected
questions and projects the result onto the shared strict DTOs.

Limit text recognition is deliberately narrow (see PATTERNS in the handoff). It
recognises "Maximum N words/characters", "Max N" (unit unknown), "up to N words",
"N words" and numeric ranges for number fields. It never picks one limit among
conflicting candidates and never assumes a character counting convention.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from strongstart_contracts.automation import (
    ApplicationDefinition,
    LimitConflict,
    Question,
    QuestionLimit,
    QuestionSet,
)
from strongstart_contracts.automation_intake import (
    AttachmentSpec,
    ChoiceOption,
    ConditionRecord,
    ExactText,
    Finding,
    IntakeLimit,
    IntakeQuestion,
    LimitConflictRecord,
    SourceLocator,
)
from strongstart_contracts.common import Provenance, SourceReference

NORMALIZATION_VERSION = "b2-norm/1"

Unit = Literal["words", "characters", "amount", "utf16_code_units", "unknown"]
AnswerKind = Literal["text", "number", "select", "choice", "group", "file", "unsupported"]
RequiredStatus = Literal["required", "optional", "conditional", "unknown"]
Scope = Literal["organization", "program", "unknown"]

_NUM = r"(\d{1,3}(?:,\d{3})+|\d+)"
_UNIT = r"(words?|characters?|chars?)"
_MAX_RE = re.compile(
    rf"\b(?:max(?:imum)?\.?|up\s+to|no\s+more\s+than|at\s+most|limit(?:ed)?\s+to)\s*"
    rf"(?:of\s+)?{_NUM}(?:\s*{_UNIT}\b)?",
    re.IGNORECASE,
)
_BARE_RE = re.compile(rf"\b{_NUM}\s*{_UNIT}\b", re.IGNORECASE)
_RANGE_RE = re.compile(rf"{_NUM}\s*(?:to|-|\u2013|\u2014)\s*{_NUM}", re.IGNORECASE)
_TEXT_KINDS = {"text"}


def display(text: str) -> str:
    return " ".join(text.split())


def exact(text: str, locator: SourceLocator) -> ExactText:
    return ExactText(text=text, display_text=display(text), locator=locator)


def _num(raw: str) -> str:
    return str(int(raw.replace(",", "")))


def _unit(raw: str | None) -> Unit:
    if raw is None:
        return "unknown"
    return "words" if raw.lower().startswith("word") else "characters"


@dataclass(frozen=True)
class TextLimit:
    minimum: str | None
    maximum: str | None
    unit: Unit


def limits_from_text(text: str, answer_kind: str) -> list[TextLimit]:
    """Recognise explicit limit wording. Returns every match; never chooses among them."""
    if answer_kind == "number":
        m = _RANGE_RE.search(text)
        if m:
            return [TextLimit(_num(m.group(1)), _num(m.group(2)), "amount")]
        found = [TextLimit(None, _num(m.group(1)), "amount") for m in _MAX_RE.finditer(text)]
        return found
    if answer_kind not in _TEXT_KINDS:
        return []
    out: list[TextLimit] = []
    spans: list[tuple[int, int]] = []
    for m in _MAX_RE.finditer(text):
        out.append(TextLimit(None, _num(m.group(1)), _unit(m.group(2))))
        spans.append(m.span())
    for m in _BARE_RE.finditer(text):
        if any(a <= m.start() < b for a, b in spans):
            continue
        out.append(TextLimit(None, _num(m.group(1)), _unit(m.group(2))))
    return out


@dataclass
class LimitDraft:
    kind: Literal[
        "instruction_text", "structured_definition", "native_dom_maxlength", "native_dom_range"
    ]
    unit: Unit
    evidence: ExactText
    minimum: str | None = None
    maximum: str | None = None
    counting_convention: str | None = None
    stream: str | None = None


@dataclass
class QuestionDraft:
    """Parser output before normalization. ``text``/instructions are exact source text."""

    question_id: str
    order: int
    text: ExactText
    answer_kind: AnswerKind
    required_status: RequiredStatus
    scope: Scope
    source_ref: SourceReference
    original_number: str | None = None
    section: ExactText | None = None
    instructions: list[ExactText] = field(default_factory=list)
    conditions: list[ConditionRecord] = field(default_factory=list)
    limits: list[LimitDraft] = field(default_factory=list)
    choices: list[ChoiceOption] = field(default_factory=list)
    choice_mode: Literal["single", "multiple"] | None = None
    attachment: AttachmentSpec | None = None
    unrecognized_fields: dict[str, object] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    primary_stream: str | None = None


def _semantic_key(lim: IntakeLimit) -> tuple[str, str | None, str | None]:
    return (lim.unit, lim.minimum, lim.maximum)


def finalize_question(d: QuestionDraft) -> tuple[IntakeQuestion, list[Finding]]:
    """Build the typed question: instruction-derived limits, conflicts, holds and findings."""
    findings = list(d.findings)
    drafts = list(d.limits)
    explicit = {
        (x.unit, x.minimum, x.maximum, x.stream) for x in drafts if x.kind != "native_dom_range"
    }
    for instr in d.instructions:
        for tl in limits_from_text(instr.text, d.answer_kind):
            stream = d.primary_stream if tl.unit == "amount" else None
            if (tl.unit, tl.minimum, tl.maximum, stream) in explicit:
                continue  # same constraint already recorded from structured input
            explicit.add((tl.unit, tl.minimum, tl.maximum, stream))
            drafts.append(
                LimitDraft("instruction_text", tl.unit, instr, tl.minimum, tl.maximum, None, stream)
            )

    limits: list[IntakeLimit] = []
    for i, ld in enumerate(drafts, start=1):
        native = ld.kind in ("native_dom_maxlength", "native_dom_range")
        if ld.kind == "native_dom_maxlength":
            convention, status = "html-maxlength-utf16-code-units", "defined_by_html_spec"
        elif ld.counting_convention:
            convention, status = ld.counting_convention, "declared_in_source"
        else:
            convention, status = "unknown", "unknown_pending_confirmation"
        limits.append(
            IntakeLimit(
                limit_id=f"{d.question_id}.limit-{i}",
                kind=ld.kind,
                minimum=ld.minimum,
                maximum=ld.maximum,
                unit=ld.unit,
                counting_convention=convention,
                convention_status=status,
                authority_status="browser_property" if native else "imported_provisional",
                applies_to_stream=ld.stream,
                evidence=ld.evidence,
            )
        )

    conflicts: list[LimitConflictRecord] = []
    holds: list[str] = []
    semantic = [x for x in limits if x.kind in ("instruction_text", "structured_definition")]
    by_stream: dict[tuple[bool, str | None], list[IntakeLimit]] = {}
    for x in semantic:
        by_stream.setdefault((x.unit == "amount", x.applies_to_stream), []).append(x)
    for (is_amount, _stream), group in by_stream.items():
        if len({_semantic_key(x) for x in group}) > 1:
            cid = f"{d.question_id}.conflict-{len(conflicts) + 1}"
            alts = "; ".join(f'"{x.evidence.display_text}"' for x in group)
            conflicts.append(
                LimitConflictRecord(
                    conflict_id=cid,
                    kind="competing_instruction_limits",
                    limit_ids=[x.limit_id for x in group],
                    description=f"Competing {'amount ' if is_amount else ''}limits: {alts}",
                )
            )
            holds.append(f"limit_conflict:{cid}")
            findings.append(
                Finding(
                    code="limit_conflict",
                    severity="blocker",
                    message=f"Imported instructions disagree ({alts}). Both are kept; "
                    "action is held until staff confirm the authoritative limit.",
                    question_id=d.question_id,
                )
            )
    natives = [x for x in limits if x.kind == "native_dom_maxlength"]
    for nat in natives:
        for x in semantic:
            if x.unit == "characters" and x.maximum is not None and x.maximum != nat.maximum:
                cid = f"{d.question_id}.conflict-{len(conflicts) + 1}"
                conflicts.append(
                    LimitConflictRecord(
                        conflict_id=cid,
                        kind="instruction_vs_native_maxlength",
                        limit_ids=[x.limit_id, nat.limit_id],
                        description=(
                            f"Instruction says {x.maximum} characters (convention unknown); "
                            f"native maxlength is {nat.maximum} UTF-16 code units."
                        ),
                    )
                )
                holds.append(f"native_maxlength_conflict:{cid}")
                findings.append(
                    Finding(
                        code="native_maxlength_conflict",
                        severity="blocker",
                        message=conflicts[-1].description + " Both are kept; action is held.",
                        question_id=d.question_id,
                    )
                )
    for x in semantic:
        if x.unit == "unknown":
            holds.append(f"unknown_limit_unit:{x.limit_id}")
            findings.append(
                Finding(
                    code="unknown_limit_unit",
                    severity="blocker",
                    message=f'"{x.evidence.display_text}" gives no unit; it is not assumed to be '
                    "words or characters.",
                    question_id=d.question_id,
                    locator=x.evidence.locator,
                )
            )
        elif x.unit in ("words", "characters") and x.convention_status != "declared_in_source":
            findings.append(
                Finding(
                    code="unknown_counting_convention",
                    severity="warning",
                    message=f"{x.unit} limit {x.maximum}: counting convention is unknown "
                    "(pending confirmation; C's counter owns APP-01).",
                    question_id=d.question_id,
                )
            )
        if x.unit == "amount" and x.applies_to_stream and x.applies_to_stream != d.primary_stream:
            findings.append(
                Finding(
                    code="stream_specific_limit",
                    severity="info",
                    message=f"Amount limit for stream '{x.applies_to_stream}' is kept as metadata "
                    "and not applied to this question's stream.",
                    question_id=d.question_id,
                )
            )
    for c in d.conditions:
        if c.status == "unresolved":
            holds.append("condition_unresolved")
            findings.append(
                Finding(
                    code="condition_unresolved",
                    severity="warning",
                    message="Conditional logic could not be resolved from the source.",
                    question_id=d.question_id,
                    locator=c.locator,
                )
            )
    if d.required_status == "unknown":
        findings.append(
            Finding(
                code="required_status_unknown",
                severity="warning",
                message="The source does not state whether this question is required.",
                question_id=d.question_id,
            )
        )
    if d.required_status == "conditional" and not d.conditions:
        holds.append("condition_unresolved")
        findings.append(
            Finding(
                code="condition_unresolved",
                severity="warning",
                message="Marked conditional but no predicate was supplied.",
                question_id=d.question_id,
            )
        )
    if d.answer_kind == "file" and (
        d.attachment is None
        or d.attachment.accepted_types is None
        or d.attachment.max_size_bytes is None
        or d.attachment.max_count is None
    ):
        findings.append(
            Finding(
                code="attachment_constraints_unknown",
                severity="warning",
                message="Some attachment constraints (type/size/count) are not stated; "
                "they stay unknown.",
                question_id=d.question_id,
            )
        )

    question = IntakeQuestion(
        question_id=d.question_id,
        order=d.order,
        original_number=d.original_number,
        section=d.section,
        text=d.text,
        instructions=d.instructions,
        scope=d.scope,
        answer_kind=d.answer_kind,
        required_status=d.required_status,
        conditions=d.conditions,
        limits=limits,
        limit_conflicts=conflicts,
        choices=d.choices,
        choice_mode=d.choice_mode,
        attachment=d.attachment,
        source_ref=d.source_ref,
        action_state="held_unresolved_requirement" if holds else "no_blocker_detected_not_approved",
        hold_reasons=sorted(set(holds)),
        unrecognized_fields=dict(d.unrecognized_fields),
    )
    return question, findings


# --------------------------------------------------------------------------- projections

_ANSWER_TYPE = {
    "text": "text",
    "number": "number",
    "select": "choice",
    "choice": "choice",
    "group": "choice",
    "file": "attachment",
    "unsupported": "other",
}


def _int(value: str | None) -> int | None:
    if value is None:
        return None
    d = Decimal(value)
    return int(d) if d == d.to_integral_value() and d >= 0 else None


def _shared_limit(x: IntakeLimit, ref: SourceReference) -> QuestionLimit:
    unit: Literal["words", "characters", "amount", "unknown"]
    if x.unit == "utf16_code_units":
        unit = "characters"
    else:
        unit = x.unit
    convention = None if x.counting_convention == "unknown" else x.counting_convention
    return QuestionLimit(
        maximum=_int(x.maximum), unit=unit, counting_convention=convention, source_refs=[ref]
    )


def to_shared_question(q: IntakeQuestion, primary_stream: str | None = None) -> Question:
    """Project onto the strict shared Question. A single limit is set only when unambiguous."""
    semantic = [
        x
        for x in q.limits
        if x.kind in ("instruction_text", "structured_definition")
        and (x.unit != "amount" or x.applies_to_stream in (None, primary_stream))
    ]
    limit = (
        _shared_limit(semantic[0], q.source_ref)
        if len(semantic) == 1 and not q.limit_conflicts
        else None
    )
    by_id = {x.limit_id: x for x in q.limits}
    conflicts = [
        LimitConflict(
            conflict_id=c.conflict_id,
            description=c.description,
            candidate_limits=[_shared_limit(by_id[i], q.source_ref) for i in c.limit_ids],
        )
        for c in q.limit_conflicts
    ]
    answer_type = _ANSWER_TYPE[q.answer_kind]
    if q.answer_kind == "number" and any(x.unit == "amount" for x in q.limits):
        answer_type = "amount"
    attachments: list[str] = []
    if q.attachment is not None:
        a = q.attachment
        attachments.append(
            f"accepted_types={','.join(a.accepted_types) if a.accepted_types else 'unknown'}; "
            f"max_size_bytes={a.max_size_bytes if a.max_size_bytes is not None else 'unknown'}; "
            f"max_count={a.max_count if a.max_count is not None else 'unknown'}; basis={a.basis}"
        )
    return Question(
        question_id=q.question_id,
        question_version=q.question_version,
        original_text=q.text.text,
        order=q.order,
        section=q.section.text if q.section else None,
        answer_type=answer_type,
        required={"required": True, "optional": False}.get(q.required_status),
        limit=limit,
        conflicts=conflicts,
        conditions=[
            c.predicate_text or f"{c.depends_on_question_id} == {c.expected_value}"
            for c in q.conditions
        ],
        attachments=attachments,
        source_refs=[q.source_ref],
    )


def project(
    *,
    import_id: str,
    definition_id: str | None,
    opportunity_id: str | None,
    form_id: str | None,
    questions: list[IntakeQuestion],
    provenance: Provenance,
    primary_stream: str | None = None,
) -> tuple[QuestionSet | None, ApplicationDefinition | None, list[str]]:
    """Shared-DTO projections; omitted (with a note) when a required ID is unknown."""
    notes: list[str] = []
    if not questions:
        return None, None, ["no questions: shared QuestionSet not produced"]
    if opportunity_id is None:
        notes.append("opportunity unknown: shared QuestionSet/ApplicationDefinition not produced")
        return None, None, notes
    qs_id = f"qs-{import_id}"
    qs = QuestionSet(
        question_set_id=qs_id,
        opportunity_id=opportunity_id,
        questions=[to_shared_question(q, primary_stream) for q in questions],
        provenance=provenance,
    )
    app = ApplicationDefinition(
        application_definition_id=definition_id or f"appdef-{import_id}",
        opportunity_id=opportunity_id,
        question_set_id=qs_id,
        form_id=form_id,
        provenance=provenance,
    )
    return qs, app, notes
