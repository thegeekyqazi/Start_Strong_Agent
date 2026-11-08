"""Namespaced synthetic verification using actual B publication/C routes and stores.

Only identity/workspace fixture adapters are provided here. Approval, persistence,
currentness, transactions and public C factories are the application implementations.
This is a bounded test producer, not the future normal-runtime real-evidence integration.
"""

from __future__ import annotations

import multiprocessing as mp
import time
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.features.applications.deps import get_workspace_source
from strongstart_api.features.applications.workspace import (
    DefinitionWorkspaceSource,
    FixtureWorkspaceSource,
    WorkspaceNotFound,
)
from strongstart_api.features.automation.public import build_application_definition_reader
from strongstart_api.identity import FIXTURE_IDENTITY, require_identity
from strongstart_contracts.answers import ApplicationWorkspace
from tests.integration.support import decide, publish, save


class NamespacedSyntheticWorkspace(FixtureWorkspaceSource):
    def __init__(self, org: str) -> None:
        super().__init__()
        self.org = org

    def get(self, organization_id: str, question_set_id: str | None = None) -> ApplicationWorkspace:
        if organization_id != self.org:
            raise WorkspaceNotFound()
        workspace = super().get("demo-org", question_set_id)
        return workspace.model_copy(
            update={
                "evidence_bundle": workspace.evidence_bundle.model_copy(
                    update={"organization_id": self.org}
                ),
                "data_label": "SYNTHETIC DATA-001 isolated verification",
            }
        )


def application(settings: Settings, org: str) -> tuple[FastAPI, DefinitionWorkspaceSource]:
    app = create_app(settings)
    identity = FIXTURE_IDENTITY.model_copy(update={"organization_id": org})
    app.dependency_overrides[require_identity] = lambda: identity
    source = DefinitionWorkspaceSource(
        build_application_definition_reader(settings), NamespacedSyntheticWorkspace(org)
    )
    app.dependency_overrides[get_workspace_source] = lambda: source
    return app, source


def reopened(
    settings: Settings, org: str, approval: str, expected: dict[str, Any], result: Any
) -> None:
    """Spawned fresh app/pool: actual C public factory over a separate connection."""
    from starlette.requests import Request

    from strongstart_api.features.applications.public import get_approved_prefill_reader
    from strongstart_api.features.applications.rules.policy import fixture_policy

    try:
        app, source = application(settings, org)
        with TestClient(app):
            reader = get_approved_prefill_reader(
                app.state.c3_answer_store,
                source,
                fixture_policy(),
                settings,
                Request({"type": "http", "app": app}),
            )
            content = reader.resolve_for_prefill(org, approval)
            assert content.model_dump(mode="json", exclude={"currentness_checked_at"}) == expected
            result.put("reopened_exact")
    except Exception:
        result.put("reopen_failed")  # no exception/DSN/payload leaves worker


def contender(settings: Settings, org: str, body: dict[str, Any], results: Any) -> None:
    app, _ = application(settings, org)

    def attempt(conn: Any, cursor: Any, sql: str, params: Any, ctx: Any, many: bool) -> None:
        if "FROM organizations" in sql and "FOR UPDATE" in sql:
            results.put(("lock_attempt", conn.connection.driver_connection.info.backend_pid))

    event.listen(app.state.c3_answer_store.engine, "before_cursor_execute", attempt)
    try:
        with TestClient(app) as c:
            response = c.post("/api/applications/answers/versions", json=body)
            results.put(("status", response.status_code))
    except Exception:
        results.put(("failed", 0))


def process_contention(
    settings: Settings, org: str, version: dict[str, Any], pub: dict[str, Any], store: Any
) -> None:
    ctx = mp.get_context("spawn")
    queues = [ctx.Queue(), ctx.Queue()]
    body = {
        "question_id": version["question_id"],
        "question_version": 1,
        "question_set_id": pub["question_set_id"],
        "evidence_bundle_id": "demo-evidence-a-v1",
        "text": "SYNTHETIC process contender",
        "expected_answer_version": 2,
    }
    workers = [ctx.Process(target=contender, args=(settings, org, body, q)) for q in queues]
    from strongstart_api.db import configured_engine

    observer = configured_engine(settings)
    try:
        with store.unit_of_work(org):
            for worker in workers:
                worker.start()
            for queue in queues:
                kind, pid = queue.get(timeout=30)
                assert kind == "lock_attempt"
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    # A separate observer connection: wait-state is measured, never inferred.
                    with observer.connect() as conn:
                        blocked = conn.execute(
                            text(
                                "select cardinality(pg_blocking_pids(:pid)) > 0 "
                                "and wait_event_type='Lock' from pg_stat_activity where pid=:pid"
                            ),
                            {"pid": pid},
                        ).scalar()
                    if blocked:
                        break
                    ctx.Event().wait(0.01)
                else:
                    raise AssertionError("hosted worker did not reach lock contention")
        assert sorted(queue.get(timeout=30)[1] for queue in queues) == [201, 409]
        for worker in workers:
            worker.join(10)
            assert worker.exitcode == 0
    finally:
        for worker in workers:
            if worker.pid is not None and worker.is_alive():
                worker.terminate()
                worker.join(5)
        observer.dispose()
        for queue in queues:
            queue.close()
            queue.join_thread()


def verify_workflow(settings: Settings, org: str) -> dict[str, Any]:
    app, source = application(settings, org)
    from starlette.requests import Request

    from strongstart_api.features.applications.public import get_approved_prefill_reader
    from strongstart_api.features.applications.rules.policy import fixture_policy

    with TestClient(app) as c:
        pub = publish(c, key="data001-isolated-publish")
        version = save(
            c,
            pub,
            "pf-summary",
            "  SYNTHETIC historic {{fact:demo-fact-children-served}}.\r\n 🦎  ",
        )
        approval = decide(c, version)
        store = app.state.c3_answer_store
        reader = get_approved_prefill_reader(
            store, source, fixture_policy(), settings, Request({"type": "http", "app": app})
        )
        content = reader.resolve_for_prefill(org, approval)
        assert content.is_fixture and content.provenance.is_simulated
        assert (
            c.post(
                "/api/applications/answers/notes",
                json={
                    "answer_version_id": version["answer_version_id"],
                    "text": "SYNTHETIC exact note 🦎\r\n ",
                },
            ).status_code
            == 201
        )
        assert (
            c.post(
                "/api/applications/answers/reviews",
                json={
                    "answer_version_id": version["answer_version_id"],
                    "role": "meaning_reviewer",
                },
            ).status_code
            == 201
        )
        export = c.post(
            "/api/applications/exports",
            json={
                "mode": "reviewed",
                "question_ids": [version["question_id"]],
                "question_set_id": pub["question_set_id"],
            },
        )
        assert export.status_code == 200 and not export.json()["blocked"]
        blob = store.get_export(org, export.json()["export_id"])
        captured = store.capture_approval(org, approval)
        ctx = mp.get_context("spawn")
        results = ctx.Queue()
        worker = ctx.Process(
            target=reopened,
            args=(
                settings,
                org,
                approval,
                content.model_dump(mode="json", exclude={"currentness_checked_at"}),
                results,
            ),
        )
        worker.start()
        try:
            assert results.get(timeout=30) == "reopened_exact"
            worker.join(10)
            assert worker.exitcode == 0
        finally:
            if worker.is_alive():
                worker.terminate()
                worker.join(5)
            results.close()
            results.join_thread()
        # New independent app/pool must see bytes/history and enforce the same expected version.
        other, _ = application(settings, org)
        with TestClient(other) as second:
            assert other.state.c3_answer_store.get_export(org, blob.result.export_id) == blob
            assert other.state.c3_answer_store.notes(org) == store.notes(org)
            assert other.state.c3_answer_store.proposals(org) == store.proposals(org)
            assert other.state.c3_answer_store.audit(org) == store.audit(org)
            save(second, pub, "pf-summary", "SYNTHETIC edit from a second client", 1)
            assert not store.approval_read_current(org, captured)
            conflict = c.post(
                "/api/applications/answers/versions",
                json={
                    "question_id": version["question_id"],
                    "question_version": 1,
                    "question_set_id": pub["question_set_id"],
                    "evidence_bundle_id": "demo-evidence-a-v1",
                    "text": "stale expected version",
                    "expected_answer_version": 1,
                },
            )
            assert conflict.status_code == 409
        process_contention(settings, org, version, pub, store)
        return {
            "process_contention_observed": True,
            "organization_id": org,
            "answer_version_id": version["answer_version_id"],
            "approval_id": approval,
            "export_id": blob.result.export_id,
            "template_sha256": version["content_sha256"],
            "rendered_sha256": version["rendered"]["text_sha256"],
            "snapshot_sha256": version["snapshot_sha256"],
            "docx_sha256": blob.result.docx_sha256,
            "audit_sha256": blob.result.audit_sha256,
            "producer_epoch": captured.epoch,
            "reopened_process": True,
            "cross_client_stale_conflict": True,
        }
