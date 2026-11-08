"""Automation API boundaries: AUTO-01, AUTO-10 (non-browser part), AUTO-13, AUTO-16, export."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from strongstart_api.config import Settings
from strongstart_api.features.automation import service
from strongstart_api.features.automation.router import get_capture_source
from strongstart_api.identity import FIXTURE_IDENTITY, require_identity
from strongstart_contracts.automation_intake import AutomationHandoffExport
from tests.automation.conftest import make_client

PROTECTED = [
    ("post", "/api/automation/intake"),
    ("post", "/api/automation/inspect-fixture"),
    ("post", "/api/automation/export-definition"),
    ("get", "/api/automation/fixtures/portal/rep-portal-v1"),
]


class SpyCapture:
    is_fixture = True

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_record(self, organization_id: str, capture_id: str) -> Any:
        self.calls.append("get_record")
        raise AssertionError("artifact access before auth")

    def read_artifact(self, organization_id: str, capture_id: str, artifact_id: str) -> bytes:
        self.calls.append("read_artifact")
        raise AssertionError("artifact access before auth")

    def list_records(self, organization_id: str) -> list[Any]:
        return []


def test_auto01_unauthenticated_denied_before_artifact_access_or_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launches: list[Any] = []
    monkeypatch.setattr(service, "inspect_page", lambda *a, **k: launches.append(a))
    spy = SpyCapture()
    client = make_client()  # auth_mode none
    client.app.dependency_overrides[get_capture_source] = lambda: spy  # type: ignore[attr-defined]
    bodies: dict[str, Any] = {
        "/api/automation/intake": {
            "source": {"mode": "capture", "capture_id": "cap-x", "artifact_id": "art-x"},
            "organization_id": "demo-org",
            "approved": True,
        },
        "/api/automation/inspect-fixture": {"fixture_id": "rep-portal-v1", "approved": True},
        "/api/automation/export-definition": {
            "source": {"mode": "fixture", "fixture_id": "rep-portal-definition-v1"},
            "inspect_fixture_id": "rep-portal-v1",
        },
    }
    for method, path in PROTECTED:
        kwargs = {"json": bodies[path]} if method == "post" else {}
        r = getattr(client, method)(path, headers={"X-Org-Id": "demo-org"}, **kwargs)
        assert r.status_code == 401, path
        assert r.json()["code"] == "unauthenticated"
    assert spy.calls == [] and launches == []


def test_auto13_production_cannot_enable_fixture_identity() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", auth_mode="fixture")


def test_auto13_production_denies_fixture_modes_even_with_an_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launches: list[Any] = []
    monkeypatch.setattr(service, "inspect_page", lambda *a, **k: launches.append(a))
    client = make_client(environment="production")
    # Simulates a future real identity provider; fixture capability must still be off.
    client.app.dependency_overrides[require_identity] = lambda: FIXTURE_IDENTITY  # type: ignore[attr-defined]
    r = client.post(
        "/api/automation/intake",
        json={"source": {"mode": "fixture", "fixture_id": "rep-portal-definition-v1"}},
    )
    assert r.status_code == 403 and r.json()["details"]["reason"] == "fixture_not_allowed"
    r = client.post("/api/automation/inspect-fixture", json={"fixture_id": "rep-portal-v1"})
    assert r.status_code == 403 and r.json()["details"]["reason"] == "fixture_not_allowed"
    r = client.get("/api/automation/fixtures/portal/rep-portal-v1")
    assert r.status_code == 403
    r = client.post(
        "/api/automation/intake",
        json={
            "source": {
                "mode": "capture",
                "capture_id": "cap-fixture-portal-html",
                "artifact_id": "art-portal-raw-html",
            }
        },
    )
    assert r.status_code == 503 and r.json()["details"]["reason"] == "source_unavailable"
    avail = client.get("/api/automation/availability").json()
    assert avail["browser_status"] == "disabled" and avail["fixtures"] == []
    assert launches == []


def test_auto10_unregistered_fixture_or_url_rejected(fixture_client: TestClient) -> None:
    r = fixture_client.post("/api/automation/inspect-fixture", json={"fixture_id": "other-portal"})
    assert r.status_code == 403 and r.json()["details"]["reason"] == "fixture_not_allowed"
    for bad in ["http://127.0.0.1:7000/", "../portal/rep-portal-v1.html", "file:///etc/passwd"]:
        r = fixture_client.post("/api/automation/inspect-fixture", json={"fixture_id": bad})
        assert r.status_code == 422, bad
    r = fixture_client.post(
        "/api/automation/inspect-fixture", json={"fixture_id": "rep-portal-v1", "url": "http://x"}
    )
    assert r.status_code == 422
    r = fixture_client.get("/api/automation/fixtures/portal/..%2F..%2Fconfig")
    assert r.status_code in (403, 404)
    r = fixture_client.post(
        "/api/automation/intake", json={"source": {"mode": "fixture", "fixture_id": "nope"}}
    )
    assert r.status_code == 403


def test_auto16_availability_is_granular(fixture_client: TestClient) -> None:
    body = fixture_client.get("/api/automation/availability").json()
    caps = {c["feature"]: c["status"] for c in body["capabilities"]}
    assert caps == {
        "automation": "fixture_only",
        "automation.saved_definitions": "fixture_only",
        "automation.intake": "available",
        "automation.capture_intake": "fixture_only",
        "automation.browser_inspection": "fixture_only",
        "automation.pdf_parsing": "not_implemented",
        "automation.approved_prefill": "fixture_only",
        "automation.prefill_plan_preparation": "fixture_only",
        "automation.prefill_execution_test_provider": "fixture_only",
        "automation.prefill_execution_c3": "fixture_only",
        "automation.prefill_choice_values": "unavailable",
        "automation.attachment_checklist": "fixture_only",
        "automation.real_portal_prefill": "unavailable",
        "automation.final_submission": "unavailable",
    }
    assert {m["mode"]: m["status"] for m in body["import_modes"]}["capture"] == "fixture_only"
    kinds = {f["kind"] for f in body["fixtures"]}
    assert kinds == {"structured_definition", "html_form", "portal", "capture"}
    assert all("FIXTURE" in f["label"] for f in body["fixtures"])
    assert "content_file" not in json.dumps(body) and "/home/" not in json.dumps(body)


def test_auto16_export_is_versioned_not_approved_and_roundtrips(
    fixture_client: TestClient,
) -> None:
    r = fixture_client.post(
        "/api/automation/export-definition",
        json={"source": {"mode": "fixture", "fixture_id": "rep-portal-definition-v1"}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["export_format"] == "b2-automation-handoff/1"
    assert body["approval_status"] == "not_approved" and body["prefill_permitted"] is False
    assert "NOT APPROVED" in body["label"] and "FIXTURE" in body["label"]
    assert body["persisted"] is False and body["inspection"] is None and body["form_map"] is None
    kinds = {(u["question_id"], u["kind"]) for u in body["unresolved"]}
    assert ("rp-partnership", "limit_conflict") in kinds
    assert ("rp-other-funding", "unknown_limit_unit") in kinds
    assert ("rp-pending-applications", "required_status_unknown") in kinds
    assert ("rp-mission", "unknown_counting_convention") in kinds
    model = AutomationHandoffExport.model_validate(body)
    assert json.loads(model.model_dump_json()) == body
    direct = fixture_client.post(
        "/api/automation/intake",
        json={"source": {"mode": "fixture", "fixture_id": "rep-portal-definition-v1"}},
    ).json()
    assert body["intake"] == direct  # server-derived; same bytes -> same semantics
    assert body["question_set"] == direct["question_set"]


def test_portal_view_is_sandboxed(fixture_client: TestClient) -> None:
    r = fixture_client.get("/api/automation/fixtures/portal/rep-portal-v1")
    assert r.status_code == 200
    csp = r.headers["content-security-policy"]
    assert csp.startswith("sandbox allow-scripts;") and "allow-same-origin" not in csp
    assert "form-action 'none'" in csp
    assert "FIXTURE - representative portal" in r.text
