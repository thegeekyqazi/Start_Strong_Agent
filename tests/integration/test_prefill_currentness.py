"""Actual C/B acceptance: stale actions, read-only views, independent integrity, history."""

from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.applications.store import InMemoryAnswerStore
from strongstart_api.features.automation.prefill_deps import (
    get_approved_prefill_reader,
    get_prefill_clock,
    get_prefill_currentness,
)
from strongstart_api.features.automation.prefill_plan import plan_hash
from strongstart_api.features.automation.prefill_store import PrefillRepository, run_id_for
from strongstart_api.features.automation.public import build_definition_repository
from strongstart_api.features.dev_b_store.core import canonical_json, new_object_id, sha256_hex
from strongstart_contracts.automation_prefill import PrefillGrant
from tests.automation.test_prefill_plan import StubBrowser

from .support import decide, prepare, publish, reader_for, save

runner = importlib.import_module("strongstart_api.features.automation.prefill_runner")
browser_module = importlib.import_module("strongstart_api.features.automation.prefill_browser")


@pytest.fixture
def current(tmp_path, monkeypatch):
    settings = Settings(_env_file=None, auth_mode="fixture", dev_b_store_dir=tmp_path / "store")
    app = create_app(settings)
    c = TestClient(app)
    pub = publish(c)
    approvals = {
        q: decide(c, save(c, pub, q, text))
        for q, text in [
            ("pf-org-name", "Riverside Youth Collective"),
            ("pf-summary", "We support early learning."),
        ]
    }
    response = prepare(c, pub, approvals)
    assert response.status_code == 201, response.text
    plan = response.json()
    stub = StubBrowser()
    monkeypatch.setattr(browser_module, "execute_actions", stub)
    return app, c, settings, pub, approvals, plan, stub


def execute(c: TestClient, plan: dict[str, Any], key: str = "int-currentness-key") -> Any:
    return c.post(
        f"/api/automation/prefill-plans/{plan['plan_id']}/execute",
        json={"expected_plan_sha256": plan["plan_sha256"], "idempotency_key": key},
    )


@pytest.mark.parametrize("change", ["one_character", "question_revision", "store_replaced"])
def test_actual_c_changes_before_entry_write_nothing(current, change):
    app, c, _settings, pub, _, plan, actuator = current
    if change == "one_character":
        save(c, pub, "pf-org-name", "Riverside Youth Collective!", 1)
    elif change == "question_revision":
        publish(c, "int-definition-revised", pub)
    else:
        app.state.c3_answer_store = InMemoryAnswerStore()
    view = c.get(f"/api/automation/prefill-plans/{plan['plan_id']}").json()
    assert view["plan"] == plan and view["availability"] == "stale"
    assert "prepare a new plan" in view["next_action"]
    response = execute(c, plan)
    assert response.status_code == 201, response.text
    run = response.json()["run"]["run"]
    assert (
        run["outcome"] == "blocked_before_entry" and run["activity"]["operations_performed"] == []
    )
    assert actuator.launches == 0


@pytest.mark.parametrize("change", ["expiry", "store_replaced"])
@pytest.mark.parametrize("stage", ["after_action", "completion"])
def test_expiry_and_replaced_store_are_rechecked_after_action_and_completion(
    current, monkeypatch, change, stage
):
    app, c, _, _, _, plan, _ = current
    now = [datetime.now(UTC)]
    app.dependency_overrides[get_prefill_clock] = lambda: lambda: now[0]

    def mutate() -> None:
        if change == "expiry":
            now[0] = datetime.fromisoformat(plan["expires_at"]) + timedelta(seconds=1)
        else:
            app.state.c3_answer_store = InMemoryAnswerStore()

    if stage == "after_action":
        original = runner._Hooks.after_write

        def after(self, index, outcome):
            if index == 0:
                mutate()
            return original(self, index, outcome)

        monkeypatch.setattr(runner._Hooks, "after_write", after)
    else:
        original_browser = browser_module.execute_actions

        def completed(*args, **kwargs):
            outcome = original_browser(*args, **kwargs)
            mutate()
            return outcome

        monkeypatch.setattr(browser_module, "execute_actions", completed)
    response = execute(c, plan)
    assert response.status_code == 201, response.text
    run = response.json()["run"]["run"]
    assert run["outcome"] == "stopped_with_partial_entry"
    if stage == "after_action":
        assert run["fields"][0]["state"] == "entered_then_stale"
        assert run["fields"][1]["state"] == "not_attempted"
    else:
        assert run["checks"][-1]["stage"] == "completion"
        assert run["checks"][-1]["status"] != "current"


@pytest.mark.parametrize("corruption", ["snapshot", "binding"])
def test_b_independently_refuses_tampered_real_c_envelope(current, corruption):
    app, c, settings, pub, approvals, _, _ = current
    real = reader_for(app, settings)

    class Tampered:
        is_fixture = True

        def resolve_for_prefill(self, org, approval):
            content = real.resolve_for_prefill(org, approval)
            if corruption == "snapshot":
                return content.model_copy(update={"dependency_snapshot_sha256": "0" * 64})
            from strongstart_contracts.knowledge_binding import ApprovedKnowledgeBinding

            return content.model_copy(
                update={
                    "a4_binding": ApprovedKnowledgeBinding(
                        organization_id=org,
                        application_context="test",
                        pack_version_id="test",
                        active_revision=1,
                        c_dependencies_sha256="0" * 64,
                        dependencies=[
                            {"kind": "pack_version", "ref_id": "test", "version": "test"}
                        ],
                        projection_sha256="0" * 64,
                    )
                }
            )

    app.dependency_overrides[get_approved_prefill_reader] = Tampered
    response = prepare(c, pub, approvals)
    assert response.status_code == 201, response.text
    assert response.json()["actions"] == []
    assert {h["reason"] for h in response.json()["held"]} == {"approval_integrity_mismatch"}


def test_missing_identity_precedes_factories_and_other_org_is_hidden(tmp_path):
    app = create_app(Settings(_env_file=None, dev_b_store_dir=tmp_path / "store"))
    calls = []

    def forbidden():
        calls.append("called")
        raise AssertionError("dependency before identity")

    app.dependency_overrides[get_approved_prefill_reader] = forbidden
    app.dependency_overrides[get_prefill_currentness] = forbidden
    c = TestClient(app)
    for path in [
        "/api/automation/prefill-plans",
        "/api/automation/prefill-plans/pfp-" + "0" * 26 + "/execute",
    ]:
        assert c.post(path, json={}).status_code == 401
    assert calls == []


def test_normal_c_empty_store_does_not_seed_unknown_approvals(tmp_path):
    app = create_app(
        Settings(_env_file=None, auth_mode="fixture", dev_b_store_dir=tmp_path / "store")
    )
    c = TestClient(app)
    pub = publish(c)
    response = prepare(c, pub, {"pf-org-name": "apr-unknown"})
    assert response.status_code == 201, response.text
    assert response.json()["actions"] == []
    assert response.json()["held"][0]["reason"] == "approval_not_usable"
    assert response.json()["producers"]["approval_reader"] == "c_reader"


def test_old_pending_format_refused_but_completed_receipt_replays_historically(current):
    _, c, settings, _, _, plan, actuator = current
    definitions = build_definition_repository(settings)
    assert definitions is not None
    repo = PrefillRepository(definitions.store)
    # Real v1-shaped plan: no new union/registration fields; verify its ORIGINAL raw hash.
    old = {k: v for k, v in plan.items() if k not in {"dependency_union", "a4_registration"}}
    old["plan_id"] = new_object_id("pfp")
    old["plan_format"] = "b2-approved-prefill/1"
    old["actions"] = [{k: v for k, v in a.items() if k != "a4_binding"} for a in old["actions"]]
    old["plan_sha256"] = plan_hash(old)
    repo.store.collection("demo-org", "prefill-plans").commit(
        idempotency_key="old-plan-create",
        command_hash=old["plan_sha256"],
        object_id=old["plan_id"],
        expected_version=0,
        build=lambda *_: old,
    )
    view = c.get(f"/api/automation/prefill-plans/{old['plan_id']}")
    assert view.status_code == 200 and view.json()["availability"] == "prepare_new_plan"
    denied = execute(c, old)
    assert denied.status_code == 409 and denied.json()["details"]["reason"] == "prepare_new_plan"
    assert actuator.launches == 0
    # Build actual historical completed receipt data, remove only new grant metadata,
    # and commit under the old plan's immutable single-use replay command.
    response = execute(c, plan)
    assert response.status_code == 201
    historical = response.json()["run"]["run"]
    historical |= {
        "run_id": run_id_for(old["plan_id"]),
        "plan_id": old["plan_id"],
        "plan_sha256": old["plan_sha256"],
        "run_version": 1,
    }
    grant = {
        k: v for k, v in historical["grant"].items() if k not in {"grant_format", "a4_registration"}
    }
    grant |= {"plan_id": old["plan_id"], "plan_sha256": old["plan_sha256"]}
    grant.pop("grant_sha256")
    grant["grant_sha256"] = sha256_hex(canonical_json(grant))
    historical["grant"] = grant
    assert not browser_module._grant_matches(
        PrefillGrant.model_validate(grant), [], "0" * 64, "0" * 64
    )
    repo.store.collection("demo-org", "prefill-runs").commit(
        idempotency_key="old-completed-key",
        command_hash=runner.command_hash(repo.get_plan("demo-org", old["plan_id"])),
        object_id=historical["run_id"],
        expected_version=0,
        build=lambda *_: historical,
    )
    before = repo.store.collection("demo-org", "prefill-runs").read(historical["run_id"], 1)
    replay = execute(c, old, "old-completed-key")
    assert replay.status_code == 200 and replay.json()["replayed"]
    assert replay.json()["run"]["run"]["outcome"] == "selected_fields_verified"
    assert replay.json()["run"]["run"]["grant"]["grant_sha256"] == grant["grant_sha256"]
    assert before == repo.store.collection("demo-org", "prefill-runs").read(historical["run_id"], 1)
    assert actuator.launches == 1


def test_actual_c_choice_prose_never_authorizes_options_or_conditional_fields(current):
    _, c, _, pub, _, _, _ = current
    approvals = {
        q: decide(c, save(c, pub, q, text))
        for q, text in [
            ("pf-service-area", "region"),
            ("pf-languages", "en"),
            ("pf-has-partners", "yes"),
            ("pf-partnership", "Community partners help with outreach."),
        ]
    }
    response = prepare(c, pub, approvals)
    assert response.status_code == 201, response.text
    plan = response.json()
    assert plan["actions"] == []
    reasons = {h["original_question_id"]: h["reason"] for h in plan["held"]}
    assert reasons == {
        "pf-service-area": "held_choice_value_unavailable",
        "pf-languages": "held_choice_value_unavailable",
        "pf-has-partners": "held_choice_value_unavailable",
        "pf-partnership": "held_parent_not_selected",
    }


def test_actual_c_demo_question_approval_cannot_substitute_for_b_published_ids(current):
    _, c, _, pub, _, _, _ = current
    response = c.post(
        "/api/applications/answers/versions",
        json={
            "question_id": "mission-q1",
            "question_version": 1,
            "evidence_bundle_id": "demo-evidence-a-v1",
            "text": "We support early learning.",
            "expected_answer_version": None,
        },
    )
    assert response.status_code == 201, response.text
    approval = decide(c, response.json())
    plan = prepare(c, pub, {"pf-org-name": approval}).json()
    assert plan["actions"] == [] and plan["held"][0]["reason"] == "approval_not_usable"
    assert plan["held"][0]["detail"] == "published_question_set_required"
