"""Shared helpers for DEV-B-BUNDLE-002 funding-case tests (fixture providers, temp stores)."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.funding.deps import get_resolver
from strongstart_api.identity import require_identity
from strongstart_contracts import SessionIdentity

GUIDELINES = "https://demo-funder.example/programs/community-grants/guidelines"
FORM_PAGE = "https://demo-funder.example/programs/community-grants"
OTHER = SessionIdentity(
    actor_id="x", organization_id="other-org", roles=[], is_fixture=True, label="TEST other org"
)
_keys = itertools.count()


def key(prefix: str = "key") -> str:
    return f"{prefix}-{next(_keys):08d}"


def make_settings(tmp_path: Path, **overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "auth_mode": "fixture",
        "funding_capture_store_dir": tmp_path / "captures",
        "dev_b_store_dir": tmp_path / "dev-b",
        "funding_search_mode": "fixture",
        "funding_capture_mode": "fixture",
    }
    base.update(overrides)
    return Settings(_env_file=None, **base)


def client_for(settings: Settings, identity: SessionIdentity | None = None) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_resolver] = lambda: lambda host: ["93.184.215.14"]
    if identity is not None:
        app.dependency_overrides[require_identity] = lambda: identity
    return TestClient(app)


def capture(c: TestClient, url: str = GUIDELINES, **extra: Any) -> dict[str, Any]:
    r = c.post("/api/funding/captures", json={"url": url, **extra})
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()
    return data


def artifact(doc: dict[str, Any], representation: str = "provider_markdown") -> dict[str, Any]:
    found: dict[str, Any] = next(
        a for a in doc["artifacts"] if a["representation"] == representation
    )
    return found


def text_of(c: TestClient, doc: dict[str, Any], art: dict[str, Any]) -> str:
    r = c.get(f"/api/funding/captures/{doc['capture_id']}/artifacts/{art['artifact_id']}/content")
    assert r.status_code == 200, r.text
    value: str = r.json()["text"]
    return value


def anchor(c: TestClient, doc: dict[str, Any], quote: str, anchor_key: str) -> dict[str, Any]:
    art = artifact(doc)
    text = text_of(c, doc, art)
    start = text.index(quote)
    return {
        "anchor_key": anchor_key,
        "capture_id": doc["capture_id"],
        "artifact_id": art["artifact_id"],
        "expected_artifact_sha256": art["sha256"],
        "quote": quote,
        "start": start,
        "end": start + len(quote),
    }


FULL_CONTEXT = {
    "funder_label": "FIXTURE Demo Funder",
    "stream_label": "standard",
    "cycle_label": "2026",
    "stage": "full_application",
    "opportunity_title": "FIXTURE Community Grants 2026 (standard, full application)",
}

AMOUNT_QUOTE = "Standard stream requests: 20,000 to 100,000 CAD per award."
NETWORK_QUOTE = "Network stream maximum: 250,000 CAD per award."
POOL_QUOTE = "The total program budget for 2026 is 1,000,000 CAD."
REGION_QUOTE = "Eligible regions: demo-region-north and demo-region-south."
INVITE_QUOTE = "Full applications are by invitation only, following an expression of interest."
FULL_DEADLINE_QUOTE = "Full applications close 31 March 2026 at 5:00 p.m. Eastern Time."
EOI_DEADLINE_QUOTE = "Expressions of interest close 15 January 2026 at 5:00 p.m. Eastern Time."


def standard_requirements() -> list[dict[str, Any]]:
    return [
        {
            "requirement_key": "standard-amount",
            "spec": {
                "kind": "amount_range",
                "limit_kind": "per_award",
                "minimum": "20000",
                "maximum": "100000",
                "currency": "CAD",
            },
            "anchor_keys": ["amount"],
            "interpretation": "Per-award range for the standard stream.",
        },
        {
            "requirement_key": "network-max",
            "spec": {
                "kind": "amount_range",
                "limit_kind": "per_award",
                "maximum": "250000",
                "currency": "CAD",
            },
            "anchor_keys": ["network"],
            "scope": {"stream_label": "network"},
            "interpretation": "Separate per-award maximum for the network stream only.",
        },
        {
            "requirement_key": "pool",
            "spec": {
                "kind": "amount_range",
                "limit_kind": "total_pool",
                "maximum": "1000000",
                "currency": "CAD",
            },
            "anchor_keys": ["pool"],
            "interpretation": "Total program budget; not a per-award cap.",
        },
        {
            "requirement_key": "region",
            "spec": {"kind": "geography", "allowed": ["demo-region-north", "demo-region-south"]},
            "anchor_keys": ["region"],
            "interpretation": "Exact eligible region identifiers.",
        },
        {
            "requirement_key": "invitation",
            "spec": {"kind": "invitation", "required": True, "evidence_required": True},
            "anchor_keys": ["invite"],
            "interpretation": "Full applications need an EOI invitation.",
        },
        {
            "requirement_key": "full-deadline",
            "spec": {
                "kind": "deadline",
                "original_wording": FULL_DEADLINE_QUOTE,
                "precision": "exact",
                "date": "2026-03-31",
                "local_time": "17:00:00",
                "timezone": "America/Toronto",
                "boundary": "unstated",
            },
            "anchor_keys": ["full-deadline"],
            "interpretation": "Full application cutoff, Eastern Time.",
        },
        {
            "requirement_key": "eoi-deadline",
            "spec": {
                "kind": "deadline",
                "original_wording": EOI_DEADLINE_QUOTE,
                "precision": "exact",
                "date": "2026-01-15",
                "local_time": "17:00:00",
                "timezone": "America/Toronto",
                "boundary": "unstated",
            },
            "anchor_keys": ["eoi-deadline"],
            "scope": {"stage": "eoi"},
            "interpretation": "EOI cutoff (different stage).",
        },
    ]


def standard_case_body(c: TestClient, doc: dict[str, Any], **over: Any) -> dict[str, Any]:
    anchors = [
        anchor(c, doc, AMOUNT_QUOTE, "amount"),
        anchor(c, doc, NETWORK_QUOTE, "network"),
        anchor(c, doc, POOL_QUOTE, "pool"),
        anchor(c, doc, REGION_QUOTE, "region"),
        anchor(c, doc, INVITE_QUOTE, "invite"),
        anchor(c, doc, FULL_DEADLINE_QUOTE, "full-deadline"),
        anchor(c, doc, EOI_DEADLINE_QUOTE, "eoi-deadline"),
    ]
    body = {
        "idempotency_key": key("case"),
        "context": FULL_CONTEXT,
        "capture_links": [{"capture_id": doc["capture_id"]}],
        "anchors": anchors,
        "requirements": standard_requirements(),
    }
    body.update(over)
    return body


def create_case(c: TestClient, body: dict[str, Any]) -> dict[str, Any]:
    r = c.post("/api/funding/cases", json=body)
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()
    return data


def review(c: TestClient, env: dict[str, Any]) -> dict[str, Any]:
    v = env["version"]
    r = c.post(
        f"/api/funding/cases/{v['case_id']}/versions/{v['version']}/review",
        json={
            "idempotency_key": key("review"),
            "version_digest": env["version_digest"],
            "requirement_keys": [x["requirement_key"] for x in v["requirements"]],
        },
    )
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()
    return data


def evaluate(c: TestClient, env: dict[str, Any], **body: Any) -> dict[str, Any]:
    v = env["version"]
    payload = {"idempotency_key": key("eval"), "case_version": v["version"], **body}
    r = c.post(f"/api/funding/cases/{v['case_id']}/evaluations", json=payload)
    assert r.status_code == 201, r.text
    data: dict[str, Any] = r.json()
    return data


def outcomes(report: dict[str, Any]) -> dict[str, str]:
    return {r["requirement_key"]: r["outcome"] for r in report["results"]}
