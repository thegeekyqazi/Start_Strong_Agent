"""Bounded, request-scoped search and capture operations (B1-DISC-001 s3-s6).

These run synchronously within the request (no JobStore/worker exists yet); each
returns its actual completion or failure. There are no background tasks, scheduled
work or retries. See decision record B1-DISC-001 (request-based operations deviation
from engineering s14 long-running job routes).
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from strongstart_contracts import DateKnowledge, Provenance, ProvenanceClass, SourceReference
from strongstart_contracts.discovery import (
    CAPTURE_PIPELINE_VERSION,
    AuthorityStatus,
    CandidateDuplicate,
    CaptureArtifact,
    CapturedDocument,
    CaptureRequest,
    FundingErrorReason,
    OmittedResult,
    RepresentationType,
    SearchCandidate,
    SearchQueryRecord,
    SearchRequest,
    SearchResult,
    SectionLocator,
)

from .normalize import build_query, matched_terms, normalize_url, stable_hash
from .providers import (
    FIXTURE_PACKAGE,
    CaptureProvider,
    ProviderError,
    SearchProvider,
    _fixture_json,
)
from .store import LocalCaptureStore
from .url_policy import Resolver, UnsafeDestinationError, check_public_url, check_syntax

SEARCH_WARNINGS = [
    "Search results are leads only: eligibility, cycle status and deadlines are unassessed.",
    "A found page may be closed, historical, an award announcement or not a grant.",
    "Provider relevance is the provider's ranking signal, not a likelihood of award.",
]
CAPTURE_WARNINGS = [
    "Representations were rendered/returned by the capture provider; they are not "
    "asserted to be the origin server's original bytes.",
    "Redirect chain is unknown; the final URL is as reported by the provider.",
    "Content completeness is not verified: login walls, paywalls or blocked pages can "
    "look like ordinary content.",
    "The capture provider performed the network fetch; destination checks here cannot "
    "observe which addresses the provider contacted (partial SEC-03 coverage).",
]


class FundingError(Exception):
    def __init__(self, reason: FundingErrorReason, message: str, **details: Any) -> None:
        super().__init__(message)
        self.reason = reason
        self.message = message
        self.details = details


@dataclass(frozen=True)
class SeedEntry:
    seed_id: str
    label: str
    hosts: frozenset[str]
    authority: AuthorityStatus
    basis: str


def load_seed(mode: str, seed_path: Path | None) -> list[SeedEntry]:
    """Discovery seed: configured source hosts. Not an eligible shortlist."""
    if mode == "fixture":
        data = _fixture_json("source_seed.json")
    elif seed_path is not None:
        data = json.loads(seed_path.read_text("utf-8"))
    else:
        return []
    return [
        SeedEntry(
            seed_id=e["seed_id"],
            label=e["label"],
            hosts=frozenset(h.lower() for h in e["hosts"]),
            authority=e["authority"],
            basis=e["basis"],
        )
        for e in data["sources"]
    ]


def _authority(host: str, seed: list[SeedEntry]) -> tuple[AuthorityStatus, str | None]:
    for entry in seed:
        if host in entry.hosts:
            return entry.authority, f"{entry.basis} (seed {entry.seed_id}: {entry.label})"
    return "unreviewed", None


def _provenance(is_fixture: bool, what: str) -> Provenance:
    if is_fixture:
        return Provenance(
            provenance_class=ProvenanceClass.SIMULATED,
            is_simulated=True,
            note=f"FIXTURE: synthetic {what} from strongstart_api funding fixture data.",
        )
    return Provenance(
        provenance_class=ProvenanceClass.PUBLIC,
        is_simulated=False,
        note=f"Public web {what} returned by a third-party provider; unverified.",
    )


def _meta_str(meta: dict[str, str | int | None], key: str) -> str | None:
    value = meta.get(key)
    return value if isinstance(value, str) and value else None


def _meta_int(meta: dict[str, str | int | None], key: str) -> int | None:
    value = meta.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------- search


def run_search(
    request: SearchRequest,
    provider: SearchProvider | None,
    *,
    max_results_limit: int,
    timeout_s: float,
    allowed_fields: list[str],
    seed: list[SeedEntry],
    fixture_capture_check: CaptureProvider | None,
) -> SearchResult:
    try:
        query, used = build_query(request.profile, allowed_fields)
    except ValueError as exc:
        raise FundingError(FundingErrorReason.INVALID_INPUT, str(exc)) from None
    if provider is None:
        raise FundingError(
            FundingErrorReason.PROVIDER_UNAVAILABLE,
            "search provider is not configured (missing STRONGSTART_TAVILY_API_KEY); "
            "no request was sent and no fixture results were substituted",
        )
    max_results = min(request.max_results, max_results_limit)
    started = _now()
    try:
        response = provider.search(query, max_results, timeout_s)
    except ProviderError as exc:
        raise FundingError(
            exc.reason,
            exc.message,
            provider=provider.name,
            provider_http_status=exc.provider_http_status,
            outcome_uncertain=exc.outcome_uncertain,
            retried=False,
        ) from None
    completed = _now()

    candidates: list[SearchCandidate] = []
    omitted: list[OmittedResult] = []
    by_url: dict[str, int] = {}
    by_content: dict[str, str] = {}
    collapsed = 0
    for rank, raw in enumerate(response.results, start=1):
        if raw is None:
            omitted.append(
                OmittedResult(
                    original_url=None, provider_rank=rank, reason="malformed provider result"
                )
            )
            continue
        try:
            _, host = check_syntax(raw.url)
        except UnsafeDestinationError as exc:
            omitted.append(
                OmittedResult(
                    original_url=raw.url[:500],
                    provider_rank=rank,
                    reason=f"unsafe or unsupported URL: {exc.reason}",
                )
            )
            continue
        normalized = normalize_url(raw.url)
        if normalized in by_url:
            collapsed += 1
            first = candidates[by_url[normalized]]
            candidates[by_url[normalized]] = first.model_copy(
                update={
                    "duplicates": [
                        *first.duplicates,
                        CandidateDuplicate(
                            original_url=raw.url, provider_rank=rank, reason="same_normalized_url"
                        ),
                    ]
                }
            )
            continue
        candidate_id = f"cand-{stable_hash(normalized)}"
        content_key = stable_hash(raw.title.strip().lower(), raw.content.strip().lower())
        authority, basis = _authority(host, seed)
        capture_allowed, block_reason = True, None
        if fixture_capture_check is not None and fixture_capture_check.is_fixture:
            if not fixture_capture_check.is_registered_fixture_url(raw.url):
                capture_allowed = False
                block_reason = "fixture capture mode: not a registered fixture page"
        candidates.append(
            SearchCandidate(
                candidate_id=candidate_id,
                provider_rank=rank,
                title=raw.title,
                original_url=raw.url,
                normalized_url=normalized,
                host=host,
                provider_excerpt=raw.content,
                provider_relevance=raw.score,
                provider_date_hint=raw.published_date,
                matched_terms=matched_terms(request.profile, raw.title, raw.content),
                authority=authority,
                authority_basis=basis,
                possible_duplicate_of=by_content.get(content_key),
                deadline=DateKnowledge(status="unknown"),
                capture_allowed=capture_allowed,
                capture_block_reason=block_reason,
                provenance=_provenance(provider.is_fixture, "search result"),
            )
        )
        by_url[normalized] = len(candidates) - 1
        by_content.setdefault(content_key, candidate_id)

    warnings = list(SEARCH_WARNINGS)
    if provider.is_fixture:
        warnings.insert(0, "FIXTURE MODE: synthetic results, not a live search.")
    if not candidates:
        warnings.append("No usable results were returned for this query.")
    return SearchResult(
        search_id=f"srch-{uuid.uuid4().hex}",
        query=SearchQueryRecord(
            query_text=query,
            public_fields_used=used,
            provider=provider.name,
            mode="fixture" if provider.is_fixture else "live",
            requested_params=response.requested_params,
            started_at=started,
            completed_at=completed,
            provider_http_status=response.http_status,
            provider_request_id=response.request_id,
            provider_response_time=response.response_time,
            provider_usage_credits=response.usage_credits,
        ),
        candidates=candidates,
        omitted=omitted,
        duplicates_collapsed=collapsed,
        warnings=warnings,
    )


# --------------------------------------------------------------------------- capture

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t#]*$", re.M)


def markdown_sections(text: str) -> list[SectionLocator]:
    matches = list(_HEADING.finditer(text))
    sections = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append(
            SectionLocator(
                heading=m.group(2)[:200], level=len(m.group(1)), start_char=m.start(), end_char=end
            )
        )
    return sections[:500]


def run_capture(
    request: CaptureRequest,
    organization_id: str,
    provider: CaptureProvider | None,
    store: LocalCaptureStore | None,
    resolver: Resolver,
    *,
    timeout_s: float,
    max_bytes: int,
    seed: list[SeedEntry],
) -> CapturedDocument:
    if store is None:
        raise FundingError(
            FundingErrorReason.STORE_UNAVAILABLE,
            "no supported capture store is available in this environment "
            "(the local store is development-only)",
        )
    if provider is None:
        raise FundingError(
            FundingErrorReason.PROVIDER_UNAVAILABLE,
            "capture provider is not configured (missing STRONGSTART_FIRECRAWL_API_KEY); "
            "no request was sent",
        )
    try:
        if provider.is_fixture:
            check_syntax(request.url)
            if not provider.is_registered_fixture_url(request.url):
                raise UnsafeDestinationError("fixture mode: not a registered fixture page")
        else:
            check_public_url(request.url, resolver)
    except UnsafeDestinationError as exc:
        raise FundingError(FundingErrorReason.UNSAFE_DESTINATION, exc.reason) from None

    try:
        response = provider.capture(request.url, timeout_s, max_bytes)
    except ProviderError as exc:
        raise FundingError(
            exc.reason,
            exc.message,
            provider=provider.name,
            provider_http_status=exc.provider_http_status,
            outcome_uncertain=exc.outcome_uncertain,
            retried=False,
        ) from None
    captured_at = _now()
    meta = response.metadata

    final_url = _meta_str(meta, "url")
    if final_url:
        try:
            if provider.is_fixture:
                check_syntax(final_url)
            else:
                check_public_url(final_url, resolver)
        except UnsafeDestinationError as exc:
            raise FundingError(
                FundingErrorReason.UNSAFE_DESTINATION,
                f"provider-reported final destination rejected: {exc.reason}",
            ) from None
    status = _meta_int(meta, "statusCode")
    if status is not None and status >= 400:
        raise FundingError(
            FundingErrorReason.SOURCE_HTTP_ERROR,
            f"source responded with HTTP {status}; nothing was stored as evidence",
            source_http_status=status,
        )
    content_type = _meta_str(meta, "contentType")
    if content_type and not re.search(r"html|markdown|text/plain", content_type, re.I):
        raise FundingError(
            FundingErrorReason.UNSUPPORTED_CONTENT,
            f"content type {content_type!r} is not supported in this slice (HTML only; "
            "PDF/OCR ingestion is future work)",
        )

    capture_id = f"cap-{uuid.uuid4().hex}"
    warnings = list(CAPTURE_WARNINGS)
    if provider.is_fixture:
        warnings.insert(0, "FIXTURE MODE: synthetic page, not a live capture.")
    if response.warning:
        warnings.append(f"Provider warning: {response.warning}")
    meta_error = _meta_str(meta, "error")
    if meta_error:
        warnings.append(f"Provider metadata error: {meta_error}")

    artifacts: list[CaptureArtifact] = []
    blobs: dict[str, bytes] = {}
    missing = 0
    reps: list[tuple[RepresentationType, str | None]] = [
        ("provider_markdown", response.markdown),
        ("provider_html", response.html),
        ("provider_raw_html", response.raw_html),
    ]
    for rep, text in reps:
        if text is None or not text.strip():
            missing += 1
            warnings.append(f"{rep}: not returned or empty")
            continue
        data = text.encode("utf-8")
        if len(data) > max_bytes:
            missing += 1
            warnings.append(
                f"{rep}: {len(data)} bytes exceeds the {max_bytes}-byte limit; not stored"
            )
            continue
        sha = hashlib.sha256(data).hexdigest()
        is_md = rep == "provider_markdown"
        artifacts.append(
            CaptureArtifact(
                artifact_id=f"{capture_id}-{rep.removeprefix('provider_').replace('_', '-')}",
                representation=rep,
                media_type="text/markdown" if is_md else "text/html",
                size_bytes=len(data),
                sha256=sha,
                locator_scheme="markdown_heading_char_offsets" if is_md else "none",
                sections=markdown_sections(text) if is_md else [],
                b2_importable=not is_md,
            )
        )
        blobs[sha] = data

    coverage = "empty" if not artifacts else ("complete" if missing == 0 else "partial")
    if response.warning and coverage == "complete":
        coverage = "partial"
    normalized = normalize_url(request.url)
    host = check_syntax(final_url)[1] if final_url else check_syntax(request.url)[1]
    authority, basis = _authority(host, seed)
    provenance = _provenance(provider.is_fixture, "page capture")
    primary = next((a for a in artifacts if a.representation != "provider_markdown"), None)
    primary = primary or (artifacts[0] if artifacts else None)
    record = CapturedDocument(
        capture_id=capture_id,
        organization_id=organization_id,
        opportunity_id=request.opportunity_id,
        stream_id=request.stream_id,
        cycle_id=request.cycle_id,
        candidate_id=request.candidate_id,
        search_id=request.search_id,
        requested_url=request.url,
        normalized_url=normalized,
        final_url=final_url,
        final_url_status="provider_reported" if final_url else "unknown",
        provider=provider.name,
        provider_mode="fixture" if provider.is_fixture else "live",
        provider_request_params=response.requested_params,
        source_http_status=status,
        source_content_type=content_type,
        page_title=_meta_str(meta, "title"),
        captured_at=captured_at,
        capture_pipeline_version=CAPTURE_PIPELINE_VERSION,
        artifacts=artifacts,
        coverage=coverage,
        warnings=warnings,
        authority_review=authority,
        authority_basis=basis,
        provenance=provenance,
        source_reference=SourceReference(
            source_id=f"web-{stable_hash(normalized)}",
            source_version_id=capture_id,
            locator=None,
            provenance=provenance,
            captured_at=captured_at,
            publication_date=DateKnowledge(status="unknown"),
            reporting_period=None,
            content_hash=primary.sha256 if primary else None,
            verification_status="unverified",
        ),
        supported_import_representations=[a.representation for a in artifacts if a.b2_importable],
        storage_capability="development_local_store",
    )
    store.save(record, blobs)
    if coverage == "empty":
        raise FundingError(
            FundingErrorReason.EXTRACTION_EMPTY,
            "the provider returned no usable content; the empty capture was recorded "
            "for inspection but is not evidence",
            capture_id=capture_id,
        )
    return record


__all__ = ["FIXTURE_PACKAGE", "FundingError", "load_seed", "run_capture", "run_search"]
