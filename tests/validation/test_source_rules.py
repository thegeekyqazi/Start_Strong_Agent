from __future__ import annotations

from dataclasses import replace

import pytest

from strongstart_api.features.validation.registry import DEFINITIONS, run
from strongstart_api.features.validation.rules import SourceContext


@pytest.fixture
def context() -> SourceContext:
    return SourceContext(
        source_version_id="srcv-1",
        source_id="src-1",
        media_type="application/pdf",
        registered_sha256="a" * 64,
        actual_sha256="a" * 64,
        registered_size=100,
        actual_size=100,
        artifact_resolvable=True,
        captured_at="2026-11-08T12:00:00+00:00",
        parser_name="pypdf",
        parser_version="6.21.4",
        parser_warnings=(),
        page_count=2,
        processed_pages=2,
        extraction_status="complete",
        passages=(("page:1", "Children served: 120"), ("page:2", "Second page")),
        duplicate_version_ids=(),
        duplicate_url_source_ids=(),
        canonical_url=None,
        previous_version_hashes=(),
        requested_locator="page:1",
        claimed_quote="Children served: 120",
    )


def _one(context: SourceContext, rule_id: str):
    return run(context, [rule_id])[0]


def test_registry_is_closed_complete_and_ordered(context: SourceContext) -> None:
    assert [definition.rule_id for definition in DEFINITIONS] == [
        f"SRC-{number:02d}" for number in range(1, 11)
    ]
    assert [result.rule_id for result in run(context, [])] == [
        f"SRC-{number:02d}" for number in range(1, 11)
    ]


def test_same_context_has_identical_semantic_results(context: SourceContext) -> None:
    assert run(context, []) == run(context, [])


def test_src01_resolved_authorized_version_passes(context: SourceContext) -> None:
    result = _one(context, "SRC-01")
    assert (result.outcome, result.reason_code) == (
        "pass",
        "authorized_source_version_resolved",
    )


def test_src02_detects_hash_or_size_tampering(context: SourceContext) -> None:
    for changed in (
        replace(context, actual_sha256="b" * 64),
        replace(context, actual_size=99),
    ):
        result = _one(changed, "SRC-02")
        assert (result.outcome, result.reason_code) == ("fail", "integrity_mismatch")


def test_src03_locator_positive_missing_and_boundary(context: SourceContext) -> None:
    assert _one(context, "SRC-03").outcome == "pass"
    missing = _one(replace(context, requested_locator=None), "SRC-03")
    invalid = _one(replace(context, requested_locator="page:3"), "SRC-03")
    assert (missing.outcome, missing.reason_code) == ("needs_review", "prerequisite_missing")
    assert (invalid.outcome, invalid.reason_code) == ("fail", "locator_unresolved")


def test_src04_allows_whitespace_but_changed_digit_fails(context: SourceContext) -> None:
    whitespace = replace(context, claimed_quote=" Children\n served:   120 ")
    changed_digit = replace(context, claimed_quote="Children served: 121")
    assert _one(whitespace, "SRC-04").outcome == "pass"
    result = _one(changed_digit, "SRC-04")
    assert (result.outcome, result.reason_code) == ("fail", "normalization_mismatch")


def test_src04_requires_quote_and_resolved_locator(context: SourceContext) -> None:
    missing = _one(replace(context, claimed_quote=None), "SRC-04")
    invalid = _one(replace(context, requested_locator="page:99"), "SRC-04")
    assert missing.outcome == "needs_review"
    assert (invalid.outcome, invalid.reason_code) == ("needs_review", "locator_unresolved")


def test_src05_empty_or_failed_capture_never_passes(context: SourceContext) -> None:
    empty = replace(context, actual_size=0, passages=(("page:1", "  "),))
    failed = replace(context, extraction_status="failed")
    assert _one(empty, "SRC-05").outcome == "needs_review"
    assert _one(failed, "SRC-05").outcome == "needs_review"


def test_src06_surfaces_duplicates_without_losing_ids(context: SourceContext) -> None:
    result = _one(
        replace(
            context,
            duplicate_version_ids=("srcv-2", "srcv-3"),
            duplicate_url_source_ids=("src-4",),
            canonical_url="https://example.test/guide",
        ),
        "SRC-06",
    )
    assert (result.outcome, result.reason_code) == (
        "needs_review",
        "duplicate_source_detected",
    )
    assert result.observed == {
        "artifact_version_ids": ["srcv-2", "srcv-3"],
        "canonical_url_source_ids": ["src-4"],
        "canonical_url_recorded": True,
    }


def test_src07_no_previous_is_not_applicable_and_change_fails(context: SourceContext) -> None:
    initial = _one(context, "SRC-07")
    unchanged = _one(replace(context, previous_version_hashes=("a" * 64,)), "SRC-07")
    changed = _one(replace(context, previous_version_hashes=("b" * 64,)), "SRC-07")
    assert (initial.outcome, initial.reason_code) == (
        "not_applicable",
        "no_previous_source_version",
    )
    assert unchanged.outcome == "pass"
    assert (changed.outcome, changed.reason_code) == ("fail", "source_version_changed")


def test_src08_requires_resolvable_original_artifact(context: SourceContext) -> None:
    assert _one(context, "SRC-08").outcome == "pass"
    result = _one(replace(context, artifact_resolvable=False), "SRC-08")
    assert (result.outcome, result.reason_code) == (
        "fail",
        "artifact_reference_incomplete",
    )


def test_src09_complete_partial_unknown_and_nonpaged(context: SourceContext) -> None:
    assert _one(context, "SRC-09").outcome == "pass"
    partial = replace(context, processed_pages=1, extraction_status="partial")
    unknown_pdf = replace(context, page_count=None, processed_pages=None, extraction_status=None)
    text = replace(unknown_pdf, media_type="text/plain")
    assert _one(partial, "SRC-09").outcome == "needs_review"
    assert _one(unknown_pdf, "SRC-09").reason_code == "extraction_coverage_unknown"
    assert _one(text, "SRC-09").outcome == "not_applicable"


def test_src10_requires_capture_parser_version_and_warning_list(context: SourceContext) -> None:
    assert _one(context, "SRC-10").outcome == "pass"
    for changed in (
        replace(context, captured_at=None),
        replace(context, parser_name=None),
        replace(context, parser_version=None),
        replace(context, parser_warnings=None),
    ):
        result = _one(changed, "SRC-10")
        assert (result.outcome, result.reason_code) == (
            "fail",
            "processing_provenance_incomplete",
        )


def test_every_not_applicable_has_stable_reason(context: SourceContext) -> None:
    results = run(context, [])
    assert all(result.reason_code for result in results if result.outcome == "not_applicable")
