"""Approved prefill plans, single-use grants and verified read-back runs. Producer: B2.

B2-AUTO-002 rev 1.0 (s5-s10). This is a new, additive B-owned module. The read-only
intake/inspection contracts (``automation_intake``) and the shared ``FormMap`` /
``PrefillAction`` keep their meaning: ``FormInspectionResult.prefill_permitted`` stays
``False``, and an inspection never authorizes entry.

What exists here:

- request bodies (strict: no coercion, no extra fields). A client sends IDs and an
  expected plan hash, never text, selectors, URLs, organization or ``approved``;
- ``PrefillPlan``: a server-built, hashed entry plan. Building it writes nothing;
- ``PrefillGrant``: a short-lived, single-use authorization derived by the server;
- ``PrefillRun``: an immutable progress/receipt history backed by real Chromium read-back.

There is no submit, sign, click, keyboard, navigation or upload operation. The field
``submitted`` is always ``False``.

Consumer ports declared by B (s5.1, s9, s11). The implementations belong to other lanes:

- ``ApprovedPrefillReader`` (producer **C**, *proposed-cross-module*, see
  ``docs/handoffs/dev-b/b2-auto-002-approved-content-request-r1.md``);
- ``AttachmentEvidenceReader`` (an authorized artifact reader; none exists yet);
- ``PrefillDependencyCurrentness`` (producer **A**/A4; no in-process factory yet).

Each default implementation fails closed with ``CapabilityUnavailable``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Final, Literal, Protocol, Self, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .answers import ApprovalSnapshot, DependencyRef
from .automation_intake import NetworkLogEntry
from .common import ContractModel, Provenance, Sha256Hex, StableId
from .knowledge_binding import ApprovedKnowledgeBinding, KnowledgeRegistration
from .ports import CapabilityUnavailable

PLAN_FORMAT: Final = "b2-approved-prefill/2"
RUN_FORMAT: Final = "b2-prefill-run/1"
BOUND_MAP_FORMAT: Final = "b2-bound-form-map/1"
CONTENT_FORMAT: Final = "b2-requested-approved-prefill-content/1"
MAX_ACTIONS: Final = 20
PLAN_TTL_SECONDS: Final = 120
EXECUTION_TIMEOUT_MS: Final = 30_000
OPERATION_TIMEOUT_MS: Final = 5_000
MAX_VALUE_CHARS: Final = 20_000

ReadbackComparison = Literal[
    "b2-readback-exact/1",  # exact Unicode string equality
    "b2-readback-textarea-crlf/1",  # exact after mapping CRLF to LF on both sides
    "b2-readback-choice-exact/1",  # exact ordered set of checked/selected option values
]
ControlType = Literal["text", "textarea", "number", "select", "radio", "checkbox"]
Operation = Literal["fill", "select_option", "check"]
FORBIDDEN_OPERATIONS: Final = (
    "submit",
    "sign",
    "click",
    "press_key",
    "navigate",
    "upload_file",
    "evaluate_untrusted_script",
)


def _config(strict: bool = False) -> ConfigDict:
    return ConfigDict(
        extra="forbid",
        frozen=True,
        strict=strict,
        str_strip_whitespace=False,
        json_schema_extra={"x-contract-status": "draft", "x-owner": "B2"},
    )


PlanId = Annotated[str, StringConstraints(pattern=r"^pfp-[0-9a-f]{26}$")]
RunId = Annotated[str, StringConstraints(pattern=r"^pfr-[0-9a-f]{26}$")]
QuestionSetId = Annotated[str, StringConstraints(pattern=r"^qs-def-[0-9a-f]{26}-v[0-9]{1,2}$")]
PortalFixtureId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9-]{0,63}$")]
IdempotencyKey = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9._:-]{8,128}$")]


# --------------------------------------------------------------------------- requests


class PrefillSelection(ContractModel):
    """One published question the staff selected, and the C approval naming it."""

    model_config = _config(strict=True)

    published_question_id: StableId
    approval_snapshot_id: StableId


class PreparePrefillPlanRequest(ContractModel):
    """Body of POST /api/automation/prefill-plans. Identity and content come from the server."""

    model_config = _config(strict=True)

    question_set_id: QuestionSetId
    portal_fixture_id: PortalFixtureId
    selections: list[PrefillSelection] = Field(min_length=1, max_length=MAX_ACTIONS)

    @model_validator(mode="after")
    def _unique(self) -> Self:
        qs = [s.published_question_id for s in self.selections]
        aps = [s.approval_snapshot_id for s in self.selections]
        if len(qs) != len(set(qs)):
            raise ValueError("a question may be selected only once")
        if len(aps) != len(set(aps)):
            raise ValueError("an approval may be used for only one question")
        return self


class ExecutePrefillRequest(ContractModel):
    """Body of POST /api/automation/prefill-plans/{plan_id}/execute ("Fill these fields")."""

    model_config = _config(strict=True)

    expected_plan_sha256: Sha256Hex
    idempotency_key: IdempotencyKey


# --------------------------------------------------------------------------- C content (port)


class ApprovedTypedValue(ContractModel):
    """A C-authorized typed value for choice controls. Prose is never a choice value."""

    model_config = _config()

    kind: Literal["choice"]
    values: list[str] = Field(min_length=1, max_length=20)


class ApprovedPrefillContent(ContractModel):
    """One consistent approved-content envelope (requested from Dev C; s5.1).

    C guarantees these properties. B recomputes the hashes and checks every identity.
    """

    model_config = _config()

    content_format: Literal["b2-requested-approved-prefill-content/1"] = CONTENT_FORMAT
    organization_id: StableId
    approval: ApprovalSnapshot
    answer_version_id: StableId
    answer_version: int = Field(ge=1)
    question_set_id: StableId
    question_id: StableId
    question_version: int = Field(ge=1)
    template_text: str = Field(max_length=MAX_VALUE_CHARS)
    template_sha256: Sha256Hex
    rendered_text: str = Field(max_length=MAX_VALUE_CHARS)
    rendered_sha256: Sha256Hex
    renderer_version: str
    unresolved_marker_count: int = Field(ge=0)
    dependency_snapshot_sha256: Sha256Hex
    dependencies: list[DependencyRef] = Field(default_factory=list)
    currentness: Literal["current"]
    currentness_checked_at: datetime
    a4_binding: ApprovedKnowledgeBinding | None = None
    typed_value: ApprovedTypedValue | None = None
    provenance: Provenance
    is_fixture: bool
    producer_id: str
    producer_epoch: str


@runtime_checkable
class ApprovedPrefillReader(Protocol):
    """Consumer port for C's approved content. Raises ``ApprovalNotUsable`` for missing,
    other-organization, rejected or stale approvals, and ``CapabilityUnavailable`` when
    unconfigured."""

    is_fixture: bool

    def resolve_for_prefill(
        self, organization_id: str, approval_snapshot_id: str
    ) -> ApprovedPrefillContent: ...


class UnconfiguredApprovedPrefillReader:
    is_fixture = False

    def resolve_for_prefill(
        self, organization_id: str, approval_snapshot_id: str
    ) -> ApprovedPrefillContent:
        raise CapabilityUnavailable(
            "ApprovedPrefillReader", "no C approved-content reader is configured"
        )


class TrustedAttachmentRecord(ContractModel):
    """Server-resolved artifact evidence for an attachment question (never client-claimed)."""

    model_config = _config()

    artifact_id: StableId
    original_question_id: StableId
    detected_media_type: str = Field(description="From the bytes, not a filename or MIME claim.")
    size_bytes: int = Field(ge=0)
    sha256: Sha256Hex
    exists: bool
    basis: Literal["trusted_synthetic_test_record", "authorized_artifact_reader"]
    is_fixture: bool


@runtime_checkable
class AttachmentEvidenceReader(Protocol):
    is_fixture: bool

    def list_for(
        self, organization_id: str, question_set_id: str
    ) -> list[TrustedAttachmentRecord]: ...


class UnconfiguredAttachmentEvidenceReader:
    is_fixture = False

    def list_for(self, organization_id: str, question_set_id: str) -> list[TrustedAttachmentRecord]:
        raise CapabilityUnavailable("AttachmentEvidenceReader", "no authorized artifact reader")


class DependencyCurrentness(ContractModel):
    model_config = _config()

    status: Literal["current", "stale", "unavailable"]
    detail: str


@runtime_checkable
class PrefillDependencyCurrentness(Protocol):
    """Currentness of a plan's exact dependencies (A4-managed kinds). Read before actions."""

    is_fixture: bool

    def check(
        self, organization_id: str, target_id: str, dependencies: list[DependencyRef]
    ) -> DependencyCurrentness: ...


# --------------------------------------------------------------------------- plan


class PlanDefinitionRef(ContractModel):
    model_config = _config()

    definition_id: StableId
    definition_version: int = Field(ge=1)
    question_set_id: StableId
    publication_digest: Sha256Hex = Field(description="normalized_digest of the publication.")
    input_sha256: Sha256Hex
    funding_case_id: StableId | None = None
    funding_case_version: int | None = Field(default=None, ge=1)
    funding_case_digest: Sha256Hex | None = None


class BoundField(ContractModel):
    """Registry control bound to a published question through the publication's mapping."""

    model_config = _config()

    original_question_id: StableId
    published_question_id: StableId
    question_version: int = Field(ge=1)
    field_id: StableId
    control: ControlType | Literal["file"]
    options: list[str] = Field(default_factory=list)
    native_max_length: int | None = Field(default=None, ge=0)
    minimum: str | None = None
    maximum: str | None = None


class PortalBinding(ContractModel):
    """Versioned bound form map for one saved definition and one registered fixture."""

    model_config = _config()

    binding_format: Literal["b2-bound-form-map/1"] = BOUND_MAP_FORMAT
    portal_fixture_id: StableId
    form_id: StableId
    form_version: int = Field(ge=1)
    page_sha256: Sha256Hex
    fingerprint_algorithm: Literal["b2-form-fp/1"] = "b2-form-fp/1"
    expected_fingerprint: Sha256Hex
    logical_origin: str = Field(pattern=r"^fixture://[a-z0-9.-]+$")
    fields: list[BoundField]


class PlanCondition(ContractModel):
    model_config = _config()

    parent_published_question_id: StableId
    expected_value: str
    basis: Literal["structured_definition_and_registry"]


class PlannedFieldAction(ContractModel):
    model_config = _config()

    action_index: int = Field(ge=0)
    published_question_id: StableId
    original_question_id: StableId
    question_version: int = Field(ge=1)
    field_id: StableId
    control: ControlType
    operation: Operation
    approval_snapshot_id: StableId
    answer_version_id: StableId
    producer_id: str
    producer_epoch: str
    template_sha256: Sha256Hex
    rendered_sha256: Sha256Hex
    dependency_snapshot_sha256: Sha256Hex
    dependencies: list[DependencyRef] = Field(default_factory=list)
    a4_binding: ApprovedKnowledgeBinding | None = None
    intended_value: str | None = Field(default=None, description="Text/number: exact string.")
    intended_choices: list[str] = Field(default_factory=list)
    intended_sha256: Sha256Hex
    intended_length_utf16: int | None = Field(default=None, ge=0)
    comparison: ReadbackComparison
    constraints: list[str] = Field(default_factory=list)
    requirement_refs: list[str] = Field(default_factory=list)
    condition: PlanCondition | None = None
    approval_provenance: Provenance


HeldReason = Literal[
    "held_unresolved_requirement",
    "held_counter_unavailable",
    "held_unconfirmed_convention",
    "held_value_format",
    "held_value_too_long",
    "held_value_empty",
    "held_choice_value_unavailable",
    "held_choice_not_registered",
    "held_condition_unsupported",
    "held_parent_not_selected",
    "held_unsupported_control",
    "held_attachment_upload_disabled",
    "mapping_missing",
    "approval_not_usable",
    "approval_identity_mismatch",
    "approval_integrity_mismatch",
    "unresolved_fact_token",
]


class HeldField(ContractModel):
    model_config = _config()

    published_question_id: StableId
    original_question_id: StableId | None = None
    field_id: StableId | None = None
    approval_snapshot_id: StableId | None = None
    reason: HeldReason
    detail: str


class UnselectedRequirement(ContractModel):
    """A required/conditional question outside the selection. It stays visible."""

    model_config = _config()

    published_question_id: StableId
    original_question_id: StableId
    required_status: Literal["required", "optional", "conditional", "unknown"]
    answer_kind: str


class AttachmentChecklistItem(ContractModel):
    """AUT-04 checklist coverage only. Nothing is uploaded."""

    model_config = _config()

    original_question_id: StableId
    published_question_id: StableId
    required_status: Literal["required", "optional", "conditional", "unknown"]
    accepted_types: list[str] | None = None
    max_size_bytes: int | None = None
    max_count: int | None = None
    status: Literal["needs_review_unavailable", "findings", "matches_trusted_record"]
    findings: list[str] = Field(default_factory=list)
    artifact_ids: list[StableId] = Field(default_factory=list)
    evidence_basis: str
    upload: Literal["disabled"] = "disabled"


class PrefillBudgets(ContractModel):
    model_config = _config()

    plan_ttl_seconds: int = PLAN_TTL_SECONDS
    max_actions: int = MAX_ACTIONS
    execution_timeout_ms: int = EXECUTION_TIMEOUT_MS
    operation_timeout_ms: int = OPERATION_TIMEOUT_MS
    browser_executions_per_grant: Literal[1] = 1
    automatic_write_retries: Literal[0] = 0


class ProducerLabel(ContractModel):
    model_config = _config()

    approval_reader: Literal["explicit_test_provider", "c_reader"]
    approval_reader_is_fixture: bool
    dependency_currentness: Literal["not_integrated", "explicit_test_provider", "a4_adapter"]
    attachment_evidence: Literal["unavailable", "explicit_test_provider", "artifact_reader"]


class PrefillPlan(ContractModel):
    model_config = _config()

    schema_version: Literal["1"] = "1"
    plan_format: Literal["b2-approved-prefill/1", "b2-approved-prefill/2"] = PLAN_FORMAT
    plan_id: PlanId
    plan_sha256: Sha256Hex = Field(description="sha256 of the canonical plan without this field.")
    organization_id: StableId
    created_by: str
    created_at: datetime
    expires_at: datetime
    runtime_epoch: str
    definition: PlanDefinitionRef
    portal: PortalBinding
    actions: list[PlannedFieldAction] = Field(max_length=MAX_ACTIONS)
    dependency_union: list[DependencyRef] = Field(default_factory=list)
    a4_registration: KnowledgeRegistration | None = None
    held: list[HeldField] = Field(default_factory=list)
    unselected_requirements: list[UnselectedRequirement] = Field(default_factory=list)
    attachments: list[AttachmentChecklistItem] = Field(default_factory=list)
    executable: bool
    not_executable_reasons: list[str] = Field(default_factory=list)
    scope: Literal["selected_fields_demo_only"] = "selected_fields_demo_only"
    scope_note: str
    producers: ProducerLabel
    budgets: PrefillBudgets
    forbidden_operations: list[str] = Field(default_factory=lambda: list(FORBIDDEN_OPERATIONS))
    submission: Literal["not_possible"] = "not_possible"
    provenance: Provenance
    is_fixture: bool
    mode_label: str


class PrefillPlanView(ContractModel):
    """GET result: the saved plan exactly as hashed, plus separately computed availability."""

    model_config = _config()

    plan: PrefillPlan
    availability: Literal[
        "executable",
        "expired",
        "runtime_epoch_changed",
        "claimed",
        "empty",
        "stale",
        "dependency_unavailable",
        "prepare_new_plan",
    ]
    availability_reason: str | None = None
    next_action: str | None = None
    run_id: RunId | None = None


# --------------------------------------------------------------------------- grant and run


class GrantedFieldOperation(ContractModel):
    model_config = _config()

    action_index: int = Field(ge=0)
    field_id: StableId
    operation: Operation
    published_question_id: StableId
    approval_snapshot_id: StableId
    rendered_sha256: Sha256Hex
    intended_sha256: Sha256Hex


class PrefillGrant(ContractModel):
    """Single-use, short-lived authorization derived by the server from one exact plan."""

    model_config = _config()

    grant_format: Literal["b2-prefill-grant/1", "b2-prefill-grant/2"] = "b2-prefill-grant/1"
    a4_registration: KnowledgeRegistration | None = None
    grant_id: StableId
    grant_sha256: Sha256Hex
    plan_id: PlanId
    plan_sha256: Sha256Hex
    organization_id: StableId
    actor_id: str
    portal_fixture_id: StableId
    logical_origin: str
    runtime_origin: Literal["ephemeral_loopback_fixture_server"] = (
        "ephemeral_loopback_fixture_server"
    )
    form_id: StableId
    form_version: int = Field(ge=1)
    expected_fingerprint: Sha256Hex
    page_sha256: Sha256Hex
    operations: list[GrantedFieldOperation] = Field(min_length=1, max_length=MAX_ACTIONS)
    created_at: datetime
    expires_at: datetime
    nonce: str
    runtime_epoch: str
    budgets: PrefillBudgets
    forbidden_operations: list[str] = Field(default_factory=lambda: list(FORBIDDEN_OPERATIONS))


FieldState = Literal[
    "not_attempted",
    "blocked_before_write",
    "write_in_flight",
    "entered_verified",
    "entered_then_stale",
    "mismatch",
    "overwritten_after_verify",
    "write_failed",
    "outcome_unknown",
]


class FieldReceipt(ContractModel):
    model_config = _config()

    action_index: int = Field(ge=0)
    published_question_id: StableId
    field_id: StableId
    operation: Operation
    approval_snapshot_id: StableId
    answer_version_id: StableId
    rendered_sha256: Sha256Hex
    state: FieldState
    intended_sha256: Sha256Hex
    intended_length_utf16: int | None = None
    actual_value: str | None = Field(default=None, description="Live DOM value/checked values.")
    actual_sha256: Sha256Hex | None = None
    actual_length_utf16: int | None = None
    compared_intended_sha256: Sha256Hex | None = None
    compared_actual_sha256: Sha256Hex | None = None
    comparison: ReadbackComparison
    result: Literal["match", "mismatch", "not_compared"]
    reason: str | None = None
    next_action: str


class CurrentnessCheck(ContractModel):
    model_config = _config()

    stage: str = Field(description="pre_execution, before:<i>, after:<i>, completion")
    status: Literal["current", "stale", "unavailable", "not_checked"]
    detail: str


class PrefillActivity(ContractModel):
    model_config = _config()

    operations_performed: list[str] = Field(default_factory=list)
    requests_allowed: int = Field(default=0, ge=0)
    requests_blocked: int = Field(default=0, ge=0)
    mutation_requests_blocked: int = Field(default=0, ge=0)
    fixture_server_mutation_hits: int = Field(default=0, ge=0)
    popups_blocked: int = Field(default=0, ge=0)
    downloads_blocked: int = Field(default=0, ge=0)
    navigations_blocked: int = Field(default=0, ge=0)
    websockets_blocked: int = Field(default=0, ge=0)
    blocked_log: list[NetworkLogEntry] = Field(default_factory=list)
    blocked_log_truncated: bool = False


RunOutcome = Literal[
    "in_progress",
    "selected_fields_verified",
    "stopped_with_partial_entry",
    "blocked_before_entry",
    "outcome_unknown",
]


class PrefillRun(ContractModel):
    """One immutable version of a run's history (v1 = claim, later versions = progress)."""

    model_config = _config()

    schema_version: Literal["1"] = "1"
    run_format: Literal["b2-prefill-run/1"] = RUN_FORMAT
    run_id: RunId
    run_version: int = Field(ge=1)
    plan_id: PlanId
    plan_sha256: Sha256Hex
    organization_id: StableId
    actor_id: str
    status: Literal["claimed", "running", "completed"]
    outcome: RunOutcome
    outcome_reason: str | None = None
    grant: PrefillGrant
    claimed_at: datetime
    deadline_at: datetime
    finished_at: datetime | None = None
    fields: list[FieldReceipt]
    checks: list[CurrentnessCheck] = Field(default_factory=list)
    final_reread: Literal["all_match", "mismatch", "not_run"] = "not_run"
    activity: PrefillActivity = Field(default_factory=PrefillActivity)
    browser_version: str | None = None
    scope: Literal["selected_fields_demo_only"] = "selected_fields_demo_only"
    receipt_note: str
    submitted: Literal[False] = False
    provenance: Provenance
    is_fixture: bool


class PrefillRunView(ContractModel):
    """A stored run version plus labels computed at read time (never rewritten)."""

    model_config = _config()

    run: PrefillRun
    effective_outcome: RunOutcome
    interrupted: bool = Field(description="True when an incomplete run passed its deadline.")
    history_note: str


class ExecutePrefillResult(ContractModel):
    model_config = _config()

    replayed: bool
    run: PrefillRunView


AUTOMATION_PREFILL_PUBLIC_MODELS: tuple[type[BaseModel], ...] = (
    PreparePrefillPlanRequest,
    ExecutePrefillRequest,
    ApprovedPrefillContent,
    TrustedAttachmentRecord,
    DependencyCurrentness,
    PrefillPlan,
    PrefillPlanView,
    PrefillRun,
    PrefillRunView,
    ExecutePrefillResult,
)
