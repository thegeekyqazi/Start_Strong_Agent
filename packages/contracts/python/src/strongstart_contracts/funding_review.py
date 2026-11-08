"""Funding cases, evidence-anchored requirements, evaluations and saved research.

Producer: Dev B funding module (label B1). DEV-B-BUNDLE-002 rev 1.0 s7-s9 (M3-M5).

Boundaries encoded here:

- A funding case is a staff-selected context, not an AI-certified opportunity. Funder,
  stream, cycle and stage are staff-entered labels; IDs are server-derived; unknown stays
  explicit. Versions are immutable; a review is a separate record bound to one exact
  version digest. There is no client ``reviewed`` Boolean anywhere.
- Every executable requirement cites anchors the server resolved against hash-verified
  stored bytes (exact code-point quote match). Code proves the quoted text exists; it does
  not prove the staff interpretation is semantically correct.
- Rule kinds come from a fixed registry; there is no expression language, regex or code.
- Evaluations separate the computed scenario outcome from reliance: staff-asserted or
  simulated inputs never make funder eligibility confirmed (``reliance_status`` is always
  ``not_confirmed`` in this bundle) and never write facts into Dev A's store.
- Saved searches persist public profile fields only; a result not seen in a bounded,
  provider-ranked result set is not a removed or closed opportunity.
- A change observation compares stored representation hashes; it never rewrites rules,
  approves answers or claims A4/C3 downstream invalidation.
"""

from __future__ import annotations

import datetime as _dt
import re
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Annotated, Final, Literal, Protocol, Self, runtime_checkable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    Strict,
    StringConstraints,
    field_validator,
    model_validator,
)

from .common import DecimalString, Sha256Hex, StableId
from .discovery import SearchProfile, SearchResult
from .funding import Opportunity, RequirementSet
from .ports import CapabilityUnavailable
from .validation import ValidationResult

CASE_FORMAT: Final = "b1-funding-case/1"
EVALUATOR_VERSION: Final = "b1-rules/1"
MAX_REQUIREMENTS: Final = 20
MAX_ANCHORS: Final = 40
MAX_CAPTURE_LINKS: Final = 20
MAX_QUOTE_CODE_POINTS: Final = 2000


def _config(strict: bool = False) -> ConfigDict:
    return ConfigDict(
        extra="forbid",
        frozen=True,
        strict=strict,
        str_strip_whitespace=False,
        json_schema_extra={"x-contract-status": "draft", "x-owner": "B1"},
    )


CaseId = Annotated[str, StringConstraints(pattern=r"^case-[0-9a-f]{26}$")]
CaptureId = Annotated[str, StringConstraints(pattern=r"^cap-[0-9a-f]{32}$")]
IdempotencyKey = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._:-]{8,128}$")]
StrictVersion = Annotated[int, Strict(), Field(ge=1, le=20)]
StrictInt = Annotated[int, Strict()]
StrictBool = Annotated[bool, Strict()]
Label = Annotated[str, StringConstraints(min_length=1, max_length=200)]
ScopeLabel = Annotated[str, StringConstraints(min_length=1, max_length=80)]
Key = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{0,39}$")]
Currency = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
Stage = Literal["eoi", "full_application", "single_stage", "unknown"]
Boundary = Literal["inclusive", "exclusive"]
InputProvenance = Literal["staff_asserted", "simulated"]
Outcome = Literal["met", "not_met", "unknown", "not_applicable", "at_cutoff_needs_review"]
_OFFSET = re.compile(r"^[+-](0[0-9]|1[0-4]):[0-5][0-9]$")


# =========================================================================== M3: cases


class FundingContextInput(BaseModel):
    """Staff-entered labels. Missing labels stay unknown; nothing is guessed from a page."""

    model_config = _config(strict=True)

    funder_label: Label | None = None
    stream_label: ScopeLabel | None = None
    cycle_label: ScopeLabel | None = None
    stage: Stage = "unknown"
    opportunity_title: Label | None = None


class FundingContext(BaseModel):
    model_config = _config()

    funder_label: str | None = None
    stream_label: str | None = None
    cycle_label: str | None = None
    stage: Stage
    opportunity_title: str | None = None
    funder_id: StableId | None = Field(default=None, description="Server-derived from the label.")
    stream_id: StableId | None = None
    cycle_id: StableId | None = None
    unknown_fields: list[str] = Field(default_factory=list)


class CaptureLinkInput(BaseModel):
    model_config = _config(strict=True)

    capture_id: CaptureId


class CaptureLink(BaseModel):
    """A capture the case relies on, resolved through the org-scoped capture reader."""

    model_config = _config()

    capture_id: StableId
    source_id: StableId
    source_version_id: StableId
    page_title: str | None = None
    requested_url: str
    final_url: str | None = None
    coverage: Literal["complete", "partial", "empty"]
    provider_mode: Literal["live", "fixture"]
    is_simulated: bool
    authority_review: str
    declared_opportunity_id: StableId | None = None
    declared_stream_id: StableId | None = None
    declared_cycle_id: StableId | None = None


class AnchorInput(BaseModel):
    """Staff selection of an exact passage. The server verifies it; it is not proof itself."""

    model_config = _config(strict=True)

    anchor_key: Key
    capture_id: CaptureId
    artifact_id: StableId
    expected_artifact_sha256: Sha256Hex = Field(
        description="Hash of the representation staff read; a different stored hash is 409."
    )
    quote: Annotated[str, StringConstraints(min_length=1)]
    start: Annotated[int, Strict(), Field(ge=0)]
    end: Annotated[int, Strict(), Field(ge=1)]

    @model_validator(mode="after")
    def _range(self) -> Self:
        if self.end <= self.start:
            raise ValueError("anchor end must be greater than start")
        return self


class EvidenceAnchor(BaseModel):
    """A server-verified exact quote inside one immutable stored representation."""

    model_config = _config()

    anchor_key: str
    capture_id: StableId
    artifact_id: StableId
    source_id: StableId
    source_version_id: StableId
    artifact_sha256: Sha256Hex
    representation: str
    locator_scheme: Literal["unicode_code_points_in_utf8_decoded_representation"] = (
        "unicode_code_points_in_utf8_decoded_representation"
    )
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    quote: str
    coverage: Literal["complete", "partial", "empty"]
    warnings: list[str] = Field(default_factory=list)
    provider_mode: Literal["live", "fixture"]
    is_simulated: bool
    verification: Literal["quote_matched_hash_verified_bytes"] = "quote_matched_hash_verified_bytes"


# --- finite rule registry ----------------------------------------------------


def _valid_zone(value: str | None) -> str | None:
    if value is None:
        return None
    if not re.fullmatch(r"[A-Za-z]+(/[A-Za-z0-9_+-]+){0,2}", value) or value.startswith("Etc"):
        raise ValueError("timezone must be an IANA region zone such as America/Toronto")
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("unknown IANA timezone") from None
    return value


def resolve_local_deadline(
    day: _dt.date, local: _dt.time, zone: str | None, offset: str | None, fold: int | None
) -> tuple[datetime | None, str]:
    """Resolve a reviewed local cutoff to an aware instant, or explain why it cannot be.

    Never normalizes an impossible local time and never silently picks fold 0: a DST
    gap is ``nonexistent``, a repeated hour without ``fold`` is ``ambiguous``, and an
    explicit offset that disagrees with the zone is ``offset_inconsistent``.
    """
    from datetime import UTC, timedelta, timezone

    naive = datetime.combine(day, local)
    explicit = None
    if offset is not None:
        sign = 1 if offset[0] == "+" else -1
        hours, minutes = int(offset[1:3]), int(offset[4:6])
        explicit = timedelta(hours=hours, minutes=minutes) * sign
    if zone is None:
        if explicit is None:
            return None, "no_zone"
        return naive.replace(tzinfo=timezone(explicit)), "ok"
    z = ZoneInfo(zone)
    first, second = naive.replace(tzinfo=z, fold=0), naive.replace(tzinfo=z, fold=1)

    def round_trips(value: datetime) -> bool:
        return value.astimezone(UTC).astimezone(z).replace(tzinfo=None) == naive

    if not round_trips(first) and not round_trips(second):
        return None, "nonexistent"
    if first.utcoffset() != second.utcoffset() and fold is None:
        return None, "ambiguous"
    chosen = naive.replace(tzinfo=z, fold=fold or 0)
    if explicit is not None and chosen.utcoffset() != explicit:
        return None, "offset_inconsistent"
    return chosen, "ok"


class DeadlineSpec(BaseModel):
    """Submission cutoff as reviewed. Unknown components stay null; nothing is guessed."""

    model_config = _config(strict=True)

    kind: Literal["deadline"]
    original_wording: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    precision: Literal["exact", "date_only", "rolling", "unknown"]
    date: _dt.date | None = None
    local_time: _dt.time | None = None
    timezone: str | None = Field(default=None, description="IANA zone, e.g. America/Toronto.")
    utc_offset: str | None = Field(default=None, description="Explicit offset like -05:00.")
    fold: Literal[0, 1] | None = Field(
        default=None,
        description="Disambiguates a repeated local time at a DST fall-back (0 first, 1 second).",
    )
    boundary: Literal["inclusive", "exclusive", "unstated"] = "unstated"

    @field_validator("timezone")
    @classmethod
    def _zone(cls, value: str | None) -> str | None:
        return _valid_zone(value)

    @field_validator("utc_offset")
    @classmethod
    def _offset(cls, value: str | None) -> str | None:
        if value is not None and not _OFFSET.fullmatch(value):
            raise ValueError("utc_offset must look like +05:30 or -05:00")
        return value

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if self.precision == "exact":
            if self.date is None or self.local_time is None:
                raise ValueError("an exact deadline needs a date and a local time")
            if self.timezone is None and self.utc_offset is None:
                raise ValueError("an exact deadline needs a timezone or an explicit UTC offset")
        if self.precision == "date_only" and (self.date is None or self.local_time is not None):
            raise ValueError("a date-only deadline has a date and no time")
        if self.precision in ("rolling", "unknown") and (self.date or self.local_time):
            raise ValueError("rolling/unknown deadlines carry no date or time")
        if self.precision == "exact" and self.date and self.local_time:
            _, status = resolve_local_deadline(
                self.date, self.local_time, self.timezone, self.utc_offset, self.fold
            )
            if status == "nonexistent":
                raise ValueError("that local time does not exist in the zone (DST gap)")
            if status == "offset_inconsistent":
                raise ValueError("the explicit UTC offset disagrees with the timezone")
        return self


class ProjectWindowSpec(BaseModel):
    model_config = _config(strict=True)

    kind: Literal["project_window"]
    earliest_start: _dt.date | None = None
    latest_end: _dt.date | None = None
    start_boundary: Boundary = "inclusive"
    end_boundary: Boundary = "inclusive"

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if self.earliest_start is None and self.latest_end is None:
            raise ValueError("a project window needs at least one reviewed endpoint")
        if self.earliest_start and self.latest_end and self.latest_end < self.earliest_start:
            raise ValueError("the reviewed funding window is inverted")
        return self


class AmountRangeSpec(BaseModel):
    """Exact Decimal bounds. A pool or matching ratio is never a per-award cap."""

    model_config = _config(strict=True)

    kind: Literal["amount_range"]
    limit_kind: Literal["per_award", "total_pool", "matching_ratio"]
    minimum: DecimalString | None = None
    maximum: DecimalString | None = None
    currency: Currency
    scale: Literal["units", "thousands", "millions"] = "units"
    min_boundary: Boundary = "inclusive"
    max_boundary: Boundary = "inclusive"

    @model_validator(mode="after")
    def _shape(self) -> Self:
        from decimal import Decimal

        if self.minimum is None and self.maximum is None:
            raise ValueError("an amount range needs a minimum or a maximum")
        if self.minimum and self.maximum and Decimal(self.maximum) < Decimal(self.minimum):
            raise ValueError("the reviewed amount range is inverted")
        return self


class MembershipSpec(BaseModel):
    """Exact membership in a reviewed finite set (no substring or geocoding guesses)."""

    model_config = _config(strict=True)

    kind: Literal["geography", "organization_type"]
    allowed: Annotated[list[StableId], Field(min_length=1, max_length=100)]


class ActivitySpec(BaseModel):
    model_config = _config(strict=True)

    kind: Literal["activity"]
    allowed: Annotated[list[StableId], Field(min_length=1, max_length=100)]
    mode: Literal["any", "all"] = Field(
        description="any: at least one applicant activity is allowed; all: every one is."
    )


class InvitationSpec(BaseModel):
    """Invitation / prior-stage requirement. An Apply button is not an invitation."""

    model_config = _config(strict=True)

    kind: Literal["invitation"]
    required: StrictBool
    evidence_required: StrictBool = True


RequirementSpec = Annotated[
    DeadlineSpec
    | ProjectWindowSpec
    | AmountRangeSpec
    | MembershipSpec
    | ActivitySpec
    | InvitationSpec,
    Field(discriminator="kind"),
]


class RequirementScope(BaseModel):
    """Which stream/stage/cycle the requirement applies to. Null = the case's own context."""

    model_config = _config(strict=True)

    stream_label: ScopeLabel | None = None
    stage: Stage | None = None
    cycle_label: ScopeLabel | None = None
    application_type: ScopeLabel | None = None


class ApplicabilityCondition(BaseModel):
    """Reviewed applicability: n/a only when the typed input is known and differs."""

    model_config = _config(strict=True)

    input_field: Literal["application_type"]
    equals: ScopeLabel


class RequirementInput(BaseModel):
    model_config = _config(strict=True)

    requirement_key: Key
    spec: RequirementSpec
    anchor_keys: Annotated[list[Key], Field(min_length=1, max_length=10)]
    scope: RequirementScope = Field(default_factory=RequirementScope)
    applicability: ApplicabilityCondition | None = None
    interpretation: Annotated[str, StringConstraints(min_length=1, max_length=2000)] = Field(
        description="Staff rationale, stored separately from the raw passage."
    )


class Requirement(BaseModel):
    model_config = _config()

    requirement_key: str
    spec: RequirementSpec
    anchor_keys: list[str]
    scope: RequirementScope
    applicability: ApplicabilityCondition | None = None
    interpretation: str
    rule_ids: list[str] = Field(description="Catalog rules this kind implements a subset of.")


class FundingCaseCommand(BaseModel):
    """Create (no expected_version) or revise (expected_version) a case. Strict."""

    model_config = _config(strict=True)

    idempotency_key: IdempotencyKey
    expected_version: StrictVersion | None = None
    context: FundingContextInput
    capture_links: Annotated[list[CaptureLinkInput], Field(max_length=MAX_CAPTURE_LINKS)] = Field(
        default_factory=list
    )
    anchors: list[AnchorInput] = Field(default_factory=list)
    requirements: list[RequirementInput] = Field(default_factory=list)


class FundingCaseVersion(BaseModel):
    """One immutable case revision. Review status lives in separate review records."""

    model_config = _config()

    schema_version: Literal["1"] = "1"
    case_format: Literal["b1-funding-case/1"] = CASE_FORMAT
    organization_id: StableId
    case_id: StableId
    version: int = Field(ge=1, le=20)
    revision_of_version: int | None = None
    created_by: str
    created_at: datetime
    context: FundingContext
    capture_links: list[CaptureLink]
    anchors: list[EvidenceAnchor]
    requirements: list[Requirement]
    case_kind_label: Literal["staff_selected_context_not_certified"] = (
        "staff_selected_context_not_certified"
    )


class ReviewCommand(BaseModel):
    """'Review these requirements': names the exact version digest and every requirement."""

    model_config = _config(strict=True)

    idempotency_key: IdempotencyKey
    version_digest: Sha256Hex
    requirement_keys: Annotated[list[Key], Field(min_length=1, max_length=MAX_REQUIREMENTS)]


class CaseReview(BaseModel):
    model_config = _config()

    case_id: StableId
    version: int
    version_digest: Sha256Hex
    reviewer: str = Field(description="Server identity actor ID.")
    reviewed_at: datetime
    requirement_keys: list[str]
    statement: str


class SourceFinding(BaseModel):
    model_config = _config()

    observation_id: StableId
    capture_id: StableId
    overall: str
    observed_at: datetime
    message: str


class FundingCaseEnvelope(BaseModel):
    """Consistent read: exact version, digest, review, source status and projections."""

    model_config = _config()

    version: FundingCaseVersion
    version_digest: Sha256Hex
    current_version: int
    is_current: bool
    review: CaseReview | None = None
    review_status: Literal["reviewed", "unreviewed"]
    source_status: Literal["current", "requires_re_review"]
    source_findings: list[SourceFinding] = Field(default_factory=list)
    readiness: Literal["ready_for_evaluation", "not_reviewed", "requires_re_review", "no_rules"]
    opportunity: Opportunity | None = Field(
        default=None, description="Emitted only when funder, stream and cycle are established."
    )
    opportunity_missing: list[str] = Field(default_factory=list)
    requirement_set: RequirementSet | None = Field(
        default=None,
        description="Reviewed finite conditions; every evaluation stays 'unknown' (no verified "
        "organizational facts). Never a confirmed eligibility pass.",
    )
    notes: list[str] = Field(default_factory=list)


class FundingCaseSummary(BaseModel):
    model_config = _config()

    case_id: StableId
    status: Literal["ok", "integrity_failure"]
    current_version: int | None = None
    title: str | None = None
    funder_label: str | None = None
    stream_label: str | None = None
    cycle_label: str | None = None
    stage: Stage | None = None
    review_status: Literal["reviewed", "unreviewed"] | None = None
    source_status: Literal["current", "requires_re_review"] | None = None
    requirement_count: int | None = None
    created_at: datetime | None = None


class FundingCaseList(BaseModel):
    model_config = _config()

    items: list[FundingCaseSummary]
    next_cursor: str | None = None
    more: bool
    incomplete: bool
    limit: int


class FundingCaseNotFound(Exception):
    """Unknown case/version, or one outside the caller's organization."""


class FundingCaseIntegrityError(Exception):
    """A stored case version or review failed verification; content is withheld."""


@runtime_checkable
class FundingCaseReader(Protocol):
    """Public org-scoped reader (DEV-B-BUNDLE-002 s7.4). Consumers: automation, future C."""

    is_fixture: bool

    def get_version(
        self, organization_id: str, case_id: str, version: int
    ) -> FundingCaseEnvelope: ...

    def get_current(self, organization_id: str, case_id: str) -> FundingCaseEnvelope: ...


class FundingCaseVersionChanged(Exception):
    """The pinned case version is no longer current, or its digest differs."""

    def __init__(self, current_version: int) -> None:
        super().__init__(f"current case version is {current_version}")
        self.current_version = current_version


@runtime_checkable
class FundingCaseVersionPin(Protocol):
    """Atomic current-version boundary for consumers that bind an exact case version.

    ``pinned(org, case_id, version, digest)`` is a context manager. On entry it takes the
    funding-case store's cross-process write lock and verifies that ``version`` is still
    the current version with exactly ``digest``; otherwise it raises
    ``FundingCaseVersionChanged`` (or ``FundingCaseNotFound``). While the block runs, no
    case revision can commit, so a write made inside the block is atomic with the check.
    Keep the block short: other case writers wait (bounded) for it.
    """

    def pinned(
        self, organization_id: str, case_id: str, version: int, digest: str
    ) -> AbstractContextManager[None]: ...


class UnconfiguredFundingCaseReader:
    is_fixture = False

    def get_version(self, organization_id: str, case_id: str, version: int) -> FundingCaseEnvelope:
        raise CapabilityUnavailable("FundingCaseReader", "no repository configured")

    def get_current(self, organization_id: str, case_id: str) -> FundingCaseEnvelope:
        raise CapabilityUnavailable("FundingCaseReader", "no repository configured")


# ====================================================================== M4: evaluation


class AmountInput(BaseModel):
    model_config = _config(strict=True)

    amount: DecimalString
    currency: Currency
    scale: Literal["units", "thousands", "millions"] = "units"
    provenance: InputProvenance


class IdInput(BaseModel):
    model_config = _config(strict=True)

    value: StableId
    provenance: InputProvenance


class IdListInput(BaseModel):
    model_config = _config(strict=True)

    values: Annotated[list[StableId], Field(min_length=1, max_length=50)]
    provenance: InputProvenance


class LabelInput(BaseModel):
    model_config = _config(strict=True)

    value: ScopeLabel
    provenance: InputProvenance


class InvitationInput(BaseModel):
    model_config = _config(strict=True)

    status: Literal["invited", "not_invited"]
    provenance: InputProvenance
    evidence_note: Annotated[str, StringConstraints(max_length=500)] | None = Field(
        default=None, description="Staff note of the invitation evidence (not verified by B)."
    )


class DateInput(BaseModel):
    model_config = _config(strict=True)

    value: _dt.date
    provenance: InputProvenance


class ScenarioInputs(BaseModel):
    """Per-evaluation typed inputs. Not a knowledge base; nothing is written to A's store."""

    model_config = _config(strict=True)

    request_amount: AmountInput | None = None
    region: IdInput | None = None
    organization_type: IdInput | None = None
    activities: IdListInput | None = None
    invitation: InvitationInput | None = None
    project_start: DateInput | None = None
    project_end: DateInput | None = None
    application_type: LabelInput | None = None


class EvaluationScope(BaseModel):
    model_config = _config(strict=True)

    stream_label: ScopeLabel | None = None
    stage: Stage | None = None
    cycle_label: ScopeLabel | None = None


class EvaluateCommand(BaseModel):
    model_config = _config(strict=True)

    idempotency_key: IdempotencyKey
    case_version: StrictVersion
    clock: datetime | None = Field(
        default=None, description="Aware evaluation instant; default is the server clock."
    )
    scope: EvaluationScope = Field(default_factory=EvaluationScope)
    inputs: ScenarioInputs = Field(default_factory=ScenarioInputs)

    @field_validator("clock")
    @classmethod
    def _aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("the evaluation clock must be timezone-aware")
        return value


class SupportExcerpt(BaseModel):
    model_config = _config()

    anchor_key: str
    capture_id: StableId
    artifact_sha256: Sha256Hex
    start: int
    end: int
    quote: str
    coverage: str


class RequirementEvaluation(BaseModel):
    """Four plain-language answers per finding, from deterministic templates."""

    model_config = _config()

    requirement_key: str
    kind: str
    rule_ids: list[str]
    outcome: Outcome
    compared: str = Field(description="What code compared.")
    support: list[SupportExcerpt] = Field(description="Exact saved source support used.")
    inputs_used: list[str] = Field(description="Typed inputs used, with provenance.")
    found: str = Field(description="What it found, with exact values.")
    uncertainty: str = Field(description="What remains uncertain.")
    next_action: str
    missing_inputs: list[str] = Field(default_factory=list)
    validation: ValidationResult | None = None


class ExcludedRequirement(BaseModel):
    model_config = _config()

    requirement_key: str
    reason: str


class EvaluationReport(BaseModel):
    model_config = _config()

    schema_version: Literal["1"] = "1"
    evaluation_id: StableId
    organization_id: StableId
    case_id: StableId
    case_version: int
    case_digest: Sha256Hex
    review_digest: Sha256Hex | None = None
    evaluator_version: Literal["b1-rules/1"] = EVALUATOR_VERSION
    clock: datetime
    clock_source: Literal["request", "server"]
    scope: EvaluationScope
    inputs: ScenarioInputs
    inputs_digest: Sha256Hex
    readiness_at_evaluation: str
    results: list[RequirementEvaluation]
    excluded: list[ExcludedRequirement] = Field(default_factory=list)
    eligibility_group_outcome: Outcome | None = Field(
        default=None, description="All-of over reviewed eligibility predicates (ELG-01 logic)."
    )
    scenario_summary: str
    reliance_status: Literal["not_confirmed"] = "not_confirmed"
    reliance_explanation: str
    created_by: str
    created_at: datetime


class EvaluationEntry(BaseModel):
    """A stored report plus its present-day staleness (computed at read, never rewritten)."""

    model_config = _config()

    report: EvaluationReport
    stale: bool
    stale_reasons: list[str] = Field(default_factory=list)


class EvaluationList(BaseModel):
    model_config = _config()

    items: list[EvaluationEntry]
    next_cursor: str | None = None
    more: bool
    incomplete: bool
    limit: int


# ===================================================================== M5: research


class SearchProfileCommand(BaseModel):
    model_config = _config(strict=True)

    idempotency_key: IdempotencyKey
    expected_version: StrictVersion | None = None
    label: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    profile: SearchProfile


class SearchProfileVersion(BaseModel):
    model_config = _config()

    organization_id: StableId
    profile_id: StableId
    version: int
    label: str = Field(description="Inert staff label; never sent to a provider.")
    profile: SearchProfile
    query_preview: str = Field(description="Exactly the public query text a run would send.")
    public_fields_used: list[str]
    created_by: str
    created_at: datetime


class SearchProfileList(BaseModel):
    model_config = _config()

    items: list[SearchProfileVersion]
    next_cursor: str | None = None
    more: bool
    incomplete: bool
    limit: int


class RunSearchCommand(BaseModel):
    model_config = _config(strict=True)

    idempotency_key: IdempotencyKey
    profile_version: StrictVersion


class SearchRunRecord(BaseModel):
    model_config = _config()

    organization_id: StableId
    run_id: StableId
    profile_id: StableId
    profile_version: int
    started_at: datetime
    completed_at: datetime
    outcome: Literal["success", "failed", "unavailable"]
    error_reason: str | None = None
    error_message: str | None = None
    provider: str | None = None
    provider_mode: str | None = None
    result: SearchResult | None = None
    normalized_urls: list[str] = Field(default_factory=list)
    created_by: str


class SearchRunList(BaseModel):
    model_config = _config()

    items: list[SearchRunRecord]
    next_cursor: str | None = None
    more: bool
    incomplete: bool
    limit: int


class RunComparison(BaseModel):
    model_config = _config()

    profile_id: StableId
    profile_version: int
    base_run_id: StableId
    run_id: StableId
    newly_seen: list[str]
    seen_again: list[str]
    not_seen_in_this_result_set: list[str]
    note: str


class RecheckCommand(BaseModel):
    model_config = _config(strict=True)

    idempotency_key: IdempotencyKey
    funding_case_id: CaseId | None = None
    funding_case_version: StrictVersion | None = None

    @model_validator(mode="after")
    def _pair(self) -> Self:
        if (self.funding_case_id is None) != (self.funding_case_version is None):
            raise ValueError("funding_case_id and funding_case_version must be given together")
        return self


class RepresentationComparison(BaseModel):
    model_config = _config()

    representation: str
    old_sha256: Sha256Hex | None = None
    new_sha256: Sha256Hex | None = None
    outcome: Literal["match", "changed", "missing_in_new", "missing_in_old"]


class ChangeObservation(BaseModel):
    model_config = _config()

    schema_version: Literal["1"] = "1"
    organization_id: StableId
    observation_id: StableId
    old_capture_id: StableId
    new_capture_id: StableId | None = None
    requested_url: str
    observed_at: datetime
    options_comparable: bool
    old_options: dict[str, str | int | bool | list[str]] = Field(default_factory=dict)
    new_options: dict[str, str | int | bool | list[str]] = Field(default_factory=dict)
    comparisons: list[RepresentationComparison] = Field(default_factory=list)
    overall: Literal["unchanged", "changed", "partial", "failed", "not_comparable"]
    failure_reason: str | None = None
    explanation: str
    text_diff: str | None = Field(
        default=None, description="Bounded unified diff to help staff; not authoritative."
    )
    text_diff_truncated: bool = False
    linked_case_id: StableId | None = None
    linked_case_version: int | None = None
    downstream_effects: list[str] = Field(default_factory=list)
    created_by: str


class ChangeObservationList(BaseModel):
    model_config = _config()

    items: list[ChangeObservation]
    next_cursor: str | None = None
    more: bool
    incomplete: bool
    limit: int


FUNDING_REVIEW_PUBLIC_MODELS: tuple[type[BaseModel], ...] = (
    FundingCaseCommand,
    ReviewCommand,
    FundingCaseEnvelope,
    FundingCaseList,
    EvaluateCommand,
    EvaluationReport,
    EvaluationList,
    SearchProfileCommand,
    SearchProfileVersion,
    SearchProfileList,
    RunSearchCommand,
    SearchRunRecord,
    SearchRunList,
    RunComparison,
    RecheckCommand,
    ChangeObservation,
    ChangeObservationList,
)
