"""QuestionSet / ApplicationDefinition / FormMap / PrefillAction. Producer: B2.

B2 has no submit/sign capability: PrefillAction cannot express one.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from .common import (
    SCHEMA_VERSION,
    ContractModel,
    Provenance,
    SourceReference,
    StableId,
    contract_model_config,
)


class QuestionLimit(ContractModel):
    model_config = contract_model_config("draft", "B2")

    maximum: int | None = Field(default=None, ge=0)
    unit: Literal["words", "characters", "amount", "unknown"] = Field(
        description="Unknown units stay 'unknown'; never guessed."
    )
    counting_convention: StableId | None = None
    source_refs: list[SourceReference] = Field(min_length=1)


class LimitConflict(ContractModel):
    model_config = contract_model_config("draft", "B2")

    conflict_id: StableId
    description: str
    candidate_limits: list[QuestionLimit] = Field(min_length=2)
    resolution: Literal["unresolved", "staff_resolved"] = "unresolved"


class Question(ContractModel):
    model_config = contract_model_config("draft", "B2")

    question_id: StableId
    question_version: int = Field(ge=1)
    original_text: str
    order: int = Field(ge=0)
    section: str | None = None
    answer_type: Literal["text", "number", "amount", "choice", "attachment", "other"]
    required: bool | None = Field(description="Null when the source does not say.")
    limit: QuestionLimit | None = None
    conflicts: list[LimitConflict] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)
    source_refs: list[SourceReference] = Field(min_length=1)


class QuestionSet(ContractModel):
    model_config = contract_model_config("draft", "B2")

    schema_version: Literal["1"] = SCHEMA_VERSION
    question_set_id: StableId
    opportunity_id: StableId
    questions: list[Question] = Field(min_length=1)
    provenance: Provenance

    @model_validator(mode="after")
    def _unique_question_ids(self) -> QuestionSet:
        ids = [q.question_id for q in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate question_id in QuestionSet")
        return self


class ApplicationDefinition(ContractModel):
    model_config = contract_model_config("draft", "B2")

    schema_version: Literal["1"] = SCHEMA_VERSION
    application_definition_id: StableId
    opportunity_id: StableId
    question_set_id: StableId
    form_id: StableId | None = None
    provenance: Provenance


class FieldMapping(ContractModel):
    model_config = contract_model_config("draft", "B2")

    field_id: StableId
    question_id: StableId
    selector: str
    field_type: Literal["text", "textarea", "number", "select", "file", "checkbox", "radio"]
    max_length: int | None = Field(default=None, ge=0)


class FormMap(ContractModel):
    model_config = contract_model_config("draft", "B2")

    schema_version: Literal["1"] = SCHEMA_VERSION
    form_id: StableId
    form_version: int = Field(ge=1)
    origin: str = Field(pattern=r"^(https?://[^/\s]+|fixture://[a-z0-9.-]+)$")
    fingerprint: str | None = None
    fields: list[FieldMapping] = Field(min_length=1)
    provenance: Provenance

    @model_validator(mode="after")
    def _unique_fields(self) -> FormMap:
        ids = [f.field_id for f in self.fields]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate field_id in FormMap (AUT-01 requires unique mappings)")
        return self


class PrefillAction(ContractModel):
    """Planned field entry. Only fill operations exist; submit/sign is unrepresentable."""

    model_config = contract_model_config("draft", "B2")

    action_id: StableId
    operation: Literal["fill_field", "attach_file"]
    origin: str
    form_id: StableId
    form_version: int = Field(ge=1)
    field_id: StableId
    question_id: StableId
    answer_snapshot_id: StableId | None = None
    attachment_ref: StableId | None = None
    approval_snapshot_id: StableId = Field(
        description="Resolved server-side through ApprovedAnswerResolver; never a client Boolean."
    )
