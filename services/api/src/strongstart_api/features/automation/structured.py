"""Bounded structured-JSON application definition parser (parser ``b2-structured-json/1``).

Input format ``strongstart-application-definition`` v1 (documented in the B2-AUTO-001
handoff). Safety properties:

- strict UTF-8 decoding, no byte-order mark, size/depth/count limits;
- nesting depth checked by a string-aware scan *before* ``json.loads`` (no recursion blow-up);
- duplicate object keys rejected; NaN/Infinity rejected;
- strict pydantic schema (no type coercion) for every recognised object;
- unknown top-level/question keys are preserved verbatim as original evidence, never
  interpreted; authority/approval/organization claims inside the upload are ignored.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from strongstart_contracts.automation_intake import (
    AttachmentSpec,
    ChoiceOption,
    ConditionRecord,
    ExactText,
    Finding,
    SourceLocator,
)
from strongstart_contracts.common import StableId

from .intake_errors import duplicate_id, malformed
from .normalize import LimitDraft, QuestionDraft, exact

PARSER_ID = "b2-structured-json"
PARSER_VERSION = "1"
MAX_JSON_BYTES = 256 * 1024
MAX_DEPTH = 12

Str = Annotated[str, StringConstraints(max_length=20_000)]
ShortStr = Annotated[str, StringConstraints(max_length=500)]
Decimalish = Annotated[str, StringConstraints(pattern=r"^(0|[1-9][0-9]{0,14})(\.[0-9]{1,6})?$")]

TOP_KEYS = {
    "format",
    "format_version",
    "definition_id",
    "opportunity_id",
    "stream_id",
    "cycle_id",
    "title",
    "provenance_note",
    "source",
    "questions",
}
QUESTION_KEYS = {
    "question_id",
    "number",
    "section",
    "text",
    "instructions",
    "scope",
    "type",
    "required",
    "condition",
    "limits",
    "choices",
    "multiple",
    "attachment",
}
AUTHORITY_CLAIM_KEYS = {
    "approved",
    "approval",
    "approval_status",
    "reviewed",
    "review_status",
    "verified",
    "verification_status",
    "authority",
    "authority_status",
    "organization_id",
    "org_id",
    "is_fixture",
    "trusted",
}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class InLimit(_Strict):
    maximum: int | Decimalish | None = None
    minimum: int | Decimalish | None = None
    unit: Literal["words", "characters", "amount", "unknown"]
    counting_convention: StableId | None = None
    stream: StableId | None = None
    text: Str


class InChoice(_Strict):
    value: ShortStr
    label: ShortStr | None = None


class InCondition(_Strict):
    text: Str | None = None
    depends_on: StableId | None = None
    equals: ShortStr | None = None


class InAttachment(_Strict):
    accepted_types: list[Annotated[str, StringConstraints(max_length=100)]] | None = Field(
        default=None, max_length=50
    )
    max_size_bytes: int | None = Field(default=None, ge=0)
    max_count: int | None = Field(default=None, ge=0, le=1000)


class InQuestion(_Strict):
    question_id: StableId
    number: ShortStr | None = None
    section: ShortStr | None = None
    text: Annotated[str, StringConstraints(min_length=1, max_length=20_000)]
    instructions: list[Str] = Field(default_factory=list, max_length=50)
    scope: Literal["organization", "program", "unknown"] = "unknown"
    type: Literal["text", "number", "select", "choice", "group", "file", "unsupported"]
    required: Literal["required", "optional", "conditional", "unknown"] = "unknown"
    condition: InCondition | None = None
    limits: list[InLimit] = Field(default_factory=list, max_length=20)
    choices: list[InChoice] = Field(default_factory=list, max_length=200)
    multiple: bool | None = None
    attachment: InAttachment | None = None


class InSource(_Strict):
    capture_id: StableId
    artifact_id: StableId


class InDefinition(_Strict):
    format: Literal["strongstart-application-definition"]
    format_version: Literal["1"]
    definition_id: StableId
    opportunity_id: StableId | None = None
    stream_id: StableId | None = None
    cycle_id: StableId | None = None
    title: ShortStr | None = None
    provenance_note: Str | None = None
    source: InSource | None = None
    questions: list[dict[str, Any]] = Field(min_length=1, max_length=200)


class _DuplicateKey(ValueError):
    pass


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise _DuplicateKey(k)
        out[k] = v
    return out


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-finite number {name} is not allowed")


def _check_depth(text: str, limit: int) -> None:
    depth = 0
    in_str = False
    esc = False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in "[{":
            depth += 1
            if depth > limit:
                raise malformed(f"JSON nesting deeper than {limit} levels", limit_depth=limit)
        elif ch in "]}":
            depth -= 1


def decode_strict_json(data: bytes, *, max_depth: int = MAX_DEPTH) -> Any:
    """Safe decode: strict UTF-8, bounded depth, unique keys, finite numbers only."""
    if data.startswith(b"\xef\xbb\xbf"):
        raise malformed("a UTF-8 byte-order mark is not accepted")
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        raise malformed("input is not valid UTF-8") from None
    _check_depth(text, max_depth)
    try:
        return json.loads(
            text, object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant
        )
    except _DuplicateKey as exc:
        raise malformed("duplicate JSON object key", key=str(exc)[:100]) from None
    except (ValueError, RecursionError) as exc:
        detail = {}
        if isinstance(exc, json.JSONDecodeError):
            detail = {"line": exc.lineno, "column": exc.colno}
        raise malformed("invalid JSON", **detail) from None


def _issues(exc: ValidationError, prefix: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [{"loc": [*prefix, *e.get("loc", ())], "type": e.get("type")} for e in exc.errors()[:50]]


def _split_unknown(obj: dict[str, Any], known: set[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    kept = {k: v for k, v in obj.items() if k in known}
    extra = {k: v for k, v in obj.items() if k not in known}
    return kept, extra


def _limit_value(v: int | str | None) -> str | None:
    if v is None:
        return None
    if isinstance(v, int):
        if v < 0:
            raise malformed("limits must be non-negative")
        return str(v)
    return v


SourceRefFactory = Callable[[str], Any]


def parse_structured(
    data: bytes, make_source_ref: SourceRefFactory
) -> tuple[InDefinition, list[QuestionDraft], dict[str, Any], list[Finding]]:
    """Parse a structured definition into question drafts. Raises ApiError on invalid input."""
    raw = decode_strict_json(data)
    if not isinstance(raw, dict):
        raise malformed("top-level JSON value must be an object")
    top, top_extra = _split_unknown(raw, TOP_KEYS)
    try:
        definition = InDefinition.model_validate(top)
    except ValidationError as exc:
        raise malformed("definition does not match the schema", issues=_issues(exc)) from None

    findings: list[Finding] = []
    original_evidence: dict[str, Any] = {}
    if top_extra:
        original_evidence["unrecognized_top_level"] = top_extra
        findings.append(_unknown_finding(sorted(top_extra), None))
    drafts: list[QuestionDraft] = []
    seen: dict[str, int] = {}
    dupes: set[str] = set()
    for i, qraw in enumerate(definition.questions):
        ptr = f"/questions/{i}"
        if not isinstance(qraw, dict):
            raise malformed("each question must be an object", issues=[{"loc": [ptr]}])
        qkept, qextra = _split_unknown(qraw, QUESTION_KEYS)
        try:
            q = InQuestion.model_validate(qkept)
        except ValidationError as exc:
            raise malformed(
                "question does not match the schema", issues=_issues(exc, ("questions", i))
            ) from None
        if q.question_id in seen:
            dupes.add(q.question_id)
        seen[q.question_id] = i
        drafts.append(_draft(q, i, ptr, qextra, definition.stream_id, make_source_ref))
    if dupes:
        raise duplicate_id("question IDs must be unique; nothing was renumbered", list(dupes))
    return definition, drafts, original_evidence, findings


def _unknown_finding(keys: list[str], question_id: str | None) -> Finding:
    claims = sorted(k for k in keys if k in AUTHORITY_CLAIM_KEYS)
    if claims:
        return Finding(
            code="untrusted_authority_claim_ignored",
            severity="warning",
            message=f"Ignored self-asserted authority/approval/scope fields {claims}; they are "
            "preserved as evidence only and grant nothing.",
            question_id=question_id,
        )
    return Finding(
        code="unrecognized_field_preserved",
        severity="info",
        message=f"Unrecognised fields {keys[:20]} preserved as original evidence, not interpreted.",
        question_id=question_id,
    )


def _draft(
    q: InQuestion,
    index: int,
    ptr: str,
    extra: dict[str, Any],
    stream: str | None,
    make_source_ref: SourceRefFactory,
) -> QuestionDraft:
    def loc(sub: str) -> SourceLocator:
        return SourceLocator(kind="json_pointer", value=f"{ptr}{sub}")

    qfindings: list[Finding] = []
    if extra:
        qfindings.append(_unknown_finding(sorted(extra), q.question_id))
    instructions = [exact(t, loc(f"/instructions/{j}")) for j, t in enumerate(q.instructions)]
    limits: list[LimitDraft] = []
    for j, lim in enumerate(q.limits):
        mx, mn = _limit_value(lim.maximum), _limit_value(lim.minimum)
        if mx is None and mn is None:
            raise malformed("a limit needs a minimum or maximum", issues=[{"loc": [ptr, j]}])
        limits.append(
            LimitDraft(
                kind="structured_definition",
                unit=lim.unit,
                evidence=exact(lim.text, loc(f"/limits/{j}/text")),
                minimum=mn,
                maximum=mx,
                counting_convention=lim.counting_convention,
                stream=lim.stream if lim.unit == "amount" else None,
            )
        )
    conditions: list[ConditionRecord] = []
    if q.condition is not None:
        c = q.condition
        conditions.append(
            ConditionRecord(
                predicate_text=c.text,
                depends_on_question_id=c.depends_on,
                expected_value=c.equals,
                basis="structured_definition",
                status="declared_unverified" if c.depends_on else "unresolved",
                locator=loc("/condition"),
            )
        )
    attachment = None
    if q.attachment is not None:
        a = q.attachment
        attachment = AttachmentSpec(
            accepted_types=list(a.accepted_types) if a.accepted_types is not None else None,
            max_size_bytes=a.max_size_bytes,
            max_count=a.max_count,
            multiple=(a.max_count > 1) if a.max_count is not None else None,
            basis="structured_definition",
            evidence=[exact(json.dumps(q.attachment.model_dump()), loc("/attachment"))],
        )
    if q.scope == "unknown":
        qfindings.append(
            Finding(
                code="scope_unknown",
                severity="info",
                message="Organization/program scope is not stated.",
                question_id=q.question_id,
            )
        )
    choices = [
        ChoiceOption(
            value=c.value,
            label=exact(c.label, loc(f"/choices/{k}/label")) if c.label is not None else None,
        )
        for k, c in enumerate(q.choices)
    ]
    choice_mode: Literal["single", "multiple"] | None = None
    if q.type in ("choice", "select", "group"):
        choice_mode = None if q.multiple is None else ("multiple" if q.multiple else "single")
    section: ExactText | None = exact(q.section, loc("/section")) if q.section else None
    return QuestionDraft(
        question_id=q.question_id,
        order=index,
        text=exact(q.text, loc("/text")),
        answer_kind=q.type,
        required_status=q.required,
        scope=q.scope,
        source_ref=make_source_ref(f"{ptr}"),
        original_number=q.number,
        section=section,
        instructions=instructions,
        conditions=conditions,
        limits=limits,
        choices=choices,
        choice_mode=choice_mode,
        attachment=attachment,
        unrecognized_fields=extra,
        findings=qfindings,
        primary_stream=stream,
    )
