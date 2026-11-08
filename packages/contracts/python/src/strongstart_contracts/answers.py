"""AnswerSnapshot / ApprovalSnapshot shapes. Producer: Dev C.

Shape only. There is deliberately no ``approved: bool`` field: approval is an
authoritative server-side record referenced by ID and resolved through
``ApprovedAnswerResolver`` (SEC-14 boundary).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from .common import (
    SCHEMA_VERSION,
    ContractModel,
    Provenance,
    Sha256Hex,
    StableId,
    contract_model_config,
)


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
