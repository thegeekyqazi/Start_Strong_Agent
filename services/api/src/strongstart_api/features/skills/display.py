"""Client-facing read models with secret-like values redacted (C4-SKL-001 s7.2, C4-07/C4-27).

Internal processing keeps the exact stored text so citation spans and hashes stay verifiable.
Every response sent to a client goes through these functions; a quarantined package also
cannot be exported, screened by a model or activated.
"""

from __future__ import annotations

from strongstart_contracts.skills import (
    PracticeCandidate,
    PracticeOverview,
    PracticeSourceVersion,
)

from .scan import has_secret, quarantined, redact


def source(s: PracticeSourceVersion) -> PracticeSourceVersion:
    return s.model_copy(update={"text": redact(s.text)}) if has_secret(s.text) else s


def candidate(c: PracticeCandidate) -> PracticeCandidate:
    if not quarantined(c.scan):
        return c
    rules = [
        r.model_copy(
            update={
                "citations": [x.model_copy(update={"quote": redact(x.quote)}) for x in r.citations]
            }
        )
        for r in c.rules
    ]
    files = [f.model_copy(update={"content": redact(f.content)}) for f in c.package.files]
    return c.model_copy(
        update={"rules": rules, "package": c.package.model_copy(update={"files": files})}
    )


def overview(o: PracticeOverview) -> PracticeOverview:
    return o.model_copy(
        update={
            "sources": [source(s) for s in o.sources],
            "candidates": [candidate(c) for c in o.candidates],
        }
    )
