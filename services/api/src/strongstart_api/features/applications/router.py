"""Applications, review and skills feature router (owner: C).

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

FEATURE = "applications"
router = APIRouter(prefix="/api/applications", tags=["applications"])

CAPABILITIES: list[Capability] = [
    Capability(
        feature="applications",
        owner="C",
        status="not_implemented",
        detail="Answer planning/drafting planned (Dev C specs).",
    ),
    Capability(
        feature="review",
        owner="C",
        status="not_implemented",
        detail="Review and exact-version approval planned (Dev C specs).",
    ),
    Capability(
        feature="skills",
        owner="C",
        status="not_implemented",
        detail="Practice-skill generation planned (Dev C specs).",
    ),
]


@router.get("/status", response_model=list[Capability])
def status() -> list[Capability]:
    return CAPABILITIES


@router.post("/draft-jobs", status_code=202, response_model=None)
def placeholder_operation(identity: Identity) -> NoReturn:
    """Protected placeholder: denies without identity, else reports not_implemented."""
    raise not_implemented(FEATURE, "draft-jobs")
