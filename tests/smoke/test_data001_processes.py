"""DATA-12..19/34/35: real process contention and transactional commit guards."""

from __future__ import annotations

import importlib
import multiprocessing as mp
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, cast

import pytest
from sqlalchemy import text

from strongstart_api.features.applications.postgres_store import PostgresAnswerStore
from strongstart_api.seed import seed_demo
from tests.conftest import BUNDLE_PATH
from tests.data.processes import command_worker, reader_worker
from tests.data.support import client_for, prepared
from tests.integration.support import publish, question, save

pytestmark = pytest.mark.db
CTX = mp.get_context("spawn")


def stop(processes: list[Any]) -> None:
    for process in processes:
        if process.pid is None:
            continue
        process.join(timeout=15)
        if process.is_alive():
            process.terminate()  # only this test's owned worker, never unrelated services
            process.join(timeout=5)
        assert process.exitcode == 0


def wait_for_lock(engine: Any, pid: int) -> None:
    deadline = time.monotonic() + 5
    wait = CTX.Event()
    while time.monotonic() < deadline:
        with engine.connect() as conn:
            blocked = conn.execute(
                text(
                    "SELECT cardinality(pg_blocking_pids(:pid)) > 0 AND wait_event_type='Lock' "
                    "FROM pg_stat_activity WHERE pid=:pid"
                ),
                {"pid": pid},
            ).scalar()
        if blocked:
            return
        wait.wait(0.01)
    raise AssertionError("worker never observed waiting on a database lock")


@pytest.mark.parametrize(
    "operation", ["first_save", "next_save", "approve_approve", "approve_reject"]
)
def test_two_spawned_processes_contend_on_real_guard_and_one_wins(data_db, tmp_path, operation):
    data_db.migrate()
    seed_demo(data_db.engine, BUNDLE_PATH)
    store = PostgresAnswerStore(data_db.engine)
    c, _ = client_for(store, tmp_path)
    pub = publish(c)
    qid = question(pub, "pf-org-name")
    version = None
    if operation != "first_save":
        version = save(c, pub, "pf-org-name", "Original organization")
    if "save" in operation:
        path = "/api/applications/answers/versions"
        bodies = [
            {
                "question_id": qid,
                "question_version": 1,
                "question_set_id": pub["question_set_id"],
                "evidence_bundle_id": "demo-evidence-a-v1",
                "text": text,
                "expected_answer_version": 1 if version else None,
            }
            for text in ("First contender", "Second contender")
        ]
        success = 201
    else:
        assert version is not None
        path = "/api/applications/answers/decisions"
        bodies = [
            {
                "answer_version_id": version["answer_version_id"],
                "expected_content_sha256": version["content_sha256"],
                "expected_snapshot_sha256": version["snapshot_sha256"],
                "decision": d,
                "acknowledge_review_items": True,
            }
            for d in ("approve", "reject" if operation == "approve_reject" else "approve")
        ]
        success = 200
    queues = [CTX.Queue(), CTX.Queue()]
    processes = [
        CTX.Process(target=command_worker, args=(data_db.url, str(tmp_path), path, body, queue))
        for body, queue in zip(bodies, queues, strict=True)
    ]
    try:
        with store.unit_of_work("demo-org"):
            for process in processes:
                process.start()
            for queue in queues:
                kind, pid = queue.get(timeout=10)
                assert kind == "lock_attempt"
                wait_for_lock(data_db.engine, pid)
        results = [queue.get(timeout=15) for queue in queues]
        assert sorted(r[1] for r in results) == [success, 409]
        history = store.versions("demo-org", qid)
        assert [v.answer_version for v in history] == ([1, 2] if operation == "next_save" else [1])
        if "approve" in operation:
            assert store.decision_for("demo-org", history[-1].answer_version_id) is not None
            assert len([e for e in store.audit("demo-org") if e.action == "approval_decided"]) == 1
    finally:
        stop(processes)
        for queue in queues:
            queue.close()
            queue.join_thread()


def test_save_between_approval_precheck_and_commit_refuses_stale_decision(data_db, tmp_path):
    data_db.migrate()
    seed_demo(data_db.engine, BUNDLE_PATH)
    store = PostgresAnswerStore(data_db.engine)
    c, _ = client_for(store, tmp_path)
    pub = publish(c)
    version = save(c, pub, "pf-org-name", "Original organization")
    body = {
        "answer_version_id": version["answer_version_id"],
        "expected_content_sha256": version["content_sha256"],
        "expected_snapshot_sha256": version["snapshot_sha256"],
        "decision": "approve",
        "acknowledge_review_items": True,
    }
    reached, resume, results = CTX.Event(), CTX.Event(), CTX.Queue()
    worker = CTX.Process(
        target=command_worker,
        args=(
            data_db.url,
            str(tmp_path),
            "/api/applications/answers/decisions",
            body,
            results,
            reached,
            resume,
        ),
    )
    worker.start()
    try:
        assert reached.wait(10)
        save(c, pub, "pf-org-name", "New organization", 1)
    finally:
        resume.set()
    try:
        assert results.get(timeout=10)[0] == "lock_attempt"
        outcome = results.get(timeout=10)
        assert outcome[1] == 409 and outcome[2]["details"]["reason"] == "store_revision_changed"
        assert store.decision_for("demo-org", version["answer_version_id"]) is None
    finally:
        stop([worker])
        results.close()
        results.join_thread()


def test_reader_observes_other_process_commit_after_capture(data_db, tmp_path):
    c, _, pub, _, approval, _ = prepared(data_db, tmp_path)
    captured, resume, results = CTX.Event(), CTX.Event(), CTX.Queue()
    worker = CTX.Process(
        target=reader_worker, args=(data_db.url, str(tmp_path), approval, captured, resume, results)
    )
    worker.start()
    try:
        assert captured.wait(10)
        save(c, pub, "pf-summary", "Changed from another process", 1)
    finally:
        resume.set()
    try:
        assert results.get(timeout=10) == ("refused", "approval_changed_during_read")
    finally:
        stop([worker])
        results.close()
        results.join_thread()


def test_commit_guard_rejects_stale_reviewed_export(data_db, tmp_path, monkeypatch):
    """Mutation must catch stale publication, not merely a scheduling timeout."""
    c, _, pub, version, _, store = prepared(data_db, tmp_path)
    exporter = importlib.import_module("strongstart_api.features.applications.exporter")
    reached, resume, results = CTX.Event(), CTX.Event(), CTX.Queue()
    original = exporter._docx

    def paused(*args: Any, **kwargs: Any) -> bytes:
        assert store._active.get() is None, "DOCX compilation held a C transaction"
        reached.set()
        assert resume.wait(10)
        return cast(bytes, original(*args, **kwargs))

    monkeypatch.setattr(exporter, "_docx", paused)
    body = {
        "question_id": version["question_id"],
        "question_version": 1,
        "question_set_id": pub["question_set_id"],
        "evidence_bundle_id": "demo-evidence-a-v1",
        "text": "Changed before export commit",
        "expected_answer_version": 1,
    }
    worker = CTX.Process(
        target=command_worker,
        args=(data_db.url, str(tmp_path), "/api/applications/answers/versions", body, results),
    )
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(
            c.post,
            "/api/applications/exports",
            json={
                "mode": "reviewed",
                "question_ids": [version["question_id"]],
                "question_set_id": pub["question_set_id"],
            },
        )
        try:
            assert reached.wait(10)
            worker.start()
            assert results.get(timeout=10)[0] == "lock_attempt"
            assert results.get(timeout=10)[1] == 201
        finally:
            resume.set()
        response = future.result(timeout=10)
    try:
        assert response.status_code == 409, (
            "stale_export_publication: reviewed export committed "
            "after another process edited its answer"
        )
        assert response.json()["details"]["reason"] == "store_revision_changed"
        assert not any(e.action == "export_created" for e in store.audit("demo-org"))
    finally:
        stop([worker])
        results.close()
        results.join_thread()
