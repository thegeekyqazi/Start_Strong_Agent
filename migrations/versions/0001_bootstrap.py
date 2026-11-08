"""Bootstrap tables: organizations and bootstrap metadata only (INIT-001 s7).

No production domain schema (facts, applications, approvals) is created here;
owning feature specs add those through later revisions sequenced by Dev A.

Revision ID: 0001_bootstrap
Revises:
Create Date: 2026-11-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_bootstrap"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("provenance_class", sa.String(32), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "provenance_class IN ('supplied','public','simulated','engineering_derived')",
            name="ck_organizations_provenance_class",
        ),
    )
    op.create_table(
        "bootstrap_metadata",
        sa.Column("key", sa.String(128), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    op.drop_table("bootstrap_metadata")
    op.drop_table("organizations")
