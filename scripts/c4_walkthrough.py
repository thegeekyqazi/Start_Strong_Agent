"""C4-SKL-001 focused Chromium walkthrough of the Skills page (demo evidence, not a CI test).

Usage: uv run python scripts/c4_walkthrough.py OUT_DIR [BASE_URL]
Requires a running fixture-mode API (PostgreSQL store, migrated to 0010, demo org seeded) and the
web dev server proxying to it. Publishes new synthetic source versions on each run (append-only).
Drives: source authority -> generate -> screen -> exact-hash review -> activate -> preview ->
revoke -> planted hostile candidate held, with screenshots, console errors and external requests.
"""

import sys

from playwright.sync_api import ConsoleMessage, expect, sync_playwright
from playwright.sync_api import Request as PwRequest

OUT = sys.argv[1]
BASE = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:5180"
errors: list[str] = []
external: list[str] = []
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1280, "height": 900})

    def on_console(m: ConsoleMessage) -> None:
        if m.type == "error":
            errors.append(m.text)

    def on_request(r: PwRequest) -> None:
        if not r.url.startswith(BASE):
            external.append(r.url)

    page.on("console", on_console)
    page.on("request", on_request)
    page.goto(f"{BASE}/#/skills")
    expect(page.get_by_role("heading", name="Skills", exact=True)).to_be_visible()

    def shot(n: str) -> None:
        page.screenshot(path=f"{OUT}/{n}.png", full_page=True)

    def click(name: str) -> None:
        page.get_by_role("button", name=name).click()

    log: list[str] = []
    click("Publish synthetic demo source")
    expect(
        page.get_by_role("button", name="Approve as practice authority for this scope")
    ).to_be_visible()
    shot("1-source")
    click("Approve as practice authority for this scope")
    expect(page.get_by_text("Reviewed as practice authority")).to_be_visible()
    click("Generate candidate from current source")
    expect(page.get_by_text("Proposed — screening not run", exact=True)).to_be_visible()
    shot("2-candidate")
    click("Run screening for this package")
    expect(page.get_by_text("Gates passed — needs staff review", exact=True)).to_be_visible()
    page.get_by_label("I confirm every rule follows from its source excerpt.").check()
    click("Approve this exact package")
    expect(page.get_by_text("Reviewed — ready to activate", exact=True)).to_be_visible()
    click("Activate for this scope")
    expect(page.get_by_text("Active release", exact=False).first).to_be_visible()
    shot("3-active")
    page.get_by_role("button", name="Preview a draft").click()
    expect(page.get_by_text("Applied-instruction trace (sent to the draft model)")).to_be_visible()
    expect(page.get_by_text('instead of "kids"').first).to_be_visible()
    practice = page.get_by_role("region", name="Sample checked with the active practice")
    expect(practice.get_by_text("children").first).to_be_visible()
    shot("4-preview")
    log.append("preview applied practice; sample flagged kids->children")
    click("Revoke")
    expect(page.get_by_text("No active practice for this scope.")).to_be_visible()
    page.get_by_role("button", name="Preview a draft").click()
    expect(page.get_by_text("No practice applied: no_active_practice")).to_be_visible()
    shot("5-revoked")
    log.append("after revoke: preview refuses (no_active_practice)")
    click("Publish planted hostile source")
    click("Approve as practice authority for this scope")
    click("Generate candidate from current source")
    expect(page.get_by_text("Held — a hard gate failed", exact=True)).to_be_visible()
    expect(page.get_by_text("secret_canary", exact=False).first).to_be_visible()
    assert page.get_by_role("button", name="Approve this exact package").is_disabled()
    assert page.get_by_role("button", name="Activate for this scope").is_disabled()
    assert "sk-can" not in page.content()
    shot("6-hostile")
    log.append("hostile candidate held; approve/activate disabled; secret redacted")
    b.close()
print("\n".join(log))
print("console errors:", errors)
print("external requests:", external)
