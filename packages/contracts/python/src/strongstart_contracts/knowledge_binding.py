"""Server-built C/A4 projection and browser registration receipts (INT-001)."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import Field

from .answers import DependencyRef
from .common import ContractModel, Sha256Hex, StableId, contract_model_config
from .validation import ValidationDependency


def canonical_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def dependency_union(refs: list[DependencyRef]) -> list[DependencyRef]:
    return [
        DependencyRef(kind=k, ref_id=r, version=v)
        for k, r, v in sorted({(d.kind, d.ref_id, d.version) for d in refs})
    ]


def c_dependency_digest(refs: list[DependencyRef]) -> str:
    return canonical_digest([d.model_dump(mode="json") for d in dependency_union(refs)])


class ApprovedKnowledgeBinding(ContractModel):
    model_config = contract_model_config("draft", "A4")

    mapping_version: Literal["c-a4-pack-root/1"] = "c-a4-pack-root/1"
    organization_id: StableId
    application_context: StableId
    pack_version_id: StableId
    active_revision: int = Field(ge=1)
    c_dependencies_sha256: Sha256Hex
    dependencies: list[ValidationDependency] = Field(min_length=1, max_length=1000)
    projection_sha256: Sha256Hex


def binding_digest(binding: ApprovedKnowledgeBinding) -> str:
    return canonical_digest(binding.model_dump(mode="json", exclude={"projection_sha256"}))


class KnowledgeRegistration(ContractModel):
    model_config = contract_model_config("draft", "A4")

    target_kind: Literal["browser_plan", "browser_grant"]
    target_id: StableId
    target_revision: int = Field(ge=1)
    binding: ApprovedKnowledgeBinding
