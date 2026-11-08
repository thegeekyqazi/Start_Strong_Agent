"""INT-23/24/25/30/32/33: normal runtime, actual C save/approve, UI and real Chromium."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import sync_playwright

from tests.browser.test_funding_e2e import FIXTURE_ENV, stack

pytestmark = pytest.mark.browser


def test_normal_runtime_c_review_to_two_field_chromium_receipt(tmp_path: Path) -> None:
    with (
        stack(tmp_path, **FIXTURE_ENV, STRONGSTART_DEV_B_STORE_DIR=str(tmp_path / "dev-b")) as base,
        sync_playwright() as p,
    ):
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            errors: list[str] = []
            external: list[str] = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on(
                "request", lambda r: external.append(r.url) if not r.url.startswith(base) else None
            )

            def post(path: str, body: dict[str, Any]) -> dict[str, Any]:
                response = page.request.post(base + path, data=body)
                assert response.status in (200, 201), response.text()
                result: dict[str, Any] = response.json()
                return result

            source = {"mode": "fixture", "fixture_id": "rep-prefill-definition-v1"}
            imported = post("/api/automation/intake", {"source": source})
            pub = post(
                "/api/automation/definitions",
                {
                    "source": source,
                    "expected_input_sha256": imported["input"]["sha256"],
                    "idempotency_key": "int-browser-publish",
                },
            )["publication"]
            ids = {m["original_question_id"]: m["published_question_id"] for m in pub["id_mapping"]}
            name = "Riverside Youth Collective"
            summary = "Historical synthetic metric: {{fact:demo-fact-children-served}}."
            versions = {}
            for original, text in [("pf-org-name", name), ("pf-summary", summary)]:
                versions[original] = post(
                    "/api/applications/answers/versions",
                    {
                        "question_id": ids[original],
                        "question_version": 1,
                        "question_set_id": pub["question_set_id"],
                        "evidence_bundle_id": "demo-evidence-a-v1",
                        "text": text,
                        "expected_answer_version": None,
                    },
                )
            page.goto(base + "/#/review")
            page.get_by_label("Questions from", exact=True).select_option(pub["question_set_id"])
            for original in ("pf-org-name", "pf-summary"):
                page.get_by_label("Question", exact=True).select_option(ids[original])
                approve = page.get_by_role(
                    "button", name=re.compile(r"^Approve this exact version")
                )
                approve.wait_for()
                ack = page.get_by_label(re.compile(r"I have read all"))
                if ack.count():
                    ack.check()
                approve.click()
                page.get_by_text("Approved this exact version.", exact=True).wait_for()
                page.get_by_role("button", name="Use approved answer in Automation").click()
                page.get_by_text(re.compile(r"Selected from Review:")).wait_for()
                page.get_by_label("Approval ID for " + original, exact=False).wait_for()
                assert (
                    page.get_by_label("Approval ID for " + original, exact=False)
                    .input_value()
                    .startswith("apr-")
                )
                if original == "pf-org-name":
                    page.get_by_role("link", name="Review", exact=True).click()
            page.get_by_role("button", name="Prepare selected-field plan (no entry)").click()
            page.get_by_text("Exact approved plan preview", exact=True).wait_for()
            assert page.get_by_text("C producer connected", exact=False).is_visible()
            assert page.get_by_text("A4 not integrated for this evidence", exact=False).is_visible()
            assert page.locator("pre").filter(has_text=name).text_content() == name
            rendered = versions["pf-summary"]["rendered"]["text"]
            assert (
                page.locator("pre").filter(has_text="Historical synthetic metric").text_content()
                == rendered
            )
            page.get_by_role("button", name="Fill these approved fields").dblclick()
            page.get_by_role("heading", name="Selected fields verified", exact=True).wait_for()
            receipt = page.get_by_label("Read-back receipt")
            assert receipt.get_by_text("Final reread: all_match.", exact=False).is_visible()
            assert receipt.get_by_text("org-name-field: entered_verified", exact=False).is_visible()
            assert receipt.get_by_text("summary-field: entered_verified", exact=False).is_visible()
            page.reload()
            assert page.get_by_label("Read-back receipt").count() == 0
            page.get_by_role("button", name="Check stored receipt").click()
            page.get_by_role("heading", name="Selected fields verified", exact=True).wait_for()
            # A new pending plan becomes visibly stale after one C character edit.
            page.get_by_role("link", name="Review", exact=True).click()
            page.get_by_label("Question", exact=True).select_option(ids["pf-summary"])
            page.get_by_role("button", name="Use approved answer in Automation").click()
            page.get_by_text(re.compile(r"Selected from Review:")).wait_for()
            with page.expect_response(
                lambda r: (
                    r.url.endswith("/api/automation/prefill-plans") and r.request.method == "POST"
                )
            ) as prepared:
                page.get_by_role("button", name="Prepare selected-field plan (no entry)").click()
            pending_plan = prepared.value.json()
            page.get_by_text("Exact approved plan preview", exact=True).wait_for()
            post(
                "/api/applications/answers/versions",
                {
                    "question_id": ids["pf-summary"],
                    "question_version": 1,
                    "question_set_id": pub["question_set_id"],
                    "evidence_bundle_id": "demo-evidence-a-v1",
                    "text": summary + "!",
                    "expected_answer_version": 1,
                },
            )
            page.get_by_role("button", name="Check current sources (no entry)").click()
            page.get_by_text("Review the answer and prepare a new plan.", exact=False).wait_for()
            assert page.get_by_role("button", name="Fill these approved fields").is_disabled()
            blocked = post(
                f"/api/automation/prefill-plans/{pending_plan['plan_id']}/execute",
                {
                    "expected_plan_sha256": pending_plan["plan_sha256"],
                    "idempotency_key": "int-real-blocked-edit",
                },
            )["run"]["run"]
            assert blocked["outcome"] == "blocked_before_entry"
            assert blocked["activity"]["operations_performed"] == []
            assert errors == [] and external == []
        finally:
            browser.close()


def test_real_chromium_stops_after_event_controlled_c_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib
    import threading
    from concurrent.futures import ThreadPoolExecutor

    from fastapi.testclient import TestClient

    from strongstart_api.app import create_app
    from strongstart_api.config import Settings
    from tests.integration.support import decide, prepare, publish, save

    runner = importlib.import_module("strongstart_api.features.automation.prefill_runner")
    app = create_app(
        Settings(_env_file=None, auth_mode="fixture", dev_b_store_dir=tmp_path / "store")
    )
    c = TestClient(app)
    pub = publish(c)
    approvals = {
        q: decide(c, save(c, pub, q, text))
        for q, text in [
            ("pf-org-name", "Riverside Youth Collective"),
            ("pf-summary", "We support early learning."),
        ]
    }
    plan = prepare(c, pub, approvals).json()
    entered, edited = threading.Event(), threading.Event()
    original = runner._Hooks.after_write

    def after(self: Any, index: int, outcome: Any) -> Any:
        if index == 0:
            entered.set()
            assert edited.wait(10)
        return original(self, index, outcome)

    monkeypatch.setattr(runner._Hooks, "after_write", after)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(
            c.post,
            f"/api/automation/prefill-plans/{plan['plan_id']}/execute",
            json={
                "expected_plan_sha256": plan["plan_sha256"],
                "idempotency_key": "int-real-partial-edit",
            },
        )
        try:
            assert entered.wait(10)
            save(c, pub, "pf-org-name", "Riverside Youth Collective!", 1)
        finally:
            edited.set()
        response = future.result(timeout=15)
    assert response.status_code == 201, response.text
    run = response.json()["run"]["run"]
    assert run["browser_version"] and run["outcome"] == "stopped_with_partial_entry"
    assert run["activity"]["operations_performed"] == ["fill:org-name-field"]
    assert run["fields"][0]["state"] == "entered_then_stale"
    assert run["fields"][0]["actual_value"] == "Riverside Youth Collective"
    assert run["fields"][1]["state"] == "not_attempted"
