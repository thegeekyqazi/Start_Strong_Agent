from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.validation.deps import (
    get_numeric_validation_service,
    get_source_validation_service,
    get_validation_repository,
)
from strongstart_api.features.validation.repository import (
    ValidationReceiptNotFoundError,
    ValidationSubjectNotFoundError,
)
from strongstart_contracts import (
    NumericValidationReport,
    NumericValidationRequest,
    SourceValidationReport,
    SourceValidationRequest,
    ValidationDependency,
    ValidationResult,
)


def _report() -> SourceValidationReport:
    return SourceValidationReport(
        evaluation_id="val-test",
        organization_id="demo-org",
        source_version_id="srcv-test",
        input_sha256="a" * 64,
        evaluator_build="test-v1",
        frozen_time=datetime(2026, 11, 8, tzinfo=UTC),
        results=[
            ValidationResult(
                rule_id="SRC-01",
                rule_version="a3-src-1",
                outcome="pass",
                reason_code="authorized_source_version_resolved",
            )
        ],
        dependencies=[
            ValidationDependency(
                kind="source_version",
                ref_id="srcv-test",
                version="a" * 64,
                content_hash="a" * 64,
            )
        ],
    )


class StubService:
    def __init__(self, *, missing: bool = False) -> None:
        self.missing = missing
        self.calls: list[tuple[str, str, SourceValidationRequest]] = []

    def evaluate(
        self, organization_id: str, actor_id: str, request: SourceValidationRequest
    ) -> SourceValidationReport:
        self.calls.append((organization_id, actor_id, request))
        if self.missing:
            raise ValidationSubjectNotFoundError
        return _report()


class StubRepository:
    def __init__(self, *, missing: bool = False) -> None:
        self.missing = missing
        self.calls: list[tuple[str, str]] = []

    def get_receipt(self, organization_id: str, evaluation_id: str) -> SourceValidationReport:
        self.calls.append((organization_id, evaluation_id))
        if self.missing:
            raise ValidationReceiptNotFoundError
        return _report()


class StubNumericService:
    def __init__(self, *, missing: bool = False) -> None:
        self.missing = missing
        self.calls: list[tuple[str, str, NumericValidationRequest]] = []

    def evaluate(
        self, organization_id: str, actor_id: str, request: NumericValidationRequest
    ) -> NumericValidationReport:
        self.calls.append((organization_id, actor_id, request))
        if self.missing:
            raise ValidationSubjectNotFoundError
        return NumericValidationReport(
            evaluation_id="val-num",
            organization_id=organization_id,
            pack_version_id=request.pack_version_id,
            fact_id=request.fact_id,
            fact_version=1,
            input_sha256="b" * 64,
            evaluator_build="test",
            frozen_time=datetime(2026, 11, 8, tzinfo=UTC),
            results=[],
            dependencies=[],
        )


def _client(
    service: StubService | None = None,
    repository: StubRepository | None = None,
    numeric_service: StubNumericService | None = None,
    *,
    auth_mode: str = "fixture",
) -> TestClient:
    app = create_app(Settings(_env_file=None, auth_mode=auth_mode))
    app.dependency_overrides[get_source_validation_service] = lambda: service
    app.dependency_overrides[get_validation_repository] = lambda: repository
    app.dependency_overrides[get_numeric_validation_service] = lambda: numeric_service
    return TestClient(app)


def test_source_validation_uses_server_identity() -> None:
    service = StubService()
    response = _client(service).post(
        "/api/validation/source?organization_id=other-org",
        headers={"X-Org-Id": "other-org"},
        json={"source_version_id": "srcv-test", "rule_ids": ["SRC-01"]},
    )
    assert response.status_code == 201
    assert response.json()["organization_id"] == "demo-org"
    assert service.calls[0][0:2] == ("demo-org", "demo-staff")


def test_identity_is_required_before_validation_service() -> None:
    service = StubService()
    response = _client(service, auth_mode="none").post(
        "/api/validation/source",
        json={"source_version_id": "srcv-test", "rule_ids": ["SRC-01"]},
    )
    assert response.status_code == 401
    assert service.calls == []


def test_request_rejects_unknown_rules_duplicates_and_identity_fields() -> None:
    client = _client(StubService())
    bodies = (
        {"source_version_id": "srcv-test", "rule_ids": ["SRC-99"]},
        {"source_version_id": "srcv-test", "rule_ids": ["SRC-01", "SRC-01"]},
        {"source_version_id": "srcv-test", "organization_id": "other-org"},
    )
    for body in bodies:
        assert client.post("/api/validation/source", json=body).status_code == 422


def test_missing_and_cross_org_subjects_have_same_safe_response() -> None:
    client = _client(StubService(missing=True))
    first = client.post("/api/validation/source", json={"source_version_id": "missing"})
    second = client.post("/api/validation/source", json={"source_version_id": "other-org"})
    assert first.status_code == second.status_code == 404
    first_body, second_body = first.json(), second.json()
    first_body.pop("request_id")
    second_body.pop("request_id")
    assert first_body == second_body


def test_receipt_read_is_server_scoped_and_non_disclosing() -> None:
    repository = StubRepository()
    response = _client(repository=repository).get(
        "/api/validation/receipts/val-test?organization_id=other-org"
    )
    assert response.status_code == 200
    assert repository.calls == [("demo-org", "val-test")]

    hidden = _client(repository=StubRepository(missing=True)).get(
        "/api/validation/receipts/val-private"
    )
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "forbidden"


def test_unconfigured_validation_is_explicit() -> None:
    response = _client().post("/api/validation/source", json={"source_version_id": "srcv-test"})
    assert response.status_code == 503
    assert response.json()["code"] == "capability_unavailable"


def test_rule_capabilities_are_honest_and_complete() -> None:
    response = _client().get("/api/validation/rules")
    assert response.status_code == 200
    rules = response.json()
    assert [item["rule_id"] for item in rules] == [
        f"SRC-{number:02d}" for number in range(1, 11)
    ] + [f"NUM-{number:02d}" for number in range(1, 13)]
    assert {item["state"] for item in rules} == {"implemented"}


def test_numeric_validation_uses_server_identity_and_hides_cross_org_fact() -> None:
    service = StubNumericService()
    response = _client(numeric_service=service).post(
        "/api/validation/numeric?organization_id=other",
        json={"pack_version_id": "pack-v1", "fact_id": "fact-1", "rule_ids": ["NUM-03"]},
    )
    assert response.status_code == 201
    assert service.calls[0][0:2] == ("demo-org", "demo-staff")

    hidden = _client(numeric_service=StubNumericService(missing=True)).post(
        "/api/validation/numeric",
        json={"pack_version_id": "other-pack", "fact_id": "other-fact"},
    )
    assert hidden.status_code == 404


def test_numeric_request_rejects_duplicate_unknown_rules_and_identity_fields() -> None:
    client = _client(numeric_service=StubNumericService())
    base = {"pack_version_id": "pack-v1", "fact_id": "fact-1"}
    for extra in (
        {"rule_ids": ["NUM-99"]},
        {"rule_ids": ["NUM-03", "NUM-03"]},
        {"organization_id": "other"},
    ):
        assert client.post("/api/validation/numeric", json={**base, **extra}).status_code == 422
