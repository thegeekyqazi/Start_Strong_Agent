"""Versioned answer counters (APP-01; engineering s10.5).

- ``words-v1``: maximal runs of non-whitespace (Unicode whitespace, including NBSP) after
  removing zero-width characters. Apostrophes and hyphens stay inside a word.
- ``code-points-v1``: Unicode code points, zero-width characters included.
- ``utf16-v1``: UTF-16 code units (what many browser ``maxlength`` checks count).

A funder's convention is "confirmed" only when the question data names one of these IDs.
"""

from __future__ import annotations

from collections.abc import Callable

_ZERO_WIDTH = {ord(c): None for c in "​‌‍⁠﻿"}


def words_v1(text: str) -> int:
    return len(text.translate(_ZERO_WIDTH).split())


def code_points_v1(text: str) -> int:
    return len(text)


def utf16_v1(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


COUNTERS: dict[str, Callable[[str], int]] = {
    "words-v1": words_v1,
    "code-points-v1": code_points_v1,
    "utf16-v1": utf16_v1,
}
DEFAULT_FOR_UNIT = {"words": "words-v1", "characters": "code-points-v1"}
