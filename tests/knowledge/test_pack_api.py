from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.knowledge.deps import get_pack_service
from strongstart_api.features.knowledge.packs import PackConflictError, PackNotFoundError
from strongstart_contracts import (
    ActivePackState,
    PackManifest,
    PackManifestRequest,
)

MANIFEST_BODY = {
    "pack_id": "pack-a",
    "pack_version_id": "pack-a-v1",
    "bundle_id": "bundle-a-v1",
    "application_context": "application-1",
    "manifest_schema_version": "1",
    "mapping_version": "pack-mapping-v1",
    "parser_version": "parser-v1",
    "locale": "en-CA",
    "access_labels": ["staff"],
    "facts": [{"fact_id": "fact-1", "fact_version": 1}],
    "source_version_ids": ["source-v1"],
    "policies": [],
    "coverage_notes": [],
    "provenance_class": "simulated",
    "is_simulated": True,
}


class StubPackService:
    def __init__(self, *, missing: bool = False, conflict: bool = False) -> None:
        self.missing = missing
        self.conflict = conflict
        self.calls: list[tuple[str, str, PackManifestRequest]] = []

    def create_manifest(
        self, organization_id: str, actor_id: str, request: PackManifestRequest
    ) -> PackManifest:
        self.calls.append((organization_id, actor_id, request))
        if self.missing:
            raise PackNotFoundError
        return PackManifest(
            organization_id=organization_id,
            manifest_sha256="a" * 64,
            created_at=datetime(2026, 11, 8, tzinfo=UTC),
            request=request,
        )

    def activate(self, *args: object) -> object:
        del args
        if self.conflict:
            raise PackConflictError
        raise PackNotFoundError

    def active_state(self, organization_id: str, context: str) -> ActivePackState:
        if self.missing:
            raise PackNotFoundError
        return ActivePackState(
            organization_id=organization_id,
            application_context=context,
            pack_version_id="pack-a-v1",
            revision=1,
        )


def client(service: StubPackService, *, auth_mode: str = "fixture") -> TestClient:
    app = create_app(Settings(_env_file=None, auth_mode=auth_mode))
    app.dependency_overrides[get_pack_service] = lambda: service
    return TestClient(app)


def test_manifest_uses_server_identity_and_strict_body() -> None:
    service = StubPackService()
    response = client(service).post(
        "/api/knowledge/packs/manifests?organization_id=other-org", json=MANIFEST_BODY
    )
    assert response.status_code == 201
    assert service.calls[0][0:2] == ("demo-org", "demo-staff")
    invalid = client(service).post(
        "/api/knowledge/packs/manifests",
        json=MANIFEST_BODY | {"organization_id": "other-org"},
    )
    assert invalid.status_code == 422


def test_pack_errors_are_non_disclosing_and_conflicts_are_explicit() -> None:
    missing = client(StubPackService(missing=True)).post(
        "/api/knowledge/packs/manifests", json=MANIFEST_BODY
    )
    assert missing.status_code == 404
    conflict = client(StubPackService(conflict=True)).post(
        "/api/knowledge/packs/contexts/application-1/activate/pack-b-v1",
        json={"expected_active_pack_version_id": "pack-a-v1"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "stale_snapshot"


def test_active_pack_is_scoped_to_server_identity() -> None:
    response = client(StubPackService()).get(
        "/api/knowledge/packs/contexts/application-1/active?organization_id=other"
    )
    assert response.status_code == 200
    assert response.json()["organization_id"] == "demo-org"
