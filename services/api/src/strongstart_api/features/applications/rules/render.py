"""Server rendering of fact slots into answer text with exact spans (engineering s8.2).

Only facts in the identity-scoped bundle's ``allowed_fact_ids`` are rendered (APP-05
boundary). An unknown or out-of-scope fact ID renders as a neutral placeholder and is
reported identically either way, so nothing about other organizations' facts leaks.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from strongstart_contracts import EvidenceBundle, Fact
from strongstart_contracts.answers import ClaimBinding, RenderedAnswer, UnsupportedMarker

from ..models.validation import TOKEN

UNAVAILABLE_TEXT = "[linked fact not available]"


@dataclass(frozen=True)
class Unresolved:
    span_start: int
    span_end: int


def render_fact(fact: Fact) -> str:
    value = "[value unknown]" if fact.value is None else fact.value
    unit = "(unit unknown)" if fact.unit is None else fact.unit
    period = "period unknown" if fact.reporting_period is None else fact.reporting_period
    return f"{value} {unit} ({period})"


def render(
    template: str, bundle: EvidenceBundle
) -> tuple[RenderedAnswer, tuple[Unresolved, ...], dict[str, Fact]]:
    allowed = set(bundle.allowed_fact_ids)
    facts = {f.fact_id: f for f in bundle.facts if f.fact_id in allowed}
    out: list[str] = []
    length = 0
    bindings: list[ClaimBinding] = []
    markers: list[UnsupportedMarker] = []
    unresolved: list[Unresolved] = []
    pos = 0
    for m in TOKEN.finditer(template):
        chunk = template[pos : m.start()]
        out.append(chunk)
        length += len(chunk)
        kind, ref = m.group(1), m.group(2)
        if kind == "fact" and ref in facts:
            text = render_fact(facts[ref])
            bindings.append(
                ClaimBinding(
                    fact_id=ref,
                    fact_version=facts[ref].fact_version,
                    pack_version_id=bundle.pack_version_id,
                    span_start=length,
                    span_end=length + len(text),
                    rendered_text=text,
                )
            )
        elif kind == "fact":
            text = UNAVAILABLE_TEXT
            unresolved.append(Unresolved(length, length + len(text)))
        else:
            text = f"[unsupported: {ref}]"
            markers.append(
                UnsupportedMarker(reason=ref, span_start=length, span_end=length + len(text))
            )
        out.append(text)
        length += len(text)
        pos = m.end()
    out.append(template[pos:])
    text = "".join(out)
    rendered = RenderedAnswer(
        text=text,
        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        bindings=bindings,
        unsupported_markers=markers,
    )
    return rendered, tuple(unresolved), facts
