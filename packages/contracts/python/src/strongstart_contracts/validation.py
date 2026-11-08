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

    rule_id: SourceRuleId
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
