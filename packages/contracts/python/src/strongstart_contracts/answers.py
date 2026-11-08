"""AnswerSnapshot / ApprovalSnapshot shapes. Producer: Dev C.

Shape only. There is deliberately no ``approved: bool`` field: approval is an
authoritative server-side record referenced by ID and resolved through
``ApprovedAnswerResolver`` (SEC-14 boundary).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .automation import QuestionSet
from .common import (
    SCHEMA_VERSION,
    ContractModel,
    Provenance,
    Sha256Hex,
    StableId,
    contract_model_config,
)
from .evidence import EvidenceBundle
from .validation import ValidationResult


class DependencyRef(ContractModel):
    model_config = contract_model_config("draft", "C")

    kind: Literal[
        "fact", "source_version", "requirement_set", "pack", "policy", "question", "rule_set"
    ]
    ref_id: StableId
    version: str


class AnswerSnapshot(ContractModel):
    model_config = contract_model_config("draft", "C")

    schema_version: Literal["1"] = SCHEMA_VERSION
    answer_snapshot_id: StableId
    answer_id: StableId
    answer_version: int = Field(ge=1)
    question_id: StableId
    question_version: int = Field(ge=1)
    content: str
    content_sha256: Sha256Hex
    dependencies: list[DependencyRef] = Field(default_factory=list)
    provenance: Provenance


class ApprovalSnapshot(ContractModel):
    model_config = contract_model_config("draft", "C")

    schema_version: Literal["1"] = SCHEMA_VERSION
    approval_snapshot_id: StableId
    answer_snapshot_id: StableId
    content_sha256: Sha256Hex
    dependencies: list[DependencyRef]
    approval_record_ref: StableId = Field(
        description="Reference to the authoritative server-side approval record."
    )
    decided_at: datetime | None = None
    provenance: Provenance


# --- C1 (docs/specs/C1-shell-and-adapter.md rev 1.0, s3) -------------------------------
# Draft proposals are proposals by type: no model provides, and no field here can carry,
# an approval, status or state (SEC-14). Fact values are never inlined by the model; the
# template references facts as ``{{fact:ID}}`` slots resolved by the server (s8.2).


def _strict_request_config() -> ConfigDict:
    """Request bodies: extra fields forbidden and no type coercion ("1" is not 1)."""
    return ConfigDict(**contract_model_config("draft", "C"), strict=True)


class DraftRequest(ContractModel):
    """Client request for a draft. Strict: extra fields (e.g. ``approved``) and coerced
    types (e.g. ``"1"`` for a version) are rejected (C2 rev 1.1 owner priority)."""

    model_config = _strict_request_config()

    question_version: int = Field(ge=1)
    evidence_bundle_id: StableId


class TextSegment(ContractModel):
    model_config = contract_model_config("draft", "C")

    kind: Literal["text"]
    text: str


class FactSlotSegment(ContractModel):
    model_config = contract_model_config("draft", "C")

    kind: Literal["fact_slot"]
    fact_id: StableId


class UnsupportedSegment(ContractModel):
    """Explicit APP-03 marker: the writer says a claim has no supporting evidence."""

    model_config = contract_model_config("draft", "C")

    kind: Literal["unsupported"]
    reason: StableId


DraftSegment = Annotated[
    TextSegment | FactSlotSegment | UnsupportedSegment, Field(discriminator="kind")
]


# --- C2 (docs/specs/C2-draft-claims.md rev 1.1, s3) ------------------------------------
# Server-rendered claim bindings and deterministic findings. Stateless: a report binds to
# the exact submitted text hash; nothing here persists, approves or carries a status.


class ClaimBinding(ContractModel):
    """A fact value the server rendered into the answer, with its exact text span (s8.2)."""

    model_config = contract_model_config("draft", "C")

    fact_id: StableId
    fact_version: int = Field(default=1, ge=1)
    pack_version_id: StableId = Field(
        description="Binding key until Fact gains a version (request to Dev A)."
    )
    span_start: int = Field(ge=0, description="Code-point offset in RenderedAnswer.text.")
    span_end: int = Field(ge=0)
    rendered_text: str


class UnsupportedMarker(ContractModel):
    model_config = contract_model_config("draft", "C")

    reason: StableId
    span_start: int = Field(ge=0)
    span_end: int = Field(ge=0)


class RenderedAnswer(ContractModel):
    """The answer as a funder would read it: slot tokens replaced by server-rendered facts."""

    model_config = contract_model_config("draft", "C")

    text: str
    text_sha256: Sha256Hex
    bindings: list[ClaimBinding]
    unsupported_markers: list[UnsupportedMarker]


class AnswerFinding(ContractModel):
    """Plain-language wrapper around a shared ValidationResult (s8.3, s9.1, s18)."""

    model_config = contract_model_config("draft", "C")

    result: ValidationResult
    message: str
    next_action: str | None = None
    span_start: int | None = Field(default=None, ge=0)
    span_end: int | None = Field(default=None, ge=0)
    affected_text: str | None = None


class CheckRequest(ContractModel):
    model_config = _strict_request_config()

    question_version: int = Field(ge=1)
    evidence_bundle_id: StableId
    text: str = Field(max_length=20_000, description="Editor text; may contain slot tokens.")
    mode: Literal["working", "reviewed"] = "working"


class CheckReport(ContractModel):
    """Deterministic findings for one exact text. Not a review or approval."""

    model_config = contract_model_config("draft", "C")

    schema_version: Literal["1"] = SCHEMA_VERSION
    question_id: StableId
    question_version: int = Field(ge=1)
    evidence_bundle_id: StableId
    mode: Literal["working", "reviewed"]
    submitted_text_sha256: Sha256Hex
    rendered: RenderedAnswer
    findings: list[AnswerFinding]


class PlanRequest(ContractModel):
    model_config = _strict_request_config()

    evidence_bundle_id: StableId


class PlanItem(ContractModel):
    model_config = contract_model_config("draft", "C")

    question_id: StableId
    question_version: int = Field(ge=1)
    evidence_fact_ids: list[StableId]
    missing_inputs: list[str]
    repeated_with: list[StableId]


class AnswerPlan(ContractModel):
    """Planner proposal (s7): evidence per question and missing inputs. Nothing invented."""

    model_config = contract_model_config("draft", "C")

    schema_version: Literal["1"] = SCHEMA_VERSION
    plan_id: StableId
    question_set_id: StableId
    evidence_bundle_id: StableId
    items: list[PlanItem]
    planner: ModelRunInfo
    provenance: Provenance


class ModelRunInfo(ContractModel):
    """Which adapter actually produced the proposal (s17: record provider/model)."""

    model_config = contract_model_config("draft", "C")

    adapter: Literal["fake", "gemini"]
    model: str
    is_fixture: bool


class DraftProposal(ContractModel):
    """Validated model proposal for one question. Not an answer version or approval."""

    model_config = contract_model_config("draft", "C")

    schema_version: Literal["1"] = SCHEMA_VERSION
    proposal_id: StableId
    question_id: StableId
    question_version: int = Field(ge=1)
    evidence_bundle_id: StableId
    pack_version_id: StableId
    template_text: str = Field(description="Proposal text with {{fact:ID}} slot tokens.")
    template_sha256: Sha256Hex
    segments: list[DraftSegment]
    fact_ids: list[StableId]
    uncertainties: list[str]
    provider: ModelRunInfo
    provenance: Provenance
    check: CheckReport | None = Field(
        default=None, description="Working-mode findings for the rendered proposal (C2)."
    )


class ApplicationWorkspace(ContractModel):
    """Questions and evidence for one application, scoped to the server identity."""

    model_config = contract_model_config("draft", "C")

    schema_version: Literal["1"] = SCHEMA_VERSION
    application_definition_id: StableId
    question_set: QuestionSet
    evidence_bundle: EvidenceBundle
    is_fixture: bool
    data_label: str


ANSWERS_PUBLIC_MODELS: tuple[type[BaseModel], ...] = (
    DraftRequest,
    DraftProposal,
    ApplicationWorkspace,
    CheckRequest,
    CheckReport,
    PlanRequest,
    AnswerPlan,
)
