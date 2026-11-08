"""DEV-B-BUNDLE-002 M2: saved capture library (BND-17..BND-20).

Fixture providers only; every client uses a per-test temporary capture store.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.funding import store as store_module
from strongstart_api.features.funding.deps import get_resolver
from strongstart_api.identity import require_identity
from strongstart_contracts import SessionIdentity

from .conftest import GRANT_URL, PUBLIC_RESOLVER

AWARDS_URL = "https://news.demo-foundation.example/2026/awards-announced"
OTHER = SessionIdentity(
    actor_id="x", organization_id="other-org", roles=[], is_fixture=True, label="TEST other org"
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        auth_mode="fixture",
        funding_capture_store_dir=tmp_path / "captures",
        dev_b_store_dir=tmp_path / "dev-b",
        funding_search_mode="fixture",
        funding_capture_mode="fixture",
    )


def client_for(settings: Settings, identity: SessionIdentity | None = None) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_resolver] = lambda: PUBLIC_RESOLVER
    if identity is not None:
        app.dependency_overrides[require_identity] = lambda: identity
    return TestClient(app)


def capture(c: TestClient, url: str = GRANT_URL) -> dict[str, Any]:
    r = c.post("/api/funding/captures", json={"url": url})
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()
    return data


def listing(c: TestClient, **params: Any) -> dict[str, Any]:
    r = c.get("/api/funding/captures", params=params)
    assert r.status_code == 200, r.text
    data: dict[str, Any] = r.json()
    return data


def test_bnd17_captures_are_listed_newest_first_and_survive_restart(settings: Settings) -> None:
    c = client_for(settings)
    first = capture(c)
    second = capture(c, AWARDS_URL)
    page = listing(c)
    assert [i["capture_id"] for i in page["items"]] == [second["capture_id"], first["capture_id"]]
    item = page["items"][1]
    assert item["status"] == "ok"
    assert item["page_title"] == first["page_title"]
    assert item["provider"] == "fixture-capture" and item["provider_mode"] == "fixture"
    assert item["coverage"] == "complete" and item["representation_count"] == 3
    assert item["authority_review"] == first["authority_review"]
    assert item["is_simulated"] is True
    assert item["content_integrity"] == "not_checked_in_listing"
    assert page["backfill_status"] == "complete" and page["backfill_pending"] == 0
    fresh = client_for(settings)  # new app instance over the same store (restart)
    assert [i["capture_id"] for i in listing(fresh)["items"]] == [
        second["capture_id"],
        first["capture_id"],
    ]
    opened = fresh.get(f"/api/funding/captures/{first['capture_id']}")
    assert opened.json() == first


def test_bnd17_pre_catalog_captures_are_backfilled_in_bounded_steps(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = client_for(settings)
    ids = [capture(c)["capture_id"] for _ in range(3)]
    for entry in settings.funding_capture_store_dir.glob("org-*/catalog/*"):
        entry.unlink()  # simulate captures saved before the catalog existed
    monkeypatch.setattr(store_module, "BACKFILL_PER_CALL", 1)
    one = listing(c)
    assert one["backfill_status"] == "pending" and one["backfill_pending"] == 2
    assert len(one["items"]) == 1
    two = listing(c)
    assert two["backfill_status"] == "pending" and two["backfill_pending"] == 1
    three = listing(c)
    assert three["backfill_status"] == "complete" and three["backfill_pending"] == 0
    assert {i["capture_id"] for i in three["items"]} == set(ids)


def test_bnd18_pagination_scan_limits_and_tenant_safety(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    c = client_for(settings)
    ids = [capture(c)["capture_id"] for _ in range(3)][::-1]
    first = listing(c, limit=2)
    assert [i["capture_id"] for i in first["items"]] == ids[:2] and first["more"] is True
    rest = listing(c, limit=2, cursor=first["next_cursor"])
    assert [i["capture_id"] for i in rest["items"]] == ids[2:] and rest["more"] is False
    for bad in ({"limit": 0}, {"limit": 101}, {"cursor": "../../x"}, {"cursor": "1-cap-1"}):
        assert c.get("/api/funding/captures", params=bad).status_code == 422
    monkeypatch.setattr(store_module, "MAX_SCAN_ENTRIES", 2)
    capped = listing(c)
    assert capped["incomplete"] is True
    assert capped["backfill_status"] == "incomplete_scan"
    other = client_for(settings, OTHER)
    assert listing(other)["items"] == []
    assert other.get(f"/api/funding/captures/{ids[0]}").status_code == 404
    assert (
        client_for(settings.model_copy(update={"auth_mode": "none"}))
        .get("/api/funding/captures")
        .status_code
        == 401
    )


def test_bnd18_corrupt_entry_is_a_safe_finding_not_a_crash(settings: Settings) -> None:
    c = client_for(settings)
    good = capture(c)
    bad = capture(c, AWARDS_URL)
    record = next(
        settings.funding_capture_store_dir.glob(f"org-*/records/{bad['capture_id']}.json")
    )
    record.chmod(0o600)
    record.write_text('{"capture_id": "tampered", "page_title": "<script>x</script>"')
    page = listing(c)
    by_id = {i["capture_id"]: i for i in page["items"]}
    assert by_id[bad["capture_id"]]["status"] == "corrupt"
    assert by_id[bad["capture_id"]]["page_title"] is None
    assert "script" not in str(by_id[bad["capture_id"]])
    assert by_id[good["capture_id"]]["status"] == "ok"
    opened = c.get(f"/api/funding/captures/{bad['capture_id']}")
    assert opened.status_code == 500
    assert opened.json()["details"]["reason"] == "integrity_failure"
    assert "script" not in opened.text


def test_bnd19_intake_reference_is_exact_and_imports_the_selected_artifact(
    settings: Settings,
) -> None:
    c = client_for(settings)
    doc = capture(c)
    item = listing(c)["items"][0]
    refs = {a["representation"]: a for a in item["importable_artifacts"]}
    assert set(refs) == {"provider_html", "provider_raw_html"}  # markdown is context only
    html = refs["provider_html"]
    assert html["intake_reference"] == f"{doc['capture_id']}:{html['artifact_id']}"
    capture_id, artifact_id = html["intake_reference"].split(":")
    r = c.post(
        "/api/automation/intake",
        json={"source": {"mode": "capture", "capture_id": capture_id, "artifact_id": artifact_id}},
    )
    assert r.status_code == 200, r.text
    lineage = r.json()["input"]["capture"]
    assert lineage["capture_id"] == doc["capture_id"]
    assert lineage["artifact_id"] == artifact_id
    assert lineage["representation_type"] == "provider_html"
    sha = next(a["sha256"] for a in doc["artifacts"] if a["artifact_id"] == artifact_id)
    assert r.json()["input"]["sha256"] == sha


def test_bnd20_listing_and_content_keep_scripts_inert(settings: Settings) -> None:
    c = client_for(settings)
    doc = capture(c, AWARDS_URL)
    item = listing(c)["items"][0]
    assert "text" not in item and "content" not in item  # metadata only
    raw = next(a for a in doc["artifacts"] if a["representation"] == "provider_raw_html")
    content = c.get(
        f"/api/funding/captures/{doc['capture_id']}/artifacts/{raw['artifact_id']}/content"
    )
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("application/json")
    assert content.json()["integrity_verified"] is True
