"""Application intake and representative-form inspection contracts. Producer: B2.

B2-AUTO-001 (spec rev 1.0, s4, s6-s8). These are automation-owned, additive wrappers
around the shared strict DTOs in ``automation.py`` (QuestionSet, ApplicationDefinition,
FormMap) and ``common.py`` (SourceReference, Provenance). The shared DTOs are not
weakened: richer intake detail (exact wording, competing limits, native browser
properties, unknown conventions, findings) lives here, and the shared DTOs are
emitted as *projections* of the same data.

Nothing in this module expresses approval, answer entry, upload, submission or
signing. ``approval_status`` is always ``not_approved``; ``prefill_permitted`` is
always ``False``. An imported limit is ``imported_provisional`` until a later
authority review exists.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, Field

from .automation import ApplicationDefinition, FormMap, QuestionSet
from .common import (
    SCHEMA_VERSION,
    ContractModel,
    DecimalString,
    Provenance,
    Sha256Hex,
    SourceReference,
    StableId,
    contract_model_config,
)
from .platform import Capability

INTAKE_FORMAT: Final = "b2-application-intake/1"
INSPECTION_FORMAT: Final = "b2-form-inspection/1"
EXPORT_FORMAT: Final = "b2-automation-handoff/1"
FINGERPRINT_ALGORITHM: Final = "b2-form-fp/1"

_B2 = contract_model_config("draft", "B2")


# --------------------------------------------------------------------------- evidence


class SourceLocator(ContractModel):
    """Precise location inside the exact imported representation. Never a made-up page."""

    model_config = _B2

    kind: Literal["json_pointer", "html_element", "dom_element", "whole_input"]
    value: str = Field(description="JSON pointer, element path or DOM description.")
    line: int | None = Field(default=None, ge=1)
    column: int | None = Field(default=None, ge=0)


class ExactText(ContractModel):
    """Exact imported text plus a separately derived display form."""

    model_config = _B2

    text: str = Field(description="Exact text as imported (entities decoded for HTML).")
    display_text: str = Field(description="Derived: whitespace-collapsed for display only.")
    locator: SourceLocator


class CaptureLineage(ContractModel):
    """Lineage of a captured document consumed through the B1-B2 capture port."""

    model_config = _B2

    capture_id: StableId
    source_version_id: StableId
    artifact_id: StableId
    representation_type: str
    organization_scope: Literal["server_verified"] = "server_verified"
    opportunity_id: StableId | None = None
    stream_id: StableId | None = None
    cycle_id: StableId | None = None
    original_url: str | None = None
    requested_url: str | None = None
    final_url: str | None = None
    final_url_status: Literal["known", "unknown"]
    provider: str | None = None
    captured_at: datetime | None = None
    authority_review_status: str
    extraction_warnings: list[str] = Field(default_factory=list)
    capture_is_fixture: bool


class InputRepresentation(ContractModel):
    """The exact bytes this result was derived from. Identity/hash are server-created."""

    model_config = _B2

    representation_id: StableId
    origin: Literal["fixture", "uploaded_unverified", "capture"]
    representation_type: Literal[
        "structured_json",
        "html_form",
        "provider_html",
        "provider_raw_html",
        "original_http_bytes",
        "provider_markdown",
        "pdf",
        "unknown",
    ]
    media_type: str
    byte_size: int = Field(ge=0)
    sha256: Sha256Hex = Field(description="SHA-256 of the exact bytes parsed (UTF-8 for text).")
    integrity: Literal["computed_on_receipt", "hash_verified_against_capture_record"]
    parser_id: str
    parser_version: str
    normalization_version: str
    persisted: Literal[False] = False
    storage: Literal["nonpersistent_response", "capture_port_reference"]
    capture: CaptureLineage | None = None


# --------------------------------------------------------------------------- questions


class IntakeLimit(ContractModel):
    """One candidate constraint. Semantic limits and native browser properties stay distinct."""

    model_config = _B2

    limit_id: StableId
    kind: Literal[
        "instruction_text", "structured_definition", "native_dom_maxlength", "native_dom_range"
    ]
    minimum: DecimalString | None = None
    maximum: DecimalString | None = None
    unit: Literal["words", "characters", "amount", "utf16_code_units", "unknown"]
    counting_convention: str = Field(
        default="unknown",
        description="'unknown' unless the source declares it; native maxlength is HTML-defined.",
    )
    convention_status: Literal[
        "unknown_pending_confirmation", "declared_in_source", "defined_by_html_spec"
    ]
    authority_status: Literal["imported_provisional", "browser_property"]
    applies_to_stream: StableId | None = None
    evidence: ExactText


class LimitConflictRecord(ContractModel):
    """Competing constraints. Never resolved by choosing the convenient one."""

    model_config = _B2

    conflict_id: StableId
    kind: Literal["competing_instruction_limits", "instruction_vs_native_maxlength"]
    limit_ids: list[StableId] = Field(min_length=2)
    description: str
    resolution: Literal["unresolved"] = "unresolved"


class ChoiceOption(ContractModel):
    model_config = _B2

    value: str
    label: ExactText | None = None


class ConditionRecord(ContractModel):
    model_config = _B2

    predicate_text: str | None = Field(default=None, description="Exact source predicate.")
    depends_on_question_id: StableId | None = None
    expected_value: str | None = None
    basis: Literal["declared_fixture_metadata", "structured_definition", "source_text"]
    status: Literal["declared_unverified", "unresolved"]
    locator: SourceLocator


class AttachmentSpec(ContractModel):
    """Only constraints the source states. ``None`` means unknown, never 'unlimited'."""

    model_config = _B2

    accepted_types: list[str] | None = None
    max_size_bytes: int | None = Field(default=None, ge=0)
    max_count: int | None = Field(default=None, ge=0)
    multiple: bool | None = None
    basis: Literal["declared_fixture_metadata", "structured_definition", "native_dom_attribute"]
    evidence: list[ExactText] = Field(default_factory=list)


FindingCode = Literal[
    # intake
    "limit_conflict",
    "native_maxlength_conflict",
    "unknown_limit_unit",
    "unknown_counting_convention",
    "required_status_unknown",
    "condition_unresolved",
    "condition_declared_fixture_metadata",
    "attachment_constraints_unknown",
    "scope_unknown",
    "missing_label",
    "missing_identifier",
    "unsupported_widget",
    "unrecognized_field_preserved",
    "untrusted_authority_claim_ignored",
    "source_claim_unresolved",
    "script_content_inert",
    "external_reference_not_loaded",
    "hidden_content",
    "submission_control_present",
    "no_supported_form_content",
    "pdf_parsing_not_implemented",
    "markdown_not_parsed",
    "stream_specific_limit",
    "element_limit_reached",
    # inspection / mapping
    "mapping_missing",
    "mapping_ambiguous",
    "mapping_type_mismatch",
    "mapping_changed",
    "fingerprint_changed",
    "unknown_form_version",
    "unmapped_field",
    "unexpected_required_field",
    "unresolved_requirement",
    "duplicate_option_value",
    "blocked_request",
    "blocked_navigation",
    "blocked_popup",
    "blocked_download",
    "field_limit_reached",
]


class Finding(ContractModel):
    model_config = _B2

    code: FindingCode
    severity: Literal["blocker", "warning", "info"]
    message: str
    question_id: StableId | None = None
    field_id: str | None = None
    locator: SourceLocator | None = None


class IntakeQuestion(ContractModel):
    model_config = _B2

    question_id: StableId
    question_version: int = Field(default=1, ge=1)
    order: int = Field(ge=0, description="Original order in the imported representation.")
    original_number: str | None = None
    section: ExactText | None = None
    text: ExactText
    instructions: list[ExactText] = Field(default_factory=list)
    scope: Literal["organization", "program", "unknown"]
    answer_kind: Literal["text", "number", "select", "choice", "group", "file", "unsupported"]
    required_status: Literal["required", "optional", "conditional", "unknown"]
    conditions: list[ConditionRecord] = Field(default_factory=list)
    limits: list[IntakeLimit] = Field(default_factory=list)
    limit_conflicts: list[LimitConflictRecord] = Field(default_factory=list)
    choices: list[ChoiceOption] = Field(default_factory=list)
    choice_mode: Literal["single", "multiple"] | None = None
    attachment: AttachmentSpec | None = None
    source_ref: SourceReference
    action_state: Literal["held_unresolved_requirement", "no_blocker_detected_not_approved"]
    hold_reasons: list[str] = Field(default_factory=list)
    unrecognized_fields: dict[str, Any] = Field(
        default_factory=dict,
        description="Original-evidence blob: preserved, never interpreted as policy or code.",
    )


class IntakeCoverage(ContractModel):
    model_config = _B2

    status: Literal[
        "supported_complete", "supported_partial", "unsupported_needs_manual_definition"
    ]
    questions_extracted: int = Field(ge=0)
    controls_seen: int = Field(ge=0)
    unsupported_elements: int = Field(ge=0)
    notes: list[str] = Field(default_factory=list)


class ApplicationIntakeResult(ContractModel):
    """Typed import result. Nonpersistent; an imported definition is not an approval."""

    model_config = _B2

    schema_version: Literal["1"] = SCHEMA_VERSION
    intake_format: Literal["b2-application-intake/1"] = INTAKE_FORMAT
    import_id: StableId
    application_definition_id: StableId | None = None
    opportunity_id: StableId | None = None
    stream_id: StableId | None = None
    cycle_id: StableId | None = None
    title: ExactText | None = None
    is_fixture: bool
    mode_label: str
    authority_status: Literal["imported_provisional_unreviewed"] = "imported_provisional_unreviewed"
    approval_status: Literal["not_approved"] = "not_approved"
    persisted: Literal[False] = False
    original_guide_present: bool = False
    input: InputRepresentation
    provenance: Provenance
    coverage: IntakeCoverage
    questions: list[IntakeQuestion] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    original_evidence: dict[str, Any] = Field(default_factory=dict)
    evidence_excerpt: ExactText | None = Field(
        default=None, description="Read-only text context for unsupported inputs (bounded)."
    )
    evidence_excerpt_truncated: bool = False
    question_set: QuestionSet | None = None
    application_definition: ApplicationDefinition | None = None


# --------------------------------------------------------------------------- inspection


class ObservedOption(ContractModel):
    model_config = _B2

    value: str
    label: str
    disabled: bool = False


class ObservedField(ContractModel):
    """A browser-observed control (read from the DOM by trusted application code)."""

    model_config = _B2

    observed_index: int = Field(ge=0)
    field_key: str
    tag: str
    input_type: str | None = None
    dom_id: str | None = None
    name: str | None = None
    role: str | None = None
    label_text: str | None = None
    legend_text: str | None = None
    described_by_text: list[str] = Field(default_factory=list)
    required: bool
    disabled: bool
    readonly: bool
    max_length: int | None = None
    min: str | None = None
    max: str | None = None
    step: str | None = None
    accept: list[str] | None = None
    multiple: bool = False
    option_value: str | None = Field(default=None, description="radio/checkbox value attribute")
    options: list[ObservedOption] = Field(default_factory=list)
    visible: bool
    supported: bool
    declared_fixture_metadata: dict[str, str] = Field(
        default_factory=dict, description="data-fixture-* attributes: fixture declarations only."
    )


class FieldMappingCheck(ContractModel):
    model_config = _B2

    question_id: StableId
    expected_field_id: StableId
    expected_selector: str
    expected_kind: Literal["single", "group"]
    expected_type: Literal["text", "textarea", "number", "select", "file", "checkbox", "radio"]
    status: Literal["matched", "missing", "ambiguous", "type_mismatch", "unsupported"]
    observed_count: int = Field(ge=0)
    observed_indexes: list[int] = Field(default_factory=list)
    requirement_hold: bool = Field(description="True when the question has unresolved limits.")
    message: str


class NetworkLogEntry(ContractModel):
    model_config = _B2

    method: str
    target: str = Field(description="Sanitized scheme://host:port/path; no query or fragment.")
    resource_type: str
    decision: Literal["allowed", "blocked"]
    reason: str


class BrowserActivity(ContractModel):
    """Observed browser activity. The inspector itself never fills, clicks or uploads."""

    model_config = _B2

    inspector_actions: list[str] = Field(
        default_factory=list, description="Always empty in this task: read-only inspection."
    )
    requests_allowed: int = Field(ge=0)
    requests_blocked: int = Field(ge=0)
    mutation_requests_blocked: int = Field(ge=0)
    fixture_server_mutation_hits: int = Field(
        ge=0, description="Non-GET requests that reached the fixture server (expected 0)."
    )
    popups_blocked: int = Field(ge=0)
    downloads_blocked: int = Field(ge=0)
    navigations_blocked: int = Field(ge=0)
    blocked_log: list[NetworkLogEntry] = Field(default_factory=list)
    blocked_log_truncated: bool = False


class InspectionBudget(ContractModel):
    model_config = _B2

    timeout_ms: int = Field(ge=1)
    max_fields: int = Field(ge=1)
    max_text_chars: int = Field(ge=1)


class FormInspectionResult(ContractModel):
    model_config = _B2

    schema_version: Literal["1"] = SCHEMA_VERSION
    inspection_format: Literal["b2-form-inspection/1"] = INSPECTION_FORMAT
    inspection_id: StableId
    fixture_id: StableId
    form_id: StableId
    origin: str
    is_fixture: Literal[True] = True
    mode_label: str
    question_set_id: StableId
    ready_condition: str
    fingerprint_algorithm: Literal["b2-form-fp/1"] = FINGERPRINT_ALGORITHM
    fingerprint: Sha256Hex
    expected_form_version: int = Field(ge=1)
    expected_fingerprint: Sha256Hex
    client_expected_fingerprint: Sha256Hex | None = None
    fingerprint_status: Literal["matches_expected", "changed"]
    map_status: Literal["valid", "invalid"]
    fields: list[ObservedField]
    fields_truncated: bool = False
    mappings: list[FieldMappingCheck]
    findings: list[Finding] = Field(default_factory=list)
    form_map: FormMap | None = Field(
        default=None, description="Emitted only when every mapping resolved uniquely."
    )
    activity: BrowserActivity
    browser_name: str
    browser_version: str
    budget: InspectionBudget
    persisted: Literal[False] = False
    prefill_permitted: Literal[False] = False


# --------------------------------------------------------------------------- requests


class FixtureIntakeSource(ContractModel):
    model_config = _B2

    mode: Literal["fixture"]
    fixture_id: StableId


class StructuredJsonIntakeSource(ContractModel):
    model_config = _B2

    mode: Literal["structured_json"]
    content: str = Field(description="Exact JSON text; the server hashes its UTF-8 bytes.")
    filename: str | None = Field(default=None, max_length=255)


class HtmlIntakeSource(ContractModel):
    model_config = _B2

    mode: Literal["html"]
    content: str = Field(description="Saved HTML; parsed without executing or fetching.")
    filename: str | None = Field(default=None, max_length=255)


class CaptureIntakeSource(ContractModel):
    model_config = _B2

    mode: Literal["capture"]
    capture_id: StableId
    artifact_id: StableId


IntakeSource = Annotated[
    FixtureIntakeSource | StructuredJsonIntakeSource | HtmlIntakeSource | CaptureIntakeSource,
    Field(discriminator="mode"),
]


class ImportApplicationRequest(ContractModel):
    """Body of POST /api/automation/intake. No org/approval fields exist to send."""

    model_config = _B2

    source: IntakeSource


class InspectFixtureRequest(ContractModel):
    """Body of POST /api/automation/inspect-fixture. A fixture ID, never a URL."""

    model_config = _B2

    fixture_id: StableId
    expected_form_version: int | None = Field(default=None, ge=1)
    expected_fingerprint: Sha256Hex | None = None


class ExportDefinitionRequest(ContractModel):
    """Body of POST /api/automation/export-definition. Server re-derives everything."""

    model_config = _B2

    source: IntakeSource
    inspect_fixture_id: StableId | None = None
    expected_fingerprint: Sha256Hex | None = None


# --------------------------------------------------------------------------- export


class UnresolvedItem(ContractModel):
    model_config = _B2

    question_id: StableId
    kind: Literal[
        "limit_conflict",
        "native_maxlength_conflict",
        "unknown_limit_unit",
        "unknown_counting_convention",
        "required_status_unknown",
        "condition_unresolved",
        "attachment_constraints_unknown",
        "scope_unknown",
    ]
    detail: str


class AutomationHandoffExport(ContractModel):
    """Versioned handoff for C and later prefill work. Not an approved application."""

    model_config = _B2

    schema_version: Literal["1"] = SCHEMA_VERSION
    export_format: Literal["b2-automation-handoff/1"] = EXPORT_FORMAT
    export_id: StableId
    exported_at: datetime
    label: str
    approval_status: Literal["not_approved"] = "not_approved"
    prefill_permitted: Literal[False] = False
    persisted: Literal[False] = False
    is_fixture: bool
    intake: ApplicationIntakeResult
    inspection: FormInspectionResult | None = None
    question_set: QuestionSet | None = None
    application_definition: ApplicationDefinition | None = None
    form_map: FormMap | None = None
    unresolved: list[UnresolvedItem] = Field(default_factory=list)
    consumer_notes: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- availability


class ImportModeInfo(ContractModel):
    model_config = _B2

    mode: Literal["fixture", "structured_json", "html", "capture"]
    status: Literal["available", "fixture_only", "unavailable"]
    max_bytes: int = Field(ge=0)
    detail: str


class FixtureEntry(ContractModel):
    model_config = _B2

    fixture_id: StableId
    kind: Literal["structured_definition", "html_form", "portal", "capture"]
    variant: Literal["representative", "malformed"]
    label: str
    description: str


class AutomationAvailability(ContractModel):
    model_config = _B2

    schema_version: Literal["1"] = SCHEMA_VERSION
    capabilities: list[Capability]
    import_modes: list[ImportModeInfo]
    browser_status: Literal["installed_not_launched", "unavailable", "disabled"]
    browser_detail: str
    fixture_mode: bool
    fixtures: list[FixtureEntry] = Field(default_factory=list)


AUTOMATION_INTAKE_PUBLIC_MODELS: tuple[type[BaseModel], ...] = (
    ApplicationIntakeResult,
    FormInspectionResult,
    AutomationHandoffExport,
    AutomationAvailability,
    ImportApplicationRequest,
    InspectFixtureRequest,
    ExportDefinitionRequest,
)
