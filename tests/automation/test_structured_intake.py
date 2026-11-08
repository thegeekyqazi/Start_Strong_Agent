"""Structured JSON intake: AUTO-02 (lineage/roundtrip), AUTO-03 (strict input), AUTO-05/06."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from strongstart_contracts.automation_intake import ApplicationIntakeResult
from tests.automation.conftest import DEFINITION_PATH, by_id, codes, definition, intake_json, sha


def _fixture_intake(client: TestClient) -> dict[str, Any]:
    r = client.post(
        "/api/automation/intake",
        json={"source": {"mode": "fixture", "fixture_id": "rep-portal-definition-v1"}},
    )
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def test_auto02_fixture_preserves_ids_order_text_hash_and_unknowns(
    fixture_client: TestClient,
) -> None:
    body = _fixture_intake(fixture_client)
    raw = DEFINITION_PATH.read_bytes()
    src = definition()
    assert body["input"]["sha256"] == sha(raw)
    assert body["input"]["byte_size"] == len(raw)
    assert body["input"]["origin"] == "fixture" and body["is_fixture"] is True
    assert body["persisted"] is False and body["approval_status"] == "not_approved"
    assert body["provenance"]["provenance_class"] == "engineering_derived"
    assert body["original_guide_present"] is False
    assert "FIXTURE" in body["mode_label"]
    # identity/order/exact wording
    assert [q["question_id"] for q in body["questions"]] == [
        q["question_id"] for q in src["questions"]
    ]
    for i, (got, want) in enumerate(zip(body["questions"], src["questions"], strict=True)):
        assert got["order"] == i
        assert got["original_number"] == want["number"]
        assert got["text"]["text"] == want["text"]
        assert got["text"]["locator"] == {
            "kind": "json_pointer",
            "value": f"/questions/{i}/text",
            "line": None,
            "column": None,
        }
        assert got["source_ref"]["content_hash"] == sha(raw)
        assert got["source_ref"]["verification_status"] == "unverified"
    q = by_id(body)
    # unknowns stay unknown
    assert q["rp-pending-applications"]["required_status"] == "unknown"
    assert q["rp-other-funding"]["limits"][0]["unit"] == "unknown"
    assert all(
        lim["counting_convention"] == "unknown"
        and lim["authority_status"] == "imported_provisional"
        for lim in q["rp-mission"]["limits"]
    )
    # shared DTO projection is produced and validates
    assert body["question_set"]["opportunity_id"] == "demo-gos"
    assert (
        body["application_definition"]["question_set_id"] == body["question_set"]["question_set_id"]
    )


def test_auto02_upload_same_bytes_is_unverified_with_distinct_identity(
    fixture_client: TestClient,
) -> None:
    text = DEFINITION_PATH.read_text(encoding="utf-8")
    up = intake_json(fixture_client, text).json()
    fx = _fixture_intake(fixture_client)
    assert up["input"]["sha256"] == fx["input"]["sha256"]
    assert up["input"]["origin"] == "uploaded_unverified" and up["is_fixture"] is False
    assert up["import_id"] != fx["import_id"]
    assert "UPLOADED" in up["mode_label"]
    # deterministic: same bytes, same server-derived identity
    assert intake_json(fixture_client, text).json()["import_id"] == up["import_id"]


def test_auto02_result_roundtrips_through_contract(fixture_client: TestClient) -> None:
    body = _fixture_intake(fixture_client)
    model = ApplicationIntakeResult.model_validate(body)
    assert json.loads(model.model_dump_json()) == body


def test_auto05_competing_limits_preserved_and_held(fixture_client: TestClient) -> None:
    body = _fixture_intake(fixture_client)
    p = by_id(body)["rp-partnership"]
    maxima = sorted(int(x["maximum"]) for x in p["limits"])
    assert maxima == [350, 500]
    assert [c["kind"] for c in p["limit_conflicts"]] == ["competing_instruction_limits"]
    assert p["limit_conflicts"][0]["resolution"] == "unresolved"
    assert p["action_state"] == "held_unresolved_requirement"
    shared = {q["question_id"]: q for q in body["question_set"]["questions"]}["rp-partnership"]
    assert shared["limit"] is None  # no convenient limit chosen
    assert sorted(c["maximum"] for c in shared["conflicts"][0]["candidate_limits"]) == [350, 500]
    other = by_id(body)["rp-other-funding"]
    assert other["action_state"] == "held_unresolved_requirement"
    assert "unknown_limit_unit" in codes(body, "rp-other-funding")
    assert {x["unit"] for x in by_id(body)["rp-pending-applications"]["limits"]} == {"characters"}


def test_auto05_network_stream_limit_is_not_applied_to_standard(fixture_client: TestClient) -> None:
    body = _fixture_intake(fixture_client)
    req = by_id(body)["rp-request-amount"]
    streams = {x["applies_to_stream"]: (x["minimum"], x["maximum"]) for x in req["limits"]}
    assert streams == {"standard": ("20000", "100000"), "network": (None, "250000")}
    assert req["limit_conflicts"] == []  # different streams are not a conflict
    assert "stream_specific_limit" in codes(body, "rp-request-amount")
    shared = {q["question_id"]: q for q in body["question_set"]["questions"]}["rp-request-amount"]
    assert shared["answer_type"] == "amount"
    assert shared["limit"]["maximum"] == 100000


def test_auto06_required_conditional_attachment(fixture_client: TestClient) -> None:
    q = by_id(_fixture_intake(fixture_client))
    assert q["rp-mission"]["required_status"] == "required"
    part = q["rp-partnership"]
    assert part["required_status"] == "conditional"
    assert part["conditions"][0]["depends_on_question_id"] == "rp-has-partners"
    assert part["conditions"][0]["status"] == "declared_unverified"
    att = q["rp-financial-statement"]["attachment"]
    assert att["accepted_types"] == [".pdf", ".docx"]
    assert (att["max_size_bytes"], att["max_count"]) == (5242880, 1)
    assert q["rp-service-area"]["choices"][2]["value"] == "province"
    assert q["rp-service-area"]["choice_mode"] == "single"


def test_auto06_unsupported_condition_stays_unresolved(fixture_client: TestClient) -> None:
    d = definition()
    d["questions"][6]["condition"] = {"text": "Shown when the JS rule fires"}
    d["questions"][8].pop("attachment")
    body = intake_json(fixture_client, json.dumps(d)).json()
    q = by_id(body)
    assert q["rp-partnership"]["conditions"][0]["status"] == "unresolved"
    assert "condition_unresolved" in q["rp-partnership"]["hold_reasons"]
    assert q["rp-financial-statement"]["attachment"] is None
    assert "attachment_constraints_unknown" in codes(body, "rp-financial-statement")


def test_auto01_self_asserted_authority_is_ignored(fixture_client: TestClient) -> None:
    d = definition()
    d["approved"] = True
    d["organization_id"] = "other-org"
    d["questions"][0]["verification_status"] = "verified"
    d["questions"][0]["x_custom"] = {"keep": "me"}
    body = intake_json(fixture_client, json.dumps(d)).json()
    assert body["approval_status"] == "not_approved"
    assert body["authority_status"] == "imported_provisional_unreviewed"
    assert body["original_evidence"]["unrecognized_top_level"] == {
        "approved": True,
        "organization_id": "other-org",
    }
    assert "untrusted_authority_claim_ignored" in codes(body)
    q0 = body["questions"][0]
    assert q0["unrecognized_fields"] == {
        "verification_status": "verified",
        "x_custom": {"keep": "me"},
    }
    assert q0["source_ref"]["verification_status"] == "unverified"


def _reason(r: Any) -> str:
    return str(r.json()["details"]["reason"])


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ("{not json", "malformed_definition"),
        ("[]", "malformed_definition"),
        ('{"format": "x"}', "malformed_definition"),
        ("﻿{}", "malformed_definition"),
        ('{"a": 1, "a": 2}', "malformed_definition"),
        ('{"a": NaN}', "malformed_definition"),
        ("[" * 50 + "]" * 50, "malformed_definition"),
    ],
)
def test_auto03_invalid_json_fails_clearly(
    fixture_client: TestClient, content: str, reason: str
) -> None:
    r = intake_json(fixture_client, content)
    assert r.status_code == 422
    assert _reason(r) == reason
    assert r.json()["code"] == "validation_failed"
    assert "Traceback" not in r.text


def test_auto03_wrong_types_are_not_coerced(fixture_client: TestClient) -> None:
    d = definition()
    d["questions"][0]["type"] = "essay"
    d["questions"][1]["limits"][0]["maximum"] = 2.5
    r = intake_json(fixture_client, json.dumps(d))
    assert r.status_code == 422 and _reason(r) == "malformed_definition"
    d = definition()
    d["questions"][0]["required"] = True  # bool where an enum string is required
    assert _reason(intake_json(fixture_client, json.dumps(d))) == "malformed_definition"


def test_auto03_duplicate_question_ids_are_errors_not_renumbered(
    fixture_client: TestClient,
) -> None:
    d = definition()
    d["questions"][3]["question_id"] = "rp-mission"
    r = intake_json(fixture_client, json.dumps(d))
    assert r.status_code == 422
    assert _reason(r) == "duplicate_id"
    assert r.json()["details"]["duplicate_ids"] == ["rp-mission"]


def test_auto03_size_limits(fixture_client: TestClient) -> None:
    d = definition()
    d["padding"] = "x" * (256 * 1024)
    r = intake_json(fixture_client, json.dumps(d))
    assert r.status_code == 413 and _reason(r) == "input_too_large"
    big = '{"source": {"mode": "html", "content": "' + "x" * (2 * 1024 * 1024 + 10) + '"}}'
    r = fixture_client.post(
        "/api/automation/intake", content=big, headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 413 and _reason(r) == "input_too_large"


def test_auto03_request_envelope_is_strict(fixture_client: TestClient) -> None:
    r = fixture_client.post(
        "/api/automation/intake",
        json={
            "source": {"mode": "fixture", "fixture_id": "rep-portal-definition-v1"},
            "org_id": "x",
        },
    )
    assert r.status_code == 422 and _reason(r) == "malformed_request"
    r = fixture_client.post("/api/automation/intake", json={"source": {"mode": "url", "url": "x"}})
    assert r.status_code == 422 and _reason(r) == "malformed_request"
