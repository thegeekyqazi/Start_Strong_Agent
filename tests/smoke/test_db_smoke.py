"""DB readiness is truthful (JOB-04 boundary only) and the demo seed is idempotent.

Requires the local PostgreSQL service and STRONGSTART_DATABASE_URL (make db-up).
"""

from __future__ import annotations

import base64

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, insert, select, update

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.db import (
    bootstrap_metadata,
    evidence_pack_versions,
    fact_source_refs,
    get_engine,
    knowledge_facts,
    knowledge_passages,
    knowledge_source_versions,
    knowledge_sources,
    organizations,
    pack_facts,
    validation_dependencies,
    validation_evaluations,
    validation_results,
)
from strongstart_api.features.knowledge.artifacts import LocalArtifactStore
from strongstart_api.features.knowledge.ingestion import TextIngestionService
from strongstart_api.features.knowledge.pdf_ingestion import BoundedPdfParser, PdfIngestionService
from strongstart_api.features.knowledge.repository import (
    KnowledgeIntegrityError,
    PostgresKnowledgeRepository,
)
from strongstart_api.features.validation.repository import (
    SourceValidationRepository,
    ValidationSubjectNotFoundError,
)
from strongstart_api.features.validation.service import SourceValidationService
from strongstart_api.seed import seed_demo
from strongstart_contracts import SourceValidationRequest
from tests.conftest import BUNDLE_PATH, REPO_ROOT
from tests.knowledge.pdf_fixture import make_text_pdf

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


def test_text_ingestion_persists_artifact_and_exact_passage(migrated: str, tmp_path) -> None:
    engine = get_engine(migrated)
    seed_demo(engine, BUNDLE_PATH)
    artifacts = LocalArtifactStore(tmp_path)
    service = TextIngestionService(engine, artifacts, max_bytes=1_000)
    result = service.ingest("demo-org", "Staff notes", "First line\nSecond line", is_fixture=True)
    validation_report = None
    try:
        assert artifacts.read("demo-org", result.artifact_key) == b"First line\nSecond line"
        snapshot = PostgresKnowledgeRepository(engine, artifacts).get_snapshot(
            "demo-org", is_fixture=True
        )
        imported = next(
            item
            for item in snapshot.source_versions
            if item.source_reference.source_version_id == result.source_version_id
        )
        passage = next(item for item in snapshot.passages if item.passage_id == result.passage_id)
        assert imported.source_reference.content_hash == result.content_sha256
        assert imported.source_reference.provenance.is_simulated is True
        assert passage.locator == "char:0-22"
        assert passage.exact_text == "First line\nSecond line"
        validation_report = SourceValidationService(
            SourceValidationRepository(engine, artifacts)
        ).evaluate(
            "demo-org",
            "demo-staff",
            SourceValidationRequest(
                source_version_id=result.source_version_id,
                rule_ids=["SRC-02", "SRC-05", "SRC-08", "SRC-10"],
            ),
        )
        assert {item.rule_id: item.outcome for item in validation_report.results} == {
            "SRC-02": "pass",
            "SRC-05": "pass",
            "SRC-08": "pass",
            "SRC-10": "pass",
        }
    finally:
        if validation_report is not None:
            _delete_validation_receipt(engine, validation_report.evaluation_id)
        with engine.begin() as conn:
            conn.execute(
                delete(knowledge_passages).where(knowledge_passages.c.id == result.passage_id)
            )
            conn.execute(
                delete(knowledge_source_versions).where(
                    knowledge_source_versions.c.id == result.source_version_id
                )
            )
            conn.execute(
                delete(knowledge_sources).where(knowledge_sources.c.id == result.source_id)
            )


def test_pdf_ingestion_and_authorized_retrieval(migrated: str, tmp_path) -> None:
    engine = get_engine(migrated)
    seed_demo(engine, BUNDLE_PATH)
    artifacts = LocalArtifactStore(tmp_path)
    service = PdfIngestionService(
        engine,
        artifacts,
        BoundedPdfParser(max_bytes=10_000, max_pages=5, max_chars=1_000),
    )
    encoded = base64.b64encode(make_text_pdf("Unique grant readiness evidence")).decode("ascii")
    result = service.ingest("demo-org", "Readiness guide", encoded, is_fixture=True)
    try:
        repository = PostgresKnowledgeRepository(engine, artifacts)
        retrieval = repository.retrieve("demo-org", "grant readiness", limit=5)
        assert len(retrieval.hits) == 1
        hit = retrieval.hits[0]
        assert hit.passage.locator == "page:1"
        assert hit.passage.source_version_id == result.source_version_id
        assert hit.source_reference.content_hash == result.content_sha256
        assert hit.source_reference.provenance.is_simulated is True
        assert repository.retrieve("unknown-org", "grant readiness", limit=5).hits == []
    finally:
        with engine.begin() as conn:
            conn.execute(
                delete(knowledge_passages).where(
                    knowledge_passages.c.source_version_id == result.source_version_id
                )
            )
            conn.execute(
                delete(knowledge_source_versions).where(
                    knowledge_source_versions.c.id == result.source_version_id
                )
            )
            conn.execute(
                delete(knowledge_sources).where(knowledge_sources.c.id == result.source_id)
            )


def _delete_validation_receipt(engine, evaluation_id: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            delete(validation_dependencies).where(
                validation_dependencies.c.evaluation_id == evaluation_id
            )
        )
        conn.execute(
            delete(validation_results).where(validation_results.c.evaluation_id == evaluation_id)
        )
        conn.execute(
            delete(validation_evaluations).where(validation_evaluations.c.id == evaluation_id)
        )


def test_source_validation_persists_and_replays_exact_receipt(migrated: str) -> None:
    engine = get_engine(migrated)
    seed_demo(engine, BUNDLE_PATH)
    repository = SourceValidationRepository(engine)
    service = SourceValidationService(repository)
    report = service.evaluate(
        "demo-org",
        "demo-staff",
        SourceValidationRequest(
            source_version_id="demo-synthetic-metrics-v1",
            locator="line:1",
            claimed_quote=(
                "SIMULATED FIXTURE - not partner data. Children served: 120; "
                "population: children enrolled; reporting period: 2025-09/2026-06."
            ),
        ),
    )
    try:
        replayed = repository.get_receipt("demo-org", report.evaluation_id)
        assert replayed == report
        outcomes = {result.rule_id: result.outcome for result in report.results}
        assert outcomes["SRC-01"] == outcomes["SRC-02"] == outcomes["SRC-03"] == "pass"
        assert outcomes["SRC-04"] == "pass"
        assert outcomes["SRC-10"] == "fail"  # legacy seed truthfully lacks parser provenance
        assert {dependency.kind for dependency in report.dependencies} >= {
            "source_version",
            "artifact_hash",
            "permission_snapshot",
        }
    finally:
        _delete_validation_receipt(engine, report.evaluation_id)


def test_source_validation_detects_tampering_and_hides_other_org(migrated: str) -> None:
    engine = get_engine(migrated)
    seed_demo(engine, BUNDLE_PATH)
    repository = SourceValidationRepository(engine)
    with engine.connect() as conn:
        original = conn.execute(
            select(knowledge_source_versions.c.content_bytes).where(
                knowledge_source_versions.c.id == "demo-synthetic-metrics-v1"
            )
        ).scalar_one()
    report = None
    try:
        with engine.begin() as conn:
            conn.execute(
                update(knowledge_source_versions)
                .where(knowledge_source_versions.c.id == "demo-synthetic-metrics-v1")
                .values(content_bytes=b"tampered")
            )
        report = SourceValidationService(repository).evaluate(
            "demo-org",
            "demo-staff",
            SourceValidationRequest(
                source_version_id="demo-synthetic-metrics-v1", rule_ids=["SRC-02"]
            ),
        )
        assert report.results[0].outcome == "fail"
        assert report.results[0].reason_code == "integrity_mismatch"
        with pytest.raises(ValidationSubjectNotFoundError):
            repository.resolve_source(
                "other-org",
                "demo-synthetic-metrics-v1",
                locator=None,
                claimed_quote=None,
            )
    finally:
        with engine.begin() as conn:
            conn.execute(
                update(knowledge_source_versions)
                .where(knowledge_source_versions.c.id == "demo-synthetic-metrics-v1")
                .values(content_bytes=original)
            )
        if report is not None:
            _delete_validation_receipt(engine, report.evaluation_id)


def test_source_validation_detects_hash_and_canonical_url_duplicates(migrated: str) -> None:
    engine = get_engine(migrated)
    seed_demo(engine, BUNDLE_PATH)
    with engine.connect() as conn:
        original = (
            conn.execute(
                select(knowledge_source_versions).where(
                    knowledge_source_versions.c.id == "demo-synthetic-metrics-v1"
                )
            )
            .mappings()
            .one()
        )
    report = None
    try:
        with engine.begin() as conn:
            conn.execute(
                update(knowledge_sources)
                .where(knowledge_sources.c.id == "demo-synthetic-metrics")
                .values(canonical_url="https://example.test/guide")
            )
            conn.execute(
                insert(knowledge_sources).values(
                    id="demo-duplicate-source",
                    organization_id="demo-org",
                    title="Duplicate origin fixture",
                    canonical_url="https://example.test/guide",
                    provenance_class="simulated",
                    is_simulated=True,
                )
            )
            conn.execute(
                insert(knowledge_source_versions).values(
                    id="demo-duplicate-version",
                    source_id="demo-duplicate-source",
                    organization_id="demo-org",
                    media_type=original["media_type"],
                    content_bytes=original["content_bytes"],
                    content_sha256=original["content_sha256"],
                    size_bytes=original["size_bytes"],
                    publication_status="unknown",
                    verification_status="unverified",
                )
            )
        report = SourceValidationService(SourceValidationRepository(engine)).evaluate(
            "demo-org",
            "demo-staff",
            SourceValidationRequest(
                source_version_id="demo-synthetic-metrics-v1", rule_ids=["SRC-06"]
            ),
        )
        result = report.results[0]
        assert (result.outcome, result.reason_code) == (
            "needs_review",
            "duplicate_source_detected",
        )
        assert result.observed == {
            "artifact_version_ids": ["demo-duplicate-version"],
            "canonical_url_source_ids": ["demo-duplicate-source"],
            "canonical_url_recorded": True,
        }
    finally:
        if report is not None:
            _delete_validation_receipt(engine, report.evaluation_id)
        with engine.begin() as conn:
            conn.execute(
                delete(knowledge_source_versions).where(
                    knowledge_source_versions.c.id == "demo-duplicate-version"
                )
            )
            conn.execute(
                delete(knowledge_sources).where(knowledge_sources.c.id == "demo-duplicate-source")
            )
            conn.execute(
                update(knowledge_sources)
                .where(knowledge_sources.c.id == "demo-synthetic-metrics")
                .values(canonical_url=None)
            )


def test_source_validation_api_round_trip_uses_fixture_identity(migrated: str) -> None:
    engine = get_engine(migrated)
    seed_demo(engine, BUNDLE_PATH)
    client = TestClient(
        create_app(
            Settings(
                _env_file=None,
                database_url=migrated,
                auth_mode="fixture",
            )
        )
    )
    response = client.post(
        "/api/validation/source?organization_id=other-org",
        headers={"X-Org-Id": "other-org"},
        json={
            "source_version_id": "demo-synthetic-metrics-v1",
            "rule_ids": ["SRC-01"],
        },
    )
    assert response.status_code == 201, response.text
    report = response.json()
    try:
        assert report["organization_id"] == "demo-org"
        assert report["results"][0]["outcome"] == "pass"
        replay = client.get(f"/api/validation/receipts/{report['evaluation_id']}")
        assert replay.status_code == 200
        assert replay.json() == report
    finally:
        _delete_validation_receipt(engine, report["evaluation_id"])
