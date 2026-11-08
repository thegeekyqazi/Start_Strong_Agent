"""Unbound-number scanner for APP-03 (engineering s8.2, s10.5; C2 spec s5).

Every digit run in the rendered answer must sit inside a server-rendered claim binding or
match a typed exception. Engineering s8.2: "classify typed exceptions instead of treating
every digit as an impact statistic". The exceptions are deliberately narrow:

- ``date``: ISO dates/months/periods (2025-09, 2025-09/2026-06), and a four-digit year
  (1900-2099) preceded by a time cue word ("in 2025", "since 1998", "FY 2024").
- ``reference``: a number preceded by question/section/part/item/page/no or by "#".
- ``label``: digits glued to a preceding letter (Q3, COVID19) form an identifier.

Anything else, such as "500 children", "50%", "$1,200", "2025 children" or "3rd", is
**unbound**. Written-out numbers ("five hundred") cannot be classified safely and are
reported for review (s8.2 "written-out numbers ... still need semantic review").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
ISO_DATE = re.compile(r"(?<!\d)\d{4}-\d{2}(?:-\d{2})?(?:/\d{4}-\d{2}(?:-\d{2})?)?(?!\d)")
YEAR = re.compile(r"^(19|20)\d{2}$")
PREV_WORD = re.compile(r"([A-Za-z]+)[\s.:]*$")
YEAR_CUES = frozenset(
    {"in", "since", "from", "by", "during", "until", "to", "between", "and", "year", "fy"}
    | {"fiscal", "of", "before", "after", "through"}
)
REF_CUES = frozenset({"question", "section", "part", "item", "page", "no", "step", "appendix"})
WRITTEN = re.compile(
    r"\b(two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
    r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|"
    r"seventy|eighty|ninety|hundreds?|thousands?|millions?|billions?|dozens?)\b",
    re.IGNORECASE,
)

Kind = Literal["unbound", "date", "reference", "label"]


@dataclass(frozen=True)
class NumericSpan:
    start: int
    end: int
    text: str
    kind: Kind


@dataclass(frozen=True)
class WrittenNumber:
    start: int
    end: int
    text: str


def _inside(start: int, end: int, spans: tuple[tuple[int, int], ...]) -> bool:
    return any(s <= start and end <= e for s, e in spans)


def _classify(text: str, start: int, end: int, dates: tuple[tuple[int, int], ...]) -> Kind:
    if _inside(start, end, dates):
        return "date"
    before = text[:start]
    if before.endswith("#"):
        return "reference"
    if before and before[-1].isalpha():
        return "label"
    match = PREV_WORD.search(before)
    prev = match.group(1).lower() if match else ""
    if prev in REF_CUES:
        return "reference"
    if YEAR.match(text[start:end]) and prev in YEAR_CUES:
        return "date"
    return "unbound"


def scan_numbers(
    text: str, bound_spans: tuple[tuple[int, int], ...]
) -> tuple[tuple[NumericSpan, ...], tuple[WrittenNumber, ...]]:
    """Classify every digit run outside ``bound_spans``; report written-out numbers."""
    dates = tuple((m.start(), m.end()) for m in ISO_DATE.finditer(text))
    numbers: list[NumericSpan] = []
    for m in NUMBER.finditer(text):
        start, end = m.start(), m.end()
        token = m.group(0)  # separators count only between digits: "2025." stays "2025"
        if _inside(start, end, bound_spans):
            continue
        numbers.append(NumericSpan(start, end, token, _classify(text, start, end, dates)))
    written = tuple(
        WrittenNumber(m.start(), m.end(), m.group(0))
        for m in WRITTEN.finditer(text)
        if not _inside(m.start(), m.end(), bound_spans)
    )
    return tuple(numbers), written
