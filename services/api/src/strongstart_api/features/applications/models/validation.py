"""Validation of every raw model response (C1 spec s5; SEC-14, SEC-05 boundary).

Order matters: size cap, strict JSON (duplicate keys and non-finite numbers rejected),
an iterative depth-bounded forbidden-key scan (approval/status/state cannot be smuggled
in, even nested), strict schema with extra fields forbidden, then fact-slot resolution
against the evidence bundle's ``allowed_fact_ids``. Schema-valid output is still not truth:
numeric/source/claim checks are later rules (C2/A3).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from strongstart_contracts.answers import FactSlotSegment, TextSegment

from .base import ModelOutputRejected

MAX_RAW_BYTES = 32 * 1024
MAX_DEPTH = 16  # the expected shape is flat (object -> list -> string)
SLOT_TOKEN = re.compile(r"\{\{fact:([a-z0-9][a-z0-9._:-]{0,127})\}\}")
FORBIDDEN_KEYS = frozenset(
    {"approved", "approval", "approved_by", "is_approved", "status", "state", "decision"}
)

_FactId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9._:-]{0,127}$")]


class ModelDraftOutput(BaseModel):
    """The only shape a model may return for ``draft_answer``. Internal, not public."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    text: str = Field(min_length=1, max_length=4000)
    fact_ids: list[_FactId] = Field(max_length=20)
    uncertainties: list[Annotated[str, StringConstraints(max_length=300)]] = Field(max_length=10)


OUTPUT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "fact_ids": {"type": "array", "items": {"type": "string"}},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["text", "fact_ids", "uncertainties"],
}


@dataclass(frozen=True)
class ValidatedDraft:
    text: str
    fact_ids: tuple[str, ...]
    uncertainties: tuple[str, ...]
    segments: tuple[TextSegment | FactSlotSegment, ...]


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
    """Iterative walk (no Python recursion): bounded depth and no approval/status keys."""
    stack: list[tuple[Any, int]] = [(node, 1)]
    while stack:
        current, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise ModelOutputRejected(issues=["too_deeply_nested"])
        if isinstance(current, dict):
            for key, value in current.items():
                k = key.lower() if isinstance(key, str) else ""
                if k in FORBIDDEN_KEYS or k.startswith("approv"):
                    raise ModelOutputRejected(issues=["sec14_forbidden_field"])
                stack.append((value, depth + 1))
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)


def segments_for(text: str) -> tuple[TextSegment | FactSlotSegment, ...]:
    out: list[TextSegment | FactSlotSegment] = []
    pos = 0
    for m in SLOT_TOKEN.finditer(text):
        if m.start() > pos:
            out.append(TextSegment(kind="text", text=text[pos : m.start()]))
        out.append(FactSlotSegment(kind="fact_slot", fact_id=m.group(1)))
        pos = m.end()
    if pos < len(text):
        out.append(TextSegment(kind="text", text=text[pos:]))
    return tuple(out)


def validate_draft_output(raw: str, allowed_fact_ids: frozenset[str]) -> ValidatedDraft:
    """Return a validated draft or raise ``ModelOutputRejected`` with issue codes."""
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

    try:
        parsed = ModelDraftOutput.model_validate(data)
    except ValidationError as exc:
        kinds = sorted({str(e["type"]) for e in exc.errors()})
        raise ModelOutputRejected(issues=["schema", *kinds]) from None

    slot_ids = [m.group(1) for m in SLOT_TOKEN.finditer(parsed.text)]
    residue = SLOT_TOKEN.sub("", parsed.text)
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
