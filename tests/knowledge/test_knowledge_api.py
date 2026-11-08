from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.knowledge.deps import (
    get_knowledge_repository,
    get_text_ingestion_service,
)
from strongstart_api.features.knowledge.ingestion import TextIngestionError
from strongstart_api.features.knowledge.repository import (
    KnowledgeIntegrityError,
    KnowledgeNotFoundError,
)
from strongstart_contracts import (
    EvidenceBundle,
    KnowledgeRetrievalResult,
    KnowledgeSnapshot,
    Provenance,
    TextSourceImportResult,
    load_fixture_bundle,
)
from tests.conftest import BUNDLE_PATH


class StubRepository:
    def __init__(self, outcome: str = "ok") -> None:
        self.outcome = outcome
        self.organizations: list[str] = []
        self.bundle = load_fixture_bundle(BUNDLE_PATH).evidence_bundles[0]

    def get_snapshot(self, organization_id: str, *, is_fixture: bool) -> KnowledgeSnapshot:
        self.organizations.append(organization_id)
        if self.outcome == "integrity":
            raise KnowledgeIntegrityError
        return KnowledgeSnapshot(
            organization_id=organization_id,
            generated_at=datetime.now(UTC),
            source_versions=[],
            passages=[],
            evidence_bundles=[self.bundle],
            is_fixture=is_fixture,
        )

    def get_bundle(self, organization_id: str, pack_version_id: str) -> EvidenceBundle:
        self.organizations.append(organization_id)
        if self.outcome == "missing" or pack_version_id != self.bundle.pack_version_id:
            raise KnowledgeNotFoundError
        if self.outcome == "integrity":
            raise KnowledgeIntegrityError
        return self.bundle

    def retrieve(self, organization_id: str, query: str, *, limit: int) -> KnowledgeRetrievalResult:
        self.organizations.append(organization_id)
        if self.outcome == "integrity":
            raise KnowledgeIntegrityError
        return KnowledgeRetrievalResult(
            organization_id=organization_id,
            query=query,
            hits=[],
            truncated=False,
        )


def _client(repository: StubRepository | None, *, auth_mode: str = "fixture") -> TestClient:
    app = create_app(Settings(_env_file=None, auth_mode=auth_mode))
    app.dependency_overrides[get_knowledge_repository] = lambda: repository
    return TestClient(app)


class StubIngestionService:
    def __init__(self, *, reject: bool = False) -> None:
        self.reject = reject
        self.calls: list[tuple[str, str, str, bool]] = []

    def ingest(
        self, organization_id: str, title: str, text: str, *, is_fixture: bool
    ) -> TextSourceImportResult:
        self.calls.append((organization_id, title, text, is_fixture))
        if self.reject:
            raise TextIngestionError("text contains a forbidden NUL character")
        return TextSourceImportResult(
            source_id="src-test",
            source_version_id="srcv-test",
            passage_id="pass-test",
            artifact_key="sha256-" + "a" * 64,
            content_sha256="a" * 64,
            size_bytes=4,
            media_type="text/plain; charset=utf-8",
            parser_name="plain_text_utf8",
            parser_version="1",
            warnings=[],
            locator="char:0-4",
            provenance=Provenance(provenance_class="simulated", is_simulated=True, note="fixture"),
        )


def _ingestion_client(
    service: StubIngestionService | None, *, auth_mode: str = "fixture"
) -> TestClient:
    app = create_app(Settings(_env_file=None, auth_mode=auth_mode))
    app.dependency_overrides[get_text_ingestion_service] = lambda: service
    return TestClient(app)


def test_snapshot_requires_identity_before_repository() -> None:
    repository = StubRepository()
    response = _client(repository, auth_mode="none").get("/api/knowledge/snapshot")
    assert response.status_code == 401
    assert repository.organizations == []


def test_server_identity_scopes_snapshot_even_with_client_org_claims() -> None:
    repository = StubRepository()
    response = _client(repository).get(
        "/api/knowledge/snapshot?organization_id=other-org",
        headers={"X-Org-Id": "other-org"},
    )
    assert response.status_code == 200
    assert response.json()["organization_id"] == "demo-org"
    assert response.json()["is_fixture"] is True
    assert repository.organizations == ["demo-org"]


def test_missing_and_other_org_pack_share_safe_response() -> None:
    repository = StubRepository("missing")
    client = _client(repository)
    missing = client.get("/api/knowledge/evidence/missing-pack")
    hidden = client.get("/api/knowledge/evidence/other-org-pack")
    assert (missing.status_code, missing.json()["code"], missing.json()["message"]) == (
        hidden.status_code,
        hidden.json()["code"],
        hidden.json()["message"],
    )
    assert missing.status_code == 404 and missing.json()["code"] == "forbidden"


def test_integrity_failure_withholds_snapshot_and_bundle() -> None:
    client = _client(StubRepository("integrity"))
    for path in ("/api/knowledge/snapshot", "/api/knowledge/evidence/demo-a-v1"):
        response = client.get(path)
        assert response.status_code == 500
        assert response.json()["details"]["reason"] == "integrity_failure"
        assert "source failed integrity" in response.json()["message"]


def test_unconfigured_repository_is_explicit() -> None:
    response = _client(None).get("/api/knowledge/snapshot")
    assert response.status_code == 503
    assert response.json()["code"] == "capability_unavailable"


def test_availability_does_not_claim_storage_when_database_unset() -> None:
    response = _client(None).get("/api/knowledge/availability")
    assert response.status_code == 200
    assert response.json()["storage"] == "unconfigured"
    assert response.json()["status"] == "unavailable"


def test_text_import_uses_server_identity_and_fixture_provenance() -> None:
    service = StubIngestionService()
    response = _ingestion_client(service).post(
        "/api/knowledge/sources/import-text?organization_id=other-org",
        json={"title": "  Staff notes  ", "text": "test"},
        headers={"X-Org-Id": "other-org"},
    )
    assert response.status_code == 201
    assert response.json()["provenance"]["is_simulated"] is True
    assert service.calls == [("demo-org", "  Staff notes  ", "test", True)]


def test_text_import_requires_identity_before_service() -> None:
    service = StubIngestionService()
    response = _ingestion_client(service, auth_mode="none").post(
        "/api/knowledge/sources/import-text", json={"title": "Notes", "text": "test"}
    )
    assert response.status_code == 401
    assert service.calls == []


def test_text_import_reports_bounded_validation_failure() -> None:
    response = _ingestion_client(StubIngestionService(reject=True)).post(
        "/api/knowledge/sources/import-text", json={"title": "Notes", "text": "bad"}
    )
    assert response.status_code == 422
    assert response.json()["code"] == "validation_failed"
    assert response.json()["details"]["reason"] == "invalid_text_source"


def test_retrieval_is_server_scoped_and_bounded() -> None:
    repository = StubRepository()
    response = _client(repository).get(
        "/api/knowledge/retrieve?query=grant%20evidence&limit=25&organization_id=other-org"
    )
    assert response.status_code == 200
    assert response.json()["organization_id"] == "demo-org"
    assert response.json()["retrieval_method"] == "lexical-v1"
    assert repository.organizations == ["demo-org"]


def test_retrieval_withholds_results_on_artifact_integrity_failure() -> None:
    response = _client(StubRepository("integrity")).get("/api/knowledge/retrieve?query=grant")
    assert response.status_code == 500
    assert response.json()["details"]["reason"] == "integrity_failure"
