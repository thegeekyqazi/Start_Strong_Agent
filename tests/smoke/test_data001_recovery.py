"""DATA-40: actual pg_dump/pg_restore into another owned disposable database.

Local test tooling uses installed host clients, or explicit local container clients when
host tools are absent. Hosted tooling never invokes Docker/Compose or any reset command.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess

import pytest
from sqlalchemy import inspect
from sqlalchemy.engine import make_url

from strongstart_api.features.applications.maintenance import rotate_dataset_epoch
from strongstart_api.features.applications.postgres_store import PostgresAnswerStore
from tests.data.db_support import Database
from tests.data.support import prepared

pytestmark = pytest.mark.db


@pytest.fixture
def restore_db(data_db):
    # Explicit second database owned by this test, never the source or a selected shared DB.
    from tests.data.db_support import disposable_database

    with disposable_database() as target:
        yield target


def local_client(db: Database, executable: str) -> list[str]:
    url = make_url(db.url)
    assert url.host in {"localhost", "127.0.0.1", "::1"}
    # Explicit owned container uses its matching server/client version (CI host has PG16).
    if not os.environ.get("DATA001_LOCAL_PG_CONTAINER") and shutil.which(executable):
        return [
            executable,
            "--host",
            str(url.host),
            "--port",
            str(url.port),
            "--username",
            str(url.username),
            "--dbname",
            db.name,
        ]
    container = os.environ.get("DATA001_LOCAL_PG_CONTAINER", "strongstart-postgres-1")
    assert re.fullmatch(r"[a-zA-Z0-9_-]+", container)
    return [
        "docker",
        "exec",
        "-i",
        container,
        executable,
        "--username",
        str(url.username),
        "--dbname",
        db.name,
    ]


def test_backup_restore_exact_bytes_identity_revision_and_explicit_rotation(
    data_db, restore_db, tmp_path
):
    c, _, pub, v, approval, source = prepared(data_db, tmp_path)
    result = c.post(
        "/api/applications/exports",
        json={
            "mode": "reviewed",
            "question_ids": [v["question_id"]],
            "question_set_id": pub["question_set_id"],
        },
    ).json()
    blob = source.get_export("demo-org", result["export_id"])
    captured = source.capture_approval("demo-org", approval)
    state = source.state("demo-org")
    assert restore_db.name != data_db.name and not inspect(restore_db.engine).get_table_names()
    # Secrets pass only through the environment; client stdout/stderr are never echoed.
    env = {k: val for k, val in os.environ.items() if not k.startswith("PG")}
    env["PGPASSWORD"] = str(make_url(data_db.url).password or "")
    dump = subprocess.run(  # noqa: S603 - fixed tools, generated local database names
        [*local_client(data_db, "pg_dump"), "--format=custom", "--no-owner", "--no-privileges"],
        env=env,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert dump.returncode == 0, "local pg_dump failed (details intentionally private)"
    restored = subprocess.run(  # noqa: S603 - fixed tools, generated local database names
        [
            *local_client(restore_db, "pg_restore"),
            "--no-owner",
            "--no-privileges",
            "--single-transaction",
            "--exit-on-error",
        ],
        input=dump.stdout,
        env=env,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert restored.returncode == 0, "local pg_restore failed (details intentionally private)"
    target = PostgresAnswerStore(restore_db.engine)
    assert target.state("demo-org") == state
    assert target.get_version("demo-org", v["answer_version_id"]) == source.get_version(
        "demo-org", v["answer_version_id"]
    )
    assert target.capture_approval("demo-org", approval) == captured
    assert target.get_export("demo-org", blob.result.export_id) == blob
    assert target.audit("demo-org") == source.audit("demo-org")
    assert target.approval_read_current("demo-org", captured)
    rotated = rotate_dataset_epoch(restore_db.engine, "demo-org", state)
    assert rotated.epoch != state.epoch and rotated.revision == state.revision + 1
    assert not target.approval_read_current("demo-org", captured)
    assert source.state("demo-org") == state  # source was untouched by restore/rotation
    assert target.get_export("demo-org", blob.result.export_id) == blob
