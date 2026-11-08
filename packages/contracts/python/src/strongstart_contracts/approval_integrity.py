"""C approval snapshot algorithm shared with independent consumers (INT-001)."""

from __future__ import annotations

import hashlib
import json

from .answers import DependencyRef

COUNTER_IDS = ("code-points-v1", "utf16-v1", "words-v1")
EVALUATION_TIME_POLICY = "live-at-action"


def approval_snapshot_sha256(
    content_sha256: str, organization_id: str, refs: list[DependencyRef]
) -> str:
    data = {
        "content_sha256": content_sha256,
        "organization_id": organization_id,
        "dependencies": sorted((r.kind, r.ref_id, r.version) for r in refs),
        "counters": list(COUNTER_IDS),
        "evaluation_time_policy": EVALUATION_TIME_POLICY,
    }
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
