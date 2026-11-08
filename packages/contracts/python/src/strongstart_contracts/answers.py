"""AnswerSnapshot / ApprovalSnapshot shapes. Producer: Dev C.

Shape only. There is deliberately no ``approved: bool`` field: approval is an
authoritative server-side record referenced by ID and resolved through
``ApprovedAnswerResolver`` (SEC-14 boundary).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field

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


class DraftRequest(ContractModel):
    """Client request for a draft. Extra fields (e.g. ``approved``) are rejected."""

    model_config = contract_model_config("draft", "C")

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


DraftSegment = Annotated[TextSegment | FactSlotSegment, Field(discriminator="kind")]


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
)
