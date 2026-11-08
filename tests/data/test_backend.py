"""No-secret backend selection/unavailability regressions."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings


@pytest.mark.parametrize("backend", ["unconfigured", "postgres"])
def test_no_url_cannot_create_an_empty_memory_success(backend):
    settings = Settings(_env_file=None, auth_mode="fixture", answer_store_backend=backend)
    app = create_app(settings)
    with TestClient(app) as c:
        assert app.state.c3_answer_store.backend == "unconfigured"
        response = c.get("/api/applications/answers/mission-q1")
        assert response.status_code == 503
        assert response.json()["details"]["reason"] in {
            "answer_store_unconfigured",
            "postgres_url_missing",
        }
        assert c.get("/health/live").status_code == 200
        assert c.get("/health/ready").status_code == 503


def test_unreachable_database_has_sanitized_failure_and_no_fallback():
    settings = Settings(
        _env_file=None,
        auth_mode="fixture",
        answer_store_backend="postgres",
        database_url="postgresql://user:private-canary@127.0.0.1:1/missing",
        db_connect_timeout_seconds=1,
    )
    app = create_app(settings)
    with TestClient(app) as c:
        response = c.get("/api/applications/answers/mission-q1")
        assert response.status_code == 503
        assert app.state.c3_answer_store.backend == "postgres"
        assert "private-canary" not in response.text + repr(settings) + settings.model_dump_json()
        assert c.get("/health/ready").status_code == 503


def test_memory_is_explicit_and_fixture_labels_remain():
    with TestClient(
        create_app(Settings(_env_file=None, auth_mode="fixture", answer_store_backend="memory"))
    ) as c:
        history = c.get("/api/applications/answers/mission-q1").json()
        assert history["store"] == {"backend": "memory", "durable": False}
        assert history["store_is_fixture"]
