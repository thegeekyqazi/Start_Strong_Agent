"""Health and capability reports consumed by the web shell. Shared host contract."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import SCHEMA_VERSION, ContractModel, contract_model_config

CapabilityStatus = Literal["available", "fixture_only", "not_implemented", "unavailable"]


class LivenessReport(ContractModel):
    model_config = contract_model_config("frozen", "shared")

    status: Literal["alive"]
    service: str


class ReadinessCheck(ContractModel):
    model_config = contract_model_config("frozen", "shared")

    name: str
    ok: bool
    detail: str


class ReadinessReport(ContractModel):
    model_config = contract_model_config("frozen", "shared")

    status: Literal["ready", "not_ready"]
    checks: list[ReadinessCheck]


class Capability(ContractModel):
    model_config = contract_model_config("frozen", "shared")

    feature: str
    owner: str
    status: CapabilityStatus
    detail: str


class CapabilityReport(ContractModel):
    model_config = contract_model_config("frozen", "shared")

    schema_version: Literal["1"] = SCHEMA_VERSION
    environment: str
    auth_mode: Literal["none", "fixture"]
    fixture_mode: bool = Field(description="True only when the local fixture identity is enabled.")
    capabilities: list[Capability]


class SessionIdentity(ContractModel):
    """Server-controlled identity. ``is_fixture`` must be shown conspicuously by clients."""

    model_config = contract_model_config("frozen", "shared")

    actor_id: str
    organization_id: str
    roles: list[str]
    is_fixture: bool
    label: str
