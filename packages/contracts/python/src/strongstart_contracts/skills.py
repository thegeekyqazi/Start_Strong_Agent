"""C4-SKL-001 thin practice generator and draft preview contracts (owner C).

Commands and read models are separate. Status, authority, screening completion, review and
activation are server-derived; no request or model output can set them (spec s6.1, s8).
Previews are working-only: ``working_preview_only`` is always true and
``approval_permitted`` always false (spec s1.2).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints

from .answers import CheckReport, DraftProposal, ModelRunInfo
from .common import ContractModel, Provenance, Sha256Hex, StableId, contract_model_config

MAX_SOURCE_BYTES = 16 * 1024
MAX_RULES = 3

_Term = Annotated[str, StringConstraints(min_length=1, max_length=60)]
_Name = Annotated[str, StringConstraints(min_length=1, max_length=120)]
_Short = Annotated[str, StringConstraints(max_length=300)]


class _C4(ContractModel):
    model_config = contract_model_config("draft", "C")


class PracticeContext(_C4):
    """Server-owned demo scope (spec s5). Never inferred from model prose or requests."""

    context_id: StableId
    label: str
    program: str
    registered_names: list[str]
    is_simulated: bool
    current_source_version_id: StableId | None
    active_release_id: StableId | None
    revision: int


class PracticeSourceCreate(_C4):
    """Administrator-authored or synthetic practice text. Bounded plain text only."""

    title: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    text: Annotated[str, StringConstraints(min_length=1, max_length=MAX_SOURCE_BYTES)]
    expected_current_source_version_id: StableId | None = None


class PracticeAuthority(_C4):
    """Explicit staff review of a source as practice authority for one context."""

    kind: Literal["synthetic_demo", "administrator_authored"]
    context_id: StableId
    approved_by: StableId
    approved_at: datetime
    is_fixture: bool


class PracticeSourceVersion(_C4):
    source_version_id: StableId
    source_id: StableId
    version: int
    context_id: StableId
    title: str
    text: str
    text_sha256: Sha256Hex
    provenance: Provenance
    authority_kind: Literal["synthetic_demo", "administrator_authored"]
    authority: PracticeAuthority | None
    is_current: bool
    created_by: StableId
    created_at: datetime


class SourceSpan(_C4):
    """Exact evidence: Unicode code-point offsets into an exact stored source version."""

    source_version_id: StableId
    text_sha256: Sha256Hex
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    quote: Annotated[str, StringConstraints(min_length=1, max_length=600)]


class PreferredTermRule(_C4):
    operator: Literal["preferred_term"]
    rule_id: StableId
    forbidden_term: _Term
    preferred_term: _Term
    matching: Literal["whole_word_case_insensitive_plural_s_outside_quotes"]
    citations: list[SourceSpan] = Field(min_length=1, max_length=3)


class ProtectedNameRule(_C4):
    operator: Literal["protected_name"]
    rule_id: StableId
    full_name: _Name
    acronym: Annotated[str, StringConstraints(max_length=20)] | None = None
    citations: list[SourceSpan] = Field(min_length=1, max_length=3)


PracticeRule = Annotated[PreferredTermRule | ProtectedNameRule, Field(discriminator="operator")]


class PackageFile(_C4):
    path: Literal["SKILL.md", "rules.json", "references/policy-excerpts.md"]
    sha256: Sha256Hex
    content: str


class CompiledPracticePackage(_C4):
    """Deterministic compiler output. Fixed allowlisted file map; no executable content."""

    compiler_version: str
    template_version: str
    package_sha256: Sha256Hex
    files: list[PackageFile]


class ScanFinding(_C4):
    finding_id: StableId
    severity: Literal["block", "review"]
    category: Literal[
        "instruction_override",
        "exfiltration",
        "hidden_control",
        "executable_request",
        "disallowed_path",
        "secret_canary",
        "unregistered_name",
        "policy_conflict",
        "mutable_fact",
    ]
    part: str
    location: str
    message: str
    excerpt: str


class ScanReport(_C4):
    scanner_version: str
    report_sha256: Sha256Hex
    inspected_parts: list[str]
    findings: list[ScanFinding]


class RuleTestCase(_C4):
    case_id: str
    rule_id: str
    sample: str
    expectation: str
    passed: bool


class RuleTestReport(_C4):
    tester_version: str
    report_sha256: Sha256Hex
    cases: list[RuleTestCase]
    passed: bool


class ScreeningFinding(_C4):
    part: str
    reason: _Short


class ScreeningReport(_C4):
    """Model-based screening signal, not a calibrated security classifier (spec s7.3)."""

    screening_id: StableId
    candidate_id: StableId
    package_sha256: Sha256Hex
    report_sha256: Sha256Hex
    signal: Literal["no_flags", "review", "block", "unknown"]
    complete: bool
    expected_parts: list[str]
    covered_parts: list[str]
    findings: list[ScreeningFinding]
    provider: ModelRunInfo | None
    hold_reason: str | None
    created_at: datetime


class PracticeReview(_C4):
    review_id: StableId
    candidate_id: StableId
    package_sha256: Sha256Hex
    scan_sha256: Sha256Hex
    tests_sha256: Sha256Hex
    screening_sha256: Sha256Hex
    source_supported: bool
    acknowledged: list[str]
    reviewed_by: StableId
    reviewed_at: datetime
    is_fixture: bool


class PracticeCandidate(_C4):
    candidate_id: StableId
    context_id: StableId
    source_version_id: StableId
    source_text_sha256: Sha256Hex
    rules: list[PracticeRule]
    package: CompiledPracticePackage
    proposer: ModelRunInfo
    scan: ScanReport
    tests: RuleTestReport
    screening: ScreeningReport | None
    review: PracticeReview | None
    status: Literal[
        "proposed",
        "needs_review",
        "held",
        "approved",
        "active",
        "superseded",
        "revoked",
        "stale_source",
    ]
    hold_reasons: list[str]
    created_at: datetime


class PracticeGenerateRequest(_C4):
    source_version_id: StableId


class PracticeReviewRequest(_C4):
    package_sha256: Sha256Hex
    source_supported: bool
    acknowledged_findings: list[StableId] = Field(default_factory=list, max_length=20)
    rationale: Annotated[str, StringConstraints(max_length=500)] = ""


class PracticeActivateRequest(_C4):
    package_sha256: Sha256Hex
    idempotency_key: StableId


class PracticeRevokeRequest(_C4):
    release_id: StableId
    reason: Annotated[str, StringConstraints(min_length=1, max_length=300)]


class PracticeRelease(_C4):
    release_id: StableId
    candidate_id: StableId
    context_id: StableId
    package_sha256: Sha256Hex
    source_version_id: StableId
    review_id: StableId
    activated_by: StableId
    activated_at: datetime
    effective_state: Literal["active", "revoked", "superseded", "stale_source"]
    revoked_reason: str | None
    is_fixture: bool


class AppliedPractice(_C4):
    release_id: StableId
    package_sha256: Sha256Hex
    source_version_id: StableId
    source_text_sha256: Sha256Hex
    instruction_sha256: Sha256Hex
    instructions: str
    rule_ids: list[str]
    is_fixture: bool


class PracticePreviewRequest(_C4):
    question_id: StableId
    question_version: int = Field(ge=1)
    evidence_bundle_id: StableId
    question_set_id: StableId | None = None
    sample_text: Annotated[str, StringConstraints(max_length=2000)] = ""


class PracticePreview(_C4):
    preview_id: StableId
    context_id: StableId
    working_preview_only: Literal[True] = True
    approval_permitted: Literal[False] = False
    applied: AppliedPractice | None
    current: bool
    hold_reason: str | None
    baseline_draft: DraftProposal
    practice_draft: DraftProposal | None
    sample_baseline_check: CheckReport | None
    sample_practice_check: CheckReport | None
    next_actions: list[str]


class PracticeAuditEvent(_C4):
    event_id: StableId
    action: str
    object_id: StableId
    actor_id: StableId
    at: datetime
    detail: str


class PracticeOverview(_C4):
    context: PracticeContext
    sources: list[PracticeSourceVersion]
    candidates: list[PracticeCandidate]
    releases: list[PracticeRelease]
    audit: list[PracticeAuditEvent]
    screening_live: bool


SKILLS_PUBLIC_MODELS: tuple[type[BaseModel], ...] = (
    PracticeContext,
    PracticeSourceCreate,
    PracticeSourceVersion,
    PracticeCandidate,
    PracticeGenerateRequest,
    PracticeReviewRequest,
    PracticeActivateRequest,
    PracticeRevokeRequest,
    PracticeRelease,
    PracticePreviewRequest,
    PracticePreview,
    PracticeOverview,
)
