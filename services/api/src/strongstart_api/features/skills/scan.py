"""Deterministic package scanner (C4-SKL-001 s7.2).

Reviewed static patterns only; candidate-provided patterns are never executed. Each part is
scanned raw and in one bounded normalized view (NFKC, case-folded, zero-width/format characters
removed). Locations name the view. Secret matches are redacted in every excerpt and quarantine
the package: it cannot export or be sent to the screening model.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Sequence

from strongstart_contracts.skills import (
    CompiledPracticePackage,
    PracticeRule,
    PreferredTermRule,
    ProtectedNameRule,
    ScanFinding,
    ScanReport,
)

from .compiler import canonical
from .demo import ContextDef

SCANNER_VERSION = "c4-scanner/1"
MAX_PART_CHARS = 20_000

_BLOCK: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "instruction_override",
        re.compile(
            r"\b(ignore|disregard|forget)\b.{0,20}\b(previous|prior|above|earlier|all)\b"
            r".{0,20}\b(instructions?|rules?|prompts?)\b"
        ),
        "Asks the model to override its instructions.",
    ),
    (
        "exfiltration",
        re.compile(
            r"\b(send|post|upload|forward|exfiltrate|email)\b.{0,60}"
            r"\b(keys?|tokens?|secrets?|passwords?|credentials?)\b"
        ),
        "Asks to move credentials or secrets elsewhere.",
    ),
    ("exfiltration", re.compile(r"\bhttps?://|\bwww\.[a-z0-9-]+\."), "Contains a network address."),
    (
        "executable_request",
        re.compile(
            r"\b(run|execute|eval|exec)\b.{0,20}\b(shell|command|script|python|bash|code)\b"
            r"|```|<script|\$\(|\bimport\s+os\b"
        ),
        "Requests or embeds executable content.",
    ),
    (
        "disallowed_path",
        re.compile(r"(^|[\s\"'])(\.\./|~/|/etc/|/home/)"),
        "References a file path.",
    ),
)
_SECRET = re.compile(
    r"\bsk-[a-z0-9_-]{8,}|\bakia[0-9a-z]{16}\b|-----begin [a-z ]*private key", re.IGNORECASE
)
_REVIEW: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "instruction_override",
        re.compile(r"\b(system prompt|jailbreak|prompt injection)\b"),
        "Mentions model-control language; confirm it is quoted policy, not an instruction.",
    ),
)


def normalize(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text[:MAX_PART_CHARS]).casefold()
    return "".join(ch for ch in folded if unicodedata.category(ch) != "Cf")


def redact(text: str) -> str:
    return _SECRET.sub("[REDACTED SECRET]", text)


_FRAGMENT = re.compile(r"\b(sk-[a-z0-9_-]*|akia[0-9a-z]*)$", re.IGNORECASE)


def _strip_fragment(text: str) -> str:
    """A window edge can cut a secret so it no longer matches; drop any trailing prefix."""
    return _FRAGMENT.sub("[REDACTED]", redact(text))


def window(text: str, start: int, end: int) -> str:
    """Context excerpt taken from fully redacted text, so a cut never exposes a secret part."""
    return _strip_fragment(redact(text)[max(0, start - 30) : end + 30])


def _hidden(text: str) -> list[int]:
    return [
        n
        for n, ch in enumerate(text[:MAX_PART_CHARS])
        if unicodedata.category(ch) == "Cf"
        or (unicodedata.category(ch) == "Cc" and ch not in "\n\r\t")
    ]


def package_parts(
    context: ContextDef, rules: Sequence[PracticeRule], package: CompiledPracticePackage
) -> list[tuple[str, str]]:
    """Every inspected/screened part: metadata, each rule's operands, each compiled file."""
    parts = [("metadata", canonical({"context_id": context.context_id, "label": context.label}))]
    for rule in rules:
        operands = rule.model_dump(mode="json", exclude={"citations"})
        quotes = [c.quote for c in rule.citations]
        parts.append((f"rule:{rule.rule_id}", canonical({"operands": operands, "quotes": quotes})))
    parts.extend((f"file:{f.path}", f.content) for f in package.files)
    return parts


def scan_package(
    context: ContextDef, rules: Sequence[PracticeRule], package: CompiledPracticePackage
) -> ScanReport:
    findings: list[ScanFinding] = []

    def add(severity: str, category: str, part: str, location: str, message: str, ex: str) -> None:
        findings.append(
            ScanFinding(
                finding_id=f"scan-{len(findings) + 1}",
                severity=severity,
                category=category,
                part=part,
                location=location,
                message=message,
                excerpt=_strip_fragment(ex[:160]),
            )
        )

    parts = package_parts(context, rules, package)
    for part, raw in parts:
        view = normalize(raw)
        seen: set[tuple[str, str]] = set()
        for severity, table in (("block", _BLOCK), ("review", _REVIEW)):
            for category, pattern, message in table:
                m = pattern.search(view)
                if m and (category, part) not in seen:
                    seen.add((category, part))
                    add(
                        severity,
                        category,
                        part,
                        f"normalized:{m.start()}-{m.end()}",
                        message,
                        window(view, m.start(), m.end()),
                    )
        secret = _SECRET.search(view)
        if secret:
            add(
                "block",
                "secret_canary",
                part,
                f"normalized:{secret.start()}-{secret.end()}",
                "Contains a credential-like value; package quarantined and never sent to a model.",
                window(view, secret.start(), secret.end()),
            )
        hidden = _hidden(raw)
        if hidden:
            add(
                "block",
                "hidden_control",
                part,
                f"raw:{hidden[0]}",
                f"Contains {len(hidden)} hidden/format control character(s).",
                redact(raw)[max(0, hidden[0] - 30) : hidden[0] + 30]
                .encode("unicode_escape")
                .decode(),
            )
    for rule in rules:
        operands = (
            [rule.forbidden_term, rule.preferred_term]
            if isinstance(rule, PreferredTermRule)
            else [rule.full_name, rule.acronym or ""]
        )
        if any(ch.isdigit() for op in operands for ch in op):
            add(
                "block",
                "mutable_fact",
                f"rule:{rule.rule_id}",
                "operands",
                "Numbers cannot become reusable practice constants; facts render from evidence.",
                " / ".join(operands),
            )
        if isinstance(rule, ProtectedNameRule) and rule.full_name not in context.registered_names:
            add(
                "block",
                "unregistered_name",
                f"rule:{rule.rule_id}",
                "operands.full_name",
                "Protected name is not registered for this context.",
                rule.full_name,
            )
    body = canonical([f.model_dump(mode="json") for f in findings] + [p for p, _ in parts])
    return ScanReport(
        scanner_version=SCANNER_VERSION,
        report_sha256=hashlib.sha256(
            (canonical([SCANNER_VERSION, package.package_sha256]) + body).encode()
        ).hexdigest(),
        inspected_parts=[p for p, _ in parts],
        findings=findings,
    )


def quarantined(report: ScanReport) -> bool:
    return any(f.category == "secret_canary" for f in report.findings)


def has_secret(text: str) -> bool:
    return bool(_SECRET.search(text) or _SECRET.search(normalize(text)))
