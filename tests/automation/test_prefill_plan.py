"""B2-AUTO-002 planning, grants, claims and staleness without Chromium (P1 harness).

The browser is replaced by ``StubBrowser``, which drives the real ``before_write`` /
``after_write`` hooks (C rechecks, persisted intent, progress) and counts launches. Real
Chromium behaviour is in ``tests/browser/test_prefill_browser.py``. Approvals come from
the explicit TEST provider in ``prefill_support``; nothing here is a C3 integration.
"""

from __future__ import annotations

import importlib
import json
import multiprocessing
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from strongstart_api.config import Settings
from strongstart_api.features.automation.prefill_browser import BrowserOutcome, FieldOutcome
from strongstart_api.features.automation.prefill_store import PrefillRepository, run_id_for
from strongstart_api.features.dev_b_store.core import LocalVersionStore, set_lock_observer
from strongstart_contracts.automation_prefill import TrustedAttachmentRecord
from tests.automation.prefill_support import (
    PORTAL_SRC,
    Harness,
    TestCurrentness,
    approve,
    execute,
    harness,
    key,
    plan,
    published,
    save_definition,
    sha,
)

prefill_browser = importlib.import_module("strongstart_api.features.automation.prefill_browser")
TIMEOUT = 10
RUNS_LOCK = "prefill-runs.lock"


class StubBrowser:
    """Stands in for Chromium: calls the real hooks and reports exact matches."""

    def __init__(self) -> None:
        self.launches = 0
        self.pause_after_launch: threading.Event | None = None
        self.launched = threading.Event()

    def __call__(self, page_html: bytes, *, actions: list[Any], hooks: Any, **_: Any) -> Any:
        self.launches += 1
        self.launched.set()
        if self.pause_after_launch is not None:
            assert self.pause_after_launch.wait(TIMEOUT)
        out = BrowserOutcome(stage="completed", reason=None, final_reread="all_match")
        for a in actions:
            stop = hooks.before_write(a.index)
            if stop is not None:
                out.fields[a.index] = FieldOutcome(a.index, "blocked_before_write", stop)
                out.stage, out.reason = (
                    ("stopped" if out.operations else "blocked_before_entry"),
                    stop,
                )
                return out
            value = a.value if a.value is not None else ",".join(a.choices)
            res = FieldOutcome(
                a.index, "entered_verified", actual_value=value, actual_sha256=sha(value),
                result="match",
            )  # fmt: skip
            out.operations.append(f"{a.operation}:{a.control.field_id}")
            stop = hooks.after_write(a.index, res)
            if stop is not None:
                res.state, res.reason = "entered_then_stale", stop
                out.fields[a.index] = res
                out.stage, out.reason = "stopped", stop
                return out
            out.fields[a.index] = res
        return out


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch) -> StubBrowser:
    s = StubBrowser()
    monkeypatch.setattr(prefill_browser, "execute_actions", s)
    return s


@pytest.fixture
def h(tmp_path: Path) -> Harness:
    return harness(tmp_path)


def two_text(h: Harness) -> tuple[dict[str, Any], dict[str, Any]]:
    pub = save_definition(h.client)
    a1 = approve(h, pub, "pf-org-name", "Riverside Youth Collective")
    a2 = approve(h, pub, "pf-summary", "We run after-school tutoring.")
    r = plan(h, pub, [("pf-org-name", a1), ("pf-summary", a2)])
    assert r.status_code == 201, r.text
    return pub, r.json()


# --------------------------------------------------------------------------- AUTO2-01 / 28


def test_auto2_01_identity_precedes_everything_and_other_org_is_unknown(
    h: Harness, stub: StubBrowser, tmp_path: Path
) -> None:
    from fastapi.testclient import TestClient

    from strongstart_api.app import create_app
    from tests.automation.prefill_support import make_settings

    anon = TestClient(create_app(make_settings(tmp_path / "anon", auth_mode="none")))
    pid, rid = "pfp-" + "0" * 26, "pfr-" + "0" * 26
    for method, url in [
        ("post", "/api/automation/prefill-plans"),
        ("get", f"/api/automation/prefill-plans/{pid}"),
        ("post", f"/api/automation/prefill-plans/{pid}/execute"),
        ("get", f"/api/automation/prefill-runs/{rid}"),
    ]:
        r = getattr(anon, method)(url, json={}) if method == "post" else anon.get(url)
        assert r.status_code == 401, (url, r.text)
    assert h.approvals.calls == [] and stub.launches == 0

    _, p = two_text(h)
    ran = execute(h, p)
    assert ran.status_code == 201
    other = h.other_org_client()
    unknown = other.get(f"/api/automation/prefill-plans/{'pfp-' + 'f' * 26}")
    foreign = other.get(f"/api/automation/prefill-plans/{p['plan_id']}")
    assert unknown.status_code == foreign.status_code == 404
    assert unknown.json()["details"] == foreign.json()["details"] == {"reason": "not_found"}
    run_id = ran.json()["run"]["run"]["run_id"]
    assert other.get(f"/api/automation/prefill-runs/{run_id}").status_code == 404
    body = {"expected_plan_sha256": p["plan_sha256"], "idempotency_key": key()}
    r = other.post(f"/api/automation/prefill-plans/{p['plan_id']}/execute", json=body)
    assert r.status_code == 404 and stub.launches == 1


def test_auto2_28_other_org_approval_is_not_usable_and_reports_leak_nothing(h: Harness) -> None:
    pub = save_definition(h.client)
    foreign = h.approvals.approve(
        pub["question_set_id"],
        published(pub, "pf-org-name"),
        "<script>alert(1)</script> Other org",
        organization_id="other-org",
    )
    p = plan(h, pub, [("pf-org-name", foreign)]).json()
    assert p["actions"] == [] and p["executable"] is False
    assert p["held"][0]["reason"] == "approval_not_usable"
    assert "Other org" not in json.dumps(p)  # content of another tenant never appears
    # Stored strings are data: a hostile approved text is kept verbatim, never interpreted.
    own = approve(h, pub, "pf-org-name", "<img src=x onerror=alert(1)>")
    p2 = plan(h, pub, [("pf-org-name", own)]).json()
    assert p2["actions"][0]["intended_value"] == "<img src=x onerror=alert(1)>"


# --------------------------------------------------------------------------- AUTO2-02


@pytest.mark.parametrize(
    "mutate",
    [
        lambda b: b.update(organization_id="demo-org"),
        lambda b: b["selections"][0].update(text="injected content"),
        lambda b: b["selections"][0].update(selector="#org-name"),
        lambda b: b.update(portal_url="http://127.0.0.1:9/portal"),
        lambda b: b["selections"][0].update(approved=True),
        lambda b: b.update(portal_fixture_id=7),
        lambda b: b.update(question_set_id="qs-def-zz"),
        lambda b: b.update(selections=b["selections"] * 11),
        lambda b: b.update(selections=[b["selections"][0], b["selections"][0]]),
        lambda b: b["selections"].append(
            {
                **b["selections"][1],
                "approval_snapshot_id": b["selections"][0]["approval_snapshot_id"],
            }
        ),
    ],
)
def test_auto2_02_strict_plan_requests(h: Harness, mutate: Any) -> None:
    pub = save_definition(h.client)
    a1 = approve(h, pub, "pf-org-name", "A")
    a2 = approve(h, pub, "pf-summary", "B")
    body: dict[str, Any] = {
        "question_set_id": pub["question_set_id"],
        "portal_fixture_id": "rep-prefill-v1",
        "selections": [
            {"published_question_id": published(pub, "pf-org-name"), "approval_snapshot_id": a1},
            {"published_question_id": published(pub, "pf-summary"), "approval_snapshot_id": a2},
        ],
    }
    mutate(body)
    r = h.client.post("/api/automation/prefill-plans", json=body)
    assert r.status_code == 422, r.text
    assert h.approvals.calls == []


def test_auto2_02_strict_execute_requests(h: Harness, stub: StubBrowser) -> None:
    _, p = two_text(h)
    url = f"/api/automation/prefill-plans/{p['plan_id']}/execute"
    good = {"expected_plan_sha256": p["plan_sha256"], "idempotency_key": key()}
    for bad in [
        {**good, "approved": True},
        {**good, "actions": [{"field_id": "org-name-field", "value": "x"}]},
        {**good, "organization_id": "demo-org"},
        {**good, "idempotency_key": 12345678},
        {"expected_plan_sha256": p["plan_sha256"]},
    ]:
        assert h.client.post(url, json=bad).status_code == 422
    assert stub.launches == 0


# --------------------------------------------------------------------------- AUTO2-03 / 04


def test_auto2_03_unconfigured_reader_is_503_without_any_seeded_fallback(tmp_path: Path) -> None:
    h = harness(tmp_path, reader="none")
    pub = save_definition(h.client)
    r = plan(h, pub, [("pf-org-name", "apr-anything")])
    assert r.status_code == 503 and r.json()["details"]["reason"] == "approval_reader_unavailable"
    assert list(h.settings.dev_b_store_dir.glob("org-*/prefill-plans/*")) == []


@pytest.mark.parametrize(
    ("how", "reason"),
    [
        ("template_hash", "approval_integrity_mismatch"),
        ("snapshot_hash", "approval_integrity_mismatch"),
        ("rendered_hash", "approval_integrity_mismatch"),
        ("answer_id", "approval_integrity_mismatch"),
        ("dependencies", "approval_integrity_mismatch"),
    ],
)
def test_auto2_04_each_hash_and_identity_is_checked_independently(
    h: Harness, how: str, reason: str
) -> None:
    pub = save_definition(h.client)
    a = approve(h, pub, "pf-org-name", "Name {template}", rendered="Name Rendered")
    ok = plan(h, pub, [("pf-org-name", a)]).json()
    assert ok["actions"][0]["intended_value"] == "Name Rendered"  # rendered text is entered
    assert ok["actions"][0]["template_sha256"] == sha("Name {template}")
    assert ok["actions"][0]["rendered_sha256"] == sha("Name Rendered")
    h.approvals.corrupt(a, how)
    bad = plan(h, pub, [("pf-org-name", a)]).json()
    assert bad["actions"] == [] and bad["held"][0]["reason"] == reason


def test_auto2_04_unresolved_fact_tokens_are_never_entered(h: Harness) -> None:
    pub = save_definition(h.client)
    for rendered in ["We served {{fact:fact-123}} youth.", "Budget {{unsupported:amount}}."]:
        a = approve(h, pub, "pf-summary", rendered)
        p = plan(h, pub, [("pf-summary", a)]).json()
        assert p["actions"] == [] and p["held"][0]["reason"] == "unresolved_fact_token"


# --------------------------------------------------------------------------- AUTO2-05 / 06


def test_auto2_05_identities_never_substitute(h: Harness) -> None:
    pub = save_definition(h.client)
    qs = pub["question_set_id"]
    # 1. the source ID and a C fixture ID are not published question IDs of this set
    for wrong in ["pf-org-name", "mission-q1"]:
        a = h.approvals.approve(qs, wrong, "text")
        body = {
            "question_set_id": qs,
            "portal_fixture_id": "rep-prefill-v1",
            "selections": [{"published_question_id": wrong, "approval_snapshot_id": a}],
        }
        r = h.client.post("/api/automation/prefill-plans", json=body)
        assert (
            r.status_code == 422 and r.json()["details"]["reason"] == "question_not_in_definition"
        )
    # 2. an approval naming another question cannot be used for the selected one
    other = h.approvals.approve(qs, published(pub, "pf-summary"), "Summary text")
    p = plan(h, pub, [("pf-org-name", other)]).json()
    assert p["held"][0]["reason"] == "approval_identity_mismatch"
    # 3. an approval for the source ID (not the published ID) is not accepted either
    src = h.approvals.approve(qs, "pf-org-name", "Name")
    p = plan(h, pub, [("pf-org-name", src)]).json()
    assert p["held"][0]["reason"] == "approval_identity_mismatch"
    # 4. the explicit publication mapping works
    good = approve(h, pub, "pf-org-name", "Name")
    p = plan(h, pub, [("pf-org-name", good)]).json()
    assert p["actions"][0]["published_question_id"] == published(pub, "pf-org-name")
    assert p["actions"][0]["original_question_id"] == "pf-org-name"
    # 5. a definition from another source cannot be bound to this portal
    rep = save_definition(h.client, PORTAL_SRC)
    a = approve(h, rep, "rp-mission", "Mission")
    r = plan(h, rep, [("rp-mission", a)], portal="rep-prefill-v1")
    assert r.status_code == 422 and r.json()["details"]["reason"] == "portal_definition_mismatch"


def test_auto2_06_plan_binds_a_unique_versioned_map(h: Harness) -> None:
    pub, p = two_text(h)
    portal = p["portal"]
    assert portal["binding_format"] == "b2-bound-form-map/1"
    assert portal["fingerprint_algorithm"] == "b2-form-fp/1" and portal["form_version"] == 1
    ids = [f["field_id"] for f in portal["fields"]]
    assert len(ids) == len(set(ids)) == 9
    assert {f["published_question_id"] for f in portal["fields"]} == {
        m["published_question_id"] for m in pub["id_mapping"]
    }


# --------------------------------------------------------------------------- AUTO2-08 / 09


def test_auto2_08_preparing_a_plan_writes_nothing_and_needs_explicit_execution(
    h: Harness, stub: StubBrowser
) -> None:
    _, p = two_text(h)
    assert stub.launches == 0 and p["submission"] == "not_possible"
    assert "submit" in p["forbidden_operations"] and "click" in p["forbidden_operations"]
    view = h.client.get(f"/api/automation/prefill-plans/{p['plan_id']}").json()
    assert view["availability"] == "executable" and view["run_id"] is None
    # a forged hash or a non-existent plan never reaches the browser
    r = execute(h, {**p, "plan_sha256": "f" * 64})
    assert r.status_code == 409 and r.json()["details"]["reason"] == "plan_hash_mismatch"
    r = execute(h, {**p, "plan_id": "pfp-" + "1" * 26})
    assert r.status_code == 404
    assert stub.launches == 0


def test_auto2_09_grant_binds_every_action_critical_value(h: Harness, stub: StubBrowser) -> None:
    from strongstart_api.features.automation.prefill_runner import derive_grant, grant_problem
    from strongstart_contracts.automation_prefill import PrefillPlan

    _, raw = two_text(h)
    p = PrefillPlan.model_validate(raw)
    grant = derive_grant(p, "fixture-staff", h.clock())
    assert grant_problem(grant, p) is None
    assert grant.expires_at == p.expires_at and grant.runtime_epoch == p.runtime_epoch
    assert [o.field_id for o in grant.operations] == ["org-name-field", "summary-field"]
    changes: list[dict[str, Any]] = [
        {"organization_id": "other-org"},
        {"actor_id": "someone-else"},
        {"logical_origin": "fixture://elsewhere.local"},
        {"expected_fingerprint": "0" * 64},
        {"plan_sha256": "1" * 64},
        {"runtime_epoch": "epoch-other"},
        {"operations": [grant.operations[0]]},
    ]
    for change in changes:
        assert grant_problem(grant.model_copy(update=change), p) is not None, change
    # A tampered stored plan fails integrity before any claim.
    path = next(h.settings.dev_b_store_dir.glob(f"org-*/prefill-plans/{p.plan_id}/v000001.json"))
    env = json.loads(path.read_text())
    env["record"]["actions"][0]["intended_value"] = "Tampered"
    path.chmod(0o644)
    path.write_text(json.dumps(env))
    r = execute(h, raw)
    assert r.status_code == 409 and r.json()["details"]["reason"] == "integrity_failure"
    assert stub.launches == 0


# --------------------------------------------------------------------------- AUTO2-10


def test_auto2_10_completed_retry_replays_receipt_without_new_writes(
    h: Harness, stub: StubBrowser
) -> None:
    _, p = two_text(h)
    idem = key("exec")
    first = execute(h, p, idem)
    assert first.status_code == 201 and first.json()["replayed"] is False
    assert first.json()["run"]["run"]["outcome"] == "selected_fields_verified"
    h.clock.advance(3600)  # long after expiry: a replay is still the historical receipt
    h.approvals.edit(p["actions"][0]["approval_snapshot_id"], "edited later")
    again = execute(h, p, idem)
    assert again.status_code == 200 and again.json()["replayed"] is True
    assert again.json()["run"]["run"] == first.json()["run"]["run"]
    assert stub.launches == 1
    other = execute(h, p)  # new key, same single-use plan
    assert other.status_code == 409 and other.json()["details"]["reason"] == "plan_already_executed"
    reused = execute(h, {**p, "plan_id": p["plan_id"]}, idem, expected_plan_sha256="e" * 64)
    assert reused.status_code == 409  # same key, different plan hash: refused, no browser
    assert stub.launches == 1


class RunsLockEvents:
    def __init__(self) -> None:
        self.blocked = threading.Event()
        self.acquired_after_wait = threading.Event()

    def __call__(self, path: Path, event: str) -> None:
        if path.name == RUNS_LOCK:
            (self.blocked if event == "blocked" else self.acquired_after_wait).set()


def test_auto2_10_racing_execute_requests_produce_one_execution(
    h: Harness, stub: StubBrowser, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, p = two_text(h)
    in_claim, resume = threading.Event(), threading.Event()
    real_claim = PrefillRepository.claim
    first = threading.Lock()

    def paused_claim(
        self: PrefillRepository, org: str, pid: str, k: str, cmd: str, build: Any
    ) -> Any:
        def paused_build() -> Any:
            if first.acquire(blocking=False):  # only the first claimant pauses, inside the lock
                in_claim.set()
                assert resume.wait(TIMEOUT)
            return build()

        return real_claim(self, org, pid, k, cmd, paused_build)

    monkeypatch.setattr(PrefillRepository, "claim", paused_claim)
    events = RunsLockEvents()
    previous = set_lock_observer(events)
    try:
        with ThreadPoolExecutor(2) as pool:
            a = pool.submit(execute, h, p, key("a"))
            assert in_claim.wait(TIMEOUT)
            b = pool.submit(execute, h, p, key("b"))
            assert events.blocked.wait(TIMEOUT), "second execute never contended for the claim"
            assert not events.acquired_after_wait.is_set() and not b.done()
            resume.set()
            ra, rb = a.result(TIMEOUT), b.result(TIMEOUT)
        assert events.acquired_after_wait.is_set()
    finally:
        set_lock_observer(previous)
    assert ra.status_code == 201
    assert rb.status_code == 409 and rb.json()["details"]["reason"] == "plan_already_executed"
    assert stub.launches == 1


def _claim_in_process(
    root: str, plan_id: str, idem: str, blocked: Any, acquired: Any, out: Any
) -> None:
    from strongstart_api.features.automation.prefill_store import AlreadyClaimed, PrefillRepository
    from strongstart_api.features.dev_b_store.core import LocalVersionStore, set_lock_observer
    from tests.automation.test_prefill_plan import _run_record

    def observe(path: Path, event: str) -> None:
        if path.name == "prefill-runs.lock":
            (blocked if event == "blocked" else acquired).set()

    set_lock_observer(observe)
    repo = PrefillRepository(LocalVersionStore(Path(root)))
    try:
        repo.claim("demo-org", plan_id, idem, "c" * 64, lambda: _run_record(plan_id))
        out.put("claimed")
    except AlreadyClaimed:
        out.put("already_claimed")


def _run_record(plan_id: str) -> Any:
    from datetime import UTC, datetime

    from strongstart_api.features.automation.prefill_runner import RECEIPT_NOTE, RUN_PROVENANCE
    from strongstart_contracts.automation_prefill import PrefillBudgets, PrefillGrant, PrefillRun

    now = datetime(2026, 11, 8, tzinfo=UTC)
    grant = PrefillGrant(
        grant_id="grant-x", grant_sha256="0" * 64, plan_id=plan_id, plan_sha256="0" * 64,
        organization_id="demo-org", actor_id="a", portal_fixture_id="rep-prefill-v1",
        logical_origin="fixture://rep-prefill.local", form_id="rep-prefill", form_version=1,
        expected_fingerprint="0" * 64, page_sha256="0" * 64,
        operations=[{"action_index": 0, "field_id": "org-name-field", "operation": "fill",
                     "published_question_id": "q", "approval_snapshot_id": "a",
                     "rendered_sha256": "0" * 64, "intended_sha256": "0" * 64}],
        created_at=now, expires_at=now, nonce="n", runtime_epoch="e", budgets=PrefillBudgets(),
    )  # fmt: skip
    return PrefillRun(
        run_id=run_id_for(plan_id), run_version=1, plan_id=plan_id, plan_sha256="0" * 64,
        organization_id="demo-org", actor_id="a", status="claimed", outcome="in_progress",
        grant=grant, claimed_at=now, deadline_at=now, fields=[], receipt_note=RECEIPT_NOTE,
        provenance=RUN_PROVENANCE, is_fixture=True,
    )  # fmt: skip


def test_auto2_10_two_processes_claim_one_plan_exactly_once(tmp_path: Path) -> None:
    root = tmp_path / "store"
    store = LocalVersionStore(root)
    plan_id = "pfp-" + "a" * 26
    ctx = multiprocessing.get_context("spawn")
    events = [ctx.Event(), ctx.Event()]
    acquired = [ctx.Event(), ctx.Event()]
    out = ctx.Queue()
    with store.collection("demo-org", "prefill-runs").locked():
        procs = [
            ctx.Process(
                target=_claim_in_process,
                args=(str(root), plan_id, f"key-proc-{i:04d}", e, acquired[i], out),
            )
            for i, e in enumerate(events)
        ]
        for proc in procs:
            proc.start()
        # Both children really attempted the cross-process claim lock and were refused.
        for e in events:
            assert e.wait(TIMEOUT), "a child never contended for the claim lock"
        assert not any(e.is_set() for e in acquired)
    results = sorted([out.get(timeout=TIMEOUT), out.get(timeout=TIMEOUT)])
    for proc in procs:
        proc.join(TIMEOUT)
        assert proc.exitcode == 0
    assert results == ["already_claimed", "claimed"]
    assert all(e.is_set() for e in acquired)


# --------------------------------------------------------------------------- AUTO2-11 / 12


class SimulatedCrash(BaseException):
    """Escapes ``except Exception`` like a process kill would."""


def test_auto2_11_interrupted_claim_is_never_replayed_as_another_write(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, p = two_text(h)
    launches = []

    def crash_after_first_intent(
        page_html: bytes, *, actions: list[Any], hooks: Any, **_: Any
    ) -> Any:
        launches.append(1)
        assert hooks.before_write(0) is None  # intent persisted: a write may have happened
        raise SimulatedCrash()

    monkeypatch.setattr(prefill_browser, "execute_actions", crash_after_first_intent)
    idem = key("exec")
    with pytest.raises((SimulatedCrash, BaseExceptionGroup)):
        execute(h, p, idem)
    run_id = run_id_for(p["plan_id"])
    live = h.client.get(f"/api/automation/prefill-runs/{run_id}").json()
    assert live["run"]["status"] == "running" and live["effective_outcome"] == "in_progress"
    assert live["run"]["fields"][0]["state"] == "write_in_flight"
    h.clock.advance(120)  # past the deadline: labelled unknown at read time, never rewritten
    later = h.client.get(f"/api/automation/prefill-runs/{run_id}").json()
    assert later["interrupted"] is True and later["effective_outcome"] == "outcome_unknown"
    assert later["run"]["fields"][0]["state"] == "outcome_unknown"
    assert later["run"]["fields"][1]["state"] == "not_attempted"
    assert later["run"]["run_version"] == live["run"]["run_version"]
    again = execute(h, p, idem)  # same command: the stored state, no browser
    assert (
        again.status_code == 200 and again.json()["run"]["effective_outcome"] == "outcome_unknown"
    )
    other = execute(h, p)
    assert other.status_code == 409 and other.json()["details"]["reason"] == "plan_already_executed"
    assert launches == [1]


def test_auto2_12_expiry_epoch_and_unavailable_reader_prevent_execution(
    h: Harness, stub: StubBrowser
) -> None:
    _, p = two_text(h)
    h.clock.advance(121)
    r = execute(h, p)
    assert r.status_code == 409 and r.json()["details"]["reason"] == "grant_expired"
    assert (
        h.client.get(f"/api/automation/prefill-plans/{p['plan_id']}").json()["availability"]
        == "expired"
    )
    _, p2 = two_text(h)
    h.epoch[0] = "epoch-after-restart"
    r = execute(h, p2)
    assert r.status_code == 409 and r.json()["details"]["reason"] == "runtime_epoch_changed"
    h.epoch[0] = "epoch-test-1"
    _, p3 = two_text(h)
    from strongstart_api.features.automation.prefill_deps import get_approved_prefill_reader
    from strongstart_contracts.automation_prefill import UnconfiguredApprovedPrefillReader

    h.client.app.dependency_overrides[get_approved_prefill_reader] = (  # type: ignore[attr-defined]
        lambda: UnconfiguredApprovedPrefillReader()
    )
    r = execute(h, p3)
    assert r.status_code == 201
    run = r.json()["run"]["run"]
    assert run["outcome"] == "blocked_before_entry"
    assert run["outcome_reason"] == "approval_reader_unavailable"
    assert stub.launches == 0


# --------------------------------------------------------------------------- AUTO2-13 / 15


def test_auto2_13_stale_or_unknown_approval_blocked_at_planning(h: Harness) -> None:
    pub = save_definition(h.client)
    a = approve(h, pub, "pf-org-name", "Name")
    h.approvals.edit(a, "Name.")
    p = plan(h, pub, [("pf-org-name", a), ("pf-summary", "apr-unknown")]).json()
    assert [x["reason"] for x in p["held"]] == ["approval_not_usable", "approval_not_usable"]
    assert "stale" in p["held"][0]["detail"] and p["executable"] is False
    assert (
        h.client.get(f"/api/automation/prefill-plans/{p['plan_id']}").json()["availability"]
        == "empty"
    )


def test_auto2_13_one_character_edit_after_planning_writes_nothing(
    h: Harness, stub: StubBrowser
) -> None:
    _, p = two_text(h)
    h.approvals.edit(p["actions"][1]["approval_snapshot_id"], "We run after-school tutoring!")
    r = execute(h, p).json()["run"]["run"]
    assert r["outcome"] == "blocked_before_entry" and "stale" in r["outcome_reason"]
    assert {f["state"] for f in r["fields"]} == {"not_attempted"}
    assert stub.launches == 0


def test_auto2_14_edit_during_an_action_stops_remaining_and_is_not_current(
    h: Harness, stub: StubBrowser
) -> None:
    """Exact-step synchronization: the edit happens inside field 0's postcheck resolve."""
    _, p = two_text(h)
    a0 = p["actions"][0]["approval_snapshot_id"]
    seen: list[str] = [a0]  # the planning resolve already happened

    def edit_on_postcheck(approval_id: str) -> None:
        seen.append(approval_id)
        # resolves of a0: planning, pre-execution, before:0, then after:0 (the postcheck)
        if approval_id == a0 and seen.count(a0) == 4:
            h.approvals.edit(a0, "edited while the browser was writing")

    h.approvals.on_resolve = edit_on_postcheck
    run = execute(h, p).json()["run"]["run"]
    f = {x["field_id"]: x for x in run["fields"]}
    assert f["org-name-field"]["state"] == "entered_then_stale"
    assert "stale" in (f["org-name-field"]["reason"] or "")
    assert f["summary-field"]["state"] == "not_attempted"
    assert run["outcome"] == "stopped_with_partial_entry"
    assert any(c["stage"] == "after:0" and c["status"] == "stale" for c in run["checks"])


def test_auto2_15_definition_revision_or_case_change_blocks_execution(
    h: Harness, stub: StubBrowser
) -> None:
    pub, p = two_text(h)
    intake = h.client.post("/api/automation/intake", json={"source": PORTAL_SRC}).json()
    r = h.client.post(
        "/api/automation/definitions",
        json={
            "source": {"mode": "fixture", "fixture_id": "rep-prefill-definition-v1"},
            "expected_input_sha256": h.client.post(
                "/api/automation/intake",
                json={"source": {"mode": "fixture", "fixture_id": "rep-prefill-definition-v1"}},
            ).json()["input"]["sha256"],
            "idempotency_key": key("rev"),
            "definition_id": pub["definition_id"],
            "expected_version": 1,
        },
    )
    assert r.status_code == 201, r.text
    del intake
    run = execute(h, p).json()["run"]["run"]
    assert run["outcome"] == "blocked_before_entry"
    assert run["outcome_reason"] == "definition_changed"
    assert stub.launches == 0


# --------------------------------------------------------------------------- AUTO2-19 / 21 / 22


def test_auto2_19_choices_need_typed_registered_values(h: Harness) -> None:
    pub = save_definition(h.client)
    prose = approve(h, pub, "pf-service-area", "We mostly serve the city.")
    absent = approve(h, pub, "pf-languages", "langs", typed=["en", "de"])
    multi = approve(h, pub, "pf-service-area", "two", typed=["city", "region"])
    good = approve(h, pub, "pf-languages", "langs", typed=["fr", "en"])
    p = plan(h, pub, [("pf-service-area", prose), ("pf-languages", absent)]).json()
    assert [x["reason"] for x in p["held"]] == [
        "held_choice_value_unavailable",
        "held_choice_not_registered",
    ]
    p = plan(h, pub, [("pf-service-area", multi), ("pf-languages", good)]).json()
    assert p["held"][0]["reason"] == "held_choice_not_registered"
    assert p["actions"][0]["intended_choices"] == ["en", "fr"]  # registered order


def test_auto2_20_conditional_child_needs_the_approved_parent_choice(h: Harness) -> None:
    pub = save_definition(h.client)
    child = approve(h, pub, "pf-partnership", "Library")
    p = plan(h, pub, [("pf-partnership", child)]).json()
    assert p["held"][0]["reason"] == "held_parent_not_selected"
    no = approve(h, pub, "pf-has-partners", "No", typed=["no"])
    p = plan(h, pub, [("pf-partnership", child), ("pf-has-partners", no)]).json()
    assert p["held"][0]["reason"] == "held_parent_not_selected"
    yes = approve(h, pub, "pf-has-partners", "Yes", typed=["yes"])
    p = plan(h, pub, [("pf-partnership", child), ("pf-has-partners", yes)]).json()
    assert [a["field_id"] for a in p["actions"]] == ["has-partners-field", "partnership-field"]
    assert p["actions"][1]["condition"]["parent_published_question_id"] == published(
        pub, "pf-has-partners"
    )


def test_auto2_21_existing_conflicts_stay_held_despite_approval(h: Harness) -> None:
    rep = save_definition(h.client, PORTAL_SRC)
    picks = ["rp-partnership", "rp-other-funding", "rp-pending-applications", "rp-mission"]
    sel = [(o, approve(h, rep, o, "Approved text")) for o in picks]
    p = plan(h, rep, sel, portal="rep-portal-v1").json()
    reasons = {x["original_question_id"]: x["reason"] for x in p["held"]}
    assert reasons == {
        "rp-partnership": "held_unresolved_requirement",  # 350 vs 500 words
        "rp-other-funding": "held_unresolved_requirement",  # Max 300, unknown unit
        "rp-pending-applications": "held_unconfirmed_convention",  # 300 chars, unknown
        "rp-mission": "held_counter_unavailable",  # 50 words: C owns counting
    }
    assert p["actions"] == [] and p["executable"] is False
    # The positive fixture's word-limited question is held the same way.
    pub = save_definition(h.client)
    a = approve(h, pub, "pf-mission-words", "Short mission.")
    assert plan(h, pub, [("pf-mission-words", a)]).json()["held"][0]["reason"] == (
        "held_counter_unavailable"
    )


def test_auto2_17_planner_refuses_non_conforming_numbers_and_overlong_text(h: Harness) -> None:
    pub = save_definition(h.client)
    for text in ["$25,000", "25000.00", " 25000", "twenty-five thousand", "999", "50001", "025000"]:
        a = approve(h, pub, "pf-request-amount", text)
        p = plan(h, pub, [("pf-request-amount", a)]).json()
        assert p["held"][0]["reason"] == "held_value_format", text
    long = approve(h, pub, "pf-org-name", "x" * 121)
    assert plan(h, pub, [("pf-org-name", long)]).json()["held"][0]["reason"] == (
        "held_value_too_long"
    )
    emoji = approve(h, pub, "pf-org-name", "😀" * 61)  # 122 UTF-16 code units
    assert plan(h, pub, [("pf-org-name", emoji)]).json()["held"][0]["reason"] == (
        "held_value_too_long"
    )


def test_auto2_22_attachment_checklist_without_upload(h: Harness) -> None:
    pub = save_definition(h.client)
    a = approve(h, pub, "pf-org-name", "Name")
    p = plan(h, pub, [("pf-org-name", a)]).json()
    [item] = p["attachments"]
    assert item["status"] == "needs_review_unavailable" and item["upload"] == "disabled"
    budget = approve(h, pub, "pf-budget", "budget.pdf")
    held = plan(h, pub, [("pf-budget", budget)]).json()["held"][0]
    assert held["reason"] == "held_attachment_upload_disabled"

    def rec(i: str, media: str, size: int, exists: bool = True) -> TrustedAttachmentRecord:
        return TrustedAttachmentRecord(
            artifact_id=i, original_question_id="pf-budget", detected_media_type=media,
            size_bytes=size, sha256="0" * 64, exists=exists,
            basis="trusted_synthetic_test_record", is_fixture=True,
        )  # fmt: skip

    from tests.automation.prefill_support import TestAttachments

    cases = [
        ([], ["Required attachment is missing."]),
        ([rec("art-1", "application/zip", 10)], ["not accepted"]),
        ([rec("art-1", "application/pdf", 3_000_000)], ["exceeds"]),
        ([rec("art-1", "application/pdf", 10), rec("art-2", "application/pdf", 10)], ["count"]),
        ([rec("art-1", "application/pdf", 10, exists=False)], ["does not exist"]),
    ]
    for records, needles in cases:
        h.attachments[:] = [TestAttachments(records)]
        [item] = plan(h, pub, [("pf-org-name", a)]).json()["attachments"]
        assert item["status"] == "findings"
        assert all(any(n in f for f in item["findings"]) for n in needles), item
    h.attachments[:] = [TestAttachments([rec("art-1", "application/pdf", 1000)])]
    [item] = plan(h, pub, [("pf-org-name", a)]).json()["attachments"]
    assert item["status"] == "matches_trusted_record" and item["upload"] == "disabled"


# --------------------------------------------------------------------------- AUTO2-30 / 31


def test_auto2_30_dependency_change_rejects_remaining_actions(
    h: Harness, stub: StubBrowser
) -> None:
    _, p = two_text(h)
    h.approvals.change_dependency(p["actions"][0]["approval_snapshot_id"])  # C ChangeSet (test)
    run = execute(h, p).json()["run"]["run"]
    assert (
        run["outcome"] == "blocked_before_entry" and "change_set_applied" in run["outcome_reason"]
    )
    # A deliberately injected TEST currentness provider (not A4) also stops entry.
    currentness = TestCurrentness()
    h.currentness[0] = currentness
    _, p2 = two_text(h)
    assert p2["producers"]["dependency_currentness"] == "explicit_test_provider"
    currentness.status = "stale"
    run = execute(h, p2).json()["run"]["run"]
    assert run["outcome"] == "blocked_before_entry" and run["outcome_reason"] == "dependency_stale"
    assert stub.launches == 0


def test_auto2_31_production_and_unregistered_portals_unavailable(
    h: Harness, tmp_path: Path
) -> None:
    pub = save_definition(h.client)
    a = approve(h, pub, "pf-org-name", "Name")
    r = plan(h, pub, [("pf-org-name", a)], portal="example-com-portal")
    assert r.status_code == 422 and r.json()["details"]["reason"] == "portal_not_registered"
    assert h.client.get("/api/automation/status").status_code == 200
    caps = {c["feature"]: c["status"] for c in h.client.get("/api/automation/status").json()}
    assert caps["automation.prefill_execution_c3"] == "unavailable"
    assert caps["automation.real_portal_prefill"] == "unavailable"
    assert caps["automation.final_submission"] == "unavailable"
    # Inspection keeps its literal-false contract (it never authorizes entry).
    from strongstart_contracts.automation_intake import FormInspectionResult

    assert FormInspectionResult.model_fields["prefill_permitted"].default is False


def test_auto2_31_production_has_no_prefill(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient

    from strongstart_api.app import create_app
    from strongstart_api.identity import require_identity
    from strongstart_contracts import SessionIdentity

    settings = Settings(
        _env_file=None, environment="production", auth_mode="none",
        dev_b_store_dir=tmp_path / "s", funding_capture_store_dir=tmp_path / "c",
    )  # fmt: skip
    app = create_app(settings)
    app.dependency_overrides[require_identity] = lambda: SessionIdentity(
        actor_id="p", organization_id="demo-org", roles=[], is_fixture=False, label="prod"
    )
    c = TestClient(app)
    body = {
        "question_set_id": "qs-def-" + "0" * 26 + "-v1",
        "portal_fixture_id": "rep-prefill-v1",
        "selections": [{"published_question_id": "q", "approval_snapshot_id": "a"}],
    }
    r = c.post("/api/automation/prefill-plans", json=body)
    assert r.status_code == 403 and r.json()["details"]["reason"] == "fixture_not_allowed"
    assert not (tmp_path / "s").exists()


def test_auto2_12_producer_restart_rejects_prepared_content(h: Harness, stub: StubBrowser) -> None:
    _, p = two_text(h)
    h.approvals.epoch = "producer-restarted"
    r = execute(h, p)
    assert r.status_code == 201
    run = r.json()["run"]["run"]
    assert run["outcome"] == "blocked_before_entry"
    assert run["outcome_reason"] == "approval_changed:producer_epoch"
    assert stub.launches == 0


def test_auto2_19_changed_typed_choice_cannot_reuse_plan(h: Harness, stub: StubBrowser) -> None:
    from dataclasses import replace

    pub = save_definition(h.client)
    approval_id = approve(h, pub, "pf-service-area", "Approved choice", typed=["region"])
    p = plan(h, pub, [("pf-service-area", approval_id)]).json()
    # Text and its hashes stay identical; the producer changes only the authorized choice.
    h.approvals._approvals[approval_id] = replace(
        h.approvals._approvals[approval_id], typed=["city"]
    )
    r = execute(h, p)
    assert r.status_code == 201
    run = r.json()["run"]["run"]
    assert run["outcome"] == "blocked_before_entry"
    assert run["outcome_reason"] == "approval_changed:typed_value"
    assert stub.launches == 0


def test_auto2_12_final_reread_does_not_outlive_grant(
    h: Harness, stub: StubBrowser, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, p = two_text(h)

    def expires_after_entries(*args: Any, **kwargs: Any) -> Any:
        result = stub(*args, **kwargs)
        h.clock.advance(121)
        return result

    monkeypatch.setattr(prefill_browser, "execute_actions", expires_after_entries)
    run = execute(h, p).json()["run"]["run"]
    assert run["final_reread"] == "all_match"
    assert run["outcome"] == "stopped_with_partial_entry"
    assert run["outcome_reason"] == "grant_expired"


def test_auto2_08_direct_executor_requires_exact_grant(
    h: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    from strongstart_api.features.automation import prefill_runner
    from strongstart_api.features.automation.prefill_deps import PrefillBrowserConfig
    from strongstart_api.features.automation.registry import PREFILL_PORTALS
    from strongstart_contracts.automation_prefill import PrefillPlan

    _, raw = two_text(h)
    p = PrefillPlan.model_validate(raw)
    grant = prefill_runner.derive_grant(p, "fixture-staff", h.clock())
    actions = prefill_runner._browser_actions(p, PREFILL_PORTALS[p.portal.portal_fixture_id])
    assert actions is not None

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("an invalid direct execution must not open a browser")

    monkeypatch.setattr(prefill_browser, "_session", forbidden)
    hooks: Any = object()
    for candidate in [None, grant.model_copy(update={"page_sha256": "f" * 64})]:
        result = prefill_browser.execute_actions(
            b"untrusted caller",
            ready_selector="body",
            expected_fingerprint=p.portal.expected_fingerprint,
            expected_page_sha256=p.portal.page_sha256,
            actions=actions,
            hooks=hooks,
            config=PrefillBrowserConfig(),
            grant=candidate,
        )
        assert result.reason == "invalid_execution_grant"
        assert result.operations == []
