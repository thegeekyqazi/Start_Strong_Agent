"""API bootstrap behaviour: liveness/readiness, capabilities, identity boundary, errors."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from strongstart_api.app import create_app
from strongstart_api.config import Settings

UNREACHABLE_DB = "postgresql+psycopg://nobody:nopw@127.0.0.1:1/none"
FEATURE_OPS = [
    "/api/knowledge/packs/import",
    "/api/funding/discovery-jobs",
    "/api/automation/intake",
    "/api/applications/draft-jobs",
]
# B2-AUTO-001 implemented automation intake; it is no longer a 501 placeholder.
UNIMPLEMENTED_OPS = [p for p in FEATURE_OPS if not p.startswith("/api/automation/")]


def client(**overrides: Any) -> TestClient:
    return TestClient(create_app(Settings(_env_file=None, **overrides)))


def test_liveness_does_not_need_database() -> None:
    r = client(database_url=UNREACHABLE_DB).get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "alive", "service": "strongstart-api"}


@pytest.mark.parametrize("url", [None, UNREACHABLE_DB])
def test_readiness_is_not_ready_without_database(url: str | None) -> None:
    r = client(database_url=url, db_connect_timeout_seconds=1).get("/health/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "not_ready"
    assert any(c["name"] == "database" and not c["ok"] for c in body["checks"])
    assert "nopw" not in r.text  # connection credentials never echoed


def test_readiness_rejects_non_postgres_url() -> None:
    r = client(database_url="sqlite:///:memory:").get("/health/ready")
    assert r.status_code == 503


def test_capabilities_are_explicit_and_features_unimplemented() -> None:
    body = client().get("/api/capabilities").json()
    assert body["auth_mode"] == "none" and body["fixture_mode"] is False
    caps = {c["feature"]: c for c in body["capabilities"]}
    for feature, owner in [
        ("knowledge", "A"),
        ("skills", "C"),
    ]:
        assert caps[feature]["status"] == "not_implemented"
        assert caps[feature]["owner"] == owner
    # B1-DISC-001: funding reports runtime availability; without provider keys it is
    # explicitly unavailable (never "available" by default).
    assert caps["funding"]["owner"] == "B1"
    assert caps["funding"]["status"] == "unavailable"
    assert caps["platform.identity"]["status"] == "unavailable"
    # C1: the workspace needs a configured producer (fixture mode only); the default
    # model adapter is the labelled deterministic fixture, never a live provider.
    assert caps["applications"]["owner"] == "C"
    assert caps["applications"]["status"] == "unavailable"
    assert caps["applications.model"]["status"] == "fixture_only"
    # C3: review needs an answer store; only the fixture store exists (fixture mode).
    assert caps["review"]["owner"] == "C"
    assert caps["review"]["status"] == "unavailable"
    assert caps["automation"]["owner"] == "B2"
    # B2-AUTO-001: intake + fixture inspection only
    assert caps["automation"]["status"] == "fixture_only"
    assert caps["automation.approved_prefill"]["status"] == "not_implemented"
    assert caps["automation.final_submission"]["status"] == "unavailable"


def test_protected_operations_deny_without_identity_provider() -> None:
    c = client()
    assert c.get("/api/session").json()["code"] == "unauthenticated"
    for path in FEATURE_OPS:
        r = c.post(path, json={"organization_id": "demo-org", "approved": True})
        assert r.status_code == 401, path
        assert r.json()["code"] == "unauthenticated"


def test_fixture_mode_unimplemented_ops_never_fake_success() -> None:
    c = client(auth_mode="fixture")
    for path in UNIMPLEMENTED_OPS:
        r = c.post(path)
        assert r.status_code == 501, path
        assert r.json()["code"] == "not_implemented"


def test_client_cannot_choose_identity_or_approval() -> None:
    c = client(auth_mode="fixture")
    r = c.get(
        "/api/session?org_id=other-org&organization_id=other-org",
        headers={"X-Org-Id": "other-org", "X-Actor-Id": "admin", "X-Approved": "true"},
    )
    body = r.json()
    assert r.status_code == 200
    assert body["organization_id"] == "demo-org"
    assert body["actor_id"] == "demo-staff"
    assert body["is_fixture"] is True and "FIXTURE" in body["label"]
    assert c.get("/api/capabilities").json()["capabilities"][1]["status"] == "fixture_only"


def test_fixture_mode_rejected_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="production", auth_mode="fixture")
    monkeypatch.setenv("STRONGSTART_ENVIRONMENT", "production")
    monkeypatch.setenv("STRONGSTART_AUTH_MODE", "fixture")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_defaults_are_safe() -> None:
    s = Settings(_env_file=None)
    assert s.auth_mode == "none" and s.environment == "local"
    assert s.gemini_api_key is None and s.tavily_api_key is None and s.firecrawl_api_key is None


def test_configured_keys_never_appear_in_responses() -> None:
    canary = "CANARY-sk-test-0000000000000000000000"
    c = client(gemini_api_key=SecretStr(canary), auth_mode="fixture")
    for path in [
        "/health/live",
        "/health/ready",
        "/api/capabilities",
        "/api/session",
        "/openapi.json",
    ]:
        assert canary not in c.get(path).text, path
    assert canary not in c.post("/api/funding/discovery-jobs").text


def test_unhandled_errors_return_safe_envelope() -> None:
    app = create_app(Settings(_env_file=None))

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    r = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert r.status_code == 500
    assert r.json()["code"] == "internal_error"
    assert "secret internal detail" not in r.text
    assert r.headers["X-Request-ID"] == r.json()["request_id"]


def test_unknown_route_is_explicit() -> None:
    r = client().get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.json()["code"] == "not_implemented"
