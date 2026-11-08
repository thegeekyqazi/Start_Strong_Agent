"""Saved application definitions and the public question reader. Producer: B2 (automation).

DEV-B-BUNDLE-002 rev 1.0 s5 (M1). Integrates the superseded B2-AUTO-001A requirements.

A *saved* definition is an immutable, versioned publication of one bounded intake. Saving
is not reviewing or approving: ``approval_status`` is always ``not_approved``,
``prefill_permitted`` is always ``False`` and ``review_status`` is ``saved_not_reviewed``.
The existing intake and export responses keep ``persisted: false``; this module adds
a separate envelope rather than changing those literals.

Consumers (C2b) import only from this module plus the documented composition factory
``strongstart_api.features.automation.public.get_application_definition_reader``.
They must pass the **server-derived** organization ID and must never accept
browser-supplied question or provenance payloads.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Final, Literal, Protocol, Self, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, Strict, StringConstraints, model_validator

from .automation import ApplicationDefinition, QuestionSet
from .automation_intake import ApplicationIntakeResult, IntakeSource, UnresolvedItem
from .common import ContractModel, Provenance, Sha256Hex, StableId
from .ports import CapabilityUnavailable

PUBLICATION_FORMAT: Final = "b2-published-definition/1"
DIGEST_ALGORITHM: Final = "dev-b-canonical-json-sha256/1"
MAX_PUBLISHED_QUESTIONS: Final = 100
MAX_DEFINITION_VERSIONS: Final = 20


def _config(strict: bool = False) -> ConfigDict:
    return ConfigDict(
        extra="forbid",
        frozen=True,
        strict=strict,
        str_strip_whitespace=False,
        json_schema_extra={"x-contract-status": "draft", "x-owner": "B2"},
    )


DefinitionId = Annotated[str, StringConstraints(pattern=r"^def-[0-9a-f]{26}$")]
QuestionSetId = Annotated[str, StringConstraints(pattern=r"^qs-def-[0-9a-f]{26}-v[0-9]{1,2}$")]
FundingCaseId = Annotated[str, StringConstraints(pattern=r"^case-[0-9a-f]{26}$")]
IdempotencyKey = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._:-]{8,128}$")]
StrictVersion = Annotated[int, Strict(), Field(ge=1, le=MAX_DEFINITION_VERSIONS)]


# --------------------------------------------------------------------------- command


class SaveDefinitionRequest(ContractModel):
    """Body of POST /api/automation/definitions. Strict: no coercion, no extra fields.

    The server re-runs intake on ``source`` and compares the parsed bytes with
    ``expected_input_sha256`` (the preview hash). Organization, actor, approval and
    provenance are never accepted from the client.
    """

    model_config = _config(strict=True)

    source: IntakeSource
    expected_input_sha256: Sha256Hex
    idempotency_key: IdempotencyKey
    definition_id: DefinitionId | None = Field(
        default=None, description="Existing lineage for a revision (with expected_version)."
    )
    expected_version: StrictVersion | None = None
    funding_case_id: FundingCaseId | None = Field(
        default=None, description="Exact funding case (with funding_case_version), M3 context."
    )
    funding_case_version: StrictVersion | None = None

    @model_validator(mode="after")
    def _pairs(self) -> Self:
        if (self.definition_id is None) != (self.expected_version is None):
            raise ValueError("definition_id and expected_version must be given together")
        if (self.funding_case_id is None) != (self.funding_case_version is None):
            raise ValueError("funding_case_id and funding_case_version must be given together")
        return self


# --------------------------------------------------------------------------- envelope


class QuestionIdMapping(ContractModel):
    model_config = _config()

    original_question_id: StableId = Field(description="ID in the imported source (a claim).")
    published_question_id: StableId = Field(description="Namespaced by the stored definition.")
    question_version: int = Field(ge=1, description="Equals the definition version.")
    order: int = Field(ge=0)


class DeclaredContext(ContractModel):
    """IDs the source itself declared. Preserved as claims, never treated as authority."""

    model_config = _config()

    opportunity_id: StableId | None = None
    stream_id: StableId | None = None
    cycle_id: StableId | None = None
    basis: Literal["fixture_registry", "source_declared_claim", "none"]


class FundingContextBinding(ContractModel):
    """An exact, version-pinned funding case selected by staff (M3)."""

    model_config = _config()

    funding_case_id: StableId
    funding_case_version: int = Field(ge=1)
    funding_case_digest: Sha256Hex
    opportunity_id: StableId
    funder_id: StableId
    stream_id: StableId
    cycle_id: StableId
    stage: Literal["eoi", "full_application", "single_stage", "unknown"]
    case_review_status: Literal["reviewed", "unreviewed"]
    linked_capture_ids: list[StableId] = Field(default_factory=list)


class PublicationContext(ContractModel):
    model_config = _config()

    opportunity_id: StableId
    opportunity_basis: Literal["funding_case", "fixture_registry", "source_declared_claim"]
    declared: DeclaredContext
    binding: FundingContextBinding | None = None
    notes: list[str] = Field(default_factory=list)


class PublicationIntegrity(ContractModel):
    model_config = _config()

    algorithm: Literal["dev-b-canonical-json-sha256/1"] = DIGEST_ALGORITHM
    raw_input_sha256: Sha256Hex
    raw_input_size: int = Field(ge=0)
    raw_input_retained: Literal["dev_b_local_blob"] = "dev_b_local_blob"
    normalized_digest: Sha256Hex = Field(
        description="Digest of the canonical JSON of the published content groups "
        "(question_set, application_definition, intake, id_mapping, unresolved, context)."
    )


class PublishedApplicationVersion(ContractModel):
    """One immutable saved revision. Saved does not mean reviewed or approved."""

    model_config = _config()

    schema_version: Literal["1"] = "1"
    publication_format: Literal["b2-published-definition/1"] = PUBLICATION_FORMAT
    organization_id: StableId = Field(description="Server-derived organization scope.")
    definition_id: StableId
    version: int = Field(ge=1, le=MAX_DEFINITION_VERSIONS)
    question_set_id: StableId
    revision_of_version: int | None = Field(default=None, ge=1)
    saved_by: str = Field(description="Server identity actor ID.")
    saved_at: datetime
    integrity: PublicationIntegrity
    question_set: QuestionSet
    application_definition: ApplicationDefinition
    intake: ApplicationIntakeResult = Field(
        description="Original rich intake (exact wording, locators, candidate/native limits, "
        "conditions, attachments, findings) with ORIGINAL question IDs."
    )
    id_mapping: list[QuestionIdMapping]
    added_original_ids: list[StableId] = Field(default_factory=list)
    removed_original_ids: list[StableId] = Field(default_factory=list)
    unresolved: list[UnresolvedItem] = Field(
        default_factory=list, description="Unresolved items keyed by PUBLISHED question IDs."
    )
    context: PublicationContext
    provenance: Provenance
    is_fixture: bool
    mode_label: str
    review_status: Literal["saved_not_reviewed"] = "saved_not_reviewed"
    approval_status: Literal["not_approved"] = "not_approved"
    prefill_permitted: Literal[False] = False
    consumer_notes: list[str] = Field(default_factory=list)


class SaveDefinitionResult(ContractModel):
    model_config = _config()

    replayed: bool = Field(description="True when an identical idempotent command was replayed.")
    publication: PublishedApplicationVersion


class DefinitionSummary(ContractModel):
    model_config = _config()

    definition_id: StableId
    status: Literal["ok", "integrity_failure"]
    current_version: int | None = None
    question_set_id: StableId | None = None
    title: str | None = None
    question_count: int | None = None
    unresolved_count: int | None = None
    opportunity_id: StableId | None = None
    saved_at: datetime | None = None
    saved_by: str | None = None
    is_fixture: bool | None = None
    mode_label: str | None = None
    raw_input_sha256: Sha256Hex | None = None
    detail: str | None = None


class DefinitionList(ContractModel):
    model_config = _config()

    items: list[DefinitionSummary]
    next_cursor: str | None = None
    more: bool
    incomplete: bool = Field(description="True when the bounded scan limit was reached.")
    limit: int


# --------------------------------------------------------------------------- reader port


class ApplicationDefinitionNotFound(Exception):
    """Unknown definition/question set, or one outside the caller's organization."""


class ApplicationDefinitionIntegrityError(Exception):
    """A stored version failed verification; all dependent content is withheld."""


@runtime_checkable
class ApplicationDefinitionReader(Protocol):
    """Public, organization-scoped read port (DEV-B-BUNDLE-002 s5.3).

    ``get_version`` returns exactly the immutable version a question-set ID names (never a
    substituted latest version). ``get_current`` returns the latest saved version of a
    definition lineage, for later current-version checks. Unknown and other-organization
    IDs raise ``ApplicationDefinitionNotFound`` identically. ``is_fixture`` describes the
    adapter only; record/source provenance stays on each version.
    """

    is_fixture: bool

    def get_version(
        self, organization_id: str, question_set_id: str
    ) -> PublishedApplicationVersion: ...

    def get_current(
        self, organization_id: str, definition_id: str
    ) -> PublishedApplicationVersion: ...


class UnconfiguredApplicationDefinitionReader:
    """Default: no saved-definition repository (production). Fails closed."""

    is_fixture = False

    def get_version(
        self, organization_id: str, question_set_id: str
    ) -> PublishedApplicationVersion:
        raise CapabilityUnavailable("ApplicationDefinitionReader", "no repository configured")

    def get_current(self, organization_id: str, definition_id: str) -> PublishedApplicationVersion:
        raise CapabilityUnavailable("ApplicationDefinitionReader", "no repository configured")


APPLICATION_PUBLICATION_PUBLIC_MODELS: tuple[type[BaseModel], ...] = (
    SaveDefinitionRequest,
    SaveDefinitionResult,
    PublishedApplicationVersion,
    DefinitionList,
)
