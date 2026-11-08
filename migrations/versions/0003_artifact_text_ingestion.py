"""Add storage and parser provenance for immutable source artifacts.

Revision ID: 0003_artifact_text_ingestion
Revises: 0002_source_fact_foundation
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_artifact_text_ingestion"
down_revision: str | None = "0002_source_fact_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "knowledge_source_versions",
        sa.Column(
            "storage_backend", sa.String(32), nullable=False, server_default="postgres_bytea"
        ),
    )
    op.add_column("knowledge_source_versions", sa.Column("artifact_key", sa.Text()))
    op.add_column("knowledge_source_versions", sa.Column("parser_name", sa.String(64)))
    op.add_column("knowledge_source_versions", sa.Column("parser_version", sa.String(32)))
    op.add_column("knowledge_source_versions", sa.Column("parser_warnings", sa.Text()))
    op.alter_column("knowledge_source_versions", "content_bytes", nullable=True)
    op.create_check_constraint(
        "ck_source_versions_storage",
        "knowledge_source_versions",
        "(storage_backend = 'postgres_bytea' AND content_bytes IS NOT NULL "
        "AND artifact_key IS NULL) OR (storage_backend = 'local_artifact' "
        "AND content_bytes IS NULL AND artifact_key IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_source_versions_parser",
        "knowledge_source_versions",
        "(parser_name IS NULL AND parser_version IS NULL AND parser_warnings IS NULL) OR "
        "(parser_name IS NOT NULL AND parser_version IS NOT NULL AND parser_warnings IS NOT NULL)",
    )


def downgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM knowledge_source_versions "
        "WHERE storage_backend = 'local_artifact') THEN "
        "RAISE EXCEPTION 'cannot downgrade while external artifact rows exist'; "
        "END IF; END $$"
    )
    op.drop_constraint("ck_source_versions_parser", "knowledge_source_versions", type_="check")
    op.drop_constraint("ck_source_versions_storage", "knowledge_source_versions", type_="check")
    op.alter_column("knowledge_source_versions", "content_bytes", nullable=False)
    for name in (
        "parser_warnings",
        "parser_version",
        "parser_name",
        "artifact_key",
        "storage_backend",
    ):
        op.drop_column("knowledge_source_versions", name)
