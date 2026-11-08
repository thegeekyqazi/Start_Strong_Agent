"""C2 rule registry: APP-01, APP-02, APP-03, POL-01, POL-02, POL-03 (C2 spec s5).

Pure functions over (question, rendered answer, mode, policy). Each returns findings that
wrap the shared ``ValidationResult``. A missing prerequisite yields ``needs_review``, never
``pass`` (s9.1). A pass names only its own predicate (s18). ``working`` mode allows
incomplete work with visible markers; ``reviewed`` mode turns them into failures (s9.2).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from strongstart_contracts import Fact, Question, ValidationResult
from strongstart_contracts.answers import AnswerFinding, RenderedAnswer

from .counters import COUNTERS, DEFAULT_FOR_UNIT
from .numeric import scan_numbers
from .policy import WritingPolicy
from .render import Unresolved

RULE_VERSION = "c2-1"
Mode = Literal["working", "reviewed"]
Outcome = Literal["pass", "fail", "needs_review", "not_applicable"]
QUOTE = re.compile(r"\"[^\"]*\"|“[^”]*”")
PLACEHOLDER = re.compile(r"\b(X{3,}|TBD|TODO|TBC)\b")


@dataclass(frozen=True)
class CheckContext:
    question: Question
    rendered: RenderedAnswer
    unresolved: tuple[Unresolved, ...]
    facts: dict[str, Fact]
    mode: Mode
    policy: WritingPolicy | None


def _finding(
    ctx: CheckContext,
    rule_id: str,
    outcome: Outcome,
    message: str,
    *,
    next_action: str | None = None,
    span: tuple[int, int] | None = None,
    expected: Any = None,
    observed: Any = None,
    reasons: list[str] | None = None,
    extra_inputs: dict[str, Any] | None = None,
) -> AnswerFinding:
    inputs: dict[str, Any] = {
        "rendered_text_sha256": ctx.rendered.text_sha256,
        "question_id": ctx.question.question_id,
        "question_version": ctx.question.question_version,
        "mode": ctx.mode,
        **(extra_inputs or {}),
    }
    return AnswerFinding(
        result=ValidationResult(
            rule_id=rule_id,
            rule_version=RULE_VERSION,
            outcome=outcome,
            inputs=inputs,
            expected=expected,
            observed=observed,
            reasons=reasons or [],
        ),
        message=message,
        next_action=next_action,
        span_start=span[0] if span else None,
        span_end=span[1] if span else None,
        affected_text=ctx.rendered.text[span[0] : span[1]] if span else None,
    )


def _soft(ctx: CheckContext) -> Outcome:
    """Incomplete-but-allowed in a working draft; blocking in reviewed mode (s9.2)."""
    return "fail" if ctx.mode == "reviewed" else "needs_review"


# --- APP-01: versioned counter ------------------------------------------------------


def app01(ctx: CheckContext) -> list[AnswerFinding]:
    q, text = ctx.question, ctx.rendered.text
    counts = {cid: fn(text) for cid, fn in COUNTERS.items()}
    conflicts = q.conflicts or []
    if conflicts:
        limits = [lim for c in conflicts for lim in c.candidate_limits]
        maxima = [
            (lim.maximum, lim.unit)
            for lim in limits
            if lim.maximum is not None and lim.unit in DEFAULT_FOR_UNIT
        ]
        observed = {f"{m} {u}": counts[DEFAULT_FOR_UNIT[u]] for m, u in maxima}
        over_all = bool(maxima) and all(counts[DEFAULT_FOR_UNIT[u]] > m for m, u in maxima)
        stated = " or ".join(f"{m} {u}" for m, u in maxima) or "conflicting limits"
        return [
            _finding(
                ctx,
                "APP-01",
                "fail" if over_all else "needs_review",
                f"The guide gives {stated}; we have not chosen one. This answer has "
                f"{counts['words-v1']} words (words-v1).",
                next_action="Ask staff to confirm which limit applies.",
                expected=[f"{m} {u}" for m, u in maxima],
                observed=observed,
                reasons=["limit_conflict_unresolved"],
                extra_inputs={"counters": sorted(COUNTERS)},
            )
        ]
    limit = q.limit
    if limit is None or limit.maximum is None:
        return [
            _finding(
                ctx,
                "APP-01",
                "not_applicable",
                "No length limit is stated for this question.",
                reasons=["no_limit_in_question_data"],
            )
        ]
    if limit.unit == "amount":
        return [
            _finding(
                ctx,
                "APP-01",
                "not_applicable",
                "This limit is an amount, not a text length.",
                reasons=["amount_limit"],
            )
        ]
    maximum = limit.maximum
    if limit.unit == "unknown":
        words, chars = counts["words-v1"], counts["code-points-v1"]
        over_both = words > maximum and chars > maximum
        return [
            _finding(
                ctx,
                "APP-01",
                "fail" if over_both else "needs_review",
                f'The guide says "Max {maximum}" but not whether it means words or characters. '
                f"This answer has {words} words and {chars} characters.",
                next_action="Ask staff to confirm the unit before relying on this count.",
                expected=maximum,
                observed={"words-v1": words, "code-points-v1": chars},
                reasons=["unit_unknown"],
                extra_inputs={"counters": ["words-v1", "code-points-v1"]},
            )
        ]
    declared = limit.counting_convention
    confirmed = declared in COUNTERS
    counter = declared if declared and confirmed else DEFAULT_FOR_UNIT[limit.unit]
    n = counts[counter]
    common: dict[str, Any] = {
        "expected": maximum,
        "observed": n,
        "extra_inputs": {"counter": counter, "convention_confirmed": confirmed},
    }
    if n > maximum:
        return [
            _finding(
                ctx,
                "APP-01",
                "fail",
                f"{n} of {maximum} {limit.unit} ({counter}) \u2013 {n - maximum} over.",
                next_action="Shorten the answer without changing its meaning.",
                reasons=["over_limit"],
                **common,
            )
        ]
    if not confirmed:
        return [
            _finding(
                ctx,
                "APP-01",
                "needs_review",
                f"{n} of {maximum} {limit.unit} ({counter}). The funder's counting method "
                "is not confirmed, so this count may differ from the portal's.",
                next_action="Confirm the funder's counting method.",
                reasons=["counting_convention_unconfirmed"],
                **common,
            )
        ]
    return [
        _finding(
            ctx,
            "APP-01",
            "pass",
            f"{n} of {maximum} {limit.unit} ({counter}).",
            reasons=["within_limit"],
            **common,
        )
    ]


# --- APP-02: required status ----------------------------------------------------------


def app02(ctx: CheckContext) -> list[AnswerFinding]:
    q = ctx.question
    empty = ctx.rendered.text.strip() == ""
    out: list[AnswerFinding] = []
    if q.required is True:
        out.append(
            _finding(
                ctx,
                "APP-02",
                "fail",
                "This question is required and has no answer yet.",
                next_action="Write an answer.",
                reasons=["required_missing"],
            )
            if empty
            else _finding(
                ctx,
                "APP-02",
                "pass",
                "Required question has an answer (this check only).",
                reasons=["required_present"],
            )
        )
    elif q.required is False:
        out.append(
            _finding(
                ctx,
                "APP-02",
                "not_applicable" if empty else "pass",
                "Optional question." if empty else "Optional question has an answer.",
                reasons=["optional"],
            )
        )
    else:
        out.append(
            _finding(
                ctx,
                "APP-02",
                "needs_review",
                "The guide does not say whether this question is required.",
                next_action="Confirm with the funder's guide.",
                reasons=["required_unknown"],
            )
        )
    if q.conditions:
        out.append(
            _finding(
                ctx,
                "APP-02",
                "needs_review",
                "This question depends on conditions we cannot evaluate yet.",
                next_action="Confirm whether the condition applies.",
                observed=list(q.conditions),
                reasons=["condition_unknown"],
            )
        )
    if q.attachments:
        out.append(
            _finding(
                ctx,
                "APP-02",
                "needs_review",
                "This question lists attachments; attachment status is not tracked yet.",
                next_action="Check the attachments manually.",
                observed=list(q.attachments),
                reasons=["attachment_status_unknown"],
            )
        )
    return out


# --- APP-03: claim support and unbound numbers -----------------------------------------


def app03(ctx: CheckContext) -> list[AnswerFinding]:
    rendered = ctx.rendered
    if rendered.text.strip() == "":
        return [
            _finding(ctx, "APP-03", "not_applicable", "No answer text to check.", reasons=["empty"])
        ]
    bound = tuple((b.span_start, b.span_end) for b in rendered.bindings)
    protected = bound + tuple((m.span_start, m.span_end) for m in rendered.unsupported_markers)
    protected += tuple((u.span_start, u.span_end) for u in ctx.unresolved)
    numbers, written = scan_numbers(rendered.text, protected)
    out: list[AnswerFinding] = []
    for n in numbers:
        if n.kind != "unbound":
            continue
        out.append(
            _finding(
                ctx,
                "APP-03",
                _soft(ctx),
                f'"{n.text}" is a number that is not linked to evidence.',
                next_action="Replace it with a linked fact, mark it {{unsupported:reason}}, "
                "or remove it.",
                span=(n.start, n.end),
                observed=n.text,
                reasons=["unbound_numeric"],
            )
        )
    for u in ctx.unresolved:
        out.append(
            _finding(
                ctx,
                "APP-03",
                "fail",
                "A linked fact is not available in this application's evidence.",
                next_action="Remove the link or choose a fact from the evidence panel.",
                span=(u.span_start, u.span_end),
                reasons=["unavailable_fact"],
            )
        )
    if written:
        out.append(
            _finding(
                ctx,
                "APP-03",
                "needs_review",
                "Written-out numbers need a person to check them: "
                + ", ".join(sorted({w.text.lower() for w in written}))
                + ".",
                next_action="Link the figure to evidence or confirm it is not a claim.",
                span=(written[0].start, written[-1].end),
                observed=[w.text for w in written],
                reasons=["written_number"],
            )
        )
    for m in rendered.unsupported_markers:
        out.append(
            _finding(
                ctx,
                "APP-03",
                _soft(ctx),
                f"Marked as unsupported: {m.reason}.",
                next_action="Add evidence for this claim or remove it before review.",
                span=(m.span_start, m.span_end),
                reasons=["unsupported_marker"],
            )
        )
    for b in rendered.bindings:
        fact = ctx.facts[b.fact_id]
        if fact.status != "verified":
            out.append(
                _finding(
                    ctx,
                    "APP-03",
                    "needs_review",
                    f"Linked fact {fact.metric_id} is not verified by staff yet "
                    "(a citation alone is not support).",
                    next_action="Verify the fact in Knowledge before relying on it.",
                    span=(b.span_start, b.span_end),
                    observed=fact.status,
                    reasons=["binding_to_unverified_fact"],
                )
            )
    if not out:
        out.append(
            _finding(
                ctx,
                "APP-03",
                "pass",
                f"No unlinked numbers found; {len(rendered.bindings)} linked figure(s) "
                "rendered from evidence (this check only).",
                reasons=["all_numbers_bound_or_typed_exception"],
            )
        )
    return out


# --- POL rules --------------------------------------------------------------------------


def _quote_spans(text: str) -> tuple[tuple[int, int], ...]:
    return tuple((m.start(), m.end()) for m in QUOTE.finditer(text))


def _outside(spans: tuple[tuple[int, int], ...], start: int) -> bool:
    return not any(s <= start < e for s, e in spans)


_SYNTHETIC = " (rule from the synthetic demo policy, not Strong Start's approved guide)"


def _policy_suffix(policy: WritingPolicy) -> str:
    return _SYNTHETIC if policy.provenance.is_simulated else ""


def pol01(ctx: CheckContext) -> list[AnswerFinding]:
    policy, text = ctx.policy, ctx.rendered.text
    if policy is None:
        return [
            _finding(
                ctx,
                "POL-01",
                "needs_review",
                "No approved writing policy is configured; terminology was not checked.",
                reasons=["policy_unavailable"],
            )
        ]
    quotes = _quote_spans(text)
    acronyms = {p.full_name.lower(): p.acronym for p in policy.protected_names if p.acronym}

    def mentions(scope: str) -> bool:
        acronym = acronyms.get(scope.lower())
        return scope.lower() in text.lower() or bool(
            acronym and re.search(rf"\b{re.escape(acronym)}\b", text)
        )

    in_scope = [
        r for r in policy.terminology_rules if r.scope == "application" or mentions(r.scope)
    ]
    if not in_scope:
        return [
            _finding(
                ctx,
                "POL-01",
                "not_applicable",
                "No terminology rule applies to this answer's programs.",
                reasons=["no_rule_in_scope"],
            )
        ]
    out: list[AnswerFinding] = []
    for rule in in_scope:
        pattern = re.compile(rf"\b{re.escape(rule.forbidden_term)}s?\b", re.IGNORECASE)
        for m in pattern.finditer(text):
            if _outside(quotes, m.start()):
                out.append(
                    _finding(
                        ctx,
                        "POL-01",
                        "fail",
                        f'In {rule.scope} text, use "{rule.preferred_term}" instead of '
                        f'"{m.group(0)}".' + _policy_suffix(policy),
                        next_action=f'Replace with "{rule.preferred_term}" '
                        "(quotes are left as is).",
                        span=(m.start(), m.end()),
                        expected=rule.preferred_term,
                        observed=m.group(0),
                        reasons=[rule.rule_id],
                    )
                )
    if not out:
        out.append(
            _finding(
                ctx,
                "POL-01",
                "pass",
                "Scoped terminology rules are followed (this check only)." + _policy_suffix(policy),
                reasons=[r.rule_id for r in in_scope],
            )
        )
    return out


def pol02(ctx: CheckContext) -> list[AnswerFinding]:
    policy, text = ctx.policy, ctx.rendered.text
    if policy is None:
        return [
            _finding(
                ctx,
                "POL-02",
                "needs_review",
                "No approved writing policy is configured; protected names were not checked.",
                reasons=["policy_unavailable"],
            )
        ]
    quotes = _quote_spans(text)
    out: list[AnswerFinding] = []
    applied = False
    for rule in policy.protected_names:
        exact = [m.start() for m in re.finditer(re.escape(rule.full_name), text)]
        loose = [
            m
            for m in re.finditer(re.escape(rule.full_name), text, re.IGNORECASE)
            if m.start() not in exact and _outside(quotes, m.start())
        ]
        acr = (
            [m.start() for m in re.finditer(rf"\b{re.escape(rule.acronym)}\b", text)]
            if rule.acronym
            else []
        )
        if not exact and not loose and not acr:
            continue
        applied = True
        for m in loose:
            out.append(
                _finding(
                    ctx,
                    "POL-02",
                    "fail",
                    f'Write the protected name exactly as "{rule.full_name}".'
                    + _policy_suffix(policy),
                    next_action=f'Change to "{rule.full_name}".',
                    span=(m.start(), m.end()),
                    expected=rule.full_name,
                    observed=m.group(0),
                    reasons=[rule.rule_id, "protected_text"],
                )
            )
        if acr and (not exact or acr[0] < exact[0]):
            start = acr[0]
            out.append(
                _finding(
                    ctx,
                    "POL-02",
                    "fail",
                    f'The first mention must use the full name "{rule.full_name}" '
                    f'before "{rule.acronym}".' + _policy_suffix(policy),
                    next_action=f'Write "{rule.full_name} ({rule.acronym})" first.',
                    span=(start, start + len(rule.acronym or "")),
                    expected=rule.full_name,
                    observed=rule.acronym,
                    reasons=[rule.rule_id, "first_use_expansion"],
                )
            )
    if not applied:
        return [
            _finding(
                ctx,
                "POL-02",
                "not_applicable",
                "No protected name appears in this answer.",
                reasons=["no_protected_name"],
            )
        ]
    if not out:
        out.append(
            _finding(
                ctx,
                "POL-02",
                "pass",
                "Protected names and first-use expansions are correct (this check only)."
                + _policy_suffix(policy),
                reasons=["protected_names_ok"],
            )
        )
    return out


def pol03(ctx: CheckContext) -> list[AnswerFinding]:
    text = ctx.rendered.text
    out: list[AnswerFinding] = []
    for m in PLACEHOLDER.finditer(text):
        out.append(
            _finding(
                ctx,
                "POL-03",
                _soft(ctx),
                f'"{m.group(0)}" is a placeholder for missing information.',
                next_action="Fill in the real information or remove the placeholder before review.",
                span=(m.start(), m.end()),
                observed=m.group(0),
                reasons=["placeholder_token"],
            )
        )
    for m in re.finditer(r"\{\{|\}\}", text):
        out.append(
            _finding(
                ctx,
                "POL-03",
                "needs_review",
                "This looks like a broken fact link.",
                next_action="Use {{fact:ID}} with an ID from the evidence panel.",
                span=(m.start(), m.end()),
                reasons=["malformed_token"],
            )
        )
        break
    if not out:
        out.append(
            _finding(
                ctx,
                "POL-03",
                "pass" if text.strip() else "not_applicable",
                "No placeholders found (this check only).",
                reasons=["no_placeholders"],
            )
        )
    return out


RULES: tuple[Callable[[CheckContext], list[AnswerFinding]], ...] = (
    app01,
    app02,
    app03,
    pol01,
    pol02,
    pol03,
)


def run_checks(ctx: CheckContext) -> list[AnswerFinding]:
    return [f for rule in RULES for f in rule(ctx)]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
