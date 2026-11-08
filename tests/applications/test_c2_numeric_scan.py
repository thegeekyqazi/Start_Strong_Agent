"""APP-03 unbound-number scanner (C2 owner priority; engineering s8.2, s10.5)."""

from __future__ import annotations

import pytest

from strongstart_api.features.applications.rules.numeric import scan_numbers


def kinds(text: str, bound: tuple[tuple[int, int], ...] = ()) -> list[tuple[str, str]]:
    numbers, _ = scan_numbers(text, bound)
    return [(n.text, n.kind) for n in numbers]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("We served 500 children in 2025.", [("500", "unbound"), ("2025", "date")]),
        ("50% of $1,200", [("50", "unbound"), ("1,200", "unbound")]),
        ("served 2025 children", [("2025", "unbound")]),  # a year-shaped figure without cue
        ("the 3rd year", [("3", "unbound")]),
        ("1.5 million dollars", [("1.5", "unbound")]),
    ],
)
def test_raw_figures_are_unbound(text: str, expected: list[tuple[str, str]]) -> None:
    assert kinds(text) == expected


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Question 3 asks", "reference"),
        ("see section 4", "reference"),
        ("priority #4", "reference"),
        ("Q3 results", "label"),
        ("since 1998", "date"),
        ("FY 2024", "date"),
    ],
)
def test_typed_exceptions(text: str, kind: str) -> None:
    assert [k for _, k in kinds(text)] == [kind]


def test_iso_periods_are_dates() -> None:
    assert {k for _, k in kinds("period 2025-09/2026-06")} == {"date"}


def test_numbers_inside_bindings_are_skipped() -> None:
    text = "We served 120 children (2025-09/2026-06) and 40 families."
    start = text.index("120")
    end = text.index(")") + 1
    assert kinds(text, ((start, end),)) == [("40", "unbound")]


def test_written_numbers_are_reported_for_review() -> None:
    _, written = scan_numbers("five hundred families and one program", ())
    assert [w.text for w in written] == ["five", "hundred"]  # "one" is too common to flag
