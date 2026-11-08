"""DATA-18/19/21..23/29/30/41: normal runtime selection and real API restart."""

from __future__ import annotations

from typing import cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from strongstart_api.app import create_app
from strongstart_api.config import Settings
from strongstart_api.db import c_store_state
from strongstart_api.features.applications.maintenance import rotate_dataset_epoch
from strongstart_api.features.applications.postgres_store import PostgresAnswerStore
from strongstart_api.seed import seed_demo
from strongstart_contracts.fixture_adapters import ApprovalNotUsable
from tests.conftest import BUNDLE_PATH
from tests.data.runtime import api_process
from tests.integration.support import decide, prepare, publish, reader_for, save

pytestmark = pytest.mark.db


def test_two_normal_apps_and_explicit_rotation(data_db, tmp_path):
    data_db.migrate()
    seed_demo(data_db.engine, BUNDLE_PATH)
    settings = Settings(
        _env_file=None,
        answer_store_backend="postgres",
        database_url=data_db.url,
        auth_mode="fixture",
        dev_b_store_dir=tmp_path / "b",
    )
    first, second = create_app(settings), create_app(settings)
    with TestClient(first) as c, TestClient(second) as other:
        pub = publish(c)
        # GET reads cannot initialize epochs.
        assert c.get("/api/applications/answers/mission-q1").status_code == 200
        with data_db.engine.connect() as conn:
            assert conn.execute(select(c_store_state)).all() == []
        v = save(c, pub, "pf-org-name", "  Synthetic 🦎\r\norganization  ")
        approval = decide(c, v)
        a, b = reader_for(first, settings), reader_for(second, settings)
        value = a.resolve_for_prefill("demo-org", approval)
        assert b.resolve_for_prefill("demo-org", approval).model_dump(
            exclude={"currentness_checked_at"}
        ) == value.model_dump(exclude={"currentness_checked_at"})
        assert first.state.c3_answer_store is not second.state.c3_answer_store
        before = first.state.c3_answer_store.capture_approval("demo-org", approval)
        state = second.state.c3_answer_store.state("demo-org")
        rotated = rotate_dataset_epoch(data_db.engine, "demo-org", state)
        assert rotated.epoch != state.epoch and rotated.revision == state.revision + 1
        assert not first.state.c3_answer_store.approval_read_current("demo-org", before)
        assert a.resolve_for_prefill("demo-org", approval).producer_epoch == rotated.epoch
        save(other, pub, "pf-org-name", "Changed in second app", 1)
        for reader in (a, b):
            with pytest.raises(ApprovalNotUsable):
                reader.resolve_for_prefill("demo-org", approval)


def test_real_api_process_restart_preserves_complete_workflow(data_db, tmp_path):
    data_db.migrate()
    seed_demo(data_db.engine, BUNDLE_PATH)
    with api_process(data_db.url, tmp_path) as raw:
        c = cast(TestClient, raw)
        assert c.get("/health/ready").status_code == 200
        pub = publish(c)
        version = save(
            c, pub, "pf-summary", "  Synthetic 🦎 {{fact:demo-fact-children-served}}.\r\n  "
        )
        approval = decide(c, version)
        assert (
            c.post(
                "/api/applications/answers/notes",
                json={
                    "answer_version_id": version["answer_version_id"],
                    "text": "Exact note 🦎\r\n ",
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
        history, audit = c.get(history_path).json(), c.get("/api/applications/audit-events").json()
        binaries = [
            c.get(f"/api/applications/exports/{export_id}/{kind}").content
            for kind in ("docx", "audit")
        ]
        pending = prepare(c, pub, {"pf-summary": approval}).json()
        state = PostgresAnswerStore(data_db.engine).state("demo-org")
    # Owned uvicorn exited before a brand-new process opens the same dataset and B files.
    with api_process(data_db.url, tmp_path) as raw:
        c = cast(TestClient, raw)
        assert c.get(history_path).json() == history
        assert c.get("/api/applications/audit-events").json() == audit
        assert [
            c.get(f"/api/applications/exports/{export_id}/{kind}").content
            for kind in ("docx", "audit")
        ] == binaries
        assert PostgresAnswerStore(data_db.engine).state("demo-org") == state
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
    with api_process(data_db.url, tmp_path) as raw:
        c = cast(TestClient, raw)
        stale = prepare(c, pub, {"pf-summary": approval}).json()
        assert stale["actions"] == [] and stale["held"][0]["reason"] == "approval_not_usable"
        replay = c.post("/api/applications/fixture/change-sets/demo-change-fact-v2/apply")
        assert replay.status_code == 200 and replay.json() == applied.json()
        events = c.get("/api/applications/audit-events").json()
        assert len([e for e in events if e["action"] == "change_set_applied"]) == 1


def test_hosted_scenario_locally_uses_real_c_with_nonowner_role(data_db, tmp_path):
    from sqlalchemy import insert

    from scripts.data001_workflow import verify_workflow
    from strongstart_api.db import organizations
    from tests.data.db_support import runtime_role

    data_db.migrate()
    with data_db.engine.begin() as conn:
        conn.execute(
            insert(organizations).values(
                id="data001-local-scenario",
                display_name="SYNTHETIC local verifier",
                provenance_class="simulated",
                is_simulated=True,
            )
        )
    with runtime_role(data_db) as role:
        settings = Settings(
            _env_file=None,
            auth_mode="fixture",
            answer_store_backend="postgres",
            database_url=role.url,
            dev_b_store_dir=tmp_path / "verifier-b",
            db_pool_size=1,
        )
        report = verify_workflow(settings, "data001-local-scenario")
        assert (
            report["reopened_process"]
            and report["cross_client_stale_conflict"]
            and report["process_contention_observed"]
        )
