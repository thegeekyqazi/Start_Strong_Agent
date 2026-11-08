"""C4-SKL-001 essential verification (lean checkpoint scope, decision C4-SKL-001).

Real API + PostgreSQL (disposable DB) + the actual C draft/check pipeline. Model calls use the
explicit labelled FakeAdapter fixture, or explicit test-only overrides below.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.db import organizations
from strongstart_api.features.applications.deps import get_model_adapter
from strongstart_api.features.applications.models.base import StructuredTask
from strongstart_api.features.applications.models.fake import FakeAdapter
from strongstart_api.features.skills.compiler import compile_package
from strongstart_api.features.skills.demo import DEMO_CONTEXT
from strongstart_api.identity import FIXTURE_IDENTITY, require_identity
from strongstart_api.seed import seed_demo
from tests.conftest import BUNDLE_PATH

pytestmark = pytest.mark.db
SAMPLE = "Our kids love story circle saturdays at the Demo Literacy Program."


class Recording(FakeAdapter):
    def __init__(self) -> None:
        self.tasks: list[StructuredTask] = []

    async def complete(self, task: StructuredTask) -> str:
        self.tasks.append(task)
        return await super().complete(task)


class DropsLastPart(Recording):
    """TEST-ONLY screening double: silently skips the trailing part."""

    async def complete(self, task: StructuredTask) -> str:
        if task.operation != "screen_practice":
            return await super().complete(task)
        parts = [p["part"] for p in task.payload["parts"]][:-1]
        return json.dumps({"signal": "no_flags", "covered_parts": parts, "findings": []})


@pytest.fixture
def env(data_db, tmp_path):
    data_db.migrate()
    seed_demo(data_db.engine, BUNDLE_PATH)
    with data_db.engine.begin() as conn:
        conn.execute(
            insert(organizations).values(
                id="other-org",
                display_name="SYNTHETIC other org",
                provenance_class="simulated",
                is_simulated=True,
            )
        )

    def make(adapter: Any = None, identity: Any = FIXTURE_IDENTITY, auth: str = "fixture"):
        settings = Settings(
            _env_file=None,
            auth_mode=auth,
            answer_store_backend="postgres",
            database_url=data_db.url,
            dev_b_store_dir=tmp_path / "b",
        )
        app = create_app(settings)
        if adapter is not None:
            app.dependency_overrides[get_model_adapter] = lambda: adapter
        if identity is not FIXTURE_IDENTITY:
            app.dependency_overrides[require_identity] = lambda: identity
        return TestClient(app)

    return make


def _target(c: TestClient) -> dict[str, Any]:
    ws = c.get("/api/applications/workspace").json()
    q = sorted(ws["question_set"]["questions"], key=lambda q: q["order"])[0]
    return {
        "question_id": q["question_id"],
        "question_version": q["question_version"],
        "evidence_bundle_id": ws["evidence_bundle"]["bundle_id"],
    }


def _candidate(c: TestClient, key: str = "demo") -> dict[str, Any]:
    src = c.post(f"/api/skills/fixture-sources/{key}")
    assert src.status_code == 201, src.text
    sid = src.json()["source_version_id"]
    # Candidate generation is refused until the source is explicitly reviewed as authority.
    early = c.post("/api/skills/candidates", json={"source_version_id": sid})
    assert (
        early.status_code == 422 and early.json()["details"]["reason"] == "source_authority_missing"
    )
    assert c.post(f"/api/skills/sources/{sid}/authority").status_code == 200
    cand = c.post("/api/skills/candidates", json={"source_version_id": sid})
    assert cand.status_code == 201, cand.text
    return cand.json()


def _activate(c: TestClient, cand: dict[str, Any], key: str = "act-1") -> dict[str, Any]:
    cid, sha = cand["candidate_id"], cand["package"]["package_sha256"]
    screened = c.post(f"/api/skills/candidates/{cid}/screening").json()
    assert screened["screening"]["complete"] and screened["status"] == "needs_review", screened
    reviewed = c.post(
        f"/api/skills/candidates/{cid}/review",
        json={"package_sha256": sha, "source_supported": True, "rationale": "matches source"},
    )
    assert reviewed.status_code == 200 and reviewed.json()["status"] == "approved", reviewed.text
    act = c.post(
        f"/api/skills/candidates/{cid}/activate",
        json={"package_sha256": sha, "idempotency_key": key},
    )
    assert act.status_code == 200, act.text
    return act.json()


def test_source_to_candidate_to_activation_to_draft_preview(env):
    adapter = Recording()
    c = env(adapter)
    cand = _candidate(c)
    assert [r["operator"] for r in cand["rules"]] == ["preferred_term", "protected_name"]
    assert cand["proposer"]["is_fixture"] is True and cand["tests"]["passed"]
    assert {f["path"] for f in cand["package"]["files"]} == {
        "SKILL.md",
        "rules.json",
        "references/policy-excerpts.md",
    }
    release = _activate(c, cand)
    assert release["effective_state"] == "active"
    # Same command is idempotent; the same key with another payload conflicts.
    again = c.post(
        f"/api/skills/candidates/{cand['candidate_id']}/activate",
        json={"package_sha256": cand["package"]["package_sha256"], "idempotency_key": "act-1"},
    )
    assert again.json()["release_id"] == release["release_id"]

    preview = c.post("/api/skills/preview", json={**_target(c), "sample_text": SAMPLE})
    assert preview.status_code == 200, preview.text
    p = preview.json()
    assert p["working_preview_only"] is True and p["approval_permitted"] is False
    assert p["current"] and p["applied"]["release_id"] == release["release_id"]
    assert p["applied"]["package_sha256"] == cand["package"]["package_sha256"]
    # The compiled guidance actually reached the draft model call; baseline did not get it.
    drafts = [t for t in adapter.tasks if t.operation == "draft_answer"]
    assert "writing_practices" not in drafts[-2].payload
    assert drafts[-1].payload["writing_practices"] == p["applied"]["instructions"]
    assert '"children" instead of "kids"' in drafts[-1].instructions

    def fails(report: dict[str, Any], rule: str) -> list[dict[str, Any]]:
        return [
            f
            for f in report["findings"]
            if f["result"]["outcome"] == "fail" and rule in f["result"]["reasons"]
        ]

    # Same sample: the activated practice flags it; the baseline (base policy only) does not.
    assert fails(p["sample_practice_check"], "c4-term-1")[0]["result"]["expected"] == "children"
    assert fails(p["sample_practice_check"], "c4-name-2")
    assert not fails(p["sample_baseline_check"], "c4-term-1")
    # Core checks are kept: base-policy rules still run in the composed preview policy.
    practice_rules = {f["result"]["rule_id"] for f in p["sample_practice_check"]["findings"]}
    assert {"APP-01", "POL-01", "POL-02"} <= practice_rules
    # A forged client field cannot reach the preview boundary.
    forged = c.post("/api/skills/preview", json={**_target(c), "approved": True})
    assert forged.status_code == 422

    # Deterministic compiler: identical inputs give a byte-identical hash.
    from strongstart_api.features.skills.service import RULES

    rules = RULES.validate_python(cand["rules"])
    src = c.get("/api/skills").json()["sources"][-1]
    a = compile_package(
        DEMO_CONTEXT, src["source_version_id"], src["text_sha256"], src["provenance"]["note"], rules
    )
    assert a.package_sha256 == cand["package"]["package_sha256"]


def test_tampered_hash_incomplete_screening_and_hostile_candidate_cannot_activate(env):
    c = env(DropsLastPart())
    cand = _candidate(c)
    cid, sha = cand["candidate_id"], cand["package"]["package_sha256"]
    screened = c.post(f"/api/skills/candidates/{cid}/screening").json()
    assert screened["screening"]["complete"] is False
    assert any(h.startswith("screening_incomplete_missing:") for h in screened["hold_reasons"])
    review = c.post(
        f"/api/skills/candidates/{cid}/review",
        json={"package_sha256": sha, "source_supported": True},
    )
    assert review.status_code == 422 and review.json()["details"]["reason"] == "gates_not_passed"
    act = c.post(
        f"/api/skills/candidates/{cid}/activate",
        json={"package_sha256": sha, "idempotency_key": "k1"},
    )
    assert act.status_code == 422

    c = env(Recording())
    good = _candidate(c)
    tampered = good["package"]["package_sha256"][::-1]
    gid = good["candidate_id"]
    c.post(f"/api/skills/candidates/{gid}/screening")
    bad_review = c.post(
        f"/api/skills/candidates/{gid}/review",
        json={"package_sha256": tampered, "source_supported": True},
    )
    assert bad_review.status_code == 409
    bad_act = c.post(
        f"/api/skills/candidates/{gid}/activate",
        json={"package_sha256": tampered, "idempotency_key": "k2"},
    )
    assert bad_act.status_code in (409, 422)
    no_review = c.post(
        f"/api/skills/candidates/{gid}/activate",
        json={"package_sha256": good["package"]["package_sha256"], "idempotency_key": "k3"},
    )
    assert no_review.json()["details"]["reason"] == "review_missing_or_stale"

    adapter = Recording()
    c = env(adapter)
    hostile = _candidate(c, "hostile")
    cats = {f["category"] for f in hostile["scan"]["findings"]}
    assert {
        "instruction_override",
        "exfiltration",
        "secret_canary",
        "hidden_control",
        "unregistered_name",
    } <= cats
    assert hostile["status"] == "held"
    # No client-facing response carries the planted secret (source, quotes, package, scan).
    # Includes truncated prefixes: an excerpt window must never expose part of a secret.
    assert "sk-can" not in json.dumps(hostile)
    assert "sk-can" not in c.get("/api/skills").text
    hid = hostile["candidate_id"]
    screened = c.post(f"/api/skills/candidates/{hid}/screening").json()
    assert screened["screening"]["hold_reason"] == "quarantined_secret_not_sent_to_model"
    assert not [t for t in adapter.tasks if t.operation == "screen_practice"]
    assert c.get(f"/api/skills/candidates/{hid}/package").status_code == 422
    act = c.post(
        f"/api/skills/candidates/{hid}/activate",
        json={"package_sha256": hostile["package"]["package_sha256"], "idempotency_key": "k4"},
    )
    assert act.status_code == 422

    conflict = _candidate(c, "conflict")
    assert "scan_block:policy_conflict" in conflict["hold_reasons"]


def test_revocation_and_source_change_prevent_subsequent_use(env):
    c = env(Recording())
    target = _target(c)
    release = _activate(c, _candidate(c))
    assert c.post("/api/skills/preview", json=target).json()["current"] is True
    revoked = c.post(
        "/api/skills/releases/revoke",
        json={"release_id": release["release_id"], "reason": "demo revoke"},
    )
    assert revoked.json()["effective_state"] == "revoked"
    after = c.post("/api/skills/preview", json=target).json()
    assert after["applied"] is None and after["hold_reason"] == "no_active_practice"

    second = _candidate(c)
    _activate(c, second, key="act-2")
    assert c.post("/api/skills/preview", json=target).json()["current"] is True
    # Publishing a new source version makes the active release's source noncurrent.
    assert c.post("/api/skills/fixture-sources/demo").status_code == 201
    stale = c.post("/api/skills/preview", json=target).json()
    assert stale["applied"] is None and stale["hold_reason"] == "release_stale_source"
    assert (
        c.get(f"/api/skills/candidates/{second['candidate_id']}").json()["status"] == "stale_source"
    )
    # A fresh app instance (new pool) sees the same durable state; history stays readable.
    fresh = env(Recording())
    overview = fresh.get("/api/skills").json()
    states = {r["release_id"]: r["effective_state"] for r in overview["releases"]}
    assert states[release["release_id"]] == "revoked"
    assert fresh.post("/api/skills/preview", json=target).json()["applied"] is None


def test_missing_identity_and_other_organization_cannot_bypass_access(env):
    c = env(Recording())
    cand = _candidate(c)
    cid, sha = cand["candidate_id"], cand["package"]["package_sha256"]

    anonymous = env(Recording(), auth="none")
    assert anonymous.get("/api/skills").status_code == 401
    assert (
        anonymous.post(
            f"/api/skills/candidates/{cid}/activate",
            json={"package_sha256": sha, "idempotency_key": "x"},
        ).status_code
        == 401
    )

    other_identity = FIXTURE_IDENTITY.model_copy(update={"organization_id": "other-org"})
    other = env(Recording(), identity=other_identity)
    assert other.get(f"/api/skills/candidates/{cid}").status_code == 404
    assert (
        other.post(
            f"/api/skills/candidates/{cid}/activate",
            json={"package_sha256": sha, "idempotency_key": "x"},
        ).status_code
        == 404
    )
    assert other.get("/api/skills").json()["candidates"] == []

    not_staff = FIXTURE_IDENTITY.model_copy(update={"is_fixture": False})
    viewer = env(Recording(), identity=not_staff)
    denied = viewer.post(f"/api/skills/candidates/{cid}/screening")
    assert denied.status_code == 403
