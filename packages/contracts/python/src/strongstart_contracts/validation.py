"""ValidationResult envelope. Shared; rule implementations belong to their catalog owners."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator

from .common import (
    SCHEMA_VERSION,
    ContractModel,
    Sha256Hex,
    SourceReference,
    StableId,
    contract_model_config,
)

ValidationOutcome = Literal["pass", "fail", "needs_review", "not_applicable"]
SourceRuleId = Literal[
    "SRC-01",
    "SRC-02",
    "SRC-03",
    "SRC-04",
    "SRC-05",
    "SRC-06",
    "SRC-07",
    "SRC-08",
    "SRC-09",
    "SRC-10",
]
NumericRuleId = Literal[
    "NUM-01",
    "NUM-02",
    "NUM-03",
    "NUM-04",
    "NUM-05",
    "NUM-06",
    "NUM-07",
    "NUM-08",
    "NUM-09",
    "NUM-10",
    "NUM-11",
    "NUM-12",
]


class ValidationResult(ContractModel):
    model_config = contract_model_config("draft", "shared")

    schema_version: Literal["1"] = SCHEMA_VERSION
    rule_id: str = Field(pattern=r"^[A-Z]{3}-[0-9]{2}$")
    rule_version: str
    outcome: ValidationOutcome
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected: Any = None
    observed: Any = None
    reasons: list[str] = Field(default_factory=list)
    evidence: list[SourceReference] = Field(default_factory=list)
    reason_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,63}$")
    next_action: str | None = None
    evaluator_id: str | None = None


class ValidationDependency(ContractModel):
    """Minimal exact dependency identity; never embeds private evidence content."""

    model_config = contract_model_config("draft", "A3")

    kind: Literal[
        "subject",
        "source_version",
        "artifact_hash",
        "passage_locator",
        "normalization_policy",
        "permission_snapshot",
        "fact_version",
        "pack_version",
        "rounding_policy",
        "formula",
        "project_input",
        "policy",
    ]
    ref_id: StableId
    version: str
    content_hash: Sha256Hex | None = None


class SourceValidationRequest(ContractModel):
    """Strict source-check request; identity and organization are server-derived."""

    model_config = ConfigDict(**contract_model_config("draft", "A3"), strict=True)

    source_version_id: StableId
    rule_ids: list[SourceRuleId] = Field(default_factory=list, max_length=10)
    locator: str | None = Field(default=None, min_length=1, max_length=256)
    claimed_quote: str | None = Field(default=None, min_length=1, max_length=20_000)

    @field_validator("rule_ids")
    @classmethod
    def _unique_rules(cls, value: list[SourceRuleId]) -> list[SourceRuleId]:
        if len(value) != len(set(value)):
            raise ValueError("rule_ids must be unique")
        return value


class RuleCapability(ContractModel):
    model_config = contract_model_config("draft", "A3")

    rule_id: SourceRuleId | NumericRuleId
    rule_version: str
    priority: Literal["P0", "P1"]
    state: Literal["planned", "implemented", "verified", "unavailable"]


class SourceValidationReport(ContractModel):
    model_config = contract_model_config("draft", "A3")

    schema_version: Literal["1"] = SCHEMA_VERSION
    evaluation_id: StableId
    organization_id: StableId
    source_version_id: StableId
    input_sha256: Sha256Hex
    evaluator_build: str
    frozen_time: datetime
    results: list[ValidationResult]
    dependencies: list[ValidationDependency]


class NumericValidationRequest(ContractModel):
    """Numeric claim/calculation request; referenced facts and inputs are server-resolved."""

    model_config = ConfigDict(**contract_model_config("draft", "A3"), strict=True)

    pack_version_id: StableId
    fact_id: StableId
    rule_ids: list[NumericRuleId] = Field(default_factory=list, max_length=12)
    raw_value: str | None = Field(default=None, max_length=256)
    locale: Literal["en-CA", "en-US"] | None = None
    claimed_value: str | None = None
    claimed_unit: str | None = None
    claimed_currency: str | None = None
    claimed_scale: str | None = None
    expected_metric_id: StableId | None = None
    claimed_scope: str | None = None
    claimed_program: str | None = None
    claimed_geography: str | None = None
    claimed_population: str | None = None
    claimed_reporting_period: str | None = None
    rounding_places: int = Field(default=0, ge=0, le=12)
    line_items: list[str] = Field(default_factory=list, max_length=200)
    declared_total: str | None = None
    numerator_fact_id: StableId | None = None
    denominator_fact_id: StableId | None = None
    change_operation: Literal["percentage_points", "relative_percent"] | None = None
    before_value: str | None = None
    after_value: str | None = None
    aggregate_fact_ids: list[StableId] = Field(default_factory=list, max_length=100)
    disjoint_scope_declaration: bool | None = None
    project_input_id: StableId | None = None

    @field_validator("rule_ids")
    @classmethod
    def _unique_numeric_rules(cls, value: list[NumericRuleId]) -> list[NumericRuleId]:
        if len(value) != len(set(value)):
            raise ValueError("rule_ids must be unique")
        return value


class NumericValidationReport(ContractModel):
    model_config = contract_model_config("draft", "A3")

    schema_version: Literal["1"] = SCHEMA_VERSION
    evaluation_id: StableId
    organization_id: StableId
    pack_version_id: StableId
    fact_id: StableId
    fact_version: int = Field(ge=1)
    input_sha256: Sha256Hex
    evaluator_build: str
    frozen_time: datetime
    results: list[ValidationResult]
    dependencies: list[ValidationDependency]
