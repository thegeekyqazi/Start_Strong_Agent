"""Persist PDF extraction coverage.

Revision ID: 0004_pdf_extraction_coverage
Revises: 0003_artifact_text_ingestion
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_pdf_extraction_coverage"
down_revision: str | None = "0003_artifact_text_ingestion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("knowledge_source_versions", sa.Column("page_count", sa.Integer()))
    op.add_column("knowledge_source_versions", sa.Column("processed_pages", sa.Integer()))
    op.add_column("knowledge_source_versions", sa.Column("extraction_status", sa.String(24)))
    op.create_check_constraint(
        "ck_source_versions_extraction_coverage",
        "knowledge_source_versions",
        "(page_count IS NULL AND processed_pages IS NULL AND extraction_status IS NULL) OR "
        "(page_count > 0 AND processed_pages >= 0 AND processed_pages <= page_count AND "
        "extraction_status IN ('complete', 'partial', 'failed'))",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_source_versions_extraction_coverage",
        "knowledge_source_versions",
        type_="check",
    )
    for name in ("extraction_status", "processed_pages", "page_count"):
        op.drop_column("knowledge_source_versions", name)
