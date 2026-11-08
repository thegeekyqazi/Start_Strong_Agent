"""DB readiness is truthful (JOB-04 boundary only) and the demo seed is idempotent.

Requires the local PostgreSQL service and STRONGSTART_DATABASE_URL (make db-up).
"""

from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.db import (
    bootstrap_metadata,
    evidence_pack_versions,
    fact_source_refs,
    get_engine,
    knowledge_facts,
    knowledge_source_versions,
    knowledge_sources,
    organizations,
    pack_facts,
)
from strongstart_api.features.knowledge.repository import (
    KnowledgeIntegrityError,
    PostgresKnowledgeRepository,
)
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
        for table in (
            knowledge_sources,
            knowledge_source_versions,
            knowledge_facts,
            evidence_pack_versions,
            fact_source_refs,
            pack_facts,
        ):
            assert conn.execute(select(func.count()).select_from(table)).scalar() == 1


def test_seeded_bundle_preserves_exact_fact_and_verified_source(migrated: str) -> None:
    engine = get_engine(migrated)
    seed_demo(engine, BUNDLE_PATH)
    bundle = PostgresKnowledgeRepository(engine).get_bundle("demo-org", "demo-a-v1")
    fact = bundle.facts[0]
    assert (fact.value, fact.raw_value, fact.unit) == ("120", "120", "children")
    assert fact.scope == "Demo Org, all programs"
    assert fact.population == "children enrolled"
    assert fact.reporting_period == "2025-09/2026-06"
    ref = fact.supporting_refs[0]
    assert ref.source_version_id == "demo-synthetic-metrics-v1"
    assert ref.locator == "line:1"
    assert ref.content_hash is not None and ref.verification_status == "verified"


def test_tampered_source_is_withheld(migrated: str) -> None:
    engine = get_engine(migrated)
    seed_demo(engine, BUNDLE_PATH)
    with engine.connect() as conn:
        original = conn.execute(
            select(knowledge_source_versions.c.content_bytes).where(
                knowledge_source_versions.c.id == "demo-synthetic-metrics-v1"
            )
        ).scalar_one()
    try:
        with engine.begin() as conn:
            conn.execute(
                update(knowledge_source_versions)
                .where(knowledge_source_versions.c.id == "demo-synthetic-metrics-v1")
                .values(content_bytes=b"tampered")
            )
        with pytest.raises(KnowledgeIntegrityError):
            PostgresKnowledgeRepository(engine).get_bundle("demo-org", "demo-a-v1")
    finally:
        with engine.begin() as conn:
            conn.execute(
                update(knowledge_source_versions)
                .where(knowledge_source_versions.c.id == "demo-synthetic-metrics-v1")
                .values(content_bytes=original)
            )
