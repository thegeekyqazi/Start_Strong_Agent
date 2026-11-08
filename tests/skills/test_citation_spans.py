"""Citation span binding for model practice proposals.

See docs/decisions/C4-SKL-001-citation-offset-resolution.md.
"""

from __future__ import annotations

from typing import Any

import pytest

from strongstart_api.features.applications.models.base import ModelOutputRejected
from strongstart_api.features.skills.model_tasks import _Cite, verify_span

TEXT = 'Prefer "children" over "kids".\nWrite "Story Circle Saturdays" exactly.\n'


def _span(start: int, end: int, quote: str) -> Any:
    return verify_span(TEXT, "psrc-x", "0" * 64, _Cite(start=start, end=end, quote=quote))


def test_exact_offsets_are_kept() -> None:
    i = TEXT.index("Story Circle Saturdays")
    span = _span(i, i + 22, "Story Circle Saturdays")
    assert (span.start, span.end) == (i, i + 22)


def test_wrong_offsets_with_unique_exact_quote_are_server_resolved() -> None:
    span = _span(3, 9, "Story Circle Saturdays")
    assert TEXT[span.start : span.end] == span.quote == "Story Circle Saturdays"


@pytest.mark.parametrize(
    "quote",
    [
        "Story Circle Saturday s",  # not exact source text
        "story circle saturdays",  # case differs
        '"',  # occurs more than once: ambiguous, never guessed
    ],
)
def test_absent_or_ambiguous_quote_is_rejected(quote: str) -> None:
    with pytest.raises(ModelOutputRejected):
        _span(0, 1 if quote != '"' else 2, quote)
