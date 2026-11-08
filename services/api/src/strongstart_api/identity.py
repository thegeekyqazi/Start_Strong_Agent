"""Server-controlled identity (SEC-01 / SEC-14 bootstrap boundary; NOT production authentication).

Identity is derived only from server configuration. Request headers, query strings
and bodies (org_id, approved flags, X-Org-Id, ...) are never consulted.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from strongstart_contracts import ErrorCode, SessionIdentity

from .config import Settings, get_settings
from .errors import ApiError

FIXTURE_IDENTITY = SessionIdentity(
    actor_id="demo-staff",
    organization_id="demo-org",
    roles=["fixture-staff"],
    is_fixture=True,
    label="LOCAL FIXTURE IDENTITY - not authentication",
)


def require_identity(settings: Annotated[Settings, Depends(get_settings)]) -> SessionIdentity:
    if settings.auth_mode == "fixture":
        if settings.environment == "production":  # defence in depth; Settings also rejects it
            raise ApiError(403, ErrorCode.FORBIDDEN, "fixture identity is disabled in production")
        return FIXTURE_IDENTITY
    raise ApiError(
        401,
        ErrorCode.UNAUTHENTICATED,
        "no identity provider is configured; protected operations are denied",
        {"auth_mode": settings.auth_mode},
    )


Identity = Annotated[SessionIdentity, Depends(require_identity)]
