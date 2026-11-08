"""Field-map validation and form fingerprinting (pure; no browser). AUT-01 inspection subset.

Fingerprint ``b2-form-fp/1``: SHA-256 over the canonical JSON (sorted keys, compact
separators) of the sorted list of per-control identity records::

    {tag, input_type, dom_id, name, role, contenteditable, required, disabled, readonly,
     max_length, min, max, step, accept, multiple, option_value, options:[values],
     condition}

Excluded as volatile display/state data: label/legend/description text, visibility,
observed order, current values and every ``data-fixture-*`` attribute other than the
declared condition. A mapping is valid only when each expected field (or declared
radio/checkbox group) resolves with the expected cardinality and type; there is no
first-match fallback.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from strongstart_contracts.automation import FieldMapping, FormMap
from strongstart_contracts.automation_intake import (
    FieldMappingCheck,
    Finding,
    IntakeQuestion,
    ObservedField,
    ObservedOption,
)

from .registry import ExpectedField

FieldType = Literal["text", "textarea", "number", "select", "file", "checkbox", "radio"]
TEXT_TYPES = {"text", "email", "url", "tel", "search"}
SUPPORTED_INPUTS = TEXT_TYPES | {"number", "radio", "checkbox", "file"}


def _str_or_none(v: Any) -> str | None:
    return None if v is None else str(v)


def observed_fields(raw: list[dict[str, Any]]) -> list[ObservedField]:
    out: list[ObservedField] = []
    for i, f in enumerate(raw):
        tag = str(f.get("tag") or "")
        itype = _str_or_none(f.get("type"))
        supported = (
            (tag == "input" and itype in SUPPORTED_INPUTS)
            or tag in ("textarea", "select")
            or (tag == "button")
        ) and not f.get("contentEditable")
        dom_id, name = _str_or_none(f.get("id")), _str_or_none(f.get("name"))
        key = f"id:{dom_id}" if dom_id else (f"name:{name}" if name else f"index:{i}")
        accept = f.get("accept")
        out.append(
            ObservedField(
                observed_index=i,
                field_key=key,
                tag=tag,
                input_type=itype,
                dom_id=dom_id,
                name=name,
                role=_str_or_none(f.get("role")),
                label_text=_str_or_none(f.get("label")),
                legend_text=_str_or_none(f.get("legend")),
                described_by_text=[str(t) for t in f.get("describedBy") or []],
                required=bool(f.get("required")),
                disabled=bool(f.get("disabled")),
                readonly=bool(f.get("readonly")),
                max_length=f.get("maxLength") if isinstance(f.get("maxLength"), int) else None,
                min=_str_or_none(f.get("min")),
                max=_str_or_none(f.get("max")),
                step=_str_or_none(f.get("step")),
                accept=[a.strip() for a in str(accept).split(",") if a.strip()] if accept else None,
                multiple=bool(f.get("multiple")),
                option_value=_str_or_none(f.get("optionValue")),
                options=[
                    ObservedOption(
                        value=str(o.get("value") or ""),
                        label=str(o.get("label") or ""),
                        disabled=bool(o.get("disabled")),
                    )
                    for o in f.get("options") or []
                ],
                visible=bool(f.get("visible")),
                supported=bool(supported),
                declared_fixture_metadata={
                    str(k): str(v) for k, v in (f.get("declared") or {}).items() if v is not None
                },
            )
        )
    return out


def _identity(f: ObservedField) -> dict[str, Any]:
    return {
        "tag": f.tag,
        "input_type": f.input_type,
        "dom_id": f.dom_id,
        "name": f.name,
        "role": f.role,
        "contenteditable": not f.supported and f.tag not in ("input", "textarea", "select"),
        "required": f.required,
        "disabled": f.disabled,
        "readonly": f.readonly,
        "max_length": f.max_length,
        "min": f.min,
        "max": f.max,
        "step": f.step,
        "accept": f.accept,
        "multiple": f.multiple,
        "option_value": f.option_value,
        "options": [o.value for o in f.options],
        "condition": f.declared_fixture_metadata.get("data-fixture-condition"),
    }


def fingerprint(fields: list[ObservedField]) -> str:
    records = sorted(
        json.dumps(_identity(f), sort_keys=True, separators=(",", ":")) for f in fields
    )
    canonical = "[" + ",".join(records) + "]"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _observed_type(f: ObservedField) -> str:
    if not f.supported:
        return "unsupported"
    if f.tag == "textarea":
        return "textarea"
    if f.tag == "select":
        return "select"
    if f.tag == "input":
        if f.input_type in TEXT_TYPES:
            return "text"
        return str(f.input_type)
    return f.tag


def check_mappings(
    fields: list[ObservedField],
    expected: tuple[ExpectedField, ...],
    questions: dict[str, IntakeQuestion],
) -> tuple[list[FieldMappingCheck], list[Finding]]:
    checks: list[FieldMappingCheck] = []
    findings: list[Finding] = []
    claimed: set[int] = set()
    for exp in expected:
        q = questions.get(exp.question_id)
        hold = q is not None and q.action_state == "held_unresolved_requirement"
        if exp.kind == "single":
            matches = [f for f in fields if f.dom_id == exp.key]
        else:
            matches = [f for f in fields if f.name == exp.key and f.tag == "input"]
        idx = [f.observed_index for f in matches]
        claimed.update(idx)
        status: Literal["matched", "missing", "ambiguous", "type_mismatch", "unsupported"]
        if not matches:
            status, msg = "missing", f"No control matches {exp.selector}."
        elif exp.kind == "single" and len(matches) > 1:
            status, msg = "ambiguous", f"{len(matches)} controls match {exp.selector}; none chosen."
        elif any(not f.supported for f in matches):
            status, msg = "unsupported", f"{exp.selector} resolves to an unsupported widget."
        elif any(_observed_type(f) != exp.field_type for f in matches):
            got = sorted({_observed_type(f) for f in matches})
            status, msg = "type_mismatch", f"Expected {exp.field_type}, observed {got}."
        else:
            status, msg = "matched", f"Resolved uniquely ({len(matches)} control(s))."
            if exp.kind == "group":
                values = [f.option_value for f in matches]
                if len(values) != len(set(values)):
                    status, msg = "ambiguous", "Group contains duplicate option values."
                    findings.append(
                        Finding(
                            code="duplicate_option_value",
                            severity="blocker",
                            message=msg,
                            question_id=exp.question_id,
                            field_id=exp.field_id,
                        )
                    )
        if status != "matched":
            code = {
                "missing": "mapping_missing",
                "ambiguous": "mapping_ambiguous",
                "type_mismatch": "mapping_type_mismatch",
                "unsupported": "unsupported_widget",
            }[status]
            findings.append(
                Finding(
                    code=code,
                    severity="blocker",
                    message=msg,
                    question_id=exp.question_id,
                    field_id=exp.field_id,
                )
            )
        elif hold:
            findings.append(
                Finding(
                    code="unresolved_requirement",
                    severity="warning",
                    message="Field resolved, but the question has unresolved limits/conditions; "
                    "any later action on it stays held.",
                    question_id=exp.question_id,
                    field_id=exp.field_id,
                )
            )
        checks.append(
            FieldMappingCheck(
                question_id=exp.question_id,
                expected_field_id=exp.field_id,
                expected_selector=exp.selector,
                expected_kind=exp.kind,
                expected_type=exp.field_type,
                status=status,
                observed_count=len(matches),
                observed_indexes=idx,
                requirement_hold=hold,
                message=msg,
            )
        )
    for f in fields:
        if f.observed_index in claimed:
            continue
        if f.tag == "button":
            continue
        if f.label_text is None and f.legend_text is None and f.supported:
            findings.append(
                Finding(
                    code="missing_label",
                    severity="warning",
                    message=f"Observed control {f.field_key} has no label.",
                    field_id=f.field_key,
                )
            )
        findings.append(
            Finding(
                code="unexpected_required_field" if f.required else "unmapped_field",
                severity="blocker" if f.required else "warning",
                message=f"Observed control {f.field_key} is not in the expected map.",
                field_id=f.field_key,
            )
        )
    for f in fields:
        if (
            f.observed_index in claimed
            and f.supported
            and f.label_text is None
            and f.tag != "button"
        ):
            if f.input_type in ("radio", "checkbox") and f.legend_text:
                continue
            findings.append(
                Finding(
                    code="missing_label",
                    severity="warning",
                    message=f"Mapped control {f.field_key} has no label; staff cannot confirm "
                    "its wording from the page.",
                    field_id=f.field_key,
                )
            )
    return checks, findings


def build_form_map(
    *,
    form_id: str,
    version: int,
    origin: str,
    fp: str,
    checks: list[FieldMappingCheck],
    fields: list[ObservedField],
    provenance: Any,
) -> FormMap:
    by_index = {f.observed_index: f for f in fields}
    out: list[FieldMapping] = []
    for c in checks:
        first = by_index[c.observed_indexes[0]]
        out.append(
            FieldMapping(
                field_id=c.expected_field_id,
                question_id=c.question_id,
                selector=c.expected_selector,
                field_type=c.expected_type,
                max_length=first.max_length if c.expected_kind == "single" else None,
            )
        )
    return FormMap(
        form_id=form_id,
        form_version=version,
        origin=origin,
        fingerprint=fp,
        fields=out,
        provenance=provenance,
    )
