"""SEC-10 audit events: complete records with configured secrets redacted (C3 spec s2).

Every event carries actor, action, object, version, decision and time. Detail values pass
through ``redact`` (configured provider keys plus known key shapes) before they are
stored, and the audit route is identity- and organization-scoped (restricted trace
access). A clean scan is not proof that no secret exists.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from strongstart_contracts.answers import AuditEvent

from ...config import Settings
from .store import AnswerStore

KEY_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_\-]{35}"),
    re.compile(r"\bsk-[A-Za-z0-9]{32,}"),
    re.compile(r"\btvly-[0-9A-Za-z]{20,}"),
    re.compile(r"\bfc-[0-9a-f]{32}\b"),
)
REDACTED = "[redacted]"
REQUIRED_FIELDS = ("actor_id", "action", "object_type", "object_id", "object_version", "decision")


def _secrets(settings: Settings) -> list[str]:
    out = []
    for key in (settings.gemini_api_key, settings.tavily_api_key, settings.firecrawl_api_key):
        value = key.get_secret_value() if key is not None else ""
        if value:
            out.append(value)
    return out


def redact(value: str, settings: Settings) -> str:
    for secret in _secrets(settings):
        value = value.replace(secret, REDACTED)
    for pattern in KEY_PATTERNS:
        value = pattern.sub(REDACTED, value)
    return value


def is_complete(event: AuditEvent) -> bool:
    """SEC-10 completeness: every required field is present and non-empty."""
    return all(str(getattr(event, name, "")).strip() for name in REQUIRED_FIELDS)


def record(
    store: AnswerStore,
    settings: Settings,
    *,
    organization_id: str,
    actor_id: str,
    action: str,
    object_type: str,
    object_id: str,
    object_version: str,
    decision: str,
    details: dict[str, str] | None = None,
) -> AuditEvent:
    event = AuditEvent.model_validate(
        {
            "event_id": "ev-" + uuid.uuid4().hex[:24],
            "actor_id": actor_id,
            "action": action,
            "object_type": object_type,
            "object_id": object_id,
            "object_version": object_version,
            "decision": decision,
            "at": datetime.now(UTC),
            "details": {k: redact(v, settings) for k, v in (details or {}).items()},
        }
    )
    if not is_complete(event):
        raise ValueError("incomplete audit event")  # fail closed: no silent partial record
    store.add_audit(organization_id, event)
    return event
