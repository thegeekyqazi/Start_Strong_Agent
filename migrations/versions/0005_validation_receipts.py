"""Persist immutable validation receipts, results and forward dependencies.

Revision ID: 0005_validation_receipts
Revises: 0004_pdf_extraction_coverage
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_validation_receipts"
down_revision: str | None = "0004_pdf_extraction_coverage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("knowledge_sources", sa.Column("origin_url", sa.Text()))
    op.add_column("knowledge_sources", sa.Column("canonical_url", sa.Text()))
    op.create_index(
        "ix_knowledge_sources_canonical_url",
        "knowledge_sources",
        ["organization_id", "canonical_url"],
    )
    op.create_table(
        "validation_evaluations",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column(
            "organization_id", sa.String(128), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("subject_kind", sa.String(32), nullable=False),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=False),
        sa.Column("evaluator_build", sa.String(64), nullable=False),
        sa.Column("frozen_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("subject_kind IN ('source_version')", name="ck_validation_subject_kind"),
        sa.CheckConstraint(
            "char_length(input_sha256) = 64", name="ck_validation_evaluations_input_sha256"
        ),
    )
    op.create_index(
        "ix_validation_evaluations_subject",
        "validation_evaluations",
        ["organization_id", "subject_kind", "subject_id", "created_at"],
    )
    op.create_table(
        "validation_results",
        sa.Column(
            "evaluation_id",
            sa.String(128),
            sa.ForeignKey("validation_evaluations.id"),
            primary_key=True,
        ),
        sa.Column("ordinal", sa.Integer(), primary_key=True),
        sa.Column("rule_id", sa.String(16), nullable=False),
        sa.Column("rule_version", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.CheckConstraint("ordinal >= 0", name="ck_validation_results_ordinal"),
        sa.CheckConstraint(
            "outcome IN ('pass','fail','needs_review','not_applicable')",
            name="ck_validation_results_outcome",
        ),
    )
    op.create_index("ix_validation_results_rule", "validation_results", ["rule_id", "outcome"])
    op.create_table(
        "validation_dependencies",
        sa.Column(
            "evaluation_id",
            sa.String(128),
            sa.ForeignKey("validation_evaluations.id"),
            primary_key=True,
        ),
        sa.Column("ordinal", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("ref_id", sa.String(128), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64)),
        sa.CheckConstraint("ordinal >= 0", name="ck_validation_dependencies_ordinal"),
        sa.CheckConstraint(
            "content_hash IS NULL OR char_length(content_hash) = 64",
            name="ck_validation_dependencies_hash",
        ),
    )
    op.create_index(
        "ix_validation_dependencies_ref",
        "validation_dependencies",
        ["kind", "ref_id", "version"],
    )


def downgrade() -> None:
    op.drop_table("validation_dependencies")
    op.drop_table("validation_results")
    op.drop_table("validation_evaluations")
    # IF EXISTS also recovers a local pre-release 0005 that was applied before
    # the optional URL fields were added to this still-unmerged migration.
    op.execute("DROP INDEX IF EXISTS ix_knowledge_sources_canonical_url")
    op.execute("ALTER TABLE knowledge_sources DROP COLUMN IF EXISTS canonical_url")
    op.execute("ALTER TABLE knowledge_sources DROP COLUMN IF EXISTS origin_url")
