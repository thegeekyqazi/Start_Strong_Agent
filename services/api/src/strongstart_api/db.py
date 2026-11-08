"""Database access and readiness. PostgreSQL only: a failed connection never falls back."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Engine,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.exc import SQLAlchemyError

from strongstart_contracts import ReadinessCheck, ReadinessReport

from .config import Settings

# Must equal the Alembic head in migrations/versions (asserted by tests/unit).
REQUIRED_MIGRATION_REVISION = "0010_practice_skills"

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
    Column("origin_url", Text),
    Column("canonical_url", Text),
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
    Column("content_bytes", LargeBinary),
    Column("storage_backend", String(32), nullable=False, server_default="postgres_bytea"),
    Column("artifact_key", Text),
    Column("content_sha256", String(64), nullable=False),
    Column("size_bytes", Integer, nullable=False),
    Column("captured_at", DateTime(timezone=True)),
    Column("publication_status", String(24), nullable=False),
    Column("publication_date", DateTime(timezone=True)),
    Column("reporting_period", Text),
    Column("verification_status", String(24), nullable=False),
    Column("parser_name", String(64)),
    Column("parser_version", String(32)),
    Column("parser_warnings", Text),
    Column("page_count", Integer),
    Column("processed_pages", Integer),
    Column("extraction_status", String(24)),
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
    Column("fact_version", Integer, nullable=False, server_default="1"),
    Column("organization_id", String(128), ForeignKey("organizations.id"), nullable=False),
    Column("metric_id", String(128), nullable=False),
    Column("value_exact", Text),
    Column("raw_value", Text),
    Column("unit", Text),
    Column("currency", Text),
    Column("scale", Text),
    Column("scope", Text, nullable=False),
    Column("program", Text),
    Column("geography", Text),
    Column("population", Text),
    Column("reporting_period", Text),
    Column("status", String(24), nullable=False),
    Column("provenance_class", String(32), nullable=False),
    Column("is_simulated", Boolean, nullable=False),
    Column("provenance_note", Text),
)

project_numeric_inputs = Table(
    "project_numeric_inputs",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("organization_id", String(128), ForeignKey("organizations.id"), nullable=False),
    Column("input_version", Integer, nullable=False, server_default="1"),
    Column("value_exact", Text, nullable=False),
    Column("unit", Text),
    Column("status", String(24), nullable=False),
    Column("is_simulated", Boolean, nullable=False, server_default="false"),
    CheckConstraint("input_version >= 1", name="ck_project_numeric_inputs_version"),
    CheckConstraint(
        "status IN ('proposed','approved','revoked')",
        name="ck_project_numeric_inputs_status",
    ),
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

validation_evaluations = Table(
    "validation_evaluations",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("organization_id", String(128), ForeignKey("organizations.id"), nullable=False),
    Column("actor_id", String(128), nullable=False),
    Column("subject_kind", String(32), nullable=False),
    Column("subject_id", String(128), nullable=False),
    Column("input_sha256", String(64), nullable=False),
    Column("evaluator_build", String(64), nullable=False),
    Column("frozen_time", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

validation_results = Table(
    "validation_results",
    metadata,
    Column("evaluation_id", String(128), ForeignKey("validation_evaluations.id"), primary_key=True),
    Column("ordinal", Integer, primary_key=True),
    Column("rule_id", String(16), nullable=False),
    Column("rule_version", String(64), nullable=False),
    Column("outcome", String(24), nullable=False),
    Column("reason_code", String(64), nullable=False),
    Column("payload_json", Text, nullable=False),
)

validation_dependencies = Table(
    "validation_dependencies",
    metadata,
    Column("evaluation_id", String(128), ForeignKey("validation_evaluations.id"), primary_key=True),
    Column("ordinal", Integer, primary_key=True),
    Column("kind", String(32), nullable=False),
    Column("ref_id", String(128), nullable=False),
    Column("version", Text, nullable=False),
    Column("content_hash", String(64)),
)

pack_manifests = Table(
    "pack_manifests",
    metadata,
    Column(
        "pack_version_id",
        String(128),
        ForeignKey("evidence_pack_versions.id"),
        primary_key=True,
    ),
    Column("organization_id", String(128), ForeignKey("organizations.id"), nullable=False),
    Column("application_context", String(128), nullable=False),
    Column("manifest_sha256", String(64), nullable=False),
    Column("manifest_json", Text, nullable=False),
    Column("created_by", String(128), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("organization_id", "manifest_sha256", name="uq_pack_manifest_org_hash"),
)

pack_manifest_sources = Table(
    "pack_manifest_sources",
    metadata,
    Column(
        "pack_version_id",
        String(128),
        ForeignKey("pack_manifests.pack_version_id"),
        primary_key=True,
    ),
    Column(
        "source_version_id",
        String(128),
        ForeignKey("knowledge_source_versions.id"),
        primary_key=True,
    ),
)

pack_policies = Table(
    "pack_policies",
    metadata,
    Column("policy_id", String(128), primary_key=True),
    Column("policy_version", Integer, primary_key=True),
    Column("organization_id", String(128), ForeignKey("organizations.id"), nullable=False),
    Column("content_sha256", String(64), nullable=False),
    Column("content", Text, nullable=False),
    Column("status", String(24), nullable=False),
)

pack_manifest_policies = Table(
    "pack_manifest_policies",
    metadata,
    Column(
        "pack_version_id",
        String(128),
        ForeignKey("pack_manifests.pack_version_id"),
        primary_key=True,
    ),
    Column("policy_id", String(128), primary_key=True),
    Column("policy_version", Integer, primary_key=True),
    ForeignKeyConstraint(
        ["policy_id", "policy_version"],
        ["pack_policies.policy_id", "pack_policies.policy_version"],
    ),
)

active_pack_contexts = Table(
    "active_pack_contexts",
    metadata,
    Column("organization_id", String(128), ForeignKey("organizations.id"), primary_key=True),
    Column("application_context", String(128), primary_key=True),
    Column(
        "pack_version_id", String(128), ForeignKey("pack_manifests.pack_version_id"), nullable=False
    ),
    Column("revision", Integer, nullable=False),
    Column("updated_by", String(128), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

pack_change_sets = Table(
    "pack_change_sets",
    metadata,
    Column("id", String(128), primary_key=True),
    Column("organization_id", String(128), ForeignKey("organizations.id"), nullable=False),
    Column("application_context", String(128), nullable=False),
    Column("previous_pack_version_id", String(128), ForeignKey("pack_manifests.pack_version_id")),
    Column(
        "new_pack_version_id",
        String(128),
        ForeignKey("pack_manifests.pack_version_id"),
        nullable=False,
    ),
    Column("actor_id", String(128), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

pack_changes = Table(
    "pack_changes",
    metadata,
    Column("change_set_id", String(128), ForeignKey("pack_change_sets.id"), primary_key=True),
    Column("ordinal", Integer, primary_key=True),
    Column("kind", String(32), nullable=False),
    Column("ref_id", String(128), nullable=False),
    Column("previous_version", Text),
    Column("new_version", Text, nullable=False),
)

dependency_targets = Table(
    "dependency_targets",
    metadata,
    Column("organization_id", String(128), ForeignKey("organizations.id"), primary_key=True),
    Column("target_kind", String(32), primary_key=True),
    Column("target_id", String(128), primary_key=True),
    Column("revision", Integer, nullable=False),
    Column("state", String(16), nullable=False),
    Column("stale_change_set_id", String(128)),
    Column("application_context", String(128)),
    Column("pack_version_id", String(128)),
    Column("active_revision", Integer),
    Column("projection_sha256", String(64)),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

dependency_target_refs = Table(
    "dependency_target_refs",
    metadata,
    Column("organization_id", String(128), primary_key=True),
    Column("target_kind", String(32), primary_key=True),
    Column("target_id", String(128), primary_key=True),
    Column("ordinal", Integer, primary_key=True),
    Column("kind", String(32), nullable=False),
    Column("ref_id", String(128), nullable=False),
    Column("version", Text, nullable=False),
    Column("content_hash", String(64)),
    ForeignKeyConstraint(
        ["organization_id", "target_kind", "target_id"],
        [
            "dependency_targets.organization_id",
            "dependency_targets.target_kind",
            "dependency_targets.target_id",
        ],
    ),
)

invalidation_events = Table(
    "invalidation_events",
    metadata,
    Column("change_set_id", String(128), ForeignKey("pack_change_sets.id"), primary_key=True),
    Column("target_kind", String(32), primary_key=True),
    Column("target_id", String(128), primary_key=True),
    Column("matched_dependencies_json", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)


# Reconcile indexes already installed by released 0005/0007 migrations.
Index(
    "ix_knowledge_sources_canonical_url",
    knowledge_sources.c.organization_id,
    knowledge_sources.c.canonical_url,
)
Index(
    "ix_validation_evaluations_subject",
    validation_evaluations.c.organization_id,
    validation_evaluations.c.subject_kind,
    validation_evaluations.c.subject_id,
    validation_evaluations.c.created_at,
)
Index("ix_validation_results_rule", validation_results.c.rule_id, validation_results.c.outcome)
Index(
    "ix_validation_dependencies_ref",
    validation_dependencies.c.kind,
    validation_dependencies.c.ref_id,
    validation_dependencies.c.version,
)
Index(
    "ix_pack_manifests_context",
    pack_manifests.c.organization_id,
    pack_manifests.c.application_context,
    pack_manifests.c.created_at,
)
Index(
    "ix_pack_changes_dependency",
    pack_changes.c.kind,
    pack_changes.c.ref_id,
    pack_changes.c.previous_version,
)
Index(
    "ix_dependency_target_refs_reverse",
    dependency_target_refs.c.organization_id,
    dependency_target_refs.c.kind,
    dependency_target_refs.c.ref_id,
    dependency_target_refs.c.version,
)

# DATA-001 C-owned durable state. Evidence remains a logical, live-verified reference.
c_store_state = Table(
    "c_store_state",
    metadata,
    Column("organization_id", String(128), ForeignKey("organizations.id"), primary_key=True),
    Column("epoch", String(128), nullable=False),
    Column("revision", BigInteger, nullable=False, server_default="0"),
    CheckConstraint("revision >= 0", name="ck_c_state_revision"),
)
c_answer_heads = Table(
    "c_answer_heads",
    metadata,
    Column("organization_id", String(128), ForeignKey("organizations.id"), primary_key=True),
    Column("question_id", String(128), primary_key=True),
    Column("latest_version", Integer, nullable=False, server_default="0"),
    CheckConstraint("latest_version >= 0", name="ck_c_head_version"),
)
c_answer_versions = Table(
    "c_answer_versions",
    metadata,
    Column("answer_version_id", String(128), primary_key=True),
    Column("organization_id", String(128), nullable=False),
    Column("question_id", String(128), nullable=False),
    Column("answer_version", Integer, nullable=False),
    Column("content_sha256", String(64), nullable=False),
    Column("rendered_sha256", String(64), nullable=False),
    Column("snapshot_sha256", String(64), nullable=False),
    Column("payload_version", Integer, nullable=False),
    Column("payload", Text, nullable=False),
    ForeignKeyConstraint(
        ["organization_id", "question_id"],
        ["c_answer_heads.organization_id", "c_answer_heads.question_id"],
    ),
    UniqueConstraint("organization_id", "answer_version_id", name="uq_c_version_org_id"),
    UniqueConstraint(
        "organization_id", "question_id", "answer_version", name="uq_c_lineage_version"
    ),
    CheckConstraint("answer_version >= 1 AND payload_version >= 1", name="ck_c_version_positive"),
    CheckConstraint(
        "char_length(content_sha256)=64 AND char_length(rendered_sha256)=64 "
        "AND char_length(snapshot_sha256)=64",
        name="ck_c_version_hashes",
    ),
)
c_decisions = Table(
    "c_decisions",
    metadata,
    Column("approval_id", String(128), primary_key=True),
    Column("organization_id", String(128), nullable=False),
    Column("answer_version_id", String(128), nullable=False),
    Column("decision", String(16), nullable=False),
    Column("payload_version", Integer, nullable=False),
    Column("payload", Text, nullable=False),
    ForeignKeyConstraint(
        ["organization_id", "answer_version_id"],
        ["c_answer_versions.organization_id", "c_answer_versions.answer_version_id"],
    ),
    UniqueConstraint("organization_id", "answer_version_id", name="uq_c_one_decision"),
    CheckConstraint("decision IN ('approve','reject')", name="ck_c_decision"),
)
c_notes = Table(
    "c_notes",
    metadata,
    Column("note_id", String(128), primary_key=True),
    Column("organization_id", String(128), nullable=False),
    Column("answer_version_id", String(128), nullable=False),
    Column("ordinal", BigInteger, Identity(), nullable=False, unique=True),
    Column("payload_version", Integer, nullable=False),
    Column("payload", Text, nullable=False),
    ForeignKeyConstraint(
        ["organization_id", "answer_version_id"],
        ["c_answer_versions.organization_id", "c_answer_versions.answer_version_id"],
    ),
)
c_proposals = Table(
    "c_proposals",
    metadata,
    Column("proposal_id", String(128), primary_key=True),
    Column("organization_id", String(128), nullable=False),
    Column("answer_version_id", String(128), nullable=False),
    Column("ordinal", BigInteger, Identity(), nullable=False, unique=True),
    Column("payload_version", Integer, nullable=False),
    Column("payload", Text, nullable=False),
    ForeignKeyConstraint(
        ["organization_id", "answer_version_id"],
        ["c_answer_versions.organization_id", "c_answer_versions.answer_version_id"],
    ),
)
c_change_sets = Table(
    "c_change_sets",
    metadata,
    Column("organization_id", String(128), ForeignKey("organizations.id"), primary_key=True),
    Column("change_set_id", String(128), primary_key=True),
    Column("ordinal", BigInteger, Identity(), nullable=False, unique=True),
    Column("payload_version", Integer, nullable=False),
    Column("payload", Text, nullable=False),
    Column("payload_sha256", String(64), nullable=False),
)
c_exports = Table(
    "c_exports",
    metadata,
    Column("export_id", String(128), primary_key=True),
    Column("organization_id", String(128), ForeignKey("organizations.id"), nullable=False),
    Column("payload_version", Integer, nullable=False),
    Column("payload", Text, nullable=False),
    Column("docx", LargeBinary, nullable=False),
    Column("audit", LargeBinary, nullable=False),
    Column("docx_sha256", String(64), nullable=False),
    Column("audit_sha256", String(64), nullable=False),
)
c_audit_events = Table(
    "c_audit_events",
    metadata,
    Column("event_id", String(128), primary_key=True),
    Column("organization_id", String(128), ForeignKey("organizations.id"), nullable=False),
    Column("ordinal", BigInteger, Identity(), nullable=False, unique=True),
    Column("payload_version", Integer, nullable=False),
    Column("payload", Text, nullable=False),
    Column("actor_id", String(128), nullable=False),
    Column("action", String(128), nullable=False),
    CheckConstraint(
        "char_length(actor_id)>0 AND char_length(action)>0", name="ck_c_audit_complete"
    ),
)
Index("ix_c_audit_org_order", c_audit_events.c.organization_id, c_audit_events.c.ordinal)
Index("ix_c_notes_org_order", c_notes.c.organization_id, c_notes.c.ordinal)
Index("ix_c_proposals_org_order", c_proposals.c.organization_id, c_proposals.c.ordinal)
APPLICATION_TABLES = (
    c_store_state,
    c_answer_heads,
    c_answer_versions,
    c_decisions,
    c_notes,
    c_proposals,
    c_change_sets,
    c_exports,
    c_audit_events,
)


@lru_cache(maxsize=16)
def get_engine(
    database_url: str,
    connect_timeout: int = 3,
    *,
    profile: str = "local",
    root_cert: str | None = None,
    pool_size: int = 3,
    max_overflow: int = 0,
    pool_timeout: float = 3,
    lock_timeout_ms: int = 3000,
    statement_timeout_ms: int = 15000,
) -> Engine:
    from typing import Literal, cast

    from .database_profile import build_engine

    return build_engine(
        database_url,
        profile=cast(Literal["local", "tigerdata"], profile),
        root_cert=root_cert,
        connect_timeout=connect_timeout,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        lock_timeout_ms=lock_timeout_ms,
        statement_timeout_ms=statement_timeout_ms,
    )


def configured_engine(settings: Settings) -> Engine:
    if not settings.database_url:
        raise ValueError("database connection is not configured")
    return get_engine(
        settings.database_url,
        settings.db_connect_timeout_seconds,
        profile=settings.database_profile,
        root_cert=settings.db_sslrootcert,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        lock_timeout_ms=settings.db_lock_timeout_ms,
        statement_timeout_ms=settings.db_statement_timeout_ms,
    )


def check_readiness(
    database_url: str | None, connect_timeout: int = 3, *, settings: Settings | None = None
) -> ReadinessReport:
    if not database_url:
        return ReadinessReport(
            status="not_ready",
            checks=[
                ReadinessCheck(name="database", ok=False, detail="STRONGSTART_DATABASE_URL unset")
            ],
        )
    checks: list[ReadinessCheck] = []
    try:
        engine = (
            configured_engine(settings)
            if settings is not None
            else get_engine(database_url, connect_timeout)
        )
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


# C4-SKL-001 practice skills (owner C). One guarded scope row per organization/context;
# everything else is an append-only immutable record. Mutation + audit share one commit.
skl_scope_state = Table(
    "skl_scope_state",
    metadata,
    Column("organization_id", String(128), ForeignKey("organizations.id"), primary_key=True),
    Column("context_id", String(128), primary_key=True),
    Column("current_source_version_id", String(128)),
    Column("active_release_id", String(128)),
    Column("revision", BigInteger, nullable=False, server_default="0"),
    CheckConstraint("revision >= 0", name="ck_skl_scope_revision"),
)
skl_records = Table(
    "skl_records",
    metadata,
    Column("record_id", String(128), primary_key=True),
    Column("organization_id", String(128), ForeignKey("organizations.id"), nullable=False),
    Column("context_id", String(128), nullable=False),
    Column("kind", String(32), nullable=False),
    Column("parent_id", String(128)),
    Column("sha256", String(64), nullable=False),
    Column("ordinal", BigInteger, Identity(), nullable=False, unique=True),
    Column("payload", Text, nullable=False),
    Column("actor_id", String(128), nullable=False),
    CheckConstraint(
        "kind IN ('source','authority','candidate','screening','review','release',"
        "'revocation','supersession','preview','audit')",
        name="ck_skl_record_kind",
    ),
    CheckConstraint("char_length(actor_id)>0", name="ck_skl_record_actor"),
)
Index(
    "ix_skl_records_scope", skl_records.c.organization_id, skl_records.c.kind, skl_records.c.ordinal
)
PRACTICE_TABLES = (skl_scope_state, skl_records)
