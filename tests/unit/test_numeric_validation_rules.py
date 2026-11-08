from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from strongstart_api.features.validation.numeric_rules import (
    NumericContext,
    NumericFact,
    parse_decimal,
    run,
)


def fact(**changes: object) -> NumericFact:
    values: dict[str, object] = {
        "fact_id": "fact-1",
        "version": 2,
        "metric_id": "share.percent",
        "value": "94",
        "raw_value": "94%",
        "unit": "children",
        "currency": None,
        "scale": None,
        "scope": "organization",
        "program": "LSW",
        "geography": "Toronto",
        "population": "participants",
        "period": "2025",
        "status": "verified",
    }
    values.update(changes)
    return NumericFact(**values)  # type: ignore[arg-type]


def result(rule_id: str, ctx: NumericContext):
    return run(ctx, [rule_id])[0]


def test_num01_preserves_sign_scale_percent_and_reviews_ambiguity() -> None:
    parsed = result("NUM-01", NumericContext(fact(), raw_value="(1.2 million)%", locale="en-CA"))
    assert parsed.outcome == "pass"
    assert parsed.observed == {"value": "-1200000.0", "scale": "million", "percent": True}
    assert result("NUM-01", NumericContext(fact(), raw_value="1,234")).outcome == "needs_review"


def test_num02_metric_specific_bounds_do_not_invent_growth_bounds() -> None:
    assert result("NUM-02", NumericContext(fact(value="101"))).outcome == "fail"
    growth = fact(metric_id="growth.percent", value="101")
    assert result("NUM-02", NumericContext(growth)).outcome == "not_applicable"


def test_num03_to_num05_bind_value_unit_and_scope() -> None:
    base = NumericContext(
        fact(),
        claimed_value="95",
        claimed_unit="families",
        expected_metric_id="completion.count",
        claimed_program="other",
        claimed_period=None,
    )
    assert result("NUM-03", base).reason_code == "claim_value_mismatch"
    assert result("NUM-04", base).reason_code == "unit_metadata_mismatch"
    assert result("NUM-05", base).reason_code == "fact_scope_mismatch"


def test_num06_shows_exact_budget_delta() -> None:
    checked = result(
        "NUM-06", NumericContext(fact(), line_items=("5000", "5001"), declared_total="10000")
    )
    assert checked.outcome == "fail"
    assert checked.observed["delta"] == "1"


def test_num07_requires_verified_nonzero_denominator() -> None:
    ctx = NumericContext(fact(), numerator=fact(), denominator=fact(value="0"))
    assert result("NUM-07", ctx).reason_code == "denominator_zero_or_unknown"
    assert result("NUM-07", replace(ctx, denominator=fact(value="2"))).outcome == "pass"


def test_num08_rejects_wrong_metric_binding() -> None:
    checked = result("NUM-08", NumericContext(fact(), expected_metric_id="completion.count"))
    assert checked.outcome == "fail"


def test_num09_surfaces_conflict_without_winner() -> None:
    ctx = NumericContext(
        fact(), comparable_facts=(fact(value="10"), fact(fact_id="fact-2", value="11"))
    )
    checked = result("NUM-09", ctx)
    assert checked.outcome == "needs_review"
    assert checked.observed == ["10", "11"]


def test_num10_distinguishes_points_and_relative_change() -> None:
    base = NumericContext(fact(), before_value="40", after_value="50")
    points = result("NUM-10", replace(base, change_operation="percentage_points"))
    relative = result("NUM-10", replace(base, change_operation="relative_percent"))
    assert points.observed == "10"
    assert relative.observed == "25.00"


def test_malformed_decimals_return_findings_instead_of_raising() -> None:
    assert result("NUM-02", NumericContext(fact(value="not-a-number"))).outcome == "needs_review"
    invalid_change = NumericContext(
        fact(), change_operation="relative_percent", before_value="bad", after_value="50"
    )
    assert result("NUM-10", invalid_change).reason_code == "invalid_change_decimal"


def test_num11_requires_disjoint_compatible_scopes() -> None:
    facts = (fact(scope="north"), fact(fact_id="fact-2", scope="south"))
    assert result("NUM-11", NumericContext(fact(), aggregate_facts=facts)).outcome == "needs_review"
    assert (
        result(
            "NUM-11", NumericContext(fact(), aggregate_facts=facts, disjoint_scopes=True)
        ).outcome
        == "pass"
    )


def test_num12_requires_approved_or_explicitly_simulated_input() -> None:
    assert (
        result(
            "NUM-12", NumericContext(fact(), project_input=("input-1", 1, "proposed", False))
        ).outcome
        == "fail"
    )
    assert (
        result(
            "NUM-12", NumericContext(fact(), project_input=("input-1", 1, "approved", False))
        ).outcome
        == "pass"
    )
    assert (
        result(
            "NUM-12", NumericContext(fact(), project_input=("input-1", 1, "proposed", True))
        ).outcome
        == "pass"
    )


@given(st.decimals(allow_nan=False, allow_infinity=False, places=6))
def test_decimal_parser_round_trips_unscaled_values(value: Decimal) -> None:
    parsed, scale, error, percent = parse_decimal(format(value, "f"), "en-CA")
    assert error is None
    assert scale is None
    assert percent is False
    assert parsed == value


@given(
    st.lists(st.decimals(allow_nan=False, allow_infinity=False, places=2), min_size=1, max_size=30)
)
def test_budget_reconciliation_is_exact(values: list[Decimal]) -> None:
    total = sum(values, Decimal(0))
    ctx = NumericContext(fact(), line_items=tuple(map(str, values)), declared_total=str(total))
    assert result("NUM-06", ctx).outcome == "pass"


def test_all_numeric_rules_are_registered_once() -> None:
    assert [item.rule_id for item in run(NumericContext(fact()), [])] == [
        f"NUM-{i:02d}" for i in range(1, 13)
    ]
