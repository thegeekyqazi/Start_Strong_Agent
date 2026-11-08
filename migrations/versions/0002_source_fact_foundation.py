"""Immutable organization-scoped source and typed fact foundation.

Revision ID: 0002_source_fact_foundation
Revises: 0001_bootstrap
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_source_fact_foundation"
down_revision: str | None = "0001_bootstrap"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    provenance = "provenance_class IN ('supplied','public','simulated','engineering_derived')"
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column(
            "organization_id", sa.String(128), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("provenance_class", sa.String(32), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), nullable=False),
        sa.Column("provenance_note", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(provenance, name="ck_knowledge_sources_provenance"),
    )
    op.create_table(
        "knowledge_source_versions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column(
            "source_id", sa.String(128), sa.ForeignKey("knowledge_sources.id"), nullable=False
        ),
        sa.Column(
            "organization_id", sa.String(128), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("content_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
        sa.Column("publication_status", sa.String(24), nullable=False),
        sa.Column("publication_date", sa.DateTime(timezone=True)),
        sa.Column("reporting_period", sa.Text()),
        sa.Column("verification_status", sa.String(24), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_source_versions_size"),
        sa.CheckConstraint("char_length(content_sha256) = 64", name="ck_source_versions_sha256"),
        sa.CheckConstraint(
            "publication_status IN ('known','unknown','not_applicable')",
            name="ck_source_versions_publication_status",
        ),
        sa.CheckConstraint(
            "verification_status IN ('unverified','verified','conflicting')",
            name="ck_source_versions_verification_status",
        ),
    )
    op.create_table(
        "knowledge_passages",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column(
            "source_version_id",
            sa.String(128),
            sa.ForeignKey("knowledge_source_versions.id"),
            nullable=False,
        ),
        sa.Column("locator", sa.Text(), nullable=False),
        sa.Column("exact_text", sa.Text(), nullable=False),
    )
    op.create_table(
        "evidence_packs",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column(
            "organization_id", sa.String(128), sa.ForeignKey("organizations.id"), nullable=False
        ),
    )
    op.create_table(
        "evidence_pack_versions",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("pack_id", sa.String(128), sa.ForeignKey("evidence_packs.id"), nullable=False),
        sa.Column("bundle_id", sa.String(128), nullable=False, unique=True),
        sa.Column("access_context", sa.Text(), nullable=False),
        sa.Column("coverage_notes", sa.Text(), nullable=False, server_default=""),
    )
    op.create_table(
        "knowledge_facts",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column(
            "organization_id", sa.String(128), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("metric_id", sa.String(128), nullable=False),
        sa.Column("value_exact", sa.Text()),
        sa.Column("raw_value", sa.Text()),
        sa.Column("unit", sa.Text()),
        sa.Column("scope", sa.Text(), nullable=False),
        sa.Column("population", sa.Text()),
        sa.Column("reporting_period", sa.Text()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("provenance_class", sa.String(32), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), nullable=False),
        sa.Column("provenance_note", sa.Text()),
        sa.CheckConstraint(provenance, name="ck_knowledge_facts_provenance"),
        sa.CheckConstraint(
            "status IN ('extracted','needs_review','verified','conflicting','superseded')",
            name="ck_knowledge_facts_status",
        ),
    )
    op.create_table(
        "fact_source_refs",
        sa.Column("fact_id", sa.String(128), sa.ForeignKey("knowledge_facts.id"), primary_key=True),
        sa.Column(
            "source_version_id",
            sa.String(128),
            sa.ForeignKey("knowledge_source_versions.id"),
            primary_key=True,
        ),
        sa.Column("locator", sa.Text(), nullable=False),
    )
    op.create_table(
        "pack_facts",
        sa.Column(
            "pack_version_id",
            sa.String(128),
            sa.ForeignKey("evidence_pack_versions.id"),
            primary_key=True,
        ),
        sa.Column("fact_id", sa.String(128), sa.ForeignKey("knowledge_facts.id"), primary_key=True),
        sa.Column("allowed", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    for name in (
        "pack_facts",
        "fact_source_refs",
        "knowledge_facts",
        "evidence_pack_versions",
        "evidence_packs",
        "knowledge_passages",
        "knowledge_source_versions",
        "knowledge_sources",
    ):
        op.drop_table(name)
