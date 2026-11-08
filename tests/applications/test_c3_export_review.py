"""C3 export, audit and reviewer roles (C3 spec s5, s6, s8).

Rules: APP-07, APP-08, POL-05, SEC-10, SEC-14 (reviewer output), plus the s8.1 roles.
"""

from __future__ import annotations

import io
import json
from typing import Any

import pytest
from docx import Document
from fastapi.testclient import TestClient

from strongstart_api.config import Settings
from strongstart_api.features.applications.audit import is_complete, redact
from strongstart_api.features.applications.exporter import validation_record_is_current
from strongstart_api.features.applications.models.base import ModelOutputRejected
from strongstart_api.features.applications.models.fake import FakeAdapter
from strongstart_api.features.applications.reviewers import validate_review_output
from strongstart_contracts.answers import AuditEvent

from .conftest import FACT, make_client
from .test_c3_approval import BOUND, PLAIN, A, Q, approve, approved_version, history, save

CANARY = "AIza" + "C3CANARYc3canaryC3CANARYc3canaryC3C"[:35]


def export(c: TestClient, mode: str, questions: list[str] | None = None) -> dict[str, Any]:
    r = c.post(f"{A}/exports", json={"mode": mode, "question_ids": questions or [Q]})
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def docx_text(c: TestClient, export_id: str) -> tuple[str, str]:
    r = c.get(f"{A}/exports/{export_id}/docx")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    doc = Document(io.BytesIO(r.content))
    body = "\n".join(p.text for p in doc.paragraphs)
    header = "\n".join(p.text for p in doc.sections[0].header.paragraphs)
    return body, header


# --- APP-07 ------------------------------------------------------------------------------


def test_app07_working_export_with_placeholder_succeeds_and_is_labelled() -> None:
    c = make_client(auth_mode="fixture")
    save(c, "We will serve XXX families.")
    result = export(c, "working")
    assert result["blocked"] is False and result["export_id"]
    body, header = docx_text(c, result["export_id"])
    assert "WORKING DRAFT - NOT REVIEWED" in header and "WORKING DRAFT - NOT REVIEWED" in body
    assert "We will serve XXX families." in body
    assert "[NEEDS REVIEW] POL-03" in body  # plain text label, no colour coding
    assert "FIXTURE APPROVAL - NOT AUTHENTICATION" not in result["labels"]  # nothing approved


@pytest.mark.parametrize(
    ("setup", "reason"),
    [
        ("none", "no_answer"),
        ("unapproved", "not_approved"),
        ("unsupported", "not_approved"),  # approval gate refuses unsupported claims first
        ("stale", "stale_approval"),
    ],
)
def test_app07_reviewed_export_blocked(setup: str, reason: str) -> None:
    c = make_client(auth_mode="fixture")
    if setup == "unapproved":
        save(c, BOUND)
    if setup == "unsupported":
        v = save(c, "Waitlist doubled {{unsupported:no-data}}.").json()
        gate = approve(c, v)
        assert gate.status_code == 422  # reviewed-mode APP-03 fail blocks approval
    if setup == "stale":
        approved_version(c)  # latest version stays the approved one ...
        c.post(f"{A}/fixture/change-sets/demo-change-fact-v2/apply")  # ... its fact changes
    result = export(c, "reviewed")
    assert result["blocked"] is True and result["export_id"] is None
    assert result["docx_sha256"] is None and result["audit_sha256"] is None
    assert reason in {b["reason"] for b in result["blocked_by"]}
    actions = [e["action"] for e in c.get(f"{A}/audit-events").json()]
    assert "export_blocked" in actions


def test_app07_reviewed_export_succeeds_for_current_approval() -> None:
    c = make_client(auth_mode="fixture")
    approved_version(c)
    result = export(c, "reviewed")
    assert result["blocked"] is False
    body, header = docx_text(c, result["export_id"])
    assert "REVIEWED - EXACT APPROVED VERSIONS" in header
    assert "Approved (this exact version)" in body
    assert "120 children (2025-09/2026-06)" in body
    assert f"fact {FACT}" in body  # source note


def test_unknown_question_blocks_reviewed_export() -> None:
    c = make_client(auth_mode="fixture")
    result = export(c, "reviewed", ["nope-q9"])
    assert result["blocked_by"][0]["reason"] == "unknown_question"


# --- POL-05 ------------------------------------------------------------------------------


def test_pol05_synthetic_label_on_every_page_and_in_audit() -> None:
    c = make_client(auth_mode="fixture")
    approved_version(c)
    result = export(c, "reviewed")
    assert "SYNTHETIC DEMO DATA" in result["labels"]
    assert "FIXTURE APPROVAL - NOT AUTHENTICATION" in result["labels"]
    _, header = docx_text(c, result["export_id"])
    assert "SYNTHETIC DEMO DATA" in header  # section header repeats on every page
    audit = json.loads(c.get(f"{A}/exports/{result['export_id']}/audit").content)
    assert "SYNTHETIC DEMO DATA" in audit["labels"]
    assert audit["answers"][0]["sources"][0]["is_simulated"] is True


# --- APP-08 ------------------------------------------------------------------------------


def test_app08_audit_records_rule_versions_hashes_and_times() -> None:
    c = make_client(auth_mode="fixture")
    v = approved_version(c)
    result = export(c, "reviewed")
    audit = json.loads(c.get(f"{A}/exports/{result['export_id']}/audit").content)
    entry = audit["answers"][0]
    assert entry["content_sha256"] == v["content_sha256"]
    assert entry["snapshot_sha256"] == v["snapshot_sha256"]
    assert entry["fact_ids"] == [FACT]
    assert entry["approval"]["decision"] == "approve"
    assert all(chk["counts_as_current"] for chk in entry["checks"])
    assert all(chk["rule_version"] == "c2-1" and chk["evaluated_at"] for chk in entry["checks"])
    assert len(result["audit_sha256"]) == 64


def test_app08_record_without_rule_version_or_time_is_not_current() -> None:
    good = {
        "rule_version": "c2-1",
        "inputs": {"rendered_text_sha256": "a" * 64},
        "evaluated_at": "2026-11-08T00:00:00Z",
        "outcome": "pass",
    }
    assert validation_record_is_current(good)
    for missing in ("rule_version", "evaluated_at", "outcome"):
        assert not validation_record_is_current({k: v for k, v in good.items() if k != missing})
    assert not validation_record_is_current({**good, "inputs": {}})


# --- SEC-10 ------------------------------------------------------------------------------


def test_sec10_every_action_is_audited_completely() -> None:
    c = make_client(auth_mode="fixture")
    v = save(c, BOUND).json()
    c.post(f"{A}/answers/notes", json={"answer_version_id": v["answer_version_id"], "text": "ok"})
    c.post(
        f"{A}/answers/reviews",
        json={"answer_version_id": v["answer_version_id"], "role": "meaning_reviewer"},
    )
    approve(c, v)
    export(c, "reviewed")
    save(c, BOUND + " edit", expected=1)
    events = c.get(f"{A}/audit-events").json()
    actions = [e["action"] for e in events]
    for action in (
        "answer_version_saved",
        "review_note_added",
        "reviewer_proposal_added",
        "approval_decided",
        "export_created",
        "approval_staled",
    ):
        assert action in actions, action
    assert all(is_complete(AuditEvent.model_validate(e)) for e in events)


def test_sec10_missing_decision_fails_completeness() -> None:
    event = AuditEvent.model_validate(
        {
            "event_id": "ev-1",
            "actor_id": "a",
            "action": "approval_decided",
            "object_type": "answer_version",
            "object_id": "av-1",
            "object_version": "1",
            "decision": "",
            "at": "2026-11-08T00:00:00Z",
        }
    )
    assert not is_complete(event)


def test_sec10_configured_secret_and_key_shapes_are_redacted() -> None:
    settings = Settings(
        _env_file=None, auth_mode="fixture", gemini_api_key="configured-secret-value-123"
    )
    assert (
        redact("key configured-secret-value-123 and " + CANARY, settings)
        == "key [redacted] and [redacted]"
    )
    c = make_client(auth_mode="fixture", gemini_api_key="configured-secret-value-123")
    v = save(c, BOUND).json()
    c.post(
        f"{A}/answers/decisions",
        json={
            "answer_version_id": v["answer_version_id"],
            "expected_content_sha256": v["content_sha256"],
            "expected_snapshot_sha256": v["snapshot_sha256"],
            "decision": "approve",
            "acknowledge_review_items": True,
            "note": f"pasted {CANARY} by mistake",
        },
    )
    text = c.get(f"{A}/audit-events").text
    assert CANARY not in text and "[redacted]" in text


def test_audit_events_require_identity_and_are_org_scoped() -> None:
    assert make_client().get(f"{A}/audit-events").status_code == 401


def test_exports_are_org_scoped() -> None:
    c = make_client(auth_mode="fixture")
    save(c, PLAIN)
    result = export(c, "working")
    assert c.get(f"{A}/exports/exp-unknown/docx").status_code == 404
    assert c.get(f"{A}/exports/{result['export_id']}/audit").status_code == 200


# --- reviewer roles (s8.1) and notes ---------------------------------------------------------


def test_numerical_reviewer_proposes_concerns_tied_to_bindings() -> None:
    c = make_client(auth_mode="fixture")
    v = save(c, BOUND).json()
    r = c.post(
        f"{A}/answers/reviews",
        json={"answer_version_id": v["answer_version_id"], "role": "numerical_reviewer"},
    )
    assert r.status_code == 201
    p = r.json()
    assert p["role"] == "numerical_reviewer" and p["reviewer"]["is_fixture"] is True
    b = v["rendered"]["bindings"][0]
    assert p["findings"][0]["fact_ids"] == [FACT]
    assert (p["findings"][0]["span_start"], p["findings"][0]["span_end"]) == (
        b["span_start"],
        b["span_end"],
    )
    assert "not an approval" in p["provenance"]["note"]
    assert history(c)["versions"][-1]["state"] == "ready_for_review"  # proposals change nothing
    assert len(history(c)["proposals"]) == 1


def test_meaning_reviewer_and_notes_have_no_approval_rights() -> None:
    c = make_client(auth_mode="fixture")
    v = save(c, BOUND).json()
    r = c.post(
        f"{A}/answers/reviews",
        json={"answer_version_id": v["answer_version_id"], "role": "meaning_reviewer"},
    )
    assert r.status_code == 201 and len(r.json()["findings"]) == 1
    n = c.post(
        f"{A}/answers/notes",
        json={"answer_version_id": v["answer_version_id"], "text": "Looks fine to me."},
    )
    assert n.status_code == 201
    h = history(c)
    assert h["versions"][-1]["state"] == "ready_for_review" and h["approvals"] == []
    assert h["notes"][0]["text"] == "Looks fine to me."


@pytest.mark.parametrize(
    ("raw", "issue"),
    [
        ('{"findings": [], "approved": true}', "sec14_forbidden_field"),
        (
            '{"findings": [{"concern": "x", "span_start": 0, "span_end": 3, '
            '"fact_ids": [], "status": "ok"}]}',
            "sec14_forbidden_field",
        ),
        ('{"findings": [], "permissions": ["approve"]}', "sec12_forbidden_field"),
        (
            '{"findings": [{"concern": "x", "span_start": 0, "span_end": 999, "fact_ids": []}]}',
            "bad_span",
        ),
        (
            '{"findings": [{"concern": "x", "span_start": 1, "span_end": null, "fact_ids": []}]}',
            "bad_span",
        ),
        (
            '{"findings": [{"concern": "x", "span_start": null, "span_end": null, '
            '"fact_ids": ["invented"]}]}',
            "unknown_fact_id",
        ),
        ('{"findings": "none"}', "schema"),
    ],
)
def test_reviewer_output_is_validated(raw: str, issue: str) -> None:
    with pytest.raises(ModelOutputRejected) as exc:
        validate_review_output(raw, 50, frozenset({FACT}))
    assert exc.value.issues[0] == issue


class _Canned:
    is_fixture = True

    def __init__(self, raw: str) -> None:
        self.raw = raw

    def capabilities(self) -> Any:
        return FakeAdapter().capabilities()

    async def complete(self, task: Any) -> str:
        return self.raw


def test_reviewer_claiming_approval_is_rejected_and_changes_nothing() -> None:
    from strongstart_api.features.applications.router import get_model_adapter

    c = make_client(auth_mode="fixture")
    v = save(c, BOUND).json()
    canned = _Canned('{"findings": [], "approved": true}')
    c.app.dependency_overrides[get_model_adapter] = lambda: canned  # type: ignore[attr-defined]
    r = c.post(
        f"{A}/answers/reviews",
        json={"answer_version_id": v["answer_version_id"], "role": "meaning_reviewer"},
    )
    assert r.status_code == 502 and r.json()["details"]["issues"] == ["sec14_forbidden_field"]
    h = history(c)
    assert (
        h["versions"][-1]["state"] == "ready_for_review"
        and h["approvals"] == []
        and h["proposals"] == []
    )
