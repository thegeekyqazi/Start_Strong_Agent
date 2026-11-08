"""Dependency providers for approved prefill (B2-AUTO-002). Defaults fail closed.

- ``get_approved_prefill_reader``: no C approved-content reader exists on ``main`` yet
  (request: ``docs/handoffs/dev-b/b2-auto-002-approved-content-request-r1.md``), so the
  default is unconfigured (503). Tests inject an explicit, labelled test provider with
  ``app.dependency_overrides``; runtime code contains no seeded approvals.
- ``get_attachment_evidence_reader``: no authorized artifact reader; the checklist shows
  "needs review / unavailable".
- ``get_prefill_currentness``: no in-process A4 consumer factory; ``None`` means the
  A4 adapter is not integrated (reported on every plan).
- ``get_prefill_clock``: injectable server clock.
- ``RUNTIME_EPOCH``: random per API process. Plans and grants bind to it because C3's
  approval store is process-local; after a restart, execution fails before the browser.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from strongstart_contracts.automation_prefill import (
    EXECUTION_TIMEOUT_MS,
    OPERATION_TIMEOUT_MS,
    ApprovedPrefillReader,
    AttachmentEvidenceReader,
    PrefillDependencyCurrentness,
    UnconfiguredApprovedPrefillReader,
    UnconfiguredAttachmentEvidenceReader,
)

Clock = Callable[[], datetime]
RUNTIME_EPOCH = "epoch-" + secrets.token_hex(12)


@dataclass(frozen=True)
class PrefillBrowserConfig:
    execution_timeout_ms: int = EXECUTION_TIMEOUT_MS
    operation_timeout_ms: int = OPERATION_TIMEOUT_MS
    reveal_timeout_ms: int = 2_000
    max_fields: int = 300
    max_text_chars: int = 2_000
    max_options: int = 200
    executable_path: str | None = None  # tests point this at a missing binary


def get_approved_prefill_reader() -> ApprovedPrefillReader:
    return UnconfiguredApprovedPrefillReader()


def get_attachment_evidence_reader() -> AttachmentEvidenceReader:
    return UnconfiguredAttachmentEvidenceReader()


def get_prefill_currentness() -> PrefillDependencyCurrentness | None:
    return None


def _utc_now() -> datetime:
    return datetime.now(UTC)


def get_prefill_clock() -> Clock:
    return _utc_now


def get_runtime_epoch() -> str:
    return RUNTIME_EPOCH


def get_prefill_browser_config() -> PrefillBrowserConfig:
    return PrefillBrowserConfig()
