"""Consumer-shaped contract test for the public ApplicationDefinitionReader (BND-16, BND-54).

This file imports ONLY the supported public entry points a consumer (C2b) may use:
``strongstart_contracts.application_publication`` and
``strongstart_api.features.automation.public``. It wires a tiny consumer route the way C
would, then runs it against a fixture reader double AND the real local repository.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.automation.public import (
    build_application_definition_reader,
    get_application_definition_reader,
)
from strongstart_api.identity import Identity
from strongstart_contracts.application_publication import (
    ApplicationDefinitionNotFound,
    ApplicationDefinitionReader,
    PublishedApplicationVersion,
)

SAMPLE = (
    Path(__file__).resolve().parents[1] / "fixtures/automation/published-definition-v1.sample.json"
)
ReaderDep = Annotated[ApplicationDefinitionReader, Depends(get_application_definition_reader)]


def consumer_app(settings: Settings) -> FastAPI:
    """What a C2b workspace source would do: server org, exact question-set ID, no fallback."""
    app = create_app(settings)

    @app.get("/consumer/questions/{question_set_id}")
    def questions(question_set_id: str, identity: Identity, reader: ReaderDep) -> dict[str, Any]:
        try:
            v = reader.get_version(identity.organization_id, question_set_id)
        except ApplicationDefinitionNotFound:
            raise HTTPException(404) from None  # never fall back to the old fixture
        return {
            "question_ids": [q.question_id for q in v.question_set.questions],
            "question_versions": sorted({q.question_version for q in v.question_set.questions}),
            "unresolved": len(v.unresolved),
            "is_fixture_record": v.is_fixture,
            "simulated": v.provenance.is_simulated,
        }

    return app


class FixtureReader:
    """A consumer-side double built from the committed sample (labelled fixture adapter)."""

    is_fixture = True

    def __init__(self, sample: PublishedApplicationVersion) -> None:
        self.sample = sample

    def get_version(
        self, organization_id: str, question_set_id: str
    ) -> PublishedApplicationVersion:
        if (
            organization_id != self.sample.organization_id
            or question_set_id != self.sample.question_set_id
        ):
            raise ApplicationDefinitionNotFound(question_set_id)
        return self.sample

    def get_current(self, organization_id: str, definition_id: str) -> PublishedApplicationVersion:
        if (
            organization_id != self.sample.organization_id
            or definition_id != self.sample.definition_id
        ):
            raise ApplicationDefinitionNotFound(definition_id)
        return self.sample


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        auth_mode="fixture",
        funding_capture_store_dir=tmp_path / "captures",
        dev_b_store_dir=tmp_path / "dev-b",
    )


def test_committed_sample_matches_the_contract() -> None:
    sample = PublishedApplicationVersion.model_validate(json.loads(SAMPLE.read_text("utf-8")))
    assert sample.approval_status == "not_approved" and sample.prefill_permitted is False
    assert len(sample.question_set.questions) == 9
    assert isinstance(FixtureReader(sample), ApplicationDefinitionReader)


@pytest.mark.parametrize("adapter", ["fixture_double", "real_repository"])
def test_consumer_route_against_fixture_and_real_producer(tmp_path: Path, adapter: str) -> None:
    settings = _settings(tmp_path)
    app = consumer_app(settings)
    client = TestClient(app)
    if adapter == "fixture_double":
        sample = PublishedApplicationVersion.model_validate(json.loads(SAMPLE.read_text("utf-8")))
        app.dependency_overrides[get_application_definition_reader] = lambda: FixtureReader(sample)
        qs_id = sample.question_set_id
    else:
        src = {"mode": "fixture", "fixture_id": "rep-portal-definition-v1"}
        sha = client.post("/api/automation/intake", json={"source": src}).json()["input"]["sha256"]
        saved = client.post(
            "/api/automation/definitions",
            json={"source": src, "expected_input_sha256": sha, "idempotency_key": "consumer-01"},
        ).json()["publication"]
        qs_id = saved["question_set_id"]
        assert isinstance(
            build_application_definition_reader(settings), ApplicationDefinitionReader
        )
    body = client.get(f"/consumer/questions/{qs_id}").json()
    assert len(body["question_ids"]) == 9
    assert body["question_versions"] == [1]
    assert body["unresolved"] > 0
    assert body["is_fixture_record"] is True and body["simulated"] is True
    assert client.get(f"/consumer/questions/qs-def-{'0' * 26}-v1").status_code == 404
