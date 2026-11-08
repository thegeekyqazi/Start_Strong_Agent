"""DEV-B-BUNDLE-002 M6: real Chromium against the real API process (BND-50, BND-51, BND-52).

Fixture identity and FIXTURE providers only (no paid/live calls), temporary stores per test.
Requires the built web app (make browser-smoke builds it first).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from tests.browser.test_funding_e2e import FIXTURE_ENV, stack

pytestmark = pytest.mark.browser
FORM_PAGE = "https://demo-funder.example/programs/community-grants"
GUIDELINES = "https://demo-funder.example/programs/community-grants/guidelines"
UPDATES = "https://demo-funder.example/programs/community-grants/updates"
AMOUNT_QUOTE = "Standard stream requests: 20,000 to 100,000 CAD per award."


@contextmanager
def session(tmp_path: Path) -> Iterator[tuple[Any, str, dict[str, list[str]]]]:
    from playwright.sync_api import sync_playwright

    env = {**FIXTURE_ENV, "STRONGSTART_DEV_B_STORE_DIR": str(tmp_path / "dev-b")}
    with stack(tmp_path, **env) as base, sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            seen: dict[str, list[str]] = {"external": [], "errors": [], "dialogs": []}
            page.on(
                "request",
                lambda r: (
                    seen["external"].append(r.url)
                    if not r.url.startswith(base) and not r.url.startswith("data:")
                    else None
                ),
            )
            page.on("pageerror", lambda e: seen["errors"].append(str(e)))

            def on_dialog(dialog: Any) -> None:
                seen["dialogs"].append(dialog.message)
                dialog.dismiss()

            page.on("dialog", on_dialog)
            yield page, base, seen
        finally:
            browser.close()


def capture_url(page: Any, url: str) -> str:
    page.get_by_label("Public http(s) URL").fill(url)
    page.get_by_role("button", name="Capture", exact=True).click()
    page.get_by_text("Coverage: complete").first.wait_for()
    text = page.locator("dl.meta dd").first.inner_text()
    assert re.fullmatch(r"cap-[0-9a-f]{32}", text), text
    return str(text)


def test_bnd50_capture_library_intake_save_reload_reopen(tmp_path: Path) -> None:
    with session(tmp_path) as (page, base, seen):
        page.goto(f"{base}/#/funding")
        capture_id = capture_url(page, FORM_PAGE)
        # Navigate away and back: the capture is found in the saved library.
        page.goto(f"{base}/#/automation")
        page.get_by_text("Saved definitions for drafting").wait_for()
        page.goto(f"{base}/#/funding")
        page.reload()
        page.get_by_role("button", name=f"Open {capture_id}").click()
        ref = page.get_by_test_id("intake-reference").first.inner_text()
        assert ref == f"{capture_id}:{capture_id}-html"
        page.get_by_role("button", name="Use provider_html in application intake").first.click()
        page.wait_for_url(re.compile(r".*#/automation$"))
        assert page.get_by_label("Or paste a capture reference").input_value() == ref
        page.get_by_role("button", name="Import", exact=True).click()
        page.get_by_text("2. Imported questions").wait_for()
        page.get_by_text("Describe your organization's mission (50 words)").first.wait_for()
        # No funding context yet: publication is held, nothing invented.
        page.get_by_role("button", name="Save definition for drafting").click()
        page.get_by_text("[publication_blocked]").wait_for()
        # The engineering-derived fixture saves, survives a reload and reopens exactly.
        page.get_by_label("Known fixture").check()
        page.get_by_role("button", name="Import", exact=True).click()
        page.get_by_text("Competing limits", exact=False).first.wait_for()
        page.get_by_role("button", name="Save definition for drafting").click()
        page.get_by_text("connection to Applications pending").first.wait_for()
        page.reload()
        page.get_by_role("button", name=re.compile(r"^Reopen def-")).first.click()
        qs_id = page.get_by_test_id("saved-qs-id").inner_text()
        assert re.fullmatch(r"qs-def-[0-9a-f]{26}-v1", qs_id)
        page.get_by_text("limit conflict", exact=False).first.wait_for()
        page.get_by_text("saved not reviewed", exact=False).wait_for()
        assert page.evaluate("typeof window.pwned") == "undefined"
        assert seen["external"] == [] and seen["errors"] == [] and seen["dialogs"] == []


def test_bnd51_case_evidence_review_and_scenario_check(tmp_path: Path) -> None:
    with session(tmp_path) as (page, base, seen):
        page.goto(f"{base}/#/funding")
        capture_id = capture_url(page, GUIDELINES)
        page.get_by_label("Funder", exact=True).fill("FIXTURE Demo Funder")
        page.get_by_label("Stream", exact=True).fill("standard")
        page.get_by_label("Cycle", exact=True).fill("2026")
        page.get_by_label("Stage", exact=True).select_option("full_application")
        page.get_by_label("Linked capture IDs").fill(capture_id)
        page.get_by_label("Capture ID", exact=True).fill(capture_id)
        page.get_by_role("button", name="Load capture").click()
        page.get_by_role("button", name="Show provider_markdown", exact=True).click()
        page.get_by_test_id("anchor-source").wait_for()
        page.get_by_label("Exact quote").fill(AMOUNT_QUOTE)
        page.get_by_label("Anchor key", exact=True).fill("amount")
        page.get_by_role("button", name="Add anchor").click()
        page.get_by_label("Requirement key").fill("standard-amount")
        page.get_by_label("Anchor keys", exact=True).fill("amount")
        page.get_by_label("Minimum (exact decimal)").fill("20000")
        page.get_by_label("Maximum (exact decimal)").fill("100000")
        page.get_by_label("Interpretation").fill("FIXTURE per-award range, standard stream.")
        page.get_by_role("button", name="Add requirement").click()
        page.get_by_role("button", name="Create funding case").click()
        page.get_by_text("Interpretation review: unreviewed").wait_for()
        page.get_by_text("Staff-selected context, not a certified opportunity").wait_for()
        page.get_by_role("button", name="Review these requirements").click()
        page.get_by_text("Interpretation review: reviewed").wait_for()
        # Missing input stays unknown.
        page.get_by_role("button", name="Run scenario check").click()
        page.get_by_text("No request amount was provided.").wait_for()
        # A staff scenario shows exact support and remains unconfirmed.
        page.get_by_label("Request amount (exact decimal)").fill("120000")
        page.get_by_role("button", name="Run scenario check").click()
        page.get_by_text("exceeds the maximum 100,000 by 20,000", exact=False).wait_for()
        page.get_by_text("Reliance: not confirmed", exact=False).first.wait_for()
        assert page.locator("q", has_text=AMOUNT_QUOTE).count() >= 1
        page.get_by_label("Request amount (exact decimal)").fill("50000")
        page.get_by_role("button", name="Run scenario check").click()
        page.get_by_text(
            "These encoded rules are met using these inputs; funder eligibility is not confirmed."
        ).wait_for()
        assert page.get_by_text(re.compile(r"^Eligible$")).count() == 0
        assert seen["external"] == [] and seen["errors"] == []


def test_bnd52_saved_search_reruns_and_capture_comparison(tmp_path: Path) -> None:
    with session(tmp_path) as (page, base, seen):
        page.goto(f"{base}/#/funding")
        page.get_by_label("Label (stays here; never sent)").fill("FIXTURE early learning")
        page.get_by_role("button", name="Save search", exact=True).click()
        page.get_by_text("early learning grant funding").first.wait_for()
        run_button = page.get_by_role("button", name="Run search now (FIXTURE early learning)")
        run_button.click()
        page.get_by_text(re.compile(r"Run run-[0-9a-f]{26}: \d+ results")).wait_for()
        run_button.click()
        page.get_by_role("button", name="Show run history (FIXTURE early learning)").click()
        options = page.get_by_label("Earlier run").locator("option")
        options.nth(2).wait_for(state="attached")
        later, earlier = (options.nth(i).get_attribute("value") for i in (1, 2))
        page.get_by_label("Earlier run").select_option(earlier)
        page.get_by_label("Later run").select_option(later)
        page.get_by_role("button", name="Compare runs").click()
        page.get_by_text(
            "Not seen in this result set (not removed or closed)", exact=False
        ).wait_for()
        # Capture again and compare: the first recheck matches, the second shows a change.
        capture_url(page, UPDATES)
        page.get_by_role("button", name="Capture again and compare").first.click()
        page.get_by_text("Unchanged (stored bytes match)").first.wait_for()
        page.get_by_role("button", name="Capture again and compare").first.click()
        page.get_by_text("Changed (stored bytes differ; re-review needed)").first.wait_for()
        page.get_by_text("A4", exact=False).first.wait_for()
        page.get_by_role("button", name="Show change observations").first.click()
        history = page.locator("li .observation")
        history.nth(1).wait_for()
        assert history.count() == 2
        assert "Changed (stored bytes differ" in history.nth(0).inner_text()
        assert "Unchanged (stored bytes match)" in history.nth(1).inner_text()
        assert seen["external"] == [] and seen["errors"] == []
