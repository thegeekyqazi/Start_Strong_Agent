"""Knowledge/evidence envelopes. Producer: Dev A. Consumers: B, C."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from .common import (
    SCHEMA_VERSION,
    ContractModel,
    DecimalString,
    Provenance,
    SourceReference,
    StableId,
    contract_model_config,
)


class Fact(ContractModel):
    model_config = contract_model_config("draft", "A")

    fact_id: StableId
    metric_id: StableId
    value: DecimalString | None = Field(description="Exact decimal string; null when unknown.")
    raw_value: str | None = None
    unit: str | None = Field(description="Null means the unit is unknown, not dimensionless.")
    scope: str
    population: str | None = None
    reporting_period: str | None = Field(description="e.g. '2025-09/2026-06'; null = unknown.")
    status: Literal["extracted", "needs_review", "verified", "conflicting", "superseded"]
    supporting_refs: list[SourceReference] = Field(min_length=1)
    provenance: Provenance


class EvidenceBundle(ContractModel):
    model_config = contract_model_config("draft", "A")

    schema_version: Literal["1"] = SCHEMA_VERSION
    bundle_id: StableId
    organization_id: StableId
    pack_id: StableId
    pack_version_id: StableId
    access_context: str = Field(
        description="Server-derived access scope label, not a client claim."
    )
    facts: list[Fact]
    allowed_fact_ids: list[StableId]
    coverage_notes: list[str] = Field(default_factory=list)


class KnowledgeSourceVersion(ContractModel):
    """Metadata for exact immutable source bytes; content is never returned as executable HTML."""

    model_config = contract_model_config("draft", "A1")

    title: str
    media_type: str
    size_bytes: int = Field(ge=0)
    source_reference: SourceReference


class KnowledgePassage(ContractModel):
    """Exact inert text at a locator in one source version."""

    model_config = contract_model_config("draft", "A1")

    passage_id: StableId
    source_id: StableId
    source_version_id: StableId
    locator: str
    exact_text: str


class KnowledgeSnapshot(ContractModel):
    model_config = contract_model_config("draft", "A1")

    schema_version: Literal["1"] = SCHEMA_VERSION
    organization_id: StableId
    generated_at: datetime
    source_versions: list[KnowledgeSourceVersion]
    passages: list[KnowledgePassage]
    evidence_bundles: list[EvidenceBundle]
    is_fixture: bool


class KnowledgeAvailability(ContractModel):
    model_config = contract_model_config("draft", "A1")

    schema_version: Literal["1"] = SCHEMA_VERSION
    authenticated: bool
    identity_is_fixture: bool
    environment: str
    storage: Literal["postgresql", "unconfigured"]
    status: Literal["available", "fixture_only", "unavailable"]
    detail: str
