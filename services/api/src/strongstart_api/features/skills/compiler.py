"""Deterministic practice compiler (C4-SKL-001 s6.2).

Compiles only validated typed rules. Readable text comes from fixed templates over typed
operands; there is no model-written body. The file map is fixed and allowlisted, timestamps
are excluded, and identical inputs produce byte-identical files and hash.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence

from strongstart_contracts.skills import (
    CompiledPracticePackage,
    PackageFile,
    PracticeRule,
    PreferredTermRule,
    ProtectedNameRule,
)

from .demo import ContextDef

COMPILER_VERSION = "c4-compiler/1"
TEMPLATE_VERSION = "c4-templates/1"
FILE_PATHS = ("SKILL.md", "rules.json", "references/policy-excerpts.md")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(data: object) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def instruction_line(rule: PracticeRule) -> str:
    if isinstance(rule, PreferredTermRule):
        return (
            f'[{rule.rule_id}] Use "{rule.preferred_term}" instead of "{rule.forbidden_term}" '
            "(whole word, case-insensitive, plural -s; quotations are left as is)."
        )
    assert isinstance(rule, ProtectedNameRule)
    acronym = f' First use the full name before "{rule.acronym}".' if rule.acronym else ""
    return f'[{rule.rule_id}] Write the registered name "{rule.full_name}" exactly.{acronym}'


def guidance_text(rules: Sequence[PracticeRule]) -> str:
    """The exact instruction snapshot sent to the draft adapter."""
    return "\n".join(f"- {instruction_line(r)}" for r in rules)


def compile_package(
    context: ContextDef,
    source_version_id: str,
    source_text_sha256: str,
    provenance_label: str,
    rules: Sequence[PracticeRule],
) -> CompiledPracticePackage:
    skill = "\n".join(
        [
            f"# Writing practice: {context.label}",
            "",
            f"Compiler: {COMPILER_VERSION}; templates: {TEMPLATE_VERSION}.",
            f"Source version: {source_version_id} (sha256 {source_text_sha256}).",
            f"Provenance: {provenance_label}",
            "This package is finite data. It contains no scripts, tools or install steps.",
            "",
            "## Practices",
            guidance_text(rules),
            "",
        ]
    )
    rules_json = canonical(
        {
            "context_id": context.context_id,
            "source_version_id": source_version_id,
            "source_text_sha256": source_text_sha256,
            "rules": [r.model_dump(mode="json") for r in rules],
        }
    )
    excerpts = ["# Authorized source excerpts", "", f"Provenance: {provenance_label}", ""]
    for rule in rules:
        for c in rule.citations:
            excerpts.append(
                f"- [{rule.rule_id}] {c.source_version_id} code points {c.start}-{c.end}:"
            )
            excerpts.append(f"  > {c.quote}")
    contents = dict(
        zip(FILE_PATHS, (skill, rules_json + "\n", "\n".join(excerpts) + "\n"), strict=True)
    )
    files = [PackageFile(path=p, sha256=_sha(contents[p]), content=contents[p]) for p in FILE_PATHS]
    manifest = canonical(
        {
            "compiler_version": COMPILER_VERSION,
            "template_version": TEMPLATE_VERSION,
            "files": [{"path": f.path, "sha256": f.sha256} for f in files],
        }
    )
    return CompiledPracticePackage(
        compiler_version=COMPILER_VERSION,
        template_version=TEMPLATE_VERSION,
        package_sha256=_sha(manifest),
        files=files,
    )
