"""Bind guarded browser targets to their expected active context and projection."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_browser_bindings"
down_revision: str | None = "0007_pack_replacement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("dependency_targets", sa.Column("application_context", sa.String(128)))
    op.add_column("dependency_targets", sa.Column("pack_version_id", sa.String(128)))
    op.add_column("dependency_targets", sa.Column("active_revision", sa.Integer()))
    op.add_column("dependency_targets", sa.Column("projection_sha256", sa.String(64)))


def downgrade() -> None:
    for name in ("projection_sha256", "active_revision", "pack_version_id", "application_context"):
        op.drop_column("dependency_targets", name)
