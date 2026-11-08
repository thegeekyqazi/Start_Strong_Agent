"""Pure A3 source evaluators: typed input in, deterministic findings out."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from strongstart_contracts import ValidationResult

RULE_VERSION = "a3-src-1"
EVALUATOR_ID = "strongstart-source-validation-v1"
Outcome = Literal["pass", "fail", "needs_review", "not_applicable"]


@dataclass(frozen=True)
class SourceContext:
    source_version_id: str
    source_id: str
    media_type: str
    registered_sha256: str
    actual_sha256: str
    registered_size: int
    actual_size: int
    artifact_resolvable: bool
    captured_at: str | None
    parser_name: str | None
    parser_version: str | None
    parser_warnings: tuple[str, ...] | None
    page_count: int | None
    processed_pages: int | None
    extraction_status: str | None
    passages: tuple[tuple[str, str], ...]
    duplicate_version_ids: tuple[str, ...]
    duplicate_url_source_ids: tuple[str, ...]
    canonical_url: str | None
    previous_version_hashes: tuple[str, ...]
    requested_locator: str | None
    claimed_quote: str | None


def _result(
    rule_id: str,
    outcome: Outcome,
    reason_code: str,
    *,
    observed: Any = None,
    expected: Any = None,
    next_action: str | None = None,
) -> ValidationResult:
    return ValidationResult(
        rule_id=rule_id,
        rule_version=RULE_VERSION,
        outcome=outcome,
        reason_code=reason_code,
        reasons=[reason_code],
        observed=observed,
        expected=expected,
        next_action=next_action,
        evaluator_id=EVALUATOR_ID,
    )


def src01(ctx: SourceContext) -> ValidationResult:
    return _result(
        "SRC-01",
        "pass",
        "authorized_source_version_resolved",
        observed=ctx.source_version_id,
        expected="authorized source version",
    )


def src02(ctx: SourceContext) -> ValidationResult:
    matches = ctx.actual_sha256 == ctx.registered_sha256 and ctx.actual_size == ctx.registered_size
    return _result(
        "SRC-02",
        "pass" if matches else "fail",
        "artifact_integrity_verified" if matches else "integrity_mismatch",
        observed={"sha256": ctx.actual_sha256, "size_bytes": ctx.actual_size},
        expected={"sha256": ctx.registered_sha256, "size_bytes": ctx.registered_size},
        next_action=None
        if matches
        else "Restore the registered bytes or create a new source version.",
    )


def src03(ctx: SourceContext) -> ValidationResult:
    if ctx.requested_locator is None:
        return _result(
            "SRC-03",
            "needs_review",
            "prerequisite_missing",
            expected="locator",
            next_action="Provide the locator used by the claim.",
        )
    locators = {locator for locator, _ in ctx.passages}
    exists = ctx.requested_locator in locators
    return _result(
        "SRC-03",
        "pass" if exists else "fail",
        "locator_resolved" if exists else "locator_unresolved",
        observed=ctx.requested_locator,
        expected=sorted(locators),
        next_action=None if exists else "Choose a locator from the exact source version.",
    )


def _normalize_quote(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def src04(ctx: SourceContext) -> ValidationResult:
    if ctx.requested_locator is None or ctx.claimed_quote is None:
        return _result(
            "SRC-04",
            "needs_review",
            "prerequisite_missing",
            expected="locator and claimed_quote",
            next_action="Provide the quote and its exact source locator.",
        )
    passage = dict(ctx.passages).get(ctx.requested_locator)
    if passage is None:
        return _result(
            "SRC-04",
            "needs_review",
            "locator_unresolved",
            observed=ctx.requested_locator,
            next_action="Resolve the locator before comparing the quote.",
        )
    observed = _normalize_quote(ctx.claimed_quote)
    expected = _normalize_quote(passage)
    matches = observed == expected
    return _result(
        "SRC-04",
        "pass" if matches else "fail",
        "quote_matches_whitespace_v1" if matches else "normalization_mismatch",
        observed=observed,
        expected=expected,
        next_action=None if matches else "Correct the quote or bind the intended passage.",
    )


def src05(ctx: SourceContext) -> ValidationResult:
    nonempty = ctx.actual_size > 0 and any(text.strip() for _, text in ctx.passages)
    failed = ctx.extraction_status == "failed"
    ok = nonempty and not failed
    return _result(
        "SRC-05",
        "pass" if ok else "needs_review",
        "capture_content_present" if ok else "capture_content_incomplete",
        observed={
            "size_bytes": ctx.actual_size,
            "nonempty_passages": sum(bool(text.strip()) for _, text in ctx.passages),
            "extraction_status": ctx.extraction_status,
        },
        expected="nonempty artifact and extracted content without failed status",
        next_action=None if ok else "Inspect or repeat capture/extraction; do not invent content.",
    )


def src06(ctx: SourceContext) -> ValidationResult:
    hash_duplicates = list(ctx.duplicate_version_ids)
    url_duplicates = list(ctx.duplicate_url_source_ids)
    duplicates = bool(hash_duplicates or url_duplicates)
    return _result(
        "SRC-06",
        "needs_review" if duplicates else "pass",
        "duplicate_source_detected" if duplicates else "no_duplicate_source_detected",
        observed={
            "artifact_version_ids": hash_duplicates,
            "canonical_url_source_ids": url_duplicates,
            "canonical_url_recorded": ctx.canonical_url is not None,
        },
        expected="no duplicate hash/canonical URL, or retained provenance for each origin",
        next_action=(
            "Deduplicate storage while retaining each source's provenance." if duplicates else None
        ),
    )


def src07(ctx: SourceContext) -> ValidationResult:
    if not ctx.previous_version_hashes:
        return _result(
            "SRC-07",
            "not_applicable",
            "no_previous_source_version",
            observed=ctx.registered_sha256,
        )
    changed = any(value != ctx.registered_sha256 for value in ctx.previous_version_hashes)
    return _result(
        "SRC-07",
        "fail" if changed else "pass",
        "source_version_changed" if changed else "source_version_unchanged",
        observed=ctx.registered_sha256,
        expected=list(ctx.previous_version_hashes),
        next_action=(
            "A4 must revalidate outputs depending on the changed source version."
            if changed
            else None
        ),
    )


def src08(ctx: SourceContext) -> ValidationResult:
    metadata_complete = bool(ctx.media_type and ctx.registered_sha256 and ctx.registered_size >= 0)
    ok = metadata_complete and ctx.artifact_resolvable
    return _result(
        "SRC-08",
        "pass" if ok else "fail",
        "artifact_reference_complete" if ok else "artifact_reference_incomplete",
        observed={
            "metadata_complete": metadata_complete,
            "artifact_resolvable": ctx.artifact_resolvable,
        },
        expected={"metadata_complete": True, "artifact_resolvable": True},
        next_action=None
        if ok
        else "Restore the original-artifact reference and required metadata.",
    )


def src09(ctx: SourceContext) -> ValidationResult:
    if ctx.page_count is None and ctx.processed_pages is None and ctx.extraction_status is None:
        if ctx.media_type != "application/pdf":
            return _result("SRC-09", "not_applicable", "non_paged_source")
        return _result(
            "SRC-09",
            "needs_review",
            "extraction_coverage_unknown",
            next_action="Record the PDF page inventory and processed range.",
        )
    complete = (
        ctx.page_count is not None
        and ctx.processed_pages == ctx.page_count
        and ctx.extraction_status == "complete"
    )
    return _result(
        "SRC-09",
        "pass" if complete else "needs_review",
        "extraction_coverage_complete" if complete else "extraction_coverage_partial",
        observed={
            "page_count": ctx.page_count,
            "processed_pages": ctx.processed_pages,
            "extraction_status": ctx.extraction_status,
        },
        expected="all pages processed with complete status",
        next_action=None
        if complete
        else "Inspect unprocessed pages before relying on full coverage.",
    )


def src10(ctx: SourceContext) -> ValidationResult:
    complete = (
        ctx.captured_at is not None
        and ctx.parser_name is not None
        and ctx.parser_version is not None
        and ctx.parser_warnings is not None
    )
    return _result(
        "SRC-10",
        "pass" if complete else "fail",
        "processing_provenance_complete" if complete else "processing_provenance_incomplete",
        observed={
            "captured_at": ctx.captured_at,
            "parser_name": ctx.parser_name,
            "parser_version": ctx.parser_version,
            "warnings_recorded": ctx.parser_warnings is not None,
        },
        expected="capture time, parser name/version, and explicit warning list",
        next_action=None if complete else "Record complete processing provenance.",
    )
