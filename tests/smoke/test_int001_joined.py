"""Joined real C producer + real PostgreSQL/A4 + B planner/runner.

The browser is a controlled actuator in this DB suite. Real Chromium is tested separately
through the normal app factory; none of these tests replaces C's approval reader/store.
"""

from __future__ import annotations

import importlib
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
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
@pytest.mark.parametrize("replacement", [1, 2, 3])
def test_actual_replacement_zero_writes_and_no_downgrade(
    managed, tmp_path, actuator, monkeypatch, phase, replacement
):
    c, pub, approvals = two(managed, tmp_path)
    response = prepare(c, pub, approvals)
    assert response.status_code == 201, response.text
    plan = response.json()
    if phase == "after_preparation":
        managed.replace(replacement)
        view = c.get(f"/api/automation/prefill-plans/{plan['plan_id']}").json()
        assert view["availability"] == "stale" and "prepare a new plan" in view["next_action"]
    else:
        from strongstart_api.features.knowledge.public import KnowledgeCurrentness

        original = KnowledgeCurrentness.register

        def replace_after(self, org, kind, target_id, binding, expected_revision=0):
            result = original(self, org, kind, target_id, binding, expected_revision)
            if kind == "browser_grant":
                managed.replace(replacement)
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


def test_event_controlled_pack_change_between_fields_preserves_partial_receipt(
    managed, tmp_path, actuator, monkeypatch
):
    c, pub, approvals = two(managed, tmp_path)
    plan = prepare(c, pub, approvals).json()
    runner = importlib.import_module("strongstart_api.features.automation.prefill_runner")
    first_entered, replaced = threading.Event(), threading.Event()
    original = runner._Hooks.after_write

    def after(self, index, outcome):
        if index == 0:
            first_entered.set()
            assert replaced.wait(5)
        return original(self, index, outcome)

    monkeypatch.setattr(runner._Hooks, "after_write", after)
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(execute, c, plan)
        try:
            assert first_entered.wait(5)
            managed.replace(2)  # real policy-only activation; conservative root invalidates
        finally:
            replaced.set()
        run = future.result(timeout=10)["run"]["run"]
    assert run["outcome"] == "stopped_with_partial_entry"
    assert run["fields"][0]["state"] == "entered_then_stale"
    assert run["fields"][1]["state"] == "not_attempted"
    assert actuator.operations == ["fill:org-name-field"]


def test_get_reads_never_register_retarget_or_renew(managed, tmp_path, actuator, monkeypatch):
    from strongstart_api.features.knowledge.public import KnowledgeCurrentness

    c, pub, approvals = two(managed, tmp_path)
    plan = prepare(c, pub, approvals).json()

    def forbidden(*args, **kwargs):
        raise AssertionError("registration during GET")

    monkeypatch.setattr(KnowledgeCurrentness, "register", forbidden)
    for _ in range(2):
        view = c.get(f"/api/automation/prefill-plans/{plan['plan_id']}").json()
        assert view["plan"] == plan and view["availability"] == "executable"
    target_before = managed.service.get_target("demo-org", "browser_plan", plan["plan_id"])
    managed.replace(3)
    for _ in range(2):
        view = c.get(f"/api/automation/prefill-plans/{plan['plan_id']}").json()
        assert view["plan"] == plan and view["availability"] == "stale"
    target_after = managed.service.get_target("demo-org", "browser_plan", plan["plan_id"])
    assert target_after.state == "stale" and target_after.revision == target_before.revision
    assert target_after.projection_sha256 == target_before.projection_sha256
    assert actuator.launches == 0


def test_registration_failure_after_claim_never_retries(managed, tmp_path, actuator, monkeypatch):
    from strongstart_api.features.knowledge.packs import PackConflictError
    from strongstart_api.features.knowledge.public import KnowledgeCurrentness

    c, pub, approvals = two(managed, tmp_path)
    plan = prepare(c, pub, approvals).json()
    original = KnowledgeCurrentness.register
    calls = []

    def fail_grant(self, org, kind, target_id, binding, expected_revision=0):
        calls.append(kind)
        if kind == "browser_grant":
            raise PackConflictError
        return original(self, org, kind, target_id, binding, expected_revision)

    monkeypatch.setattr(KnowledgeCurrentness, "register", fail_grant)
    result = execute(c, plan)
    assert result["run"]["run"]["outcome_reason"] == "grant_registration_failed"
    assert result["run"]["run"]["outcome"] == "blocked_before_entry"
    replay = execute(c, plan)
    assert replay["replayed"] and replay["run"]["run"] == result["run"]["run"]
    assert calls == ["browser_grant"] and actuator.launches == 0


def test_replacement_before_preparation_registration_publishes_no_executable_plan(
    managed, tmp_path, actuator, monkeypatch
):
    from strongstart_api.features.automation.public import build_definition_repository
    from strongstart_api.features.knowledge.public import KnowledgeCurrentness

    c, settings, _source = managed_client(managed, tmp_path)
    pub = publish(c)
    approval = decide(c, save(c, pub, "pf-org-name", "Synthetic organization"))
    original = KnowledgeCurrentness.register

    def replacement_wins(self, org, kind, target_id, binding, expected_revision=0):
        managed.replace()
        return original(self, org, kind, target_id, binding, expected_revision)

    monkeypatch.setattr(KnowledgeCurrentness, "register", replacement_wins)
    response = prepare(c, pub, {"pf-org-name": approval})
    assert (
        response.status_code == 409
        and response.json()["details"]["reason"] == "managed_registration_failed"
    )
    repository = build_definition_repository(settings)
    assert repository is not None
    assert (
        repository.store.collection("demo-org", "prefill-plans").list_ids(None, 50).object_ids == []
    )
    assert actuator.launches == 0


@pytest.mark.parametrize("stage", ["after_action", "completion"])
def test_managed_verifier_failure_cannot_finish_fully_verified(
    managed, tmp_path, actuator, monkeypatch, stage
):
    from strongstart_api.features.knowledge.public import KnowledgeCurrentness
    from strongstart_contracts.automation_prefill import DependencyCurrentness

    runner = importlib.import_module("strongstart_api.features.automation.prefill_runner")
    c, pub, approvals = two(managed, tmp_path)
    plan = prepare(c, pub, approvals).json()
    unavailable = threading.Event()
    check = KnowledgeCurrentness.check_registration

    def failing(self, org, registration):
        if unavailable.is_set():
            return DependencyCurrentness(status="unavailable", detail="injected_verifier_outage")
        return check(self, org, registration)

    monkeypatch.setattr(KnowledgeCurrentness, "check_registration", failing)
    if stage == "after_action":
        after = runner._Hooks.after_write

        def fail_after(self, index, outcome):
            unavailable.set()
            return after(self, index, outcome)

        monkeypatch.setattr(runner._Hooks, "after_write", fail_after)
    else:

        def completed(*args, **kwargs):
            result = actuator(*args, **kwargs)
            unavailable.set()
            return result

        monkeypatch.setattr(browser_module, "execute_actions", completed)
    run = execute(c, plan)["run"]["run"]
    assert run["outcome"] == "stopped_with_partial_entry"
    assert run["outcome_reason"] == "dependency_unavailable"
    if stage == "after_action":
        assert run["fields"][0]["state"] == "entered_then_stale"
        assert run["fields"][1]["state"] == "not_attempted"
