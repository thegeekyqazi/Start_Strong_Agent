"""Find Funding feature router (owner: B1).

Registered in strongstart_api.features during INIT-001 so the owner's first task does
not need to edit the shared app entry point. Every operation is explicitly
unavailable until its feature spec is implemented; nothing here fabricates success.
"""

from __future__ import annotations

from typing import NoReturn

from fastapi import APIRouter

from strongstart_contracts import Capability

from ...errors import not_implemented
from ...identity import Identity

FEATURE = "funding"
router = APIRouter(prefix="/api/funding", tags=["funding"])

CAPABILITIES: list[Capability] = [
    Capability(
        feature="funding",
        owner="B1",
        status="not_implemented",
        detail="Discovery/capture/eligibility planned for B1-DISC-001.",
    ),
]


@router.get("/status", response_model=list[Capability])
def status() -> list[Capability]:
    return CAPABILITIES


@router.post("/discovery-jobs", status_code=202, response_model=None)
def placeholder_operation(identity: Identity) -> NoReturn:
    """Protected placeholder: denies without identity, else reports not_implemented."""
    raise not_implemented(FEATURE, "discovery-jobs")
