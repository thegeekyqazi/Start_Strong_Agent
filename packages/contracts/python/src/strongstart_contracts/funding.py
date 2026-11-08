"""Opportunity / RequirementSet envelopes. Producer: B1 (Funding Discovery).

A discovered link is not eligibility proof; unknown conditions stay ``unknown``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import (
    SCHEMA_VERSION,
    ContractModel,
    DateKnowledge,
    Provenance,
    SourceReference,
    StableId,
    contract_model_config,
)


class RequirementCondition(ContractModel):
    model_config = contract_model_config("draft", "B1")

    condition_id: StableId
    kind: Literal["eligibility", "deadline", "limit", "stage", "other"]
    description: str
    evaluation: Literal["met", "not_met", "unknown", "not_applicable"] = Field(
        description="Missing inputs must remain 'unknown' (ELG-01); this is not a pass."
    )
    missing_inputs: list[str] = Field(default_factory=list)
    source_refs: list[SourceReference] = Field(min_length=1)


class RequirementSet(ContractModel):
    model_config = contract_model_config("draft", "B1")

    requirement_set_id: StableId
    requirement_version: int = Field(ge=1)
    opportunity_id: StableId
    conditions: list[RequirementCondition]
    uncertainty_notes: list[str] = Field(default_factory=list)


class Opportunity(ContractModel):
    model_config = contract_model_config("draft", "B1")

    schema_version: Literal["1"] = SCHEMA_VERSION
    opportunity_id: StableId
    funder_id: StableId
    stream_id: StableId
    cycle_id: StableId
    stage_id: StableId | None = None
    title: str
    deadline: DateKnowledge
    source_refs: list[SourceReference] = Field(min_length=1)
    requirement_set_ids: list[StableId] = Field(default_factory=list)
    provenance: Provenance
