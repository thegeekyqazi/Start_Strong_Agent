from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.knowledge.deps import get_knowledge_repository
from strongstart_api.features.knowledge.repository import (
    KnowledgeIntegrityError,
    KnowledgeNotFoundError,
)
from strongstart_contracts import EvidenceBundle, KnowledgeSnapshot, load_fixture_bundle
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


def _client(repository: StubRepository | None, *, auth_mode: str = "fixture") -> TestClient:
    app = create_app(Settings(_env_file=None, auth_mode=auth_mode))
    app.dependency_overrides[get_knowledge_repository] = lambda: repository
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
