"""Test-only process factory: explicit approval injection; never an application runtime fallback."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from tests.automation.prefill_support import approve, harness, save_definition


def app_factory() -> Any:
    root = Path(os.environ["STRONGSTART_DEV_B_STORE_DIR"]).parent
    h = harness(root)
    pub = save_definition(h.client)
    a = approve(h, pub, "pf-org-name", "  Approved organization 🦎  ")
    b = approve(h, pub, "pf-summary", "Exact saved summary\nSecond line")
    (root / "prefill-test-ids.json").write_text(
        json.dumps({"question_set_id": pub["question_set_id"], "org": a, "summary": b}),
        encoding="utf-8",
    )
    return h.client.app
