"""Common contract primitives (shared; changes need A/B/C coordination).

Contract status vocabulary used in each model's JSON Schema (``x-contract-status``):
- ``frozen``: envelope/identity fields consumers may rely on for v1.
- ``draft``: structural v1 shape; owners may extend compatibly in their feature specs.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

SCHEMA_VERSION: Final = "1"

# Stable identifiers: lowercase slug or UUID-like; never titles. (Engineering v1.1 s4.1)
StableId = Annotated[
    str,
    StringConstraints(pattern=r"^[a-z0-9][a-z0-9._:-]{0,127}$", min_length=1, max_length=128),
]
# Exact decimal serialized as a string; never a float. (Engineering v1.1 s4.1)
DecimalString = Annotated[str, StringConstraints(pattern=r"^-?(0|[1-9][0-9]*)(\.[0-9]+)?$")]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


def contract_model_config(status: Literal["frozen", "draft"], owner: str) -> ConfigDict:
    return ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=False,
        json_schema_extra={"x-contract-status": status, "x-owner": owner},
    )


class ContractModel(BaseModel):
    model_config = contract_model_config("draft", "shared")


class ProvenanceClass(StrEnum):
    """Where material came from. Simulated/synthetic material must stay labelled."""

    SUPPLIED = "supplied"
    PUBLIC = "public"
    SIMULATED = "simulated"
    ENGINEERING_DERIVED = "engineering_derived"


class Provenance(ContractModel):
    model_config = contract_model_config("draft", "shared")

    provenance_class: ProvenanceClass
    is_simulated: bool
    note: str | None = None


class DateKnowledge(ContractModel):
    """A date that may be unknown. Unknown is explicit; it is never a fabricated value."""

    model_config = contract_model_config("draft", "shared")

    status: Literal["known", "unknown", "not_applicable"]
    value: date | None = None


class SourceReference(ContractModel):
    model_config = contract_model_config("draft", "A")

    source_id: StableId
    source_version_id: StableId
    locator: str | None = Field(default=None, description="Page/section/offset/selector.")
    provenance: Provenance
    captured_at: datetime | None = None
    publication_date: DateKnowledge
    reporting_period: str | None = None
    content_hash: Sha256Hex | None = Field(
        default=None, description="Hash of original bytes when actually computed; else null."
    )
    verification_status: Literal["unverified", "verified", "conflicting"] = "unverified"


class ErrorCode(StrEnum):
    NOT_IMPLEMENTED = "not_implemented"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    UNAUTHENTICATED = "unauthenticated"
    FORBIDDEN = "forbidden"
    VALIDATION_FAILED = "validation_failed"
    VERSION_CONFLICT = "version_conflict"
    STALE_SNAPSHOT = "stale_snapshot"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    INTERNAL_ERROR = "internal_error"


class ErrorEnvelope(ContractModel):
    """Safe structured error. Never include secrets or raw exception text."""

    model_config = contract_model_config("frozen", "shared")

    schema_version: Literal["1"] = SCHEMA_VERSION
    code: ErrorCode
    message: str
    request_id: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
