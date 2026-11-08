"""G1 seam: B1's real capture store/records through B2's real importer (no overrides of
B2's capture wiring). Uses B1's committed sample (`tests/fixtures/funding/sample-capture-v1`)
and a fresh capture produced by B1's API in fixture mode."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.funding import deps as funding_deps
from strongstart_api.features.funding.store import LocalCaptureStore
from strongstart_contracts.discovery import CapturedDocument
from tests.automation.conftest import by_id, codes
from tests.conftest import REPO_ROOT

SAMPLE = REPO_ROOT / "tests/fixtures/funding/sample-capture-v1"
RECORD = CapturedDocument.model_validate_json((SAMPLE / "record.json").read_bytes())
HTML_ID = f"{RECORD.capture_id}-html"
RAW_ID = f"{RECORD.capture_id}-raw-html"
MD_ID = f"{RECORD.capture_id}-markdown"


def _blobs(record: CapturedDocument) -> dict[str, bytes]:
    return {a.sha256: (SAMPLE / "artifacts" / a.artifact_id).read_bytes() for a in record.artifacts}


def _client(store_dir: Path, **settings: Any) -> TestClient:
    settings.setdefault("auth_mode", "fixture")
    return TestClient(
        create_app(Settings(_env_file=None, funding_capture_store_dir=store_dir, **settings))
    )


def _import(client: TestClient, capture_id: str, artifact_id: str) -> Any:
    return client.post(
        "/api/automation/intake",
        json={"source": {"mode": "capture", "capture_id": capture_id, "artifact_id": artifact_id}},
    )


def test_g1_b1_sample_html_imports_with_ids_hashes_and_provenance(
    tmp_path: Path, no_network: list[Any]
) -> None:
    LocalCaptureStore(tmp_path).save(RECORD, _blobs(RECORD))
    r = _import(_client(tmp_path), RECORD.capture_id, HTML_ID)
    assert r.status_code == 200, r.text
    body = r.json()
    assert no_network == []  # saved bytes only; the URL is never refetched
    art = next(a for a in RECORD.artifacts if a.artifact_id == HTML_ID)
    html = (SAMPLE / "artifacts" / HTML_ID).read_bytes()
    lin = body["input"]["capture"]
    assert lin["capture_id"] == RECORD.capture_id
    assert lin["source_version_id"] == RECORD.source_reference.source_version_id
    assert lin["artifact_id"] == HTML_ID and lin["representation_type"] == "provider_html"
    assert lin["producer"] == "b1-capture-store"
    assert lin["producer_source_reference_hash"] == RECORD.source_reference.content_hash
    assert lin["producer_supported_representations"] == ["provider_html", "provider_raw_html"]
    assert lin["requested_url"] == RECORD.requested_url
    assert lin["final_url"] == RECORD.final_url
    assert lin["final_url_status"] == "provider_reported"
    assert lin["authority_review_status"] == "confirmed_official"
    assert lin["capture_is_fixture"] is True
    assert any("FIXTURE MODE" in w for w in lin["extraction_warnings"])
    assert body["input"]["sha256"] == art.sha256 == hashlib.sha256(html).hexdigest()
    assert body["input"]["integrity"] == "hash_verified_against_capture_record"
    assert body["provenance"] == RECORD.provenance.model_dump(mode="json")
    assert "FIXTURE/SIMULATED" in body["mode_label"] and "not approved" in body["mode_label"]
    q = by_id(body)
    assert set(q) == {"html-mission", "html-services"}
    assert q["html-mission"]["text"]["text"] == "Describe your organization's mission (50 words)"
    assert q["html-mission"]["limits"][0]["maximum"] == "50"
    for question in body["questions"]:
        ref = question["source_ref"]
        assert ref["source_id"] == RECORD.source_reference.source_id
        assert ref["source_version_id"] == RECORD.source_reference.source_version_id
        assert ref["content_hash"] == art.sha256
        assert ref["provenance"]["is_simulated"] is True
        assert ref["verification_status"] == "unverified"
    assert body["question_set"] is None  # B1 record has no opportunity_id; nothing invented
    assert body["approval_status"] == "not_approved"


def test_g1_b1_raw_html_is_inert(tmp_path: Path, no_network: list[Any]) -> None:
    LocalCaptureStore(tmp_path).save(RECORD, _blobs(RECORD))
    body = _import(_client(tmp_path), RECORD.capture_id, RAW_ID).json()
    assert no_network == []
    assert set(by_id(body)) == {"html-mission", "html-services"}
    assert {"script_content_inert", "external_reference_not_loaded"} <= codes(body)
    assert body["input"]["sha256"] == next(
        a.sha256 for a in RECORD.artifacts if a.artifact_id == RAW_ID
    )
    # Hidden page text is never a question and grants nothing.
    assert all("approve" not in q["text"]["text"].lower() for q in body["questions"])
    assert body["approval_status"] == "not_approved"


def test_g1_b1_markdown_is_context_only(tmp_path: Path) -> None:
    LocalCaptureStore(tmp_path).save(RECORD, _blobs(RECORD))
    body = _import(_client(tmp_path), RECORD.capture_id, MD_ID).json()
    assert body["questions"] == []
    assert body["coverage"]["status"] == "unsupported_needs_manual_definition"
    assert "markdown_not_parsed" in codes(body)
    assert body["input"]["capture"]["source_version_id"] == RECORD.capture_id


def test_g1_tampered_b1_blob_fails_integrity(tmp_path: Path) -> None:
    store = LocalCaptureStore(tmp_path)
    store.save(RECORD, _blobs(RECORD))
    art = next(a for a in RECORD.artifacts if a.artifact_id == HTML_ID)
    blob = next(p for p in tmp_path.rglob(art.sha256))
    blob.write_bytes(blob.read_bytes().replace(b"50 words", b"55 words"))
    r = _import(_client(tmp_path), RECORD.capture_id, HTML_ID)
    assert r.status_code == 409 and r.json()["details"]["reason"] == "hash_mismatch"


def test_g1_other_org_b1_capture_is_indistinguishable_from_unknown(tmp_path: Path) -> None:
    other = RECORD.model_copy(update={"organization_id": "other-org"})
    LocalCaptureStore(tmp_path).save(other, _blobs(other))
    c = _client(tmp_path)
    a, b = _import(c, RECORD.capture_id, HTML_ID), _import(c, "cap-unknown", "art-x")
    assert a.status_code == b.status_code == 404
    assert a.json()["details"] == b.json()["details"] == {"reason": "source_unavailable"}


def test_g1_fresh_b1_api_capture_flows_into_b2_importer(tmp_path: Path) -> None:
    """B1's real capture endpoint (fixture provider) -> store -> B2's real importer."""
    c = _client(tmp_path, funding_search_mode="fixture", funding_capture_mode="fixture")
    c.app.dependency_overrides[funding_deps.get_resolver] = lambda: (  # type: ignore[attr-defined]
        lambda host: ["93.184.215.14"]
    )
    cap = c.post(
        "/api/funding/captures",
        json={"url": "https://demo-funder.example/programs/community-grants"},
    )
    assert cap.status_code == 201, cap.text
    doc = cap.json()
    html = next(a for a in doc["artifacts"] if a["representation"] == "provider_html")
    body = _import(c, doc["capture_id"], html["artifact_id"]).json()
    assert body["input"]["sha256"] == html["sha256"]
    assert (
        body["input"]["capture"]["source_version_id"]
        == doc["source_reference"]["source_version_id"]
    )
    assert body["questions"][0]["source_ref"]["source_id"] == doc["source_reference"]["source_id"]
    assert set(by_id(body)) == {"html-mission", "html-services"}


def test_production_has_no_capture_source(tmp_path: Path) -> None:
    from strongstart_api.identity import FIXTURE_IDENTITY, require_identity

    c = _client(tmp_path, auth_mode="none", environment="production")
    c.app.dependency_overrides[require_identity] = lambda: FIXTURE_IDENTITY  # type: ignore[attr-defined]
    r = _import(c, RECORD.capture_id, HTML_ID)
    assert r.status_code == 503 and r.json()["details"]["reason"] == "source_unavailable"
