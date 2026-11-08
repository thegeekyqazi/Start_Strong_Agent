"""DEV-B-BUNDLE-002 BND-49: production uses unconfigured adapters; no fixture/memory fallback."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.identity import require_identity
from strongstart_contracts import SessionIdentity

PROD_STAFF = SessionIdentity(
    actor_id="prod-staff",
    organization_id="prod-org",
    roles=[],
    is_fixture=False,
    label="TEST injected production identity",
)
CASE = "case-" + "0" * 26
PROFILE = "prof-" + "0" * 26
CAPTURE = "cap-" + "0" * 32


@pytest.fixture
def prod(tmp_path: Path) -> TestClient:
    settings = Settings(
        _env_file=None,
        environment="production",
        funding_capture_store_dir=tmp_path / "captures",
        dev_b_store_dir=tmp_path / "dev-b",
    )
    app = create_app(settings)
    app.dependency_overrides[require_identity] = lambda: PROD_STAFF
    return TestClient(app)


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/api/automation/definitions", None),
        ("get", "/api/automation/definitions/def-" + "0" * 26, None),
        ("get", "/api/automation/question-sets/qs-def-" + "0" * 26 + "-v1", None),
        ("post", "/api/automation/definitions", {}),
        ("get", "/api/funding/captures", None),
        ("get", "/api/funding/cases", None),
        ("get", f"/api/funding/cases/{CASE}", None),
        ("post", "/api/funding/cases", {}),
        ("post", f"/api/funding/cases/{CASE}/evaluations", {}),
        ("get", "/api/funding/searches", None),
        ("post", "/api/funding/searches", {}),
        ("post", f"/api/funding/searches/{PROFILE}/runs", {}),
        ("post", f"/api/funding/captures/{CAPTURE}/recheck", {}),
        ("get", f"/api/funding/captures/{CAPTURE}/observations", None),
    ],
)
def test_bnd49_every_new_route_is_unavailable_in_production(
    prod: TestClient, tmp_path: Path, method: str, path: str, body: dict[str, object] | None
) -> None:
    r = getattr(prod, method)(path, json=body) if body is not None else getattr(prod, method)(path)
    assert r.status_code == 503, (path, r.text)
    assert r.json()["details"]["reason"] in ("store_unavailable",)
    assert not list(tmp_path.rglob("*.json"))  # nothing written anywhere


def test_bnd49_capabilities_report_unavailable_in_production(prod: TestClient) -> None:
    caps = {c["feature"]: c for c in prod.get("/api/capabilities").json()["capabilities"]}
    for feature in (
        "automation.saved_definitions",
        "funding.capture_library",
        "funding.reviewed_requirements",
        "funding.evaluations",
        "funding.saved_searches",
    ):
        assert caps[feature]["status"] == "unavailable", feature


def test_capabilities_are_truthful_locally(tmp_path: Path) -> None:
    c = TestClient(create_app(Settings(_env_file=None, dev_b_store_dir=tmp_path)))
    caps = {x["feature"]: x for x in c.get("/api/capabilities").json()["capabilities"]}
    assert caps["automation.saved_definitions"]["status"] == "fixture_only"
    assert "development-only" in caps["funding.reviewed_requirements"]["detail"]
    assert "No scheduling" in caps["funding.saved_searches"]["detail"]
    assert caps["automation.approved_prefill"]["status"] == "not_implemented"
