"""Database access and readiness. PostgreSQL only: a failed connection never falls back."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Engine,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    text,
)
from sqlalchemy.exc import SQLAlchemyError

from strongstart_contracts import ReadinessCheck, ReadinessReport

# Must equal the Alembic head in migrations/versions (asserted by tests/unit).
REQUIRED_MIGRATION_REVISION = "0001_bootstrap"

metadata = MetaData()

organizations = Table(
    "organizations",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("display_name", Text, nullable=False),
    Column("provenance_class", String(32), nullable=False),
    Column("is_simulated", Boolean, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint(
        "provenance_class IN ('supplied','public','simulated','engineering_derived')",
        name="ck_organizations_provenance_class",
    ),
)

bootstrap_metadata = Table(
    "bootstrap_metadata",
    metadata,
    Column("key", String(128), primary_key=True),
    Column("value", Text, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


@lru_cache(maxsize=4)
def get_engine(database_url: str, connect_timeout: int = 3) -> Engine:
    if not database_url.startswith("postgresql"):
        raise ValueError("only PostgreSQL URLs are supported (no SQLite/in-memory substitute)")
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": connect_timeout},
    )


def check_readiness(database_url: str | None, connect_timeout: int = 3) -> ReadinessReport:
    if not database_url:
        return ReadinessReport(
            status="not_ready",
            checks=[
                ReadinessCheck(name="database", ok=False, detail="STRONGSTART_DATABASE_URL unset")
            ],
        )
    checks: list[ReadinessCheck] = []
    try:
        engine = get_engine(database_url, connect_timeout)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            checks.append(ReadinessCheck(name="database", ok=True, detail="connected"))
            try:
                revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            except SQLAlchemyError:
                revision = None
            ok = revision == REQUIRED_MIGRATION_REVISION
            checks.append(
                ReadinessCheck(
                    name="migrations",
                    ok=ok,
                    detail=f"revision={revision or 'none'} required={REQUIRED_MIGRATION_REVISION}",
                )
            )
    except (SQLAlchemyError, ValueError) as exc:
        # Report the failure class only; connection strings may contain credentials.
        checks.append(ReadinessCheck(name="database", ok=False, detail=type(exc).__name__))
    status = "ready" if checks and all(c.ok for c in checks) and len(checks) == 2 else "not_ready"
    return ReadinessReport(status=status, checks=checks)
