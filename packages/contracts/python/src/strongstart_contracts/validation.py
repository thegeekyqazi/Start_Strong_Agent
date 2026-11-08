"""ValidationResult envelope. Shared; rule implementations belong to their catalog owners."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .common import (
    SCHEMA_VERSION,
    ContractModel,
    SourceReference,
    contract_model_config,
)


class ValidationResult(ContractModel):
    model_config = contract_model_config("draft", "shared")

    schema_version: Literal["1"] = SCHEMA_VERSION
    rule_id: str = Field(pattern=r"^[A-Z]{3}-[0-9]{2}$")
    rule_version: str
    outcome: Literal["pass", "fail", "needs_review", "not_applicable"]
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected: Any = None
    observed: Any = None
    reasons: list[str] = Field(default_factory=list)
    evidence: list[SourceReference] = Field(default_factory=list)
