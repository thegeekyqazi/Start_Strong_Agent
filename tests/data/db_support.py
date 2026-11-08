"""Disposable PostgreSQL databases only; never downgrade/reset the shared target."""

from __future__ import annotations

import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

from strongstart_api.config import Settings
from strongstart_api.database_profile import build_engine
from strongstart_api.db import APPLICATION_TABLES, get_engine
from tests.conftest import REPO_ROOT


@dataclass
class Database:
    url: str = field(repr=False)
    engine: Engine
    name: str
    admin: Engine

    def migrate(self, revision: str = "head", downgrade: bool = False) -> None:
        cfg = Config(str(REPO_ROOT / "alembic.ini"))
        cfg.attributes["database_url"] = self.url
        (command.downgrade if downgrade else command.upgrade)(cfg, revision)


@pytest.fixture
def data_db() -> Iterator[Database]:
    raw = Settings().database_url
    if not raw:
        pytest.fail("local PostgreSQL URL required for DATA-001 DB tests")
    parsed = make_url(raw)
    if parsed.host not in {"127.0.0.1", "localhost", "::1"}:
        pytest.fail("disposable database fixture refuses a non-local host")
    name = "data001_" + secrets.token_hex(8)
    admin = create_engine(
        parsed.set(database="postgres"), isolation_level="AUTOCOMMIT", hide_parameters=True
    )
    with admin.connect() as conn:
        conn.exec_driver_sql(f'CREATE DATABASE "{name}"')
    url = parsed.set(database=name).render_as_string(hide_password=False)
    engine = get_engine(url)
    db = Database(url, engine, name, admin)
    try:
        yield db
    finally:
        engine.dispose()
        with admin.connect() as conn:
            # Name is generated here, never operator input. Only this owned disposable DB.
            conn.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()


@dataclass
class RuntimeRole:
    engine: Engine
    url: str = field(repr=False)


@contextmanager
def runtime_role(db: Database) -> Iterator[RuntimeRole]:
    """Test-only role in this owned DB; no DDL/table ownership needed by runtime."""
    name, password = "data001_role_" + secrets.token_hex(8), secrets.token_hex(24)
    engine = None
    with db.engine.begin() as conn:
        conn.execute(
            text("select set_config('data001.test_password', :password, true)"),
            {"password": password},
        )
        conn.exec_driver_sql(f"""DO $$ BEGIN EXECUTE format('CREATE ROLE %%I LOGIN PASSWORD %%L',
            '{name}', current_setting('data001.test_password')); END $$""")
        conn.exec_driver_sql(f'GRANT CONNECT ON DATABASE "{db.name}" TO "{name}"')
        conn.exec_driver_sql(f'GRANT USAGE ON SCHEMA public TO "{name}"')
        conn.exec_driver_sql(f'GRANT SELECT, UPDATE(id) ON organizations TO "{name}"')
        for table in APPLICATION_TABLES:
            conn.exec_driver_sql(f'GRANT SELECT, INSERT ON "{table.name}" TO "{name}"')
        conn.exec_driver_sql(f'GRANT UPDATE(revision) ON c_store_state TO "{name}"')
        conn.exec_driver_sql(f'GRANT UPDATE(latest_version) ON c_answer_heads TO "{name}"')
        conn.exec_driver_sql(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{name}"')
    try:
        url = (
            make_url(db.url)
            .set(username=name, password=password)
            .render_as_string(hide_password=False)
        )
        engine = build_engine(url)
        yield RuntimeRole(engine, url)
    finally:
        if engine is not None:
            engine.dispose()
        with db.engine.begin() as conn:
            # Role and database are uniquely owned test objects; never a shared runtime role.
            conn.exec_driver_sql(f'DROP OWNED BY "{name}"')
            conn.exec_driver_sql(f'DROP ROLE "{name}"')
