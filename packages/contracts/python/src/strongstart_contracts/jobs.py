"""JobContext / JobResult and ChangeSet. Schema/protocol only: no durable worker exists yet."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from .common import (
    SCHEMA_VERSION,
    ContractModel,
    ErrorEnvelope,
    StableId,
    contract_model_config,
)

JobState = Literal[
    "queued", "running", "paused", "succeeded", "failed", "canceled", "outcome_unknown"
]


class JobBudget(ContractModel):
    model_config = contract_model_config("draft", "shared")

    max_attempts: int = Field(ge=1)
    timeout_seconds: int = Field(ge=1)
    max_tool_calls: int | None = Field(default=None, ge=0)


class JobContext(ContractModel):
    model_config = contract_model_config("draft", "shared")

    schema_version: Literal["1"] = SCHEMA_VERSION
    job_id: StableId
    task_id: StableId
    actor_id: StableId = Field(description="Server-derived actor; never taken from tool text.")
    organization_id: StableId
    operation: StableId
    state: JobState
    attempt: int = Field(ge=0)
    budget: JobBudget
    version_snapshot: dict[str, str] = Field(default_factory=dict)


class JobResult(ContractModel):
    model_config = contract_model_config("draft", "shared")

    schema_version: Literal["1"] = SCHEMA_VERSION
    job_id: StableId
    state: JobState
    completeness: Literal["complete", "partial", "none"]
    output: dict[str, Any] | None = None
    error: ErrorEnvelope | None = None


class ChangedVersion(ContractModel):
    model_config = contract_model_config("draft", "A")

    kind: Literal["source", "fact", "pack", "policy", "requirement_set", "question"]
    ref_id: StableId
    previous_version: str | None
    new_version: str


class ChangeSet(ContractModel):
    model_config = contract_model_config("draft", "A")

    schema_version: Literal["1"] = SCHEMA_VERSION
    change_set_id: StableId
    changes: list[ChangedVersion] = Field(min_length=1)
    affected_refs: list[StableId] = Field(
        default_factory=list, description="Dependents consumers must stale in their real state."
    )
