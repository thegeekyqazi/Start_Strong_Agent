"""DATA-31: durable C, actual restarted API, NEW B plan, real Chromium entry/read-back."""

from __future__ import annotations

from typing import cast

import httpx
import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright

from strongstart_api.seed import seed_demo
from tests.browser.test_funding_e2e import FIXTURE_ENV, stack
from tests.conftest import BUNDLE_PATH
from tests.integration.support import decide, prepare, publish, save

pytestmark = [pytest.mark.db, pytest.mark.browser]


def test_durable_approval_new_plan_after_api_restart_chromium_readback(data_db, tmp_path):
    data_db.migrate()
    seed_demo(data_db.engine, BUNDLE_PATH)
    env = {
        **FIXTURE_ENV,
        "STRONGSTART_ANSWER_STORE_BACKEND": "postgres",
        "STRONGSTART_DATABASE_URL": data_db.url,
        "STRONGSTART_DEV_B_STORE_DIR": str(tmp_path / "b"),
    }
    with stack(tmp_path, **env) as base, httpx.Client(base_url=base) as raw:
        c = cast(TestClient, raw)
        pub = publish(c)
        v = save(c, pub, "pf-summary", "Synthetic historic: {{fact:demo-fact-children-served}}.")
        approval = decide(c, v)
        old = prepare(c, pub, {"pf-summary": approval}).json()
        assert len(old["actions"]) == 1
    # First real API is stopped. B files are explicitly retained; C is in PostgreSQL.
    with stack(tmp_path, **env) as base, httpx.Client(base_url=base, timeout=30) as raw:
        c = cast(TestClient, raw)
        old_view = c.get(f"/api/automation/prefill-plans/{old['plan_id']}").json()
        assert old_view["availability"] == "runtime_epoch_changed"
        fresh = prepare(c, pub, {"pf-summary": approval}).json()
        assert fresh["actions"][0]["producer_epoch"] == old["actions"][0]["producer_epoch"]
        assert fresh["runtime_epoch"] != old["runtime_epoch"]
        executed = c.post(
            f"/api/automation/prefill-plans/{fresh['plan_id']}/execute",
            json={
                "expected_plan_sha256": fresh["plan_sha256"],
                "idempotency_key": "data-restart-real-browser",
            },
        )
        assert executed.status_code == 201, executed.text
        run = executed.json()["run"]["run"]
        assert run["outcome"] == "selected_fields_verified"
        assert run["final_reread"] == "all_match"
        assert run["fields"][0]["actual_value"] == v["rendered"]["text"]
        assert run["fields"][0]["state"] == "entered_verified"
        assert run["activity"]["blocked_log"] == []
        assert run["activity"]["fixture_server_mutation_hits"] == 0
        # Reopen Review in a staff Chromium page and verify durable/simulation labels coexist.
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(base + "/#/review")
                page.get_by_label("Questions from", exact=True).select_option(
                    pub["question_set_id"]
                )
                page.get_by_label("Question", exact=True).select_option(v["question_id"])
                page.get_by_text("Durable PostgreSQL store", exact=False).wait_for()
                page.get_by_text("SYNTHETIC", exact=False).first.wait_for()
            finally:
                browser.close()
