"""Real B publication and C save/decide helpers. Never inject approval readers."""

from __future__ import annotations

from typing import Any, cast

from fastapi.testclient import TestClient

from strongstart_api.features.applications.public import get_approved_prefill_reader
from strongstart_api.features.applications.rules.policy import fixture_policy
from strongstart_api.features.applications.workspace import (
    DefinitionWorkspaceSource,
    FixtureWorkspaceSource,
)
from strongstart_api.features.automation.public import build_application_definition_reader

ORG = "demo-org"
SOURCE = {"mode": "fixture", "fixture_id": "rep-prefill-definition-v1"}
FACT = "demo-fact-children-served"


def publish(
    c: TestClient, key: str = "int-publish-0001", previous: dict[str, Any] | None = None
) -> dict[str, Any]:
    sha = c.post("/api/automation/intake", json={"source": SOURCE}).json()["input"]["sha256"]
    body: dict[str, Any] = {"source": SOURCE, "expected_input_sha256": sha, "idempotency_key": key}
    if previous:
        body |= {
            "definition_id": previous["definition_id"],
            "expected_version": previous["version"],
        }
    response = c.post("/api/automation/definitions", json=body)
    assert response.status_code in (200, 201), response.text
    return cast(dict[str, Any], response.json()["publication"])


def question(pub: dict[str, Any], original: str) -> str:
    return str(
        next(
            m["published_question_id"]
            for m in pub["id_mapping"]
            if m["original_question_id"] == original
        )
    )


def save(
    c: TestClient, pub: dict[str, Any], original: str, text: str, expected: int | None = None
) -> dict[str, Any]:
    ws = c.get("/api/applications/workspace", params={"question_set_id": pub["question_set_id"]})
    assert ws.status_code == 200, ws.text
    response = c.post(
        "/api/applications/answers/versions",
        json={
            "question_id": question(pub, original),
            "question_version": 1,
            "question_set_id": pub["question_set_id"],
            "evidence_bundle_id": ws.json()["evidence_bundle"]["bundle_id"],
            "text": text,
            "expected_answer_version": expected,
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def decide(c: TestClient, version: dict[str, Any], decision: str = "approve") -> str:
    response = c.post(
        "/api/applications/answers/decisions",
        json={
            "answer_version_id": version["answer_version_id"],
            "expected_content_sha256": version["content_sha256"],
            "expected_snapshot_sha256": version["snapshot_sha256"],
            "decision": decision,
            "acknowledge_review_items": True,
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["approval_id"])


def reader_for(app: Any, settings: Any, source: Any = None):
    source = source or DefinitionWorkspaceSource(
        build_application_definition_reader(settings), FixtureWorkspaceSource()
    )
    return get_approved_prefill_reader(
        app.state.c3_answer_store, source, fixture_policy(), settings
    )


def prepare(c: TestClient, pub: dict[str, Any], approvals: dict[str, str]):
    return c.post(
        "/api/automation/prefill-plans",
        json={
            "question_set_id": pub["question_set_id"],
            "portal_fixture_id": "rep-prefill-v1",
            "selections": [
                {"published_question_id": question(pub, q), "approval_snapshot_id": a}
                for q, a in approvals.items()
            ],
        },
    )
