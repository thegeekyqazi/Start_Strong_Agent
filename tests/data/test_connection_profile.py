from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy.pool import QueuePool

from strongstart_api.config import Settings
from strongstart_api.database_profile import DatabaseProfileError, build_engine, postgres_url


def test_explicit_backend_and_production_memory_refusal():
    assert Settings(_env_file=None).answer_store_backend == "unconfigured"
    assert Settings(_env_file=None, answer_store_backend="memory").answer_store_backend == "memory"
    with pytest.raises(ValidationError, match="memory answer storage"):
        Settings(_env_file=None, environment="production", answer_store_backend="memory")


def test_url_preserves_reserved_password_and_all_safe_query_parameters():
    url = postgres_url(
        "postgres://user:p%40ss%3Aword%2F%3F%25@localhost/db?application_name=a%20b&sslmode=disable&options=-c%20search_path%3Dpublic"
    )
    assert url.password == "p@ss:word/?%"
    assert url.drivername == "postgresql+psycopg"
    assert url.query["application_name"] == "a b"
    assert url.query["options"] == "-c search_path=public"
    assert postgres_url(url.render_as_string(hide_password=False)) == url
    engine = build_engine(url.render_as_string(hide_password=False))
    try:
        assert engine.hide_parameters and not engine.echo
        assert isinstance(engine.pool, QueuePool)
        assert engine.pool.size() == 3
        assert "p@ss" not in repr(engine)
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "query",
    [
        "",
        "sslmode=require",
        "sslmode=verify-ca",
        "sslmode=disable&sslrootcert=system",
        "sslmode=verify-full",
    ],
)
def test_cloud_requires_hostname_verification_and_explicit_trust(query):
    with pytest.raises(DatabaseProfileError):
        postgres_url("postgresql://user:secret@isolated.example/db?" + query, "tigerdata")


def test_cloud_budget_and_system_roots():
    url = "postgresql://user:secret@isolated.example/db?sslmode=verify-full&sslrootcert=system"
    assert postgres_url(url, "tigerdata").query["sslrootcert"] == "system"
    with pytest.raises(ValidationError, match="connection budget"):
        Settings(_env_file=None, database_profile="tigerdata", database_url=url)
    s = Settings(
        _env_file=None, database_profile="tigerdata", database_url=url, db_connection_budget=3
    )
    assert "secret" not in repr(s) and "secret" not in s.model_dump_json(exclude={"database_url"})


@pytest.mark.parametrize(
    "raw",
    [
        "sqlite://",
        "postgresql://user:secret@remote.example/db",
        "postgresql://user:secret@localhost/db?host=remote.example",
    ],
)
def test_local_is_not_a_cloud_plaintext_escape_hatch(raw):
    with pytest.raises(DatabaseProfileError) as exc:
        postgres_url(raw)
    assert "secret" not in str(exc.value) and raw not in str(exc.value)
