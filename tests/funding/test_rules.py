"""DEV-B-BUNDLE-002 M4: deterministic deadline/window and eligibility predicates.

Pure-function tests (BND-28..BND-38) with a frozen clock and exact Decimal values. The
fixture values (350/500, 100,000 vs 250,000, demo regions) are synthetic/engineering-
derived; none is Strong Start's real budget, registration, invitation or impact.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from strongstart_api.features.funding import rules
from strongstart_contracts.funding_review import (
    DeadlineSpec,
    EvaluationScope,
    EvidenceAnchor,
    FundingContext,
    Requirement,
    ScenarioInputs,
    resolve_local_deadline,
)

TZ = ZoneInfo("America/Toronto")
ANCHORS = {
    "a": EvidenceAnchor(
        anchor_key="a",
        capture_id="cap-" + "a" * 32,
        artifact_id="cap-a-markdown",
        source_id="web-a",
        source_version_id="cap-a",
        artifact_sha256="b" * 64,
        representation="provider_markdown",
        start=0,
        end=5,
        quote="FIXTURE quote",
        coverage="complete",
        provider_mode="fixture",
        is_simulated=True,
    )
}
CONTEXT = FundingContext(
    funder_label="F", stream_label="standard", cycle_label="2026", stage="full_application"
)


def req(spec: dict[str, Any], key: str = "r", **extra: Any) -> Requirement:
    raw = {
        "requirement_key": key,
        "spec": spec,
        "anchor_keys": ["a"],
        "interpretation": "x",
        "scope": extra.pop("scope", {}),
        "rule_ids": rules.RULE_IDS[spec["kind"]],
        **extra,
    }
    return Requirement.model_validate_json(__import__("json").dumps(raw, default=str))


def inputs(**values: Any) -> ScenarioInputs:
    return ScenarioInputs.model_validate_json(__import__("json").dumps(values, default=str))


def run(r: Requirement, clock: datetime | None = None, **values: Any) -> Any:
    return rules.evaluate_one(
        r, clock or datetime(2026, 2, 1, tzinfo=TZ), inputs(**values), ANCHORS
    )


EXACT = {
    "kind": "deadline",
    "original_wording": "Close 31 March 2026 5 p.m. ET",
    "precision": "exact",
    "date": "2026-03-31",
    "local_time": "17:00:00",
    "timezone": "America/Toronto",
}
CUTOFF = datetime(2026, 3, 31, 17, 0, tzinfo=TZ)


# ------------------------------------------------------------------- BND-28


@pytest.mark.parametrize(
    ("boundary", "delta", "expected"),
    [
        ("unstated", -1, "met"),
        ("unstated", 0, "at_cutoff_needs_review"),
        ("unstated", 1, "not_met"),
        ("inclusive", 0, "met"),
        ("exclusive", 0, "not_met"),
        ("inclusive", 1, "not_met"),
    ],
)
def test_bnd28_exact_deadline_before_at_after(boundary: str, delta: int, expected: str) -> None:
    r = req({**EXACT, "boundary": boundary})
    result = run(r, CUTOFF + timedelta(seconds=delta))
    assert result.outcome == expected
    assert result.validation.rule_id == "DAT-02"
    assert "2026-03-31T17:00:00-04:00" in result.found  # EDT on 31 March


def test_bnd28_clock_in_another_zone_compares_instants() -> None:
    utc_after = datetime(2026, 3, 31, 21, 0, 1, tzinfo=ZoneInfo("UTC"))
    assert run(req(EXACT), utc_after).outcome == "not_met"


# ------------------------------------------------------------------- BND-29


def test_bnd29_date_only_never_becomes_an_exact_time() -> None:
    spec = {
        "kind": "deadline",
        "original_wording": "Due 31 March 2026",
        "precision": "date_only",
        "date": "2026-03-31",
        "timezone": "America/Toronto",
    }
    before = run(req(spec), datetime(2026, 3, 30, 23, 0, tzinfo=TZ))
    same = run(req(spec), datetime(2026, 3, 31, 23, 59, tzinfo=TZ))
    after = run(req(spec), datetime(2026, 4, 1, 0, 1, tzinfo=TZ))
    assert (before.outcome, same.outcome, after.outcome) == ("unknown", "unknown", "not_met")
    assert "23:59" not in before.found and "time is not stated" in before.found
    assert "deadline_time" in before.missing_inputs
    nozone = {k: v for k, v in spec.items() if k != "timezone"}
    assert (
        run(req(nozone), datetime(2026, 4, 1, 11, 0, tzinfo=ZoneInfo("UTC"))).outcome == "unknown"
    )
    assert (
        run(req(nozone), datetime(2026, 4, 1, 12, 0, tzinfo=ZoneInfo("UTC"))).outcome == "not_met"
    )


def test_bnd29_rolling_and_unknown_cutoffs_stay_unknown() -> None:
    rolling = {
        "kind": "deadline",
        "original_wording": "Applications accepted on a rolling basis",
        "precision": "rolling",
    }
    assert run(req(rolling)).outcome == "unknown"
    assert "no fixed cutoff" in run(req(rolling)).found
    with pytest.raises(ValidationError):
        DeadlineSpec.model_validate_json(
            '{"kind":"deadline","original_wording":"x","precision":"rolling","date":"2026-01-01"}'
        )
    with pytest.raises(ValidationError):  # exact without a zone or offset is not accepted
        DeadlineSpec.model_validate_json(
            '{"kind":"deadline","original_wording":"x","precision":"exact",'
            '"date":"2026-01-01","local_time":"17:00:00"}'
        )


# ------------------------------------------------------------------- BND-30


def test_bnd30_dst_ambiguous_nonexistent_and_inconsistent_offsets() -> None:
    from datetime import date, time

    ambiguous = {**EXACT, "date": "2026-11-01", "local_time": "01:30:00"}
    r = run(req(ambiguous), datetime(2026, 10, 1, tzinfo=TZ))
    assert r.outcome == "unknown" and "occurs twice" in r.found
    first, _ = resolve_local_deadline(date(2026, 11, 1), time(1, 30), "America/Toronto", None, 0)
    second, _ = resolve_local_deadline(date(2026, 11, 1), time(1, 30), "America/Toronto", None, 1)
    assert first is not None and second is not None
    assert second.astimezone(ZoneInfo("UTC")) - first.astimezone(ZoneInfo("UTC")) == timedelta(
        hours=1
    )
    # Between the two occurrences, fold decides the outcome (compared as UTC instants).
    between = datetime(2026, 11, 1, 5, 45, tzinfo=ZoneInfo("UTC"))  # 01:45 EDT == after fold 0
    assert run(req({**ambiguous, "fold": 0}), between).outcome == "not_met"
    assert run(req({**ambiguous, "fold": 1}), between).outcome == "met"
    assert run(req({**ambiguous, "fold": 1}), datetime(2026, 10, 1, tzinfo=TZ)).outcome == "met"
    with pytest.raises(ValidationError, match="DST gap"):
        DeadlineSpec.model_validate_json(
            '{"kind":"deadline","original_wording":"x","precision":"exact","date":"2026-03-08",'
            '"local_time":"02:30:00","timezone":"America/Toronto"}'
        )
    with pytest.raises(ValidationError, match="disagrees"):
        DeadlineSpec.model_validate_json(
            '{"kind":"deadline","original_wording":"x","precision":"exact","date":"2026-03-31",'
            '"local_time":"17:00:00","timezone":"America/Toronto","utc_offset":"-05:00"}'
        )
    ok = req({**EXACT, "utc_offset": "-04:00"})  # consistent with EDT on that date
    assert run(ok, CUTOFF - timedelta(minutes=1)).outcome == "met"


# ------------------------------------------------------------------- BND-31


def _case(*requirements: Requirement, scope: dict[str, Any] | None = None, **values: Any) -> Any:
    return rules.evaluate_case(
        list(requirements),
        CONTEXT,
        EvaluationScope(**(scope or {})),
        datetime(2026, 1, 10, tzinfo=TZ),
        inputs(**values),
        ANCHORS,
        blocked_reason=None,
    )


def test_bnd31_stage_cycle_and_stream_never_substitute() -> None:
    eoi = req({**EXACT, "date": "2026-01-15"}, "eoi", scope={"stage": "eoi"})
    full = req(EXACT, "full")
    old_cycle = req(EXACT, "old", scope={"cycle_label": "2025"})
    network = req(
        {"kind": "amount_range", "limit_kind": "per_award", "maximum": "250000", "currency": "CAD"},
        "net",
        scope={"stream_label": "network"},
    )
    results, excluded, _ = _case(eoi, full, old_cycle, network)
    assert [r.requirement_key for r in results] == ["full"]
    reasons = {e.requirement_key: e.reason for e in excluded}
    assert "stage 'eoi'" in reasons["eoi"] and "cycle '2025'" in reasons["old"]
    assert "stream 'network'" in reasons["net"]
    eoi_results, _, _ = _case(eoi, full, scope={"stage": "eoi"})
    assert [r.requirement_key for r in eoi_results] == ["eoi"]


# ------------------------------------------------------------------- BND-32


@pytest.mark.parametrize(
    ("start", "end", "start_b", "end_b", "expected"),
    [
        ("2026-07-01", "2027-06-30", "inclusive", "inclusive", "met"),
        ("2026-07-01", "2027-06-30", "exclusive", "inclusive", "not_met"),
        ("2026-07-02", "2027-06-30", "inclusive", "exclusive", "not_met"),
        ("2026-06-30", "2027-01-01", "inclusive", "inclusive", "not_met"),
        ("2026-08-01", "2027-07-01", "inclusive", "inclusive", "not_met"),
        ("2027-01-01", "2026-08-01", "inclusive", "inclusive", "not_met"),
    ],
)
def test_bnd32_project_window(
    start: str, end: str, start_b: str, end_b: str, expected: str
) -> None:
    spec = {
        "kind": "project_window",
        "earliest_start": "2026-07-01",
        "latest_end": "2027-06-30",
        "start_boundary": start_b,
        "end_boundary": end_b,
    }
    result = run(
        req(spec),
        project_start={"value": start, "provenance": "simulated"},
        project_end={"value": end, "provenance": "simulated"},
    )
    assert result.outcome == expected
    if start > end:
        assert "inverted" in result.found
    missing = run(req(spec), project_start={"value": start, "provenance": "simulated"})
    assert missing.outcome == "unknown" and missing.missing_inputs == ["project_end"]


def test_bnd32_inverted_reviewed_window_is_rejected() -> None:
    with pytest.raises(ValidationError):
        req({"kind": "project_window", "earliest_start": "2027-01-01", "latest_end": "2026-01-01"})


# ------------------------------------------------------------------- BND-33/38


AMOUNT: dict[str, Any] = {
    "kind": "amount_range",
    "limit_kind": "per_award",
    "minimum": "20000",
    "maximum": "100000",
    "currency": "CAD",
}


def test_bnd33_missing_inputs_are_unknown_never_pass() -> None:
    specs: list[dict[str, Any]] = [
        AMOUNT,
        {"kind": "geography", "allowed": ["demo-region-north"]},
        {"kind": "organization_type", "allowed": ["registered-charity"]},
        {"kind": "activity", "allowed": ["early-learning"], "mode": "any"},
        {"kind": "invitation", "required": True},
    ]
    for spec in specs:
        result = run(req(spec))
        assert result.outcome == "unknown", spec["kind"]
        assert result.missing_inputs and result.validation.outcome == "needs_review"


@pytest.mark.parametrize(
    ("amount", "expected", "found"),
    [
        ("99999", "met", "within"),
        ("100000", "met", "within"),
        ("100001", "not_met", "exceeds the maximum 100,000 by 1"),
        ("100000.01", "not_met", "by 0.01"),
        ("20000", "met", "within"),
        ("19999.99", "not_met", "below the minimum 20,000 by 0.01"),
    ],
)
def test_bnd34_exact_decimal_boundaries(amount: str, expected: str, found: str) -> None:
    result = run(
        req(AMOUNT),
        request_amount={"amount": amount, "currency": "CAD", "provenance": "staff_asserted"},
    )
    assert result.outcome == expected and found in result.found


def test_bnd34_exclusive_max_currency_and_scale_mismatch() -> None:
    exclusive = req({**AMOUNT, "max_boundary": "exclusive"})
    at = {"amount": "100000", "currency": "CAD", "provenance": "staff_asserted"}
    assert run(exclusive, request_amount=at).outcome == "not_met"
    usd = run(req(AMOUNT), request_amount={**at, "currency": "USD"})
    assert usd.outcome == "unknown" and "no conversion" in usd.found
    thousands = run(req(AMOUNT), request_amount={**at, "amount": "100", "scale": "thousands"})
    assert thousands.outcome == "unknown"


def test_bnd35_network_maximum_and_pool_never_validate_a_standard_request() -> None:
    standard = req(AMOUNT, "standard")
    network = req(
        {**AMOUNT, "minimum": None, "maximum": "250000"},
        "network",
        scope={"stream_label": "network"},
    )
    pool = req(
        {**AMOUNT, "limit_kind": "total_pool", "minimum": None, "maximum": "1000000"}, "pool"
    )
    match = req(
        {**AMOUNT, "limit_kind": "matching_ratio", "minimum": None, "maximum": "1"}, "match"
    )
    results, excluded, group = _case(
        standard,
        network,
        pool,
        match,
        request_amount={"amount": "120000", "currency": "CAD", "provenance": "staff_asserted"},
    )
    assert [(r.requirement_key, r.outcome) for r in results] == [("standard", "not_met")]
    assert {e.requirement_key for e in excluded} == {"network", "pool", "match"}
    assert "not a per-award cap" in next(e.reason for e in excluded if e.requirement_key == "pool")
    assert group == "not_met"


def test_bnd36_membership_and_activity_semantics() -> None:
    geo = req({"kind": "geography", "allowed": ["demo-region-north", "demo-region-south"]})
    assert (
        run(geo, region={"value": "demo-region-north", "provenance": "simulated"}).outcome == "met"
    )
    near = run(geo, region={"value": "demo-region", "provenance": "simulated"})
    assert near.outcome == "not_met" and "no substring" in near.found
    org = req({"kind": "organization_type", "allowed": ["registered-charity"]})
    assert (
        run(org, organization_type={"value": "for-profit", "provenance": "simulated"}).outcome
        == "not_met"
    )
    acts = {"values": ["early-learning", "sports"], "provenance": "simulated"}
    any_ = req({"kind": "activity", "allowed": ["early-learning"], "mode": "any"})
    all_ = req({"kind": "activity", "allowed": ["early-learning"], "mode": "all"})
    assert run(any_, activities=acts).outcome == "met"
    assert run(all_, activities=acts).outcome == "not_met"


def test_bnd37_invitation_needs_status_and_evidence() -> None:
    inv = req({"kind": "invitation", "required": True, "evidence_required": True})
    missing = run(inv)
    assert missing.outcome == "unknown" and "Apply button is not an invitation" in missing.found
    no = run(inv, invitation={"status": "not_invited", "provenance": "staff_asserted"})
    assert no.outcome == "not_met"
    bare = run(inv, invitation={"status": "invited", "provenance": "staff_asserted"})
    assert bare.outcome == "unknown" and bare.missing_inputs == ["invitation_evidence"]
    full = run(
        inv,
        invitation={
            "status": "invited",
            "provenance": "staff_asserted",
            "evidence_note": "FIXTURE letter",
        },
    )
    assert full.outcome == "met" and full.validation.rule_id == "ELG-04"


def test_bnd38_all_of_distinguishes_fail_unknown_and_not_applicable() -> None:
    assert rules.all_of(["met", "met"]) == "met"
    assert rules.all_of(["met", "unknown"]) == "unknown"
    assert rules.all_of(["unknown", "not_met"]) == "not_met"
    assert rules.all_of(["met", "not_applicable"]) == "met"
    assert rules.all_of(["not_applicable"]) == "not_applicable"
    assert rules.all_of([]) is None
    gated = req(
        {"kind": "geography", "allowed": ["x"]},
        applicability={"input_field": "application_type", "equals": "capital"},
    )
    na = run(gated, application_type={"value": "operating", "provenance": "staff_asserted"})
    assert na.outcome == "not_applicable" and na.validation.outcome == "not_applicable"
    unknown = run(gated)
    assert unknown.outcome == "unknown" and unknown.missing_inputs == ["application_type"]
