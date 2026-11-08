"""DB readiness is truthful (JOB-04 boundary only) and the demo seed is idempotent.

Requires the local PostgreSQL service and STRONGSTART_DATABASE_URL (make db-up).
"""

from __future__ import annotations

import base64
import hashlib
import json

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, insert, select, update

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.db import (
    active_pack_contexts,
    bootstrap_metadata,
    dependency_target_refs,
    dependency_targets,
    evidence_pack_versions,
    evidence_packs,
    fact_source_refs,
    get_engine,
    invalidation_events,
    knowledge_facts,
    knowledge_passages,
    knowledge_source_versions,
    knowledge_sources,
    organizations,
    pack_change_sets,
    pack_changes,
    pack_facts,
    pack_manifest_policies,
    pack_manifest_sources,
    pack_manifests,
    pack_policies,
    validation_dependencies,
    validation_evaluations,
    validation_results,
)
from strongstart_api.features.knowledge.artifacts import LocalArtifactStore
from strongstart_api.features.knowledge.ingestion import TextIngestionService
from strongstart_api.features.knowledge.packs import (
    PackConflictError,
    PackManifestError,
    PackNotFoundError,
    PackService,
)
from strongstart_api.features.knowledge.pdf_ingestion import BoundedPdfParser, PdfIngestionService
from strongstart_api.features.knowledge.repository import (
    KnowledgeIntegrityError,
    PostgresKnowledgeRepository,
)
from strongstart_api.features.validation.repository import (
    SourceValidationRepository,
    ValidationSubjectNotFoundError,
)
from strongstart_api.features.validation.service import (
    NumericValidationService,
    SourceValidationService,
)
from strongstart_api.seed import seed_demo
from strongstart_contracts import (
    DependencyRegistrationRequest,
    NumericValidationRequest,
    PackManifestRequest,
    SourceValidationRequest,
    ValidationDependency,
)
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


def test_numeric_validation_resolves_authorized_fact_and_persists_dependencies(
    migrated: str,
) -> None:
    engine = get_engine(migrated)
    seed_demo(engine, BUNDLE_PATH)
    repository = SourceValidationRepository(engine)
    report = NumericValidationService(repository).evaluate(
        "demo-org",
        "demo-staff",
        NumericValidationRequest(
            pack_version_id="demo-a-v1",
            fact_id="demo-fact-children-served",
            rule_ids=["NUM-03", "NUM-08"],
            claimed_value="120",
            expected_metric_id="children-served",
        ),
    )
    try:
        assert repository.get_numeric_receipt("demo-org", report.evaluation_id) == report
        assert [item.outcome for item in report.results] == ["pass", "pass"]
        assert report.fact_version == 1
        assert {item.kind for item in report.dependencies} >= {
            "fact_version",
            "pack_version",
            "rounding_policy",
            "permission_snapshot",
        }
        with pytest.raises(ValidationSubjectNotFoundError):
            repository.resolve_numeric(
                "other-org",
                NumericValidationRequest(
                    pack_version_id="demo-a-v1", fact_id="demo-fact-children-served"
                ),
            )
    finally:
        _delete_validation_receipt(engine, report.evaluation_id)


def test_pack_replacement_stales_exact_dependents_and_keeps_history(migrated: str) -> None:
    engine = get_engine(migrated)
    seed_demo(engine, BUNDLE_PATH)
    service = PackService(engine)
    policy_v1 = "Approved policy version one"
    policy_v2 = "Approved policy version two"
    policy_hash_v1 = hashlib.sha256(policy_v1.encode()).hexdigest()
    policy_hash_v2 = hashlib.sha256(policy_v2.encode()).hexdigest()
    fact_ids = ("a4-fact-old", "a4-fact-common", "a4-fact-new")
    pack_versions = ("a4-pack-v1", "a4-pack-v2")
    context = "a4-test-application"
    evaluation_id = None
    try:
        with engine.begin() as conn:
            conn.execute(
                insert(knowledge_facts),
                [
                    {
                        "id": fact_id,
                        "fact_version": version,
                        "organization_id": "demo-org",
                        "metric_id": metric,
                        "value_exact": value,
                        "raw_value": value,
                        "unit": "children",
                        "scope": "Demo Org",
                        "population": "children",
                        "reporting_period": "2026",
                        "status": "verified",
                        "provenance_class": "simulated",
                        "is_simulated": True,
                    }
                    for fact_id, version, metric, value in (
                        (fact_ids[0], 1, "served", "120"),
                        (fact_ids[1], 1, "capacity", "50"),
                        (fact_ids[2], 2, "served", "125"),
                    )
                ],
            )
            conn.execute(
                insert(fact_source_refs),
                [
                    {
                        "fact_id": fact_id,
                        "source_version_id": "demo-synthetic-metrics-v1",
                        "locator": "line:1",
                    }
                    for fact_id in fact_ids
                ],
            )
            conn.execute(
                insert(pack_policies),
                [
                    {
                        "policy_id": "a4-writing-policy",
                        "policy_version": version,
                        "organization_id": "demo-org",
                        "content_sha256": content_hash,
                        "content": content,
                        "status": "approved",
                    }
                    for version, content_hash, content in (
                        (1, policy_hash_v1, policy_v1),
                        (2, policy_hash_v2, policy_v2),
                    )
                ],
            )
        fixture = json.loads(
            (REPO_ROOT / "tests/fixtures/demo/a4-pack-replacement.json").read_text(
                encoding="utf-8"
            )
        )
        manifest_a, manifest_b = [
            PackManifestRequest.model_validate(item) for item in fixture["manifests"]
        ]
        bad_manifest = manifest_a.model_copy(
            update={
                "pack_version_id": "a4-bad-pack-v1",
                "bundle_id": "a4-bad-bundle-v1",
                "source_version_ids": ["missing-source-version"],
            }
        )
        with pytest.raises(PackManifestError, match="source_version_not_found"):
            service.create_manifest("demo-org", "demo-staff", bad_manifest)
        with engine.connect() as conn:
            assert conn.execute(
                select(evidence_pack_versions.c.id).where(
                    evidence_pack_versions.c.id == "a4-bad-pack-v1"
                )
            ).scalar_one_or_none() is None
        service.create_manifest("demo-org", "demo-staff", manifest_a)
        service.create_manifest("demo-org", "demo-staff", manifest_b)
        with pytest.raises(PackConflictError):
            service.create_manifest("demo-org", "demo-staff", manifest_a)
        first = service.activate("demo-org", "demo-staff", context, pack_versions[0], None)
        assert first.active.revision == 1 and first.invalidated == []

        for kind, target_id, dependency in (
            (
                "approval",
                "a4-approval",
                ValidationDependency(kind="fact_version", ref_id=fact_ids[0], version="1"),
            ),
            (
                "browser_grant",
                "a4-browser-grant",
                ValidationDependency(kind="policy", ref_id="a4-writing-policy", version="1"),
            ),
            (
                "answer",
                "a4-unaffected-answer",
                ValidationDependency(kind="fact_version", ref_id=fact_ids[1], version="1"),
            ),
        ):
            service.register_target(
                "demo-org",
                DependencyRegistrationRequest(
                    target_kind=kind,
                    target_id=target_id,
                    dependencies=[dependency],
                ),
            )
        with pytest.raises(PackConflictError):
            service.register_target(
                "demo-org",
                DependencyRegistrationRequest(
                    target_kind="approval",
                    target_id="a4-approval",
                    dependencies=[
                        ValidationDependency(
                            kind="fact_version", ref_id=fact_ids[0], version="1"
                        )
                    ],
                ),
            )
        with pytest.raises(PackManifestError, match="dependency_version_invalid"):
            service.register_target(
                "demo-org",
                DependencyRegistrationRequest(
                    target_kind="answer",
                    target_id="a4-invalid-target",
                    dependencies=[
                        ValidationDependency(
                            kind="fact_version", ref_id=fact_ids[0], version="invalid"
                        )
                    ],
                ),
            )

        validation_repository = SourceValidationRepository(engine)
        numeric_report = NumericValidationService(validation_repository).evaluate(
            "demo-org",
            "demo-staff",
            NumericValidationRequest(
                pack_version_id=pack_versions[0],
                fact_id=fact_ids[0],
                rule_ids=["NUM-03"],
                claimed_value="120",
            ),
        )
        evaluation_id = numeric_report.evaluation_id
        before_receipt = validation_repository.get_numeric_receipt("demo-org", evaluation_id)

        replaced = service.activate(
            "demo-org", "demo-staff", context, pack_versions[1], pack_versions[0]
        )
        invalidated = {(item.target_kind, item.target_id) for item in replaced.invalidated}
        assert invalidated >= {
            ("approval", "a4-approval"),
            ("browser_grant", "a4-browser-grant"),
            ("validation", evaluation_id),
        }
        assert ("answer", "a4-unaffected-answer") not in invalidated
        assert service.get_target("demo-org", "approval", "a4-approval").state == "stale"
        assert service.get_target("demo-org", "browser_grant", "a4-browser-grant").state == "stale"
        assert service.get_target("demo-org", "answer", "a4-unaffected-answer").state == "current"
        assert (
            validation_repository.get_numeric_receipt("demo-org", evaluation_id) == before_receipt
        )
        assert service.active_state("demo-org", context).pack_version_id == pack_versions[1]
        assert {
            fact.fact_id
            for fact in PostgresKnowledgeRepository(engine)
            .get_bundle("demo-org", pack_versions[1])
            .facts
        } == {fact_ids[1], fact_ids[2]}
        api = TestClient(
            create_app(
                Settings(_env_file=None, database_url=migrated, auth_mode="fixture")
            )
        )
        assert api.get(f"/api/knowledge/evidence/{pack_versions[0]}").status_code == 409
        active_response = api.get(f"/api/knowledge/evidence/{pack_versions[1]}")
        assert active_response.status_code == 200
        assert active_response.json()["pack_version_id"] == pack_versions[1]
        with pytest.raises(PackConflictError):
            service.require_active("demo-org", context, pack_versions[0])
        with pytest.raises(PackConflictError):
            service.activate("demo-org", "demo-staff", context, pack_versions[0], pack_versions[0])
        repeated = service.activate(
            "demo-org", "demo-staff", context, pack_versions[1], pack_versions[1]
        )
        assert repeated.idempotent is True and repeated.change_set is None
        with pytest.raises(PackNotFoundError):
            service.get_manifest("other-org", pack_versions[1])
    finally:
        if evaluation_id is not None:
            _delete_validation_receipt(engine, evaluation_id)
        with engine.begin() as conn:
            target_ids = ["a4-approval", "a4-browser-grant", "a4-unaffected-answer"]
            if evaluation_id is not None:
                target_ids.append(evaluation_id)
            change_set_ids = list(
                conn.execute(
                    select(pack_change_sets.c.id).where(
                        pack_change_sets.c.application_context == context
                    )
                ).scalars()
            )
            conn.execute(
                delete(invalidation_events).where(
                    invalidation_events.c.change_set_id.in_(change_set_ids)
                )
            )
            conn.execute(
                delete(dependency_target_refs).where(
                    dependency_target_refs.c.target_id.in_(target_ids)
                )
            )
            conn.execute(
                delete(dependency_targets).where(dependency_targets.c.target_id.in_(target_ids))
            )
            conn.execute(
                delete(pack_changes).where(pack_changes.c.change_set_id.in_(change_set_ids))
            )
            conn.execute(delete(pack_change_sets).where(pack_change_sets.c.id.in_(change_set_ids)))
            conn.execute(
                delete(active_pack_contexts).where(
                    active_pack_contexts.c.application_context == context
                )
            )
            conn.execute(
                delete(pack_manifest_policies).where(
                    pack_manifest_policies.c.pack_version_id.in_(pack_versions)
                )
            )
            conn.execute(
                delete(pack_manifest_sources).where(
                    pack_manifest_sources.c.pack_version_id.in_(pack_versions)
                )
            )
            conn.execute(delete(pack_facts).where(pack_facts.c.pack_version_id.in_(pack_versions)))
            conn.execute(
                delete(pack_manifests).where(pack_manifests.c.pack_version_id.in_(pack_versions))
            )
            conn.execute(
                delete(evidence_pack_versions).where(evidence_pack_versions.c.id.in_(pack_versions))
            )
            conn.execute(delete(evidence_packs).where(evidence_packs.c.id == "a4-pack"))
            conn.execute(delete(fact_source_refs).where(fact_source_refs.c.fact_id.in_(fact_ids)))
            conn.execute(delete(knowledge_facts).where(knowledge_facts.c.id.in_(fact_ids)))
            conn.execute(
                delete(pack_policies).where(pack_policies.c.policy_id == "a4-writing-policy")
            )


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
