"""B1-B2 capture seam through the real importer: AUTO-14, AUTO-15, AUTO-13 (cross-org)."""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from strongstart_api.features.automation.capture import (
    InMemoryCaptureSource,
    load_fixture_capture_source,
    parse_capture_record,
)
from strongstart_api.features.automation.router import get_capture_source
from tests.automation.conftest import CAPTURE_DIR, PORTAL_PATH, by_id, codes, make_client, sha

RECORDS = json.loads((CAPTURE_DIR / "records.json").read_text(encoding="utf-8"))["records"]


def _capture(client: TestClient, capture_id: str, artifact_id: str) -> Any:
    return client.post(
        "/api/automation/intake",
        json={"source": {"mode": "capture", "capture_id": capture_id, "artifact_id": artifact_id}},
    )


def _b1_style_record(html: bytes) -> dict[str, Any]:
    """A record serialized as B1 would (semantic v1), not via the B2 fixture loader."""
    rec: dict[str, Any] = json.loads(json.dumps(RECORDS[0]))
    rec.update(
        capture_id="cap-b1-sample-1",
        source_id="src-b1-sample",
        source_version_id="srcv-b1-sample-1",
        stream_id="standard",
        cycle_id="cycle-2026",
        provider="firecrawl",
        authority_review_status="unreviewed",
    )
    rec["urls"] = {
        "original": "https://example.org/apply",
        "requested": "https://example.org/apply",
        "final": "https://example.org/apply/form",
        "final_status": "known",
    }
    rec["provenance"] = {"provenance_class": "public", "is_simulated": False, "note": "sample"}
    rec["artifacts"] = [
        {
            "artifact_id": "art-b1-html",
            "representation_type": "provider_raw_html",
            "media_type": "text/html; charset=utf-8",
            "byte_size": len(html),
            "sha256": sha(html),
        }
    ]
    return dict(rec)


def _client_with(source: InMemoryCaptureSource) -> TestClient:
    client = make_client(auth_mode="fixture")
    client.app.dependency_overrides[get_capture_source] = lambda: source  # type: ignore[attr-defined]
    return client


def test_auto14_b1_saved_html_passes_through_importer_with_lineage(no_network: list[Any]) -> None:
    html = PORTAL_PATH.read_bytes()
    record = parse_capture_record(_b1_style_record(html))
    source = InMemoryCaptureSource([(record, {"art-b1-html": html})], is_fixture=False)
    r = _capture(_client_with(source), "cap-b1-sample-1", "art-b1-html")
    assert r.status_code == 200, r.text
    body = r.json()
    assert no_network == []  # no refetch of the URL; saved bytes only
    lineage = body["input"]["capture"]
    assert lineage["capture_id"] == "cap-b1-sample-1"
    assert lineage["source_version_id"] == "srcv-b1-sample-1"
    assert lineage["artifact_id"] == "art-b1-html"
    assert lineage["representation_type"] == "provider_raw_html"
    assert lineage["final_url"] == "https://example.org/apply/form"
    assert lineage["capture_is_fixture"] is False
    assert body["input"]["sha256"] == sha(html)
    assert body["input"]["integrity"] == "hash_verified_against_capture_record"
    assert (body["opportunity_id"], body["stream_id"], body["cycle_id"]) == (
        "demo-gos",
        "standard",
        "cycle-2026",
    )
    q = by_id(body)
    assert len(q) == 9
    ref = q["rp-partnership"]["source_ref"]
    assert (ref["source_id"], ref["source_version_id"], ref["content_hash"]) == (
        "src-b1-sample",
        "srcv-b1-sample-1",
        sha(html),
    )
    assert ref["provenance"]["provenance_class"] == "public"
    assert body["question_set"]["questions"][0]["source_refs"][0]["source_version_id"] == (
        "srcv-b1-sample-1"
    )


def test_auto14_modified_bytes_fail_integrity() -> None:
    html = PORTAL_PATH.read_bytes()
    record = parse_capture_record(_b1_style_record(html))
    altered = html.replace(b"Maximum 50 words.", b"Maximum 51 words.")
    source = InMemoryCaptureSource([(record, {"art-b1-html": altered})], is_fixture=False)
    r = _capture(_client_with(source), "cap-b1-sample-1", "art-b1-html")
    assert r.status_code == 409
    assert r.json()["details"]["reason"] == "hash_mismatch"
    assert "questions" not in r.json()


def test_auto14_fixture_producer_and_tampered_fixture(fixture_client: TestClient) -> None:
    ok = _capture(fixture_client, "cap-fixture-portal-html", "art-portal-raw-html")
    assert ok.status_code == 200
    assert ok.json()["input"]["capture"]["capture_is_fixture"] is True
    assert "FIXTURE PRODUCER" in ok.json()["mode_label"]
    bad = _capture(fixture_client, "cap-fixture-tampered", "art-tampered-html")
    assert bad.status_code == 409 and bad.json()["details"]["reason"] == "hash_mismatch"


def test_fixture_capture_records_hash_their_bytes() -> None:
    src = load_fixture_capture_source()
    for rec in src.list_records("demo-org"):
        for art in rec.artifacts:
            data = src.read_artifact("demo-org", rec.capture_id, art.artifact_id)
            matches = sha(data) == art.sha256
            assert matches is (rec.capture_id != "cap-fixture-tampered"), rec.capture_id


def test_auto15_markdown_and_pdf_are_preserved_not_parsed(fixture_client: TestClient) -> None:
    md = _capture(fixture_client, "cap-fixture-guide-markdown", "art-guide-markdown").json()
    assert md["questions"] == [] and md["question_set"] is None
    assert md["coverage"]["status"] == "unsupported_needs_manual_definition"
    assert "markdown_not_parsed" in codes(md)
    assert "350 or 500 words" in md["evidence_excerpt"]["text"]
    assert md["input"]["representation_type"] == "provider_markdown"
    assert md["input"]["capture"]["source_version_id"] == "srcv-cap-fixture-guide-markdown"
    pdf = _capture(fixture_client, "cap-fixture-guide-pdf", "art-guide-pdf").json()
    assert pdf["questions"] == [] and pdf["evidence_excerpt"] is None
    assert "pdf_parsing_not_implemented" in codes(pdf)
    assert pdf["input"]["representation_type"] == "pdf"


def test_auto13_cross_org_and_unknown_captures_are_indistinguishable(
    fixture_client: TestClient,
) -> None:
    other = _capture(fixture_client, "cap-fixture-other-org", "art-other-org-html")
    unknown = _capture(fixture_client, "cap-does-not-exist", "art-x")
    assert other.status_code == unknown.status_code == 404
    assert other.json()["details"] == unknown.json()["details"] == {"reason": "source_unavailable"}
    assert "Section A" not in other.text


def test_capture_unavailable_without_producer() -> None:
    from strongstart_api.features.automation.capture import UnconfiguredCaptureSource

    client = make_client(auth_mode="fixture")
    client.app.dependency_overrides[get_capture_source] = UnconfiguredCaptureSource  # type: ignore[attr-defined]
    r = _capture(client, "cap-fixture-portal-html", "art-portal-raw-html")
    assert r.status_code == 503 and r.json()["details"]["reason"] == "source_unavailable"
