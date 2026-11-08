"""Server-only PostgreSQL profile; never render a DSN in errors or diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import psycopg.pq
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url


class DatabaseProfileError(ValueError):
    pass


def postgres_url(
    raw: str, profile: Literal["local", "tigerdata"] = "local", root_cert: str | None = None
) -> URL:
    try:
        url = make_url(raw)
    except Exception:
        raise DatabaseProfileError("invalid PostgreSQL connection configuration") from None
    if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
        raise DatabaseProfileError("only the PostgreSQL psycopg dialect is supported")
    url = url.set(drivername="postgresql+psycopg")
    if set(url.query) & {"host", "hostaddr", "service", "dbname", "user", "password"}:
        raise DatabaseProfileError(
            "alternate endpoint or credential query overrides are unsupported"
        )
    if profile == "local":
        if url.host not in {None, "localhost", "127.0.0.1", "::1"}:
            raise DatabaseProfileError("plaintext/local profile requires a local endpoint")
    else:
        if not url.host or url.host in {"localhost", "127.0.0.1", "::1"}:
            raise DatabaseProfileError(
                "TigerData profile requires an explicitly selected hosted endpoint"
            )
        if url.query.get("sslmode") != "verify-full":
            raise DatabaseProfileError("TigerData requires sslmode=verify-full")
        root = root_cert or url.query.get("sslrootcert")
        if not isinstance(root, str) or not root:
            raise DatabaseProfileError("TigerData requires an explicit certificate trust root")
        if root == "system":
            if psycopg.pq.version() < 160000:
                raise DatabaseProfileError("system roots require compatible libpq")
        elif not Path(root).is_file():
            raise DatabaseProfileError("configured certificate trust root is unavailable")
        url = url.update_query_dict({"sslrootcert": root})
    return url


def build_engine(
    raw: str,
    *,
    profile: Literal["local", "tigerdata"] = "local",
    root_cert: str | None = None,
    connect_timeout: int = 3,
    pool_size: int = 3,
    max_overflow: int = 0,
    pool_timeout: float = 3,
    lock_timeout_ms: int = 3000,
    statement_timeout_ms: int = 15000,
) -> Engine:
    url = postgres_url(raw, profile, root_cert)
    options = url.query.get("options", "")
    if not isinstance(options, str):
        raise DatabaseProfileError("repeated connection options are unsupported")
    return create_engine(
        url,
        echo=False,
        hide_parameters=True,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        connect_args={
            "connect_timeout": connect_timeout,
            "options": f"{options} -c lock_timeout={lock_timeout_ms} "
            f"-c statement_timeout={statement_timeout_ms}",
        },
    )
