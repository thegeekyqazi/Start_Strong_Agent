"""Validation of every raw model response (C1 spec s5; C2 spec s4; SEC-14, SEC-12, SEC-05).

Shared stage for every role: size cap, strict JSON (duplicate keys and non-finite numbers
rejected) and an iterative depth-bounded scan. The scan rejects approval/status/state keys
(SEC-14) and permission/identity/fact-overwrite keys (SEC-12), even when nested. A strict
per-role schema follows, then reference checks against the authorized evidence. Schema-valid
output is still not truth: the deterministic rules (``rules/``) run after this.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from strongstart_contracts.answers import FactSlotSegment, TextSegment, UnsupportedSegment

from .base import ModelOutputRejected

MAX_RAW_BYTES = 32 * 1024
MAX_DEPTH = 16  # every expected shape is shallow
_ID = r"[a-z0-9][a-z0-9._:-]{0,127}"
SLOT_TOKEN = re.compile(r"\{\{fact:(" + _ID + r")\}\}")
TOKEN = re.compile(r"\{\{(fact|unsupported):(" + _ID + r")\}\}")
SEC14_KEYS = frozenset(
    {"approved", "approval", "approved_by", "is_approved", "status", "state", "decision"}
)
SEC12_KEYS = frozenset(
    {
        "permission",
        "permissions",
        "grant",
        "grants",
        "role",
        "roles",
        "actor_id",
        "organization_id",
        "org_id",
        "facts",
        "fact_values",
        "value",
        "values",
    }
)

_FactId = Annotated[str, StringConstraints(pattern=r"^" + _ID + r"$")]
_Short = Annotated[str, StringConstraints(max_length=300)]


class ModelDraftOutput(BaseModel):
    """Writer role output. Internal, not public."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    text: str = Field(min_length=1, max_length=4000)
    fact_ids: list[_FactId] = Field(max_length=20)
    uncertainties: list[_Short] = Field(max_length=10)


class _PlanItemOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    question_id: _FactId
    evidence_fact_ids: list[_FactId] = Field(max_length=20)
    missing_inputs: list[Annotated[str, StringConstraints(max_length=200)]] = Field(max_length=5)
    repeated_with: list[_FactId] = Field(max_length=20)


class ModelPlanOutput(BaseModel):
    """Planner role output. Internal, not public."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    items: list[_PlanItemOutput] = Field(max_length=100)


OUTPUT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "fact_ids": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["text", "fact_ids", "uncertainties"],
}

PLAN_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question_id": {"type": "string"},
                    "evidence_fact_ids": {"type": "array", "items": {"type": "string"}},
                    "missing_inputs": {"type": "array", "items": {"type": "string"}},
                    "repeated_with": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["question_id", "evidence_fact_ids", "missing_inputs", "repeated_with"],
            },
        }
    },
    "required": ["items"],
}


@dataclass(frozen=True)
class ValidatedDraft:
    text: str
    fact_ids: tuple[str, ...]
    uncertainties: tuple[str, ...]
    segments: tuple[TextSegment | FactSlotSegment | UnsupportedSegment, ...]


@dataclass(frozen=True)
class ValidatedPlanItem:
    question_id: str
    evidence_fact_ids: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    repeated_with: tuple[str, ...]


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ModelOutputRejected(issues=["duplicate_key"])
        out[key] = value
    return out


def _reject_constant(_: str) -> Any:
    raise ModelOutputRejected(issues=["non_finite_number"])


def _scan_structure(node: Any) -> None:
    """Iterative walk (no Python recursion): bounded depth and no forbidden keys."""
    stack: list[tuple[Any, int]] = [(node, 1)]
    while stack:
        current, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise ModelOutputRejected(issues=["too_deeply_nested"])
        if isinstance(current, dict):
            for key, value in current.items():
                k = key.lower() if isinstance(key, str) else ""
                if k in SEC14_KEYS or k.startswith("approv"):
                    raise ModelOutputRejected(issues=["sec14_forbidden_field"])
                if k in SEC12_KEYS:
                    raise ModelOutputRejected(issues=["sec12_forbidden_field"])
                stack.append((value, depth + 1))
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)


def parse_model_json(raw: str) -> dict[str, Any]:
    """Shared first stage for every role's raw output."""
    if len(raw.encode("utf-8")) > MAX_RAW_BYTES:
        raise ModelOutputRejected(issues=["oversize"])
    try:
        data = json.loads(
            raw, object_pairs_hook=_reject_duplicates, parse_constant=_reject_constant
        )
    except json.JSONDecodeError:
        raise ModelOutputRejected(issues=["malformed_json"]) from None
    except RecursionError:
        raise ModelOutputRejected(issues=["too_deeply_nested"]) from None
    if not isinstance(data, dict):
        raise ModelOutputRejected(issues=["not_an_object"])
    _scan_structure(data)
    return data


def _schema_issues(exc: ValidationError) -> list[str]:
    return ["schema", *sorted({str(e["type"]) for e in exc.errors()})]


def segments_for(text: str) -> tuple[TextSegment | FactSlotSegment | UnsupportedSegment, ...]:
    out: list[TextSegment | FactSlotSegment | UnsupportedSegment] = []
    pos = 0
    for m in TOKEN.finditer(text):
        if m.start() > pos:
            out.append(TextSegment(kind="text", text=text[pos : m.start()]))
        if m.group(1) == "fact":
            out.append(FactSlotSegment(kind="fact_slot", fact_id=m.group(2)))
        else:
            out.append(UnsupportedSegment(kind="unsupported", reason=m.group(2)))
        pos = m.end()
    if pos < len(text):
        out.append(TextSegment(kind="text", text=text[pos:]))
    return tuple(out)


def validate_draft_output(raw: str, allowed_fact_ids: frozenset[str]) -> ValidatedDraft:
    """Writer output: return a validated draft or raise ``ModelOutputRejected``."""
    data = parse_model_json(raw)
    try:
        parsed = ModelDraftOutput.model_validate(data)
    except ValidationError as exc:
        raise ModelOutputRejected(issues=_schema_issues(exc)) from None

    slot_ids = [m.group(1) for m in SLOT_TOKEN.finditer(parsed.text)]
    residue = TOKEN.sub("", parsed.text)
    if "{{" in residue or "}}" in residue:
        raise ModelOutputRejected(issues=["malformed_slot"])
    unknown = sorted({fid for fid in [*slot_ids, *parsed.fact_ids] if fid not in allowed_fact_ids})
    if unknown:
        raise ModelOutputRejected(issues=["unknown_fact_id"])
    if set(slot_ids) != set(parsed.fact_ids) or len(parsed.fact_ids) != len(set(parsed.fact_ids)):
        raise ModelOutputRejected(issues=["fact_ids_mismatch"])

    return ValidatedDraft(
        text=parsed.text,
        fact_ids=tuple(parsed.fact_ids),
        uncertainties=tuple(parsed.uncertainties),
        segments=segments_for(parsed.text),
    )


def validate_plan_output(
    raw: str, question_ids: tuple[str, ...], allowed_fact_ids: frozenset[str]
) -> tuple[ValidatedPlanItem, ...]:
    """Planner output: exactly one item per question; only allowed facts (s7, SEC-12)."""
    data = parse_model_json(raw)
    try:
        parsed = ModelPlanOutput.model_validate(data)
    except ValidationError as exc:
        raise ModelOutputRejected(issues=_schema_issues(exc)) from None
    got = [i.question_id for i in parsed.items]
    if sorted(got) != sorted(question_ids) or len(got) != len(set(got)):
        raise ModelOutputRejected(issues=["plan_questions_mismatch"])
    known = set(question_ids)
    for item in parsed.items:
        if any(f not in allowed_fact_ids for f in item.evidence_fact_ids):
            raise ModelOutputRejected(issues=["unknown_fact_id"])
        if any(r not in known or r == item.question_id for r in item.repeated_with):
            raise ModelOutputRejected(issues=["unknown_repeated_question"])
    order = {q: n for n, q in enumerate(question_ids)}
    return tuple(
        ValidatedPlanItem(
            question_id=i.question_id,
            evidence_fact_ids=tuple(i.evidence_fact_ids),
            missing_inputs=tuple(i.missing_inputs),
            repeated_with=tuple(i.repeated_with),
        )
        for i in sorted(parsed.items, key=lambda i: order[i.question_id])
    )
