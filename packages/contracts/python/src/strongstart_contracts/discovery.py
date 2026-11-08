"""Funding discovery search and captured-document contracts (owner: B1).

B1-DISC-001 rev 1.0; launch agreement s3 (capture-to-intake seam, semantic v1).

Boundaries encoded here:
- Search candidates are *unassessed*: no eligibility, cycle status or deadline is
  inferred from search results; provider relevance is labelled as such.
- A captured representation returned by a third-party provider is labelled
  ``provider_*``; it is never asserted to be the origin server's original bytes.
- A capture date is ``captured_at`` only; it is never a deadline, publication
  date or reporting period.
- Organization scope is server-derived; clients never supply it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Final, Literal, Protocol, runtime_checkable

from pydantic import Field, StringConstraints

from .common import (
    ContractModel,
    DateKnowledge,
    DecimalString,
    Provenance,
    Sha256Hex,
    SourceReference,
    StableId,
    contract_model_config,
)

CAPTURE_RECORD_SCHEMA_VERSION: Final = "1"
CAPTURE_PIPELINE_VERSION = "b1-disc-001/1"

ProviderMode = Literal["live", "fixture"]
AuthorityStatus = Literal["unreviewed", "confirmed_official", "other"]

# Public profile terms: short, printable, no control characters or markup.
PublicTerm = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=2, max_length=60, pattern=r"^[\w][\w .,&'/-]*$"
    ),
]
PublicContext = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=2, max_length=80, pattern=r"^[\w][\w .,&'/-]*$"
    ),
]


class FundingErrorReason(StrEnum):
    """Funding-specific reason carried in ``ErrorEnvelope.details['reason']``.

    The shared ``ErrorCode`` enum is frozen; these reasons refine it without a
    cross-module change (see decision B1-DISC-001-capture-and-errors).
    """

    INVALID_INPUT = "invalid_input"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_ERROR = "provider_error"
    PROVIDER_AUTH_REJECTED = "provider_auth_rejected"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXCEEDED = "quota_exceeded"
    TIMEOUT = "timeout"
    OUTCOME_UNKNOWN = "outcome_unknown"
    UNSAFE_DESTINATION = "unsafe_destination"
    UNSUPPORTED_CONTENT = "unsupported_content"
    SOURCE_HTTP_ERROR = "source_http_error"
    EXTRACTION_EMPTY = "extraction_empty"
    CAPTURE_NOT_FOUND = "capture_not_found"
    INTEGRITY_FAILURE = "integrity_failure"
    STORE_UNAVAILABLE = "store_unavailable"


# --------------------------------------------------------------------------- search


class SearchProfile(ContractModel):
    """Public search inputs. Only these staff-entered public fields reach the provider."""

    model_config = contract_model_config("draft", "B1")

    interests: list[PublicTerm] = Field(min_length=1, max_length=5)
    geography: PublicContext | None = None
    program_context: PublicContext | None = None


class SearchRequest(ContractModel):
    model_config = contract_model_config("draft", "B1")

    profile: SearchProfile
    max_results: int = Field(default=5, ge=1, le=5)


class SearchQueryRecord(ContractModel):
    model_config = contract_model_config("draft", "B1")

    query_text: str
    public_fields_used: list[Literal["interests", "geography", "program_context"]]
    provider: str
    mode: ProviderMode
    requested_params: dict[str, str | int | bool]
    started_at: datetime
    completed_at: datetime
    provider_http_status: int | None = None
    provider_request_id: str | None = None
    provider_response_time: str | None = None
    provider_usage_credits: DecimalString | None = None


class CandidateDuplicate(ContractModel):
    model_config = contract_model_config("draft", "B1")

    original_url: str
    provider_rank: int = Field(ge=1)
    reason: Literal["same_normalized_url"]


class SearchCandidate(ContractModel):
    model_config = contract_model_config("draft", "B1")

    candidate_id: StableId
    provider_rank: int = Field(ge=1)
    title: str
    original_url: str = Field(description="URL exactly as the provider returned it.")
    normalized_url: str
    host: str
    provider_excerpt: str = Field(description="Provider-supplied snippet; not verified text.")
    provider_relevance: DecimalString | None = Field(
        default=None, description="Provider ranking score; not a success or eligibility score."
    )
    provider_date_hint: str | None = Field(
        default=None,
        description="Provider's estimated published/updated date, raw. NOT a deadline, "
        "publication date of a grant round, or reporting period.",
    )
    matched_terms: list[str] = Field(description="Public query terms found in title/excerpt.")
    authority: AuthorityStatus
    authority_basis: str | None = None
    possible_duplicate_of: StableId | None = Field(
        default=None, description="Identical title+excerpt as another candidate; not merged."
    )
    eligibility_status: Literal["unassessed"] = "unassessed"
    cycle_status: Literal["unknown"] = "unknown"
    deadline: DateKnowledge
    capture_allowed: bool
    capture_block_reason: str | None = None
    duplicates: list[CandidateDuplicate] = Field(default_factory=list)
    provenance: Provenance


class OmittedResult(ContractModel):
    model_config = contract_model_config("draft", "B1")

    original_url: str | None
    provider_rank: int = Field(ge=1)
    reason: str


class SearchResult(ContractModel):
    model_config = contract_model_config("draft", "B1")

    schema_version: Literal["1"] = "1"
    search_id: StableId
    query: SearchQueryRecord
    candidates: list[SearchCandidate]
    omitted: list[OmittedResult]
    duplicates_collapsed: int = Field(ge=0)
    warnings: list[str]


# --------------------------------------------------------------------------- capture

RepresentationType = Literal["provider_markdown", "provider_html", "provider_raw_html"]


class SectionLocator(ContractModel):
    """Character-offset range within the exact stored (UTF-8 decoded) representation."""

    model_config = contract_model_config("draft", "B1")

    heading: str
    level: int = Field(ge=1, le=6)
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)


class CaptureArtifact(ContractModel):
    model_config = contract_model_config("draft", "B1")

    artifact_id: StableId
    representation: RepresentationType
    media_type: Literal["text/markdown", "text/html"]
    encoding: Literal["utf-8"] = "utf-8"
    size_bytes: int = Field(ge=0)
    sha256: Sha256Hex = Field(description="SHA-256 of exactly the stored bytes.")
    locator_scheme: Literal["markdown_heading_char_offsets", "none"]
    sections: list[SectionLocator] = Field(default_factory=list)
    b2_importable: bool = Field(description="True only for HTML representations.")


class CaptureRequest(ContractModel):
    model_config = contract_model_config("draft", "B1")

    url: str = Field(min_length=8, max_length=2048)
    candidate_id: StableId | None = None
    search_id: StableId | None = None
    opportunity_id: StableId | None = None
    stream_id: StableId | None = None
    cycle_id: StableId | None = None


class CapturedDocument(ContractModel):
    """Semantic v1 capture record shared with B2 (launch agreement s3)."""

    model_config = contract_model_config("draft", "B1")

    schema_version: Literal["1"] = CAPTURE_RECORD_SCHEMA_VERSION
    capture_id: StableId
    organization_id: StableId = Field(description="Server-derived organization scope.")
    opportunity_id: StableId | None = None
    stream_id: StableId | None = None
    cycle_id: StableId | None = None
    candidate_id: StableId | None = None
    search_id: StableId | None = None
    requested_url: str
    normalized_url: str
    final_url: str | None = Field(description="Provider-reported final URL; null = unknown.")
    final_url_status: Literal["provider_reported", "unknown"]
    redirect_chain: Literal["unknown"] = "unknown"
    provider: str
    provider_mode: ProviderMode
    provider_request_params: dict[str, str | int | bool | list[str]]
    source_http_status: int | None = Field(default=None, description="As reported by provider.")
    source_content_type: str | None = None
    page_title: str | None = None
    captured_at: datetime = Field(description="Actual provider call completion time only.")
    capture_pipeline_version: str = CAPTURE_PIPELINE_VERSION
    artifacts: list[CaptureArtifact]
    coverage: Literal["complete", "partial", "empty"]
    warnings: list[str]
    authority_review: AuthorityStatus
    authority_basis: str | None = None
    provenance: Provenance
    source_reference: SourceReference
    supported_import_representations: list[RepresentationType]
    storage_capability: Literal["development_local_store"]


class CaptureContent(ContractModel):
    """Authorized, integrity-verified artifact content for inert display."""

    model_config = contract_model_config("draft", "B1")

    capture_id: StableId
    artifact: CaptureArtifact
    text: str
    integrity_verified: Literal[True] = True


class ProviderAvailability(ContractModel):
    model_config = contract_model_config("draft", "B1")

    operation: Literal["search", "capture", "capture_store"]
    provider: str
    mode: ProviderMode | Literal["development_only", "disabled"]
    status: Literal["available", "fixture_only", "unavailable"]
    configured: bool
    live_verified: Literal[False] = Field(
        default=False, description="This service never claims live verification by itself."
    )
    detail: str


class FundingAvailability(ContractModel):
    model_config = contract_model_config("draft", "B1")

    schema_version: Literal["1"] = "1"
    authenticated: bool
    identity_is_fixture: bool
    environment: str
    providers: list[ProviderAvailability]
    limits: dict[str, int | float]
    notes: list[str]


# --------------------------------------------------------------------------- seam port


@dataclass(frozen=True)
class VerifiedArtifact:
    """In-process only (not serialized): artifact metadata plus hash-verified bytes."""

    artifact: CaptureArtifact
    content: bytes


@runtime_checkable
class CapturedDocumentReader(Protocol):
    """Authorized read port B2 consumes. No URL refetch; bytes are hash-verified.

    Implementations raise ``CaptureNotFoundError`` for unknown *or* other-organization
    capture IDs (indistinguishable) and ``CaptureIntegrityError`` on hash mismatch.
    """

    is_fixture: bool

    def get_record(self, organization_id: str, capture_id: str) -> CapturedDocument: ...

    def read_artifact(
        self, organization_id: str, capture_id: str, artifact_id: str
    ) -> VerifiedArtifact: ...


class CaptureNotFoundError(Exception):
    """Capture/artifact absent or not visible to this organization."""


class CaptureIntegrityError(Exception):
    """Stored bytes do not match the registered SHA-256."""
