"""Funding-case binding is atomic with definition publication (BND-26a..d, PR #12 follow-up).

The current-version check for a bound funding case runs under the funding-case store's
cross-process lock, and the definition commit happens inside that lock. These tests pause
publication at precise points with events, and observe real lock contention through
``set_lock_observer`` (no sleep or Queue.empty() decides any outcome), to show:

- a case revision committed after context resolution makes publication fail 409, and
  nothing is published (BND-26a);
- a case revision attempted while publication holds the pin is observed to contend for the
  lock and be refused, then acquires it and commits after release (BND-26b); the same
  holds for a revision from another process (BND-26c);
- an already-committed idempotent publication still replays after the case changed
  (BND-26d).
"""

from __future__ import annotations

import importlib
import multiprocessing
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from strongstart_api.config import Settings
from strongstart_api.features.automation.definitions import DefinitionRepository
from strongstart_api.features.dev_b_store.core import set_lock_observer
from strongstart_api.features.funding.public import build_funding_case_repository
from strongstart_contracts.funding_review import FundingCaseCommand
from tests.funding.case_helpers import (
    FORM_PAGE,
    FULL_CONTEXT,
    capture,
    client_for,
    create_case,
    key,
    make_settings,
)

TIMEOUT = 10
CASE_LOCK = "cases.lock"
# The package re-exports the APIRouter as `router`; patch the module itself.
automation_router = importlib.import_module("strongstart_api.features.automation.router")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def c(settings: Settings) -> TestClient:
    return client_for(settings)


def _setup(c: TestClient) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    form = capture(c, FORM_PAGE)
    art = next(a for a in form["artifacts"] if a["representation"] == "provider_html")
    source = {
        "mode": "capture",
        "capture_id": form["capture_id"],
        "artifact_id": art["artifact_id"],
    }
    case = create_case(
        c,
        {
            "idempotency_key": key("case"),
            "context": FULL_CONTEXT,
            "capture_links": [{"capture_id": form["capture_id"]}],
        },
    )
    sha = c.post("/api/automation/intake", json={"source": source}).json()["input"]["sha256"]
    body = {
        "source": source,
        "expected_input_sha256": sha,
        "idempotency_key": key("save"),
        "funding_case_id": case["version"]["case_id"],
        "funding_case_version": 1,
    }
    return form, case, body


def _revision(form: dict[str, Any], version: int = 1) -> dict[str, Any]:
    return {
        "idempotency_key": key("rev"),
        "expected_version": version,
        "context": {**FULL_CONTEXT, "opportunity_title": "revised while publishing"},
        "capture_links": [{"capture_id": form["capture_id"]}],
    }


def _definitions(settings: Settings) -> list[Path]:
    return list(settings.dev_b_store_dir.glob("org-*/definitions/def-*"))


def test_bnd26a_revision_after_context_resolution_blocks_publication(
    c: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    form, case, body = _setup(c)
    resolved, resume = threading.Event(), threading.Event()
    real = automation_router.resolve_publication_context

    def paused(*args: Any, **kwargs: Any) -> Any:
        context = real(*args, **kwargs)  # early check passes: v1 is still current here
        resolved.set()
        assert resume.wait(TIMEOUT)
        return context

    monkeypatch.setattr(automation_router, "resolve_publication_context", paused)
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(c.post, "/api/automation/definitions", json=body)
        assert resolved.wait(TIMEOUT)
        cid = case["version"]["case_id"]
        rev = c.post(f"/api/funding/cases/{cid}/revisions", json=_revision(form))
        assert rev.status_code == 201 and rev.json()["version"]["version"] == 2
        resume.set()
        result = pending.result(TIMEOUT)
    assert result.status_code == 409, result.text
    assert result.json()["details"] == {"reason": "context_changed", "current_version": 2}
    assert c.get("/api/automation/definitions").json()["items"] == []
    assert _definitions(settings) == []


class CaseLockEvents:
    """Lock observer: records real contention on the funding-case lock in this process."""

    def __init__(self) -> None:
        self.blocked = threading.Event()
        self.acquired_after_wait = threading.Event()

    def __call__(self, path: Path, event: str) -> None:
        if path.name != CASE_LOCK:
            return
        (self.blocked if event == "blocked" else self.acquired_after_wait).set()


def test_bnd26b_revision_is_blocked_by_the_held_pin_then_commits(
    c: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    form, case, body = _setup(c)
    in_commit, resume = threading.Event(), threading.Event()
    real_save = DefinitionRepository.save

    def paused_save(self: DefinitionRepository, **kwargs: Any) -> Any:
        in_commit.set()  # inside publication_guard: the case lock is held
        assert resume.wait(TIMEOUT)
        return real_save(self, **kwargs)

    monkeypatch.setattr(DefinitionRepository, "save", paused_save)
    events = CaseLockEvents()
    previous = set_lock_observer(events)
    try:
        cid = case["version"]["case_id"]
        with ThreadPoolExecutor(2) as pool:
            publication = pool.submit(c.post, "/api/automation/definitions", json=body)
            assert in_commit.wait(TIMEOUT)
            revision = pool.submit(
                c.post, f"/api/funding/cases/{cid}/revisions", json=_revision(form)
            )
            # Synchronization point: the revision really tried to take the case lock and
            # the attempt failed because the publication's pin holds it.
            assert events.blocked.wait(TIMEOUT), "revision never contended for the lock"
            # While the pin is held the revision cannot have acquired it or committed.
            assert not events.acquired_after_wait.is_set()
            assert not revision.done()
            resume.set()  # release: publication commits and leaves the pin
            pub, rev = publication.result(TIMEOUT), revision.result(TIMEOUT)
        assert events.acquired_after_wait.is_set()  # acquired only after the release
    finally:
        set_lock_observer(previous)
    assert pub.status_code == 201, pub.text
    assert pub.json()["publication"]["context"]["binding"]["funding_case_version"] == 1
    assert rev.status_code == 201 and rev.json()["version"]["version"] == 2


def _revise_in_process(
    settings_json: str, case_id: str, cmd_json: str, blocked: Any, acquired: Any, out: Any
) -> None:
    def observe(path: Path, event: str) -> None:
        if path.name == CASE_LOCK:
            (blocked if event == "blocked" else acquired).set()

    set_lock_observer(observe)
    settings = Settings.model_validate_json(settings_json)
    repo = build_funding_case_repository(settings)
    assert repo is not None
    env, _ = repo.save(
        "demo-org", "other-process", case_id, FundingCaseCommand.model_validate_json(cmd_json)
    )
    out.put(env.version.version)


def test_bnd26c_pin_blocks_another_process_then_its_revision_commits(
    c: TestClient, settings: Settings
) -> None:
    import json

    form, case, _ = _setup(c)
    cid = case["version"]["case_id"]
    repo = build_funding_case_repository(settings)
    assert repo is not None
    ctx = multiprocessing.get_context("spawn")
    blocked, acquired, out = ctx.Event(), ctx.Event(), ctx.Queue()
    with repo.pinned("demo-org", cid, 1, case["version_digest"]):
        proc = ctx.Process(
            target=_revise_in_process,
            args=(
                settings.model_dump_json(),
                cid,
                json.dumps(_revision(form)),
                blocked,
                acquired,
                out,
            ),
        )
        proc.start()
        # The child really attempted the cross-process lock and was refused by our pin.
        assert blocked.wait(TIMEOUT), "child never contended for the case lock"
        assert not acquired.is_set()  # it cannot acquire while this process holds the pin
    # Pin released: the child acquires the lock and commits the revision.
    assert acquired.wait(TIMEOUT)
    assert out.get(timeout=TIMEOUT) == 2
    proc.join(TIMEOUT)
    assert proc.exitcode == 0
    current = c.get(f"/api/funding/cases/{cid}").json()
    assert current["version"]["version"] == 2


def test_bnd26d_committed_replay_survives_a_later_case_change(c: TestClient) -> None:
    form, case, body = _setup(c)
    first = c.post("/api/automation/definitions", json=body)
    assert first.status_code == 201, first.text
    cid = case["version"]["case_id"]
    assert c.post(f"/api/funding/cases/{cid}/revisions", json=_revision(form)).status_code == 201
    replay = c.post("/api/automation/definitions", json=body)  # lost-response retry
    assert replay.status_code == 200 and replay.json()["replayed"] is True
    assert replay.json()["publication"] == first.json()["publication"]
    assert replay.json()["publication"]["context"]["binding"]["funding_case_version"] == 1
    fresh = c.post("/api/automation/definitions", json={**body, "idempotency_key": key("new")})
    assert fresh.status_code == 409
    assert fresh.json()["details"]["reason"] == "context_changed"
    assert len(c.get("/api/automation/definitions").json()["items"]) == 1


def test_bnd26e_stale_digest_under_the_pin_is_a_conflict(c: TestClient, settings: Settings) -> None:
    from strongstart_contracts.funding_review import FundingCaseVersionChanged

    _, case, _ = _setup(c)
    repo = build_funding_case_repository(settings)
    assert repo is not None
    with (
        pytest.raises(FundingCaseVersionChanged),
        repo.pinned("demo-org", case["version"]["case_id"], 1, "0" * 64),
    ):
        pass  # pragma: no cover - entry fails
