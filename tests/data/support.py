"""Real C service/store construction for memory and PostgreSQL parity."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.applications.deps import get_answer_store
from strongstart_api.features.applications.postgres_store import PostgresAnswerStore
from strongstart_api.features.applications.store import AnswerStore
from strongstart_api.seed import seed_demo
from tests.conftest import BUNDLE_PATH
from tests.data.db_support import Database
from tests.integration.support import decide, publish, save


def client_for(store: AnswerStore, tmp_path: Any) -> tuple[TestClient, Settings]:
    settings = Settings(
        _env_file=None,
        auth_mode="fixture",
        answer_store_backend="memory",
        dev_b_store_dir=tmp_path / "b",
    )
    app = create_app(settings)
    app.dependency_overrides[get_answer_store] = lambda: store
    return TestClient(app), settings


def prepared(db: Database, tmp_path: Any, store: AnswerStore | None = None) -> tuple[Any, ...]:
    db.migrate()
    seed_demo(db.engine, BUNDLE_PATH)
    store = store or PostgresAnswerStore(db.engine)
    c, settings = client_for(store, tmp_path)
    pub = publish(c)
    version = save(
        c, pub, "pf-summary", "  L'été 🦎\r\nLinked: {{fact:demo-fact-children-served}}.  "
    )
    approval = decide(c, version)
    return c, settings, pub, version, approval, store
