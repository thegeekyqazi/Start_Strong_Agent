"""Deterministic deadline/window and eligibility predicates (DEV-B-BUNDLE-002 M4).

Pure functions over exact reviewed case versions and typed scenario inputs. No model
calls, no I/O, no expression language. Each result answers: what code compared, which
saved source/input it used, what it found (exact Decimal values) and what remains
uncertain. Results also carry a shared ``ValidationResult`` so A3's runner can register
these predicates later (outcome mapping: met->pass, not_met->fail,
unknown/at-cutoff->needs_review, not_applicable->not_applicable).

Catalog coverage is a tested subset only: DAT-01/02/03/04, ELG-01/02/03/04.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from strongstart_contracts import ValidationResult
from strongstart_contracts.funding_review import (
    EVALUATOR_VERSION,
    ActivitySpec,
    AmountRangeSpec,
    DeadlineSpec,
    EvaluationScope,
    EvidenceAnchor,
    ExcludedRequirement,
    FundingContext,
    InvitationSpec,
    MembershipSpec,
    Outcome,
    ProjectWindowSpec,
    Requirement,
    RequirementEvaluation,
    ScenarioInputs,
    SupportExcerpt,
    resolve_local_deadline,
)

__all__ = ["EVALUATOR_VERSION", "RULE_IDS", "all_of", "evaluate_case", "evaluate_one"]

RULE_IDS: dict[str, list[str]] = {
    "deadline": ["DAT-01", "DAT-02", "DAT-03"],
    "project_window": ["DAT-04"],
    "amount_range": ["ELG-02", "ELG-03"],
    "geography": ["ELG-02"],
    "organization_type": ["ELG-02"],
    "activity": ["ELG-02"],
    "invitation": ["ELG-04"],
}
PRIMARY_RULE = {
    "deadline": "DAT-02",
    "project_window": "DAT-04",
    "amount_range": "ELG-03",
    "geography": "ELG-02",
    "organization_type": "ELG-02",
    "activity": "ELG-02",
    "invitation": "ELG-04",
}
ELIGIBILITY_KINDS = {
    "amount_range",
    "geography",
    "organization_type",
    "activity",
    "invitation",
    "project_window",
}
_VALIDATION = {
    "met": "pass",
    "not_met": "fail",
    "unknown": "needs_review",
    "at_cutoff_needs_review": "needs_review",
    "not_applicable": "not_applicable",
}
MAX_QUOTE_IN_REPORT = 600


@dataclass(frozen=True)
class Scope:
    stream: str | None
    stage: str
    cycle: str | None


def case_scope(context: FundingContext, requested: EvaluationScope) -> Scope:
    return Scope(
        stream=requested.stream_label or context.stream_label,
        stage=requested.stage or context.stage,
        cycle=requested.cycle_label or context.cycle_label,
    )


def requirement_scope(req: Requirement, context: FundingContext) -> Scope:
    return Scope(
        stream=req.scope.stream_label or context.stream_label,
        stage=req.scope.stage or context.stage,
        cycle=req.scope.cycle_label or context.cycle_label,
    )


def scope_mismatch(req: Requirement, context: FundingContext, evaluation: Scope) -> str | None:
    """Exact identity selection: an EOI rule never stands in for a full application, etc."""
    own = requirement_scope(req, context)
    for field, label in (("stream", "stream"), ("stage", "stage"), ("cycle", "cycle")):
        a, b = getattr(own, field), getattr(evaluation, field)
        if a != b:
            return (
                f"applies to {label} {a!r}; this evaluation is for {label} {b!r} "
                "(different identities are never substituted)"
            )
    return None


def _money(value: Decimal) -> str:
    return f"{value:,}"


def _support(req: Requirement, anchors: dict[str, EvidenceAnchor]) -> list[SupportExcerpt]:
    out = []
    for key in req.anchor_keys:
        a = anchors[key]
        quote = a.quote if len(a.quote) <= MAX_QUOTE_IN_REPORT else a.quote[:MAX_QUOTE_IN_REPORT]
        out.append(
            SupportExcerpt(
                anchor_key=a.anchor_key,
                capture_id=a.capture_id,
                artifact_sha256=a.artifact_sha256,
                start=a.start,
                end=a.end,
                quote=quote,
                coverage=a.coverage,
            )
        )
    return out


def _source_caveat(req: Requirement, anchors: dict[str, EvidenceAnchor]) -> str:
    notes = []
    if any(anchors[k].coverage != "complete" for k in req.anchor_keys):
        notes.append("the cited capture is partial, so omitted sections were not checked")
    if any(anchors[k].is_simulated for k in req.anchor_keys):
        notes.append("the cited source is simulated/fixture material")
    return ("; ".join(notes) + ". ") if notes else ""


def _result(
    req: Requirement,
    anchors: dict[str, EvidenceAnchor],
    outcome: Outcome,
    *,
    compared: str,
    found: str,
    uncertainty: str,
    next_action: str,
    inputs_used: list[str] | None = None,
    missing: list[str] | None = None,
    observed: Any = None,
    expected: Any = None,
) -> RequirementEvaluation:
    kind = req.spec.kind
    uncertainty = _source_caveat(req, anchors) + uncertainty
    return RequirementEvaluation(
        requirement_key=req.requirement_key,
        kind=kind,
        rule_ids=RULE_IDS[kind],
        outcome=outcome,
        compared=compared,
        support=_support(req, anchors),
        inputs_used=inputs_used or [],
        found=found,
        uncertainty=uncertainty,
        next_action=next_action,
        missing_inputs=missing or [],
        validation=ValidationResult(
            rule_id=PRIMARY_RULE[kind],
            rule_version=EVALUATOR_VERSION,
            outcome=_VALIDATION[outcome],
            inputs={"requirement_key": req.requirement_key},
            expected=expected,
            observed=observed,
            reasons=[found],
        ),
    )


# --------------------------------------------------------------------------- deadline


def evaluate_deadline(
    req: Requirement, spec: DeadlineSpec, clock: datetime, anchors: dict[str, EvidenceAnchor]
) -> RequirementEvaluation:
    compared = f"the evaluation clock {clock.isoformat()} against the reviewed cutoff"
    wording = f'Reviewed wording: "{spec.original_wording}".'
    if spec.precision == "unknown":
        return _result(
            req,
            anchors,
            "unknown",
            compared=compared,
            found="The deadline is not stated in the reviewed source.",
            uncertainty=wording,
            next_action="Find the official cutoff for this stage.",
            missing=["deadline"],
        )
    if spec.precision == "rolling":
        return _result(
            req,
            anchors,
            "unknown",
            compared=compared,
            found="Rolling intake: there is no fixed cutoff to compare.",
            uncertainty=wording + " Rolling intake can still close without notice.",
            next_action="Confirm with the funder that intake is still open.",
        )
    assert spec.date is not None
    if spec.precision == "date_only":
        if spec.timezone:
            local_day = clock.astimezone(ZoneInfo(spec.timezone)).date()
            where = f"in {spec.timezone}"
        else:
            # Without a zone, the date has passed only once it has ended everywhere (UTC-12).
            end_everywhere = datetime.combine(spec.date, datetime.min.time(), UTC) + timedelta(
                days=1, hours=12
            )
            if clock >= end_everywhere:
                return _result(
                    req,
                    anchors,
                    "not_met",
                    compared=compared,
                    found=f"The cutoff date {spec.date} has passed in every timezone.",
                    uncertainty=wording,
                    next_action="Look for a later cycle.",
                    observed=clock.isoformat(),
                    expected=str(spec.date),
                )
            return _result(
                req,
                anchors,
                "unknown",
                compared=compared,
                found=f"Date-only cutoff {spec.date}; no time or timezone is stated, "
                "so exact-time readiness is unknown (no 23:59 or server timezone "
                "is assumed).",
                uncertainty=wording,
                next_action="Confirm the cutoff time and timezone with the funder.",
                missing=["deadline_time", "deadline_timezone"],
            )
        if local_day > spec.date:
            return _result(
                req,
                anchors,
                "not_met",
                compared=compared,
                found=f"The cutoff date {spec.date} has passed {where}.",
                uncertainty=wording,
                next_action="Look for a later cycle.",
                observed=str(local_day),
                expected=str(spec.date),
            )
        observation = (
            "it is the cutoff date" if local_day == spec.date else "the cutoff date is not reached"
        )
        return _result(
            req,
            anchors,
            "unknown",
            compared=compared,
            found=f"Calendar observation: {observation} ({local_day} {where} vs "
            f"{spec.date}). The cutoff time is not stated, so exact-time readiness "
            "is unknown.",
            uncertainty=wording,
            next_action="Confirm the cutoff time before relying on it.",
            missing=["deadline_time"],
        )
    assert spec.local_time is not None
    instant, status = resolve_local_deadline(
        spec.date, spec.local_time, spec.timezone, spec.utc_offset, spec.fold
    )
    if instant is None:
        reason = {
            "ambiguous": "the local time occurs twice at a DST fall-back and the reviewed spec "
            "does not say which (no fold is chosen silently)",
            "nonexistent": "the local time does not exist (DST spring-forward gap)",
            "offset_inconsistent": "the explicit offset disagrees with the timezone",
            "no_zone": "no timezone or offset is stated",
        }[status]
        return _result(
            req,
            anchors,
            "unknown",
            compared=compared,
            found=f"The cutoff instant cannot be determined: {reason}.",
            uncertainty=wording,
            next_action="Ask the funder which instant applies.",
            missing=["deadline_disambiguation"],
        )
    # Compare absolute instants: same-tzinfo datetime comparison ignores ``fold``.
    now_utc, cutoff_utc = clock.astimezone(UTC), instant.astimezone(UTC)
    where = spec.timezone or spec.utc_offset or "explicit offset"
    found_at = f"cutoff {instant.isoformat()} ({where})"
    if now_utc < cutoff_utc:
        return _result(
            req,
            anchors,
            "met",
            compared=compared,
            found=f"The clock is before the {found_at}.",
            uncertainty=wording + " This is time-stamped evidence, not a lasting pass.",
            next_action="Re-check at submission time.",
            observed=clock.isoformat(),
            expected=instant.isoformat(),
        )
    if now_utc > cutoff_utc:
        return _result(
            req,
            anchors,
            "not_met",
            compared=compared,
            found=f"The clock is after the {found_at}.",
            uncertainty=wording,
            next_action="Look for a later cycle or stage.",
            observed=clock.isoformat(),
            expected=instant.isoformat(),
        )
    if spec.boundary == "unstated":
        return _result(
            req,
            anchors,
            "at_cutoff_needs_review",
            compared=compared,
            found=f"The clock is exactly at the {found_at}; the source does not say "
            "whether the boundary is inclusive.",
            uncertainty=wording,
            next_action="Confirm the boundary convention with the funder.",
            observed=clock.isoformat(),
            expected=instant.isoformat(),
        )
    outcome: Outcome = "met" if spec.boundary == "inclusive" else "not_met"
    return _result(
        req,
        anchors,
        outcome,
        compared=compared,
        found=f"The clock is exactly at the {found_at}; the reviewed boundary is {spec.boundary}.",
        uncertainty=wording,
        next_action="Re-check at submission.",
        observed=clock.isoformat(),
        expected=instant.isoformat(),
    )


# --------------------------------------------------------------------------- window


def evaluate_window(
    req: Requirement, spec: ProjectWindowSpec, inputs: ScenarioInputs, anchors: dict[str, Any]
) -> RequirementEvaluation:
    compared = "the project start/end dates against the reviewed funding window"
    used = [
        f"{name}={value.value} ({value.provenance})"
        for name, value in (
            ("project_start", inputs.project_start),
            ("project_end", inputs.project_end),
        )
        if value is not None
    ]
    missing = [
        n
        for n, v, needed in (
            ("project_start", inputs.project_start, spec.earliest_start is not None),
            ("project_end", inputs.project_end, spec.latest_end is not None),
        )
        if needed and v is None
    ]
    if (
        inputs.project_start
        and inputs.project_end
        and inputs.project_end.value < inputs.project_start.value
    ):
        return _result(
            req,
            anchors,
            "not_met",
            compared=compared,
            inputs_used=used,
            found=f"The project dates are inverted ({inputs.project_start.value} to "
            f"{inputs.project_end.value}).",
            uncertainty="Scenario input.",
            next_action="Correct the project dates.",
        )
    if missing:
        return _result(
            req,
            anchors,
            "unknown",
            compared=compared,
            inputs_used=used,
            found="Required project dates are missing.",
            missing=missing,
            uncertainty="Missing inputs never pass.",
            next_action="Enter the planned project dates.",
        )
    problems = []
    if spec.earliest_start and inputs.project_start:
        s, e = inputs.project_start.value, spec.earliest_start
        if s < e or (s == e and spec.start_boundary == "exclusive"):
            problems.append(f"start {s} is before the window start {e} ({spec.start_boundary})")
    if spec.latest_end and inputs.project_end:
        s, e = inputs.project_end.value, spec.latest_end
        if s > e or (s == e and spec.end_boundary == "exclusive"):
            problems.append(f"end {s} is after the window end {e} ({spec.end_boundary})")
    if problems:
        return _result(
            req,
            anchors,
            "not_met",
            compared=compared,
            inputs_used=used,
            found="; ".join(problems) + ".",
            uncertainty="Scenario inputs.",
            next_action="Adjust the project dates or confirm another window.",
        )
    return _result(
        req,
        anchors,
        "met",
        compared=compared,
        inputs_used=used,
        found="The project dates fall inside the reviewed window "
        f"({spec.earliest_start or 'open'} to {spec.latest_end or 'open'}).",
        uncertainty="Scenario inputs; confirm the actual project plan.",
        next_action="Confirm the dates in the application.",
    )


# --------------------------------------------------------------------------- eligibility


def evaluate_amount(
    req: Requirement, spec: AmountRangeSpec, inputs: ScenarioInputs, anchors: dict[str, Any]
) -> RequirementEvaluation:
    bounds = (
        f"{spec.minimum or '-'} to {spec.maximum or '-'} {spec.currency} ({spec.scale}, "
        f"min {spec.min_boundary}, max {spec.max_boundary})"
    )
    compared = f"the requested amount against the reviewed per-award range {bounds}"
    r = inputs.request_amount
    if r is None:
        return _result(
            req,
            anchors,
            "unknown",
            compared=compared,
            found="No request amount was provided.",
            missing=["request_amount"],
            uncertainty="Missing inputs never pass.",
            next_action="Enter the planned request amount.",
        )
    used = [f"request_amount={r.amount} {r.currency} {r.scale} ({r.provenance})"]
    if r.currency != spec.currency or r.scale != spec.scale:
        return _result(
            req,
            anchors,
            "unknown",
            compared=compared,
            inputs_used=used,
            found=f"Unit mismatch: request {r.currency}/{r.scale} vs limit "
            f"{spec.currency}/{spec.scale}; no conversion is performed.",
            uncertainty="Currency and scale must match exactly.",
            next_action="Enter the request in the funder's currency and scale.",
        )
    amount = Decimal(r.amount)
    lo = Decimal(spec.minimum) if spec.minimum is not None else None
    hi = Decimal(spec.maximum) if spec.maximum is not None else None
    if hi is not None and (amount > hi or (amount == hi and spec.max_boundary == "exclusive")):
        return _result(
            req,
            anchors,
            "not_met",
            compared=compared,
            inputs_used=used,
            found=f"Request {_money(amount)} exceeds the maximum {_money(hi)} by "
            f"{_money(amount - hi)} (exact Decimal).",
            uncertainty="The request is a staff scenario; confirm the actual budget.",
            next_action="Reduce the request or confirm a different stream.",
            observed=r.amount,
            expected=spec.maximum,
        )
    if lo is not None and (amount < lo or (amount == lo and spec.min_boundary == "exclusive")):
        return _result(
            req,
            anchors,
            "not_met",
            compared=compared,
            inputs_used=used,
            found=f"Request {_money(amount)} is below the minimum {_money(lo)} by "
            f"{_money(lo - amount)} (exact Decimal).",
            uncertainty="The request is a staff scenario; confirm the actual budget.",
            next_action="Increase the request or confirm the minimum.",
            observed=r.amount,
            expected=spec.minimum,
        )
    return _result(
        req,
        anchors,
        "met",
        compared=compared,
        inputs_used=used,
        found=f"Request {_money(amount)} is within {bounds}.",
        uncertainty="The request is a staff scenario; confirm the actual budget and currency.",
        next_action="Use the confirmed budget figure in the application.",
        observed=r.amount,
        expected=[spec.minimum, spec.maximum],
    )


def evaluate_membership(
    req: Requirement, spec: MembershipSpec, inputs: ScenarioInputs, anchors: dict[str, Any]
) -> RequirementEvaluation:
    field = "region" if spec.kind == "geography" else "organization_type"
    value = inputs.region if spec.kind == "geography" else inputs.organization_type
    compared = f"the {field} identifier against the reviewed set {sorted(spec.allowed)}"
    if value is None:
        return _result(
            req,
            anchors,
            "unknown",
            compared=compared,
            found=f"No {field} was provided (it is never defaulted).",
            missing=[field],
            uncertainty="Missing inputs never pass.",
            next_action=f"Enter the {field} identifier.",
        )
    used = [f"{field}={value.value} ({value.provenance})"]
    if value.value in spec.allowed:
        return _result(
            req,
            anchors,
            "met",
            compared=compared,
            inputs_used=used,
            found=f"{value.value!r} is an exact member of the reviewed set.",
            uncertainty="Exact identifier match only; the input is a staff scenario.",
            next_action="Confirm the identifier with organizational records.",
        )
    return _result(
        req,
        anchors,
        "not_met",
        compared=compared,
        inputs_used=used,
        found=f"{value.value!r} is not in the reviewed set (no substring or geographic guessing).",
        uncertainty="An unmapped region is not inferred.",
        next_action="Check whether a different identifier applies.",
    )


def evaluate_activity(
    req: Requirement, spec: ActivitySpec, inputs: ScenarioInputs, anchors: dict[str, Any]
) -> RequirementEvaluation:
    compared = f"the applicant activities against the reviewed allowlist ({spec.mode} semantics)"
    acts = inputs.activities
    if acts is None:
        return _result(
            req,
            anchors,
            "unknown",
            compared=compared,
            found="No activities were provided.",
            missing=["activities"],
            uncertainty="Missing inputs never pass.",
            next_action="Enter the planned activities.",
        )
    used = [f"activities={acts.values} ({acts.provenance})"]
    allowed = [a for a in acts.values if a in spec.allowed]
    ok = bool(allowed) if spec.mode == "any" else len(allowed) == len(acts.values)
    found = (
        f"{len(allowed)} of {len(acts.values)} activities are on the allowlist "
        f"({spec.mode}): {allowed}."
    )
    return _result(
        req,
        anchors,
        "met" if ok else "not_met",
        compared=compared,
        inputs_used=used,
        found=found,
        uncertainty="Exact identifiers only; no keyword similarity.",
        next_action="Confirm the activity classification.",
    )


def evaluate_invitation(
    req: Requirement, spec: InvitationSpec, inputs: ScenarioInputs, anchors: dict[str, Any]
) -> RequirementEvaluation:
    compared = "the invitation/prior-stage status against the reviewed requirement"
    if not spec.required:
        return _result(
            req,
            anchors,
            "met",
            compared=compared,
            found="The reviewed requirement says no invitation is needed.",
            uncertainty="Based on the cited text only.",
            next_action="None for this rule.",
        )
    inv = inputs.invitation
    if inv is None:
        return _result(
            req,
            anchors,
            "unknown",
            compared=compared,
            found="Invitation status was not provided. A visible Apply button is not "
            "an invitation.",
            missing=["invitation"],
            uncertainty="Missing history never passes.",
            next_action="Record whether the organization was invited.",
        )
    used = [f"invitation={inv.status} ({inv.provenance})"]
    if inv.status == "not_invited":
        return _result(
            req,
            anchors,
            "not_met",
            compared=compared,
            inputs_used=used,
            found="An invitation is required and the scenario says none was received.",
            uncertainty="Scenario input.",
            next_action="Do not apply to this stage.",
        )
    if spec.evidence_required and not inv.evidence_note:
        return _result(
            req,
            anchors,
            "unknown",
            compared=compared,
            inputs_used=used,
            found="Invitation is asserted, but no invitation evidence was noted.",
            missing=["invitation_evidence"],
            uncertainty="Evidence is required.",
            next_action="Attach or reference the invitation letter.",
        )
    return _result(
        req,
        anchors,
        "met",
        compared=compared,
        inputs_used=used,
        found="Invitation asserted with an evidence note.",
        uncertainty="The evidence note is staff-supplied and not verified by B.",
        next_action="Keep the invitation evidence with the application.",
    )


# --------------------------------------------------------------------------- driver


def applicability(req: Requirement, inputs: ScenarioInputs) -> Outcome | None:
    if req.applicability is None:
        return None
    value = inputs.application_type
    if value is None:
        return "unknown"
    return None if value.value == req.applicability.equals else "not_applicable"


def evaluate_one(
    req: Requirement,
    clock: datetime,
    inputs: ScenarioInputs,
    anchors: dict[str, EvidenceAnchor],
) -> RequirementEvaluation:
    gate = applicability(req, inputs)
    if gate is not None:
        cond = req.applicability
        assert cond is not None
        found = (
            f"Reviewed applicability: applies only when application_type is {cond.equals!r}; "
            + (
                "the application type was not provided."
                if gate == "unknown"
                else f"the scenario's type is {inputs.application_type.value!r}."  # type: ignore[union-attr]
            )
        )
        return _result(
            req,
            anchors,
            gate,
            compared="the reviewed applicability condition",
            found=found,
            uncertainty="Not-applicable only from a reviewed condition.",
            next_action="Enter the application type." if gate == "unknown" else "None.",
            missing=["application_type"] if gate == "unknown" else None,
        )
    spec = req.spec
    if isinstance(spec, DeadlineSpec):
        return evaluate_deadline(req, spec, clock, anchors)
    if isinstance(spec, ProjectWindowSpec):
        return evaluate_window(req, spec, inputs, anchors)
    if isinstance(spec, AmountRangeSpec):
        return evaluate_amount(req, spec, inputs, anchors)
    if isinstance(spec, MembershipSpec):
        return evaluate_membership(req, spec, inputs, anchors)
    if isinstance(spec, ActivitySpec):
        return evaluate_activity(req, spec, inputs, anchors)
    if isinstance(spec, InvitationSpec):
        return evaluate_invitation(req, spec, inputs, anchors)
    raise ValueError("unknown rule kind")  # pragma: no cover - registry is closed


def all_of(outcomes: list[Outcome]) -> Outcome | None:
    """ELG-01 all-of: any not_met -> not_met; all met/n-a -> met; otherwise unknown."""
    if not outcomes:
        return None
    if "not_met" in outcomes:
        return "not_met"
    if all(o == "not_applicable" for o in outcomes):
        return "not_applicable"
    if all(o in ("met", "not_applicable") for o in outcomes):
        return "met"
    return "unknown"


def evaluate_case(
    requirements: list[Requirement],
    context: FundingContext,
    requested: EvaluationScope,
    clock: datetime,
    inputs: ScenarioInputs,
    anchors: dict[str, EvidenceAnchor],
    *,
    blocked_reason: str | None,
) -> tuple[list[RequirementEvaluation], list[ExcludedRequirement], Outcome | None]:
    scope = case_scope(context, requested)
    results: list[RequirementEvaluation] = []
    excluded: list[ExcludedRequirement] = []
    for req in requirements:
        mismatch = scope_mismatch(req, context, scope)
        if mismatch:
            excluded.append(
                ExcludedRequirement(requirement_key=req.requirement_key, reason=mismatch)
            )
            continue
        if isinstance(req.spec, AmountRangeSpec) and req.spec.limit_kind != "per_award":
            excluded.append(
                ExcludedRequirement(
                    requirement_key=req.requirement_key,
                    reason=f"a {req.spec.limit_kind.replace('_', ' ')} is not a per-award cap; "
                    "it is never compared with the request",
                )
            )
            continue
        if blocked_reason is not None:
            results.append(
                _result(
                    req,
                    anchors,
                    "unknown",
                    compared="nothing (rule not active)",
                    found=blocked_reason,
                    uncertainty="Inactive rules never pass.",
                    next_action="Review the current case version first.",
                )
            )
            continue
        results.append(evaluate_one(req, clock, inputs, anchors))
    group = all_of([r.outcome for r in results if r.kind in ELIGIBILITY_KINDS])
    return results, excluded, group
