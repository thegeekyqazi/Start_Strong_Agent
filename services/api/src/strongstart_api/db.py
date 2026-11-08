"""Database access and readiness. PostgreSQL only: a failed connection never falls back."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Engine,
    ForeignKey,
    Integer,
    LargeBinary,
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
REQUIRED_MIGRATION_REVISION = "0002_source_fact_foundation"

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

knowledge_sources = Table(
    "knowledge_sources",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("organization_id", String(128), ForeignKey("organizations.id"), nullable=False),
    Column("title", Text, nullable=False),
    Column("provenance_class", String(32), nullable=False),
    Column("is_simulated", Boolean, nullable=False),
    Column("provenance_note", Text),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

knowledge_source_versions = Table(
    "knowledge_source_versions",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("source_id", String(128), ForeignKey("knowledge_sources.id"), nullable=False),
    Column("organization_id", String(128), ForeignKey("organizations.id"), nullable=False),
    Column("media_type", Text, nullable=False),
    Column("content_bytes", LargeBinary, nullable=False),
    Column("content_sha256", String(64), nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("captured_at", DateTime(timezone=True)),
    Column("publication_status", String(24), nullable=False),
    Column("publication_date", DateTime(timezone=True)),
    Column("reporting_period", Text),
    Column("verification_status", String(24), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

knowledge_passages = Table(
    "knowledge_passages",
    metadata,
    Column("id", String(128), primary_key=True),
    Column(
        "source_version_id", String(128), ForeignKey("knowledge_source_versions.id"), nullable=False
    ),
    Column("locator", Text, nullable=False),
    Column("exact_text", Text, nullable=False),
)

evidence_packs = Table(
    "evidence_packs",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("organization_id", String(128), ForeignKey("organizations.id"), nullable=False),
)

evidence_pack_versions = Table(
    "evidence_pack_versions",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("pack_id", String(128), ForeignKey("evidence_packs.id"), nullable=False),
    Column("bundle_id", String(128), nullable=False, unique=True),
    Column("access_context", Text, nullable=False),
    Column("coverage_notes", Text, nullable=False, server_default=""),
)

knowledge_facts = Table(
    "knowledge_facts",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("organization_id", String(128), ForeignKey("organizations.id"), nullable=False),
    Column("metric_id", String(128), nullable=False),
    Column("value_exact", Text),
    Column("raw_value", Text),
    Column("unit", Text),
    Column("scope", Text, nullable=False),
    Column("population", Text),
    Column("reporting_period", Text),
    Column("status", String(24), nullable=False),
    Column("provenance_class", String(32), nullable=False),
    Column("is_simulated", Boolean, nullable=False),
    Column("provenance_note", Text),
)

fact_source_refs = Table(
    "fact_source_refs",
    metadata,
    Column("fact_id", String(128), ForeignKey("knowledge_facts.id"), primary_key=True),
    Column(
        "source_version_id",
        String(128),
        ForeignKey("knowledge_source_versions.id"),
        primary_key=True,
    ),
    Column("locator", Text, nullable=False),
)

pack_facts = Table(
    "pack_facts",
    metadata,
    Column(
        "pack_version_id", String(128), ForeignKey("evidence_pack_versions.id"), primary_key=True
    ),
    Column("fact_id", String(128), ForeignKey("knowledge_facts.id"), primary_key=True),
    Column("allowed", Boolean, nullable=False, server_default="true"),
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
