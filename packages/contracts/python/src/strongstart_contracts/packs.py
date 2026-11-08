"""A4 immutable pack manifests, activation and dependency-currentness contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from .common import (
    SCHEMA_VERSION,
    ContractModel,
    Sha256Hex,
    StableId,
    contract_model_config,
)
from .jobs import ChangeSet
from .validation import ValidationDependency

DependencyTargetKind = Literal[
    "validation",
    "answer",
    "check",
    "approval",
    "export",
    "browser_plan",
    "browser_grant",
    "job",
    "skill",
]


def _request_config() -> ConfigDict:
    return ConfigDict(**contract_model_config("draft", "A4"), strict=True)


class PackFactBinding(ContractModel):
    model_config = contract_model_config("draft", "A4")

    fact_id: StableId
    fact_version: int = Field(ge=1)


class PackPolicyBinding(ContractModel):
    model_config = contract_model_config("draft", "A4")

    policy_id: StableId
    policy_version: int = Field(ge=1)
    content_sha256: Sha256Hex


class PackManifestRequest(ContractModel):
    model_config = _request_config()

    pack_id: StableId
    pack_version_id: StableId
    bundle_id: StableId
    application_context: StableId
    manifest_schema_version: Literal["1"] = SCHEMA_VERSION
    mapping_version: Literal["pack-mapping-v1"]
    parser_version: str = Field(min_length=1, max_length=64)
    locale: Literal["en-CA"]
    access_labels: list[StableId] = Field(min_length=1, max_length=32)
    facts: list[PackFactBinding] = Field(min_length=1, max_length=10_000)
    source_version_ids: list[StableId] = Field(min_length=1, max_length=10_000)
    policies: list[PackPolicyBinding] = Field(default_factory=list, max_length=1_000)
    coverage_notes: list[str] = Field(default_factory=list, max_length=100)
    provenance_class: Literal["supplied", "public", "simulated", "engineering_derived"]
    is_simulated: bool

    @field_validator("access_labels", "source_version_ids")
    @classmethod
    def _unique_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("values must be unique")
        return value

    @field_validator("facts")
    @classmethod
    def _unique_facts(cls, value: list[PackFactBinding]) -> list[PackFactBinding]:
        if len({item.fact_id for item in value}) != len(value):
            raise ValueError("fact IDs must be unique")
        return value

    @field_validator("policies")
    @classmethod
    def _unique_policies(cls, value: list[PackPolicyBinding]) -> list[PackPolicyBinding]:
        if len({item.policy_id for item in value}) != len(value):
            raise ValueError("policy IDs must be unique")
        return value


class PackManifest(ContractModel):
    model_config = contract_model_config("draft", "A4")

    schema_version: Literal["1"] = SCHEMA_VERSION
    organization_id: StableId
    manifest_sha256: Sha256Hex
    created_at: datetime
    request: PackManifestRequest


class ActivatePackRequest(ContractModel):
    model_config = _request_config()

    expected_active_pack_version_id: StableId | None


class DependencyRegistrationRequest(ContractModel):
    model_config = _request_config()

    target_kind: DependencyTargetKind
    target_id: StableId
    expected_revision: int = Field(default=0, ge=0)
    dependencies: list[ValidationDependency] = Field(min_length=1, max_length=1_000)


class DependencyTargetState(ContractModel):
    model_config = contract_model_config("draft", "A4")

    organization_id: StableId
    target_kind: DependencyTargetKind
    target_id: StableId
    revision: int = Field(ge=1)
    state: Literal["current", "stale"]
    stale_change_set_id: StableId | None = None
    dependencies: list[ValidationDependency]
    application_context: StableId | None = None
    pack_version_id: StableId | None = None
    active_revision: int | None = None
    projection_sha256: Sha256Hex | None = None


class ActivePackState(ContractModel):
    model_config = contract_model_config("draft", "A4")

    organization_id: StableId
    application_context: StableId
    pack_version_id: StableId
    revision: int = Field(ge=1)


class InvalidationSummary(ContractModel):
    model_config = contract_model_config("draft", "A4")

    target_kind: DependencyTargetKind
    target_id: StableId
    matched_dependencies: list[ValidationDependency]


class PackActivationReport(ContractModel):
    model_config = contract_model_config("draft", "A4")

    schema_version: Literal["1"] = SCHEMA_VERSION
    active: ActivePackState
    previous_pack_version_id: StableId | None
    change_set: ChangeSet | None
    invalidated: list[InvalidationSummary]
    idempotent: bool
