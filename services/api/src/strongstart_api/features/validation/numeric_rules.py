"""Pure, deterministic NUM-01..12 evaluators. No I/O and no binary floats."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, cast

from strongstart_contracts import RuleCapability, ValidationResult
from strongstart_contracts.validation import NumericRuleId

RULE_VERSION = "a3c-1"
EVALUATOR_ID = "strongstart.numeric.a3c-1"
_SCALE = {
    None: Decimal(1),
    "thousand": Decimal(1000),
    "million": Decimal(1000000),
    "billion": Decimal(1000000000),
}


@dataclass(frozen=True)
class NumericFact:
    fact_id: str
    version: int
    metric_id: str
    value: str | None
    raw_value: str | None
    unit: str | None
    currency: str | None
    scale: str | None
    scope: str
    program: str | None
    geography: str | None
    population: str | None
    period: str | None
    status: str


@dataclass(frozen=True)
class NumericContext:
    fact: NumericFact
    raw_value: str | None = None
    locale: str | None = None
    claimed_value: str | None = None
    claimed_unit: str | None = None
    claimed_currency: str | None = None
    claimed_scale: str | None = None
    expected_metric_id: str | None = None
    claimed_scope: str | None = None
    claimed_program: str | None = None
    claimed_geography: str | None = None
    claimed_population: str | None = None
    claimed_period: str | None = None
    rounding_places: int = 0
    line_items: tuple[str, ...] = ()
    declared_total: str | None = None
    numerator: NumericFact | None = None
    denominator: NumericFact | None = None
    comparable_facts: tuple[NumericFact, ...] = ()
    change_operation: str | None = None
    before_value: str | None = None
    after_value: str | None = None
    aggregate_facts: tuple[NumericFact, ...] = ()
    disjoint_scopes: bool | None = None
    project_input: tuple[str, int, str, bool] | None = None


def _result(
    rule: str,
    outcome: str,
    code: str,
    *,
    observed: Any = None,
    expected: Any = None,
    reasons: list[str] | None = None,
) -> ValidationResult:
    return ValidationResult(
        rule_id=rule,
        rule_version=RULE_VERSION,
        outcome=outcome,
        reason_code=code,
        observed=observed,
        expected=expected,
        reasons=reasons or [code],
        evaluator_id=EVALUATOR_ID,
    )


def parse_decimal(
    raw: str, locale: str | None
) -> tuple[Decimal | None, str | None, str | None, bool]:
    text = raw.strip().lower()
    percent = text.endswith("%")
    if percent:
        text = text[:-1].strip()
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    scale = next((s for s in ("thousand", "million", "billion") if text.endswith(" " + s)), None)
    if scale:
        text = text[: -len(scale)].strip()
    text = re.sub(r"^(cad|usd|\$)\s*", "", text)
    if re.fullmatch(r"[+-]?\d{1,3},\d{3}", text) and locale is None:
        return None, scale, "ambiguous_grouping", percent
    if locale in {"en-CA", "en-US"}:
        text = text.replace(",", "")
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", text):
        return None, scale, "invalid_numeric_format", percent
    try:
        value = Decimal(text)
        if scale is not None:
            value *= _SCALE[scale]
    except InvalidOperation:
        return None, scale, "invalid_numeric_format", percent
    if negative:
        value = -value
    return value, scale, None, percent


def num01(c: NumericContext) -> ValidationResult:
    raw = c.raw_value or c.fact.raw_value or c.fact.value
    if raw is None:
        return _result("NUM-01", "needs_review", "numeric_value_missing")
    value, scale, error, percent = parse_decimal(raw, c.locale)
    if error:
        return _result("NUM-01", "needs_review", error, observed=raw)
    return _result(
        "NUM-01",
        "pass",
        "numeric_value_parsed",
        observed={"value": str(value), "scale": scale, "percent": percent},
    )


def num02(c: NumericContext) -> ValidationResult:
    if c.fact.value is None:
        return _result("NUM-02", "needs_review", "numeric_value_missing")
    try:
        value = Decimal(c.fact.value)
    except InvalidOperation:
        return _result("NUM-02", "needs_review", "invalid_fact_decimal")
    if c.fact.metric_id in {"share.percent", "proportion.percent", "rate.percent"}:
        ok = Decimal(0) <= value <= Decimal(100)
        return _result(
            "NUM-02",
            "pass" if ok else "fail",
            "metric_range_valid" if ok else "metric_range_invalid",
            observed=str(value),
            expected="0..100",
        )
    return _result("NUM-02", "not_applicable", "metric_has_no_registered_bounds")


def num03(c: NumericContext) -> ValidationResult:
    if c.claimed_value is None or c.fact.value is None:
        return _result("NUM-03", "needs_review", "claim_or_fact_value_missing")
    try:
        claim = Decimal(c.claimed_value)
        fact = Decimal(c.fact.value)
    except InvalidOperation:
        return _result("NUM-03", "fail", "invalid_decimal_claim")
    quantum = Decimal(1).scaleb(-c.rounding_places)
    expected = fact.quantize(quantum, rounding=ROUND_HALF_UP)
    ok = claim == expected
    return _result(
        "NUM-03",
        "pass" if ok else "fail",
        "claim_matches_fact" if ok else "claim_value_mismatch",
        observed=str(claim),
        expected=str(expected),
    )


def num04(c: NumericContext) -> ValidationResult:
    pairs = (
        (c.claimed_unit, c.fact.unit),
        (c.claimed_currency, c.fact.currency),
        (c.claimed_scale, c.fact.scale),
    )
    if all(a is None for a, _ in pairs):
        return _result("NUM-04", "needs_review", "claim_unit_metadata_missing")
    mismatches = [
        name
        for name, (a, b) in zip(("unit", "currency", "scale"), pairs, strict=True)
        if a is not None and a != b
    ]
    return _result(
        "NUM-04",
        "fail" if mismatches else "pass",
        "unit_metadata_mismatch" if mismatches else "unit_metadata_matches",
        observed=mismatches,
    )


def num05(c: NumericContext) -> ValidationResult:
    pairs = (
        ("scope", c.claimed_scope, c.fact.scope),
        ("program", c.claimed_program, c.fact.program),
        ("geography", c.claimed_geography, c.fact.geography),
        ("population", c.claimed_population, c.fact.population),
        ("period", c.claimed_period, c.fact.period),
    )
    supplied = [p for p in pairs if p[1] is not None]
    if not supplied:
        return _result("NUM-05", "needs_review", "claim_scope_metadata_missing")
    bad = [name for name, claim, fact in supplied if claim != fact]
    return _result(
        "NUM-05",
        "fail" if bad else "pass",
        "fact_scope_mismatch" if bad else "fact_scope_matches",
        observed=bad,
    )


def num06(c: NumericContext) -> ValidationResult:
    if not c.line_items or c.declared_total is None:
        return _result("NUM-06", "not_applicable", "budget_inputs_missing")
    try:
        total = sum((Decimal(v) for v in c.line_items), Decimal(0))
        declared = Decimal(c.declared_total)
    except InvalidOperation:
        return _result("NUM-06", "fail", "invalid_budget_decimal")
    delta = total - declared
    return _result(
        "NUM-06",
        "pass" if delta == 0 else "fail",
        "budget_reconciles" if delta == 0 else "budget_discrepancy",
        observed={"sum": str(total), "declared": str(declared), "delta": str(delta)},
    )


def num07(c: NumericContext) -> ValidationResult:
    if c.numerator is None or c.denominator is None:
        return _result("NUM-07", "needs_review", "ratio_input_missing")
    if c.numerator.status != "verified" or c.denominator.status != "verified":
        return _result("NUM-07", "needs_review", "ratio_input_not_verified")
    if c.numerator.value is None or c.denominator.value is None:
        return _result("NUM-07", "fail", "denominator_zero_or_unknown")
    try:
        numerator = Decimal(c.numerator.value)
        denominator = Decimal(c.denominator.value)
    except InvalidOperation:
        return _result("NUM-07", "fail", "invalid_ratio_decimal")
    if denominator == 0:
        return _result("NUM-07", "fail", "denominator_zero_or_unknown")
    return _result(
        "NUM-07",
        "pass",
        "registered_ratio_executed",
        observed=str(numerator / denominator),
        expected="ratio-v1",
    )


def num08(c: NumericContext) -> ValidationResult:
    if c.expected_metric_id is None:
        return _result("NUM-08", "needs_review", "expected_metric_missing")
    ok = c.expected_metric_id == c.fact.metric_id
    return _result(
        "NUM-08",
        "pass" if ok else "fail",
        "metric_id_matches" if ok else "metric_id_mismatch",
        observed=c.fact.metric_id,
        expected=c.expected_metric_id,
    )


def num09(c: NumericContext) -> ValidationResult:
    values = {f.value for f in c.comparable_facts if f.value is not None}
    if len(values) > 1:
        return _result(
            "NUM-09", "needs_review", "comparable_fact_conflict", observed=sorted(values)
        )
    return _result("NUM-09", "pass", "no_comparable_fact_conflict")


def num10(c: NumericContext) -> ValidationResult:
    if c.change_operation is None or c.before_value is None or c.after_value is None:
        return _result("NUM-10", "not_applicable", "change_inputs_missing")
    try:
        before, after = Decimal(c.before_value), Decimal(c.after_value)
    except InvalidOperation:
        return _result("NUM-10", "fail", "invalid_change_decimal")
    if c.change_operation == "relative_percent" and before == 0:
        return _result("NUM-10", "fail", "relative_change_zero_baseline")
    value = (
        after - before
        if c.change_operation == "percentage_points"
        else (after - before) / before * 100
    )
    return _result(
        "NUM-10",
        "pass",
        "change_operation_explicit",
        observed=str(value),
        expected=c.change_operation,
    )


def num11(c: NumericContext) -> ValidationResult:
    if not c.aggregate_facts:
        return _result("NUM-11", "not_applicable", "aggregate_inputs_missing")
    if c.disjoint_scopes is not True:
        return _result("NUM-11", "needs_review", "scope_disjointness_unproven")
    keys = {(f.unit, f.currency, f.scale, f.period) for f in c.aggregate_facts}
    if len(keys) != 1:
        return _result("NUM-11", "fail", "aggregate_scope_incompatible")
    try:
        values = [Decimal(f.value) for f in c.aggregate_facts if f.value is not None]
    except InvalidOperation:
        return _result("NUM-11", "fail", "invalid_aggregate_decimal")
    if len(values) != len(c.aggregate_facts):
        return _result("NUM-11", "needs_review", "aggregate_value_missing")
    return _result(
        "NUM-11",
        "pass",
        "aggregate_scopes_compatible",
        observed=str(sum(values, Decimal(0))),
    )


def num12(c: NumericContext) -> ValidationResult:
    if c.project_input is None:
        return _result("NUM-12", "needs_review", "project_input_missing")
    _, _, status, simulated = c.project_input
    ok = status == "approved" or simulated
    return _result(
        "NUM-12",
        "pass" if ok else "fail",
        "project_input_authorized" if ok else "project_input_not_authorized",
    )


REGISTRY = {
    f"NUM-{i:02d}": fn
    for i, fn in enumerate(
        (num01, num02, num03, num04, num05, num06, num07, num08, num09, num10, num11, num12), 1
    )
}


def capabilities() -> list[RuleCapability]:
    return [
        RuleCapability(
            rule_id=cast(NumericRuleId, rule_id),
            rule_version=RULE_VERSION,
            priority="P0" if int(rule_id[-2:]) <= 6 else "P1",
            state="implemented",
        )
        for rule_id in REGISTRY
    ]


def run(ctx: NumericContext, requested: list[str]) -> list[ValidationResult]:
    return [REGISTRY[rule](ctx) for rule in sorted(requested or REGISTRY)]
