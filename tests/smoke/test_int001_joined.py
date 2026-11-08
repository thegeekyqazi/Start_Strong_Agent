"""Joined real C producer + real PostgreSQL/A4 + B planner/runner.

The browser is a controlled actuator in this DB suite. Real Chromium is tested separately
through the normal app factory; none of these tests replaces C's approval reader/store.
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from strongstart_api.features.automation.prefill_browser import BrowserOutcome, FieldOutcome, Hooks
from strongstart_api.features.automation.prefill_deps import get_prefill_currentness
from tests.automation.test_prefill_plan import StubBrowser
from tests.integration.a4_support import Managed
from tests.integration.managed_workspace import managed_client
from tests.integration.support import decide, prepare, publish, save

pytest_plugins = ["tests.integration.a4_support"]
pytestmark = pytest.mark.db
browser_module = importlib.import_module("strongstart_api.features.automation.prefill_browser")


def two(managed: Managed, tmp_path: Path) -> tuple[TestClient, dict[str, Any], dict[str, str]]:
    c, _settings, _source = managed_client(managed, tmp_path)
    pub = publish(c)
    bundle = managed.facade.resolve_active("demo-org", managed.context)
    approvals = {}
    for q, fact in zip(("pf-org-name", "pf-summary"), bundle.facts, strict=True):
        version = save(c, pub, q, "Linked: {{fact:" + fact.fact_id + "}}.")
        approvals[q] = decide(c, version)
    return c, pub, approvals


def execute(
    c: TestClient, plan: dict[str, Any], key: str = "int-joined-execute-1"
) -> dict[str, Any]:
    r = c.post(
        f"/api/automation/prefill-plans/{plan['plan_id']}/execute",
        json={"expected_plan_sha256": plan["plan_sha256"], "idempotency_key": key},
    )
    assert r.status_code in (200, 201), r.text
    return cast(dict[str, Any], r.json())


@pytest.fixture
def actuator(monkeypatch):
    class Actuator(StubBrowser):
        def __init__(self) -> None:
            super().__init__()
            self.operations: list[str] = []
            self.before: Callable[[int], None] = lambda index: None

        def __call__(self, page_html: bytes, *, hooks: Hooks, **kwargs: Any) -> BrowserOutcome:
            before = self.before

            class Boundary:
                def before_write(self, index: int) -> str | None:
                    before(index)
                    return hooks.before_write(index)

                def after_write(self, index: int, result: FieldOutcome) -> str | None:
                    return hooks.after_write(index, result)

            result = super().__call__(page_html, hooks=Boundary(), **kwargs)
            self.operations.extend(result.operations)
            return cast(BrowserOutcome, result)

    stub = Actuator()
    monkeypatch.setattr(browser_module, "execute_actions", stub)
    return stub


def test_managed_actual_plan_grant_and_full_union_replay(managed, tmp_path, actuator):
    c, pub, approvals = two(managed, tmp_path)
    response = prepare(c, pub, approvals)
    assert response.status_code == 201, response.text
    plan = response.json()
    assert plan["plan_format"] == "b2-approved-prefill/2"
    assert plan["producers"]["dependency_currentness"] == "a4_adapter"
    assert plan["producers"]["approval_reader"] == "c_reader"
    registration = plan["a4_registration"]
    assert (
        len([d for d in registration["binding"]["dependencies"] if d["kind"] == "fact_version"])
        == 2
    )
    target = managed.service.get_target("demo-org", "browser_plan", plan["plan_id"])
    assert target.projection_sha256 == registration["binding"]["projection_sha256"]
    assert target.revision == registration["target_revision"] == 1
    run = execute(c, plan)["run"]["run"]
    assert run["outcome"] == "selected_fields_verified" and len(run["fields"]) == 2
    assert len(actuator.operations) == 2
    grant = run["grant"]
    target = managed.service.get_target("demo-org", "browser_grant", grant["grant_id"])
    assert target.projection_sha256 == registration["binding"]["projection_sha256"]
    assert grant["a4_registration"]["target_id"] == grant["grant_id"]
    assert (
        target.dependencies
        == managed.service.get_target("demo-org", "browser_plan", plan["plan_id"]).dependencies
    )
    managed.replace()
    assert (
        c.get(f"/api/automation/prefill-plans/{plan['plan_id']}").json()["availability"]
        == "claimed"
    )
    replay = execute(c, plan)
    assert replay["replayed"] and replay["run"]["run"] == run
    assert actuator.launches == 1


@pytest.mark.parametrize("phase", ["after_preparation", "after_grant_registration"])
def test_actual_replacement_zero_writes_and_no_downgrade(
    managed, tmp_path, actuator, monkeypatch, phase
):
    c, pub, approvals = two(managed, tmp_path)
    response = prepare(c, pub, approvals)
    assert response.status_code == 201, response.text
    plan = response.json()
    if phase == "after_preparation":
        managed.replace()
        view = c.get(f"/api/automation/prefill-plans/{plan['plan_id']}").json()
        assert view["availability"] == "stale" and "prepare a new plan" in view["next_action"]
    else:
        from strongstart_api.features.knowledge.public import KnowledgeCurrentness

        original = KnowledgeCurrentness.register

        def replace_after(self, org, kind, target_id, binding, expected_revision=0):
            result = original(self, org, kind, target_id, binding, expected_revision)
            if kind == "browser_grant":
                managed.replace()
            return result

        monkeypatch.setattr(KnowledgeCurrentness, "register", replace_after)
    run = execute(c, plan)["run"]["run"]
    assert run["outcome"] == "blocked_before_entry"
    assert actuator.launches == 0 and actuator.operations == []


def test_missing_managed_verifier_blocks_preparation_and_execution(managed, tmp_path, actuator):
    c, pub, approvals = two(managed, tmp_path)
    response = prepare(c, pub, approvals)
    assert response.status_code == 201, response.text
    cast(FastAPI, c.app).dependency_overrides[get_prefill_currentness] = lambda: None
    unavailable = prepare(c, pub, approvals)
    assert (
        unavailable.status_code == 503
        and unavailable.json()["details"]["reason"] == "managed_verifier_unavailable"
    )
    view = c.get(f"/api/automation/prefill-plans/{response.json()['plan_id']}").json()
    assert view["availability"] == "dependency_unavailable"
    run = execute(c, response.json())["run"]["run"]
    assert (
        run["outcome"] == "blocked_before_entry"
        and run["outcome_reason"] == "dependency_unavailable"
    )
    assert actuator.launches == 0


def test_later_field_fact_change_is_checked_against_whole_union(managed, tmp_path, actuator):
    c, pub, approvals = two(managed, tmp_path)
    plan = prepare(c, pub, approvals).json()
    # Fact-only pack replacement is observed at the first action boundary and stops all.
    actuator.before = lambda index: managed.replace() if index == 0 else None
    run = execute(c, plan)["run"]["run"]
    assert run["outcome"] == "blocked_before_entry"
    assert actuator.operations == []
