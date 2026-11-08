"""DB readiness is truthful (JOB-04 boundary only) and the demo seed is idempotent.

Requires the local PostgreSQL service and STRONGSTART_DATABASE_URL (make db-up).
"""

from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.db import bootstrap_metadata, get_engine, organizations
from strongstart_api.seed import seed_demo
from tests.conftest import BUNDLE_PATH, REPO_ROOT

pytestmark = pytest.mark.db


@pytest.fixture(scope="module")
def database_url() -> str:
    url = Settings().database_url
    if not url:
        pytest.fail("STRONGSTART_DATABASE_URL must be set for db smoke tests")
    return url


@pytest.fixture(scope="module")
def migrated(database_url: str) -> str:
    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.attributes["database_url"] = database_url
    command.upgrade(cfg, "head")
    return database_url


def test_ready_after_migration(migrated: str) -> None:
    app = create_app(Settings(_env_file=None, database_url=migrated))
    r = TestClient(app).get("/health/ready")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ready"


def test_seed_is_idempotent(migrated: str) -> None:
    engine = get_engine(migrated)
    assert seed_demo(engine, BUNDLE_PATH) == 1
    assert seed_demo(engine, BUNDLE_PATH) == 1
    with engine.connect() as conn:
        assert conn.execute(select(func.count()).select_from(organizations)).scalar() == 1
        row = conn.execute(select(organizations)).mappings().one()
        assert row["id"] == "demo-org"
        assert row["is_simulated"] is True and row["provenance_class"] == "simulated"
        meta = conn.execute(
            select(bootstrap_metadata.c.value).where(bootstrap_metadata.c.key == "demo_seed_bundle")
        ).scalar()
        assert meta == "demo-bundle@1"
