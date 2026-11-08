"""Namespaced synthetic verification using actual B publication/C routes and stores.

Only identity/workspace fixture adapters are provided here. Approval, persistence,
currentness, transactions and public C factories are the application implementations.
This is a bounded test producer, not the future normal-runtime real-evidence integration.
"""

from __future__ import annotations

import hashlib
import multiprocessing as mp
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, cast

import httpx
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

ROOT = Path(__file__).resolve().parents[1]


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


SYNTHETIC_ORG_ENV = "DATA001_SYNTHETIC_ORG"


def hosted_app_factory() -> FastAPI:
    """Uvicorn factory for the hosted restart phase only: same namespaced adapters as above.

    Settings come from the private process environment (runtime role, TigerData profile).
    """
    import os

    org = os.environ[SYNTHETIC_ORG_ENV]
    if not org.startswith("data001-"):
        raise RuntimeError("hosted factory requires a namespaced synthetic organization")
    return application(Settings(_env_file=None), org)[0]


@contextmanager
def api_process(env: dict[str, str], directory: Path) -> Iterator[httpx.Client]:
    """An actual uvicorn API process; output is discarded so no DSN/exception can leak."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    proc = subprocess.Popen(  # noqa: S603 - fixed owned API command, private env
        [
            sys.executable,
            "-m",
            "uvicorn",
            "--factory",
            "scripts.data001_workflow:hosted_app_factory",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=60) as client:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if proc.poll() is not None:
                    raise AssertionError("owned API process exited during startup")
                try:
                    if client.get("/health/ready").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                threading.Event().wait(0.1)  # readiness polling, never contention proof
            else:
                raise AssertionError("owned API readiness timeout")
            yield client
    finally:
        proc.terminate()
        proc.wait(timeout=15)


def restart_workflow(settings: Settings, org: str, directory: Path) -> dict[str, Any]:
    """Save/approve/export in one real API process, then reopen everything in new ones."""
    import os

    from strongstart_api.features.applications.postgres_store import PostgresAnswerStore
    from tests.integration.support import prepare

    env = {k: v for k, v in os.environ.items() if not k.startswith("STRONGSTART_")}
    env.update(
        STRONGSTART_ENVIRONMENT="test",
        STRONGSTART_AUTH_MODE="fixture",
        STRONGSTART_ANSWER_STORE_BACKEND="postgres",
        STRONGSTART_DATABASE_PROFILE=settings.database_profile,
        STRONGSTART_DATABASE_URL=str(settings.database_url),
        STRONGSTART_DB_CONNECT_TIMEOUT_SECONDS=str(settings.db_connect_timeout_seconds),
        STRONGSTART_DB_POOL_SIZE="1",
        STRONGSTART_DB_MAX_OVERFLOW="0",
        STRONGSTART_DEV_B_STORE_DIR=str(directory / "b"),
        **{SYNTHETIC_ORG_ENV: org},
    )
    # Hosted-only settings are forwarded only when configured; never invented for local runs.
    if settings.db_sslrootcert:
        env["STRONGSTART_DB_SSLROOTCERT"] = str(settings.db_sslrootcert)
    if settings.db_connection_budget is not None:
        env["STRONGSTART_DB_CONNECTION_BUDGET"] = str(settings.db_connection_budget)
    from strongstart_api.db import configured_engine

    engine = configured_engine(settings)
    store = PostgresAnswerStore(engine)
    try:
        with api_process(env, directory) as raw:
            c = cast(TestClient, raw)
            pub = publish(c, key="data001-hosted-restart")
            version = save(
                c, pub, "pf-summary", "  SYNTHETIC restart 🦎 {{fact:demo-fact-children-served}}.\n"
            )
            approval = decide(c, version)
            for path, body in (
                (
                    "/api/applications/answers/notes",
                    {"answer_version_id": version["answer_version_id"], "text": "Exact 🦎\r\n "},
                ),
                (
                    "/api/applications/answers/reviews",
                    {"answer_version_id": version["answer_version_id"], "role": "meaning_reviewer"},
                ),
            ):
                assert c.post(path, json=body).status_code == 201
            result = c.post(
                "/api/applications/exports",
                json={
                    "mode": "reviewed",
                    "question_ids": [version["question_id"]],
                    "question_set_id": pub["question_set_id"],
                },
            ).json()
            export_id = result["export_id"]
            assert export_id and not result["blocked"]
            history_path = (
                f"/api/applications/answers/{version['question_id']}"
                f"?question_set_id={pub['question_set_id']}"
            )
            history = c.get(history_path).json()
            audit = c.get("/api/applications/audit-events").json()
            binaries = [
                c.get(f"/api/applications/exports/{export_id}/{kind}").content
                for kind in ("docx", "audit")
            ]
            pending = prepare(c, pub, {"pf-summary": approval}).json()
            assert pending["actions"][0]["intended_value"] == version["rendered"]["text"]
            state = store.state(org)
        # First uvicorn has exited; a brand-new process reopens the same hosted dataset.
        with api_process(env, directory) as raw:
            c = cast(TestClient, raw)
            assert c.get(history_path).json() == history
            assert c.get("/api/applications/audit-events").json() == audit
            reread = [
                c.get(f"/api/applications/exports/{export_id}/{kind}").content
                for kind in ("docx", "audit")
            ]
            assert reread == binaries
            assert store.state(org) == state
            fresh = prepare(c, pub, {"pf-summary": approval}).json()
            assert (
                fresh["actions"][0]["producer_epoch"]
                == pending["actions"][0]["producer_epoch"]
                == state.epoch
            )
            assert fresh["runtime_epoch"] != pending["runtime_epoch"]
            assert fresh["actions"][0]["intended_value"] == version["rendered"]["text"]
            old = c.get(f"/api/automation/prefill-plans/{pending['plan_id']}").json()
            assert old["availability"] == "runtime_epoch_changed"
            applied = c.post("/api/applications/fixture/change-sets/demo-change-fact-v2/apply")
            assert applied.status_code == 200
        # A4 replacement survives another restart and keeps the old approval out of prefill.
        with api_process(env, directory) as raw:
            c = cast(TestClient, raw)
            stale = prepare(c, pub, {"pf-summary": approval}).json()
            assert stale["actions"] == [] and stale["held"][0]["reason"] == "approval_not_usable"
            replay = c.post("/api/applications/fixture/change-sets/demo-change-fact-v2/apply")
            assert replay.status_code == 200 and replay.json() == applied.json()
            events = c.get("/api/applications/audit-events").json()
            assert len([e for e in events if e["action"] == "change_set_applied"]) == 1
            final_state = store.state(org)
    finally:
        engine.dispose()
    return {
        "organization_id": org,
        "approval_id": approval,
        "answer_version_id": version["answer_version_id"],
        "export_id": export_id,
        "template_sha256": version["content_sha256"],
        "rendered_sha256": version["rendered"]["text_sha256"],
        "snapshot_sha256": version["snapshot_sha256"],
        "docx_sha256": hashlib.sha256(binaries[0]).hexdigest(),
        "audit_sha256": hashlib.sha256(binaries[1]).hexdigest(),
        "export_docx_sha256_reported": result.get("docx_sha256"),
        "producer_epoch": state.epoch,
        "epoch_stable_across_restart": True,
        "old_plan_availability": "runtime_epoch_changed",
        "new_plan_from_preserved_approval": True,
        "a4_replacement_held_after_restart": "approval_not_usable",
        "final_revision": final_state.revision,
        "api_processes": 3,
    }
