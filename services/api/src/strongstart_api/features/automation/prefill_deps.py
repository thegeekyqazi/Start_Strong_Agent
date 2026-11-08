"""Dependency providers for approved prefill (B2-AUTO-002). Defaults fail closed.

- ``get_approved_prefill_reader``: C's public factory uses the app-scoped save/approve
  store and workspace. No approvals are seeded; unconfigured C storage fails closed.
- ``get_attachment_evidence_reader``: unavailable; checklist shows needs review.
- ``get_prefill_currentness``: knowledge-owned PostgreSQL facade when configured.
  Only successfully registered managed bindings earn the A4 label; the default
  synthetic evidence is unmanaged. A missing facade never downgrades managed content.
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
    AttachmentEvidenceReader,
    UnconfiguredAttachmentEvidenceReader,
)

from ..applications.public import get_approved_prefill_reader as get_approved_prefill_reader
from ..knowledge.public import get_prefill_currentness as get_prefill_currentness

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


def get_attachment_evidence_reader() -> AttachmentEvidenceReader:
    return UnconfiguredAttachmentEvidenceReader()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def get_prefill_clock() -> Clock:
    return _utc_now


def get_runtime_epoch() -> str:
    return RUNTIME_EPOCH


def get_prefill_browser_config() -> PrefillBrowserConfig:
    return PrefillBrowserConfig()
