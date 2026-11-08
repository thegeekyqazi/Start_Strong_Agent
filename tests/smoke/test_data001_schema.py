from __future__ import annotations

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from strongstart_api.db import (
    APPLICATION_TABLES,
    REQUIRED_MIGRATION_REVISION,
    check_readiness,
    metadata,
)
from strongstart_api.seed import seed_demo
from tests.conftest import BUNDLE_PATH

pytestmark = pytest.mark.db


def test_fresh_migration_metadata_and_disposable_rollback(data_db):
    data_db.migrate()
    assert check_readiness(data_db.url).status == "ready"
    assert all(t.name in inspect(data_db.engine).get_table_names() for t in APPLICATION_TABLES)
    with data_db.engine.connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn), metadata)
        assert diffs == []
        assert (
            conn.execute(text("select version_num from alembic_version")).scalar()
            == REQUIRED_MIGRATION_REVISION
        )
    data_db.migrate("0008_browser_bindings", downgrade=True)
    assert check_readiness(data_db.url).status == "not_ready"
    data_db.migrate()
    assert check_readiness(data_db.url).status == "ready"


def test_upgrade_populated_0008_preserves_a4_and_organization(data_db):
    data_db.migrate("0008_browser_bindings")
    seed_demo(data_db.engine, BUNDLE_PATH)
    with data_db.engine.connect() as conn:
        before = conn.execute(
            text("select * from active_pack_contexts order by organization_id, application_context")
        ).all()
    data_db.migrate()
    with data_db.engine.connect() as conn:
        assert (
            conn.execute(
                text(
                    "select * from active_pack_contexts "
                    "order by organization_id, application_context"
                )
            ).all()
            == before
        )
        assert conn.execute(text("select count(*) from organizations")).scalar() == 1
        assert conn.execute(text("select count(*) from c_store_state")).scalar() == 0


def test_runtime_role_has_no_schema_owner_or_ddl(data_db):
    from sqlalchemy.exc import ProgrammingError

    from tests.data.db_support import runtime_role

    data_db.migrate()
    seed_demo(data_db.engine, BUNDLE_PATH)
    with runtime_role(data_db) as runtime:
        with runtime.engine.connect() as conn:
            row = conn.execute(
                text(
                    "select rolsuper, rolcreatedb, rolcreaterole "
                    "from pg_roles where rolname=current_user"
                )
            ).one()
            assert tuple(row) == (False, False, False)
            assert not conn.execute(
                text("select has_schema_privilege(current_user, 'public', 'CREATE')")
            ).scalar()
            assert conn.execute(text("select count(*) from c_answer_versions")).scalar() == 0
        with pytest.raises(ProgrammingError), runtime.engine.begin() as conn:
            conn.execute(text("create table runtime_must_not_create(id integer)"))
