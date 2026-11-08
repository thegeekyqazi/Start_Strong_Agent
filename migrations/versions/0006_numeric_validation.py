"""Add versioned numeric facts and approved project inputs for A3c."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_numeric_validation"
down_revision: str | None = "0005_validation_receipts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_validation_subject_kind", "validation_evaluations", type_="check")
    op.create_check_constraint(
        "ck_validation_subject_kind",
        "validation_evaluations",
        "subject_kind IN ('source_version','fact')",
    )
    op.add_column(
        "knowledge_facts",
        sa.Column("fact_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_check_constraint(
        "ck_knowledge_facts_fact_version", "knowledge_facts", "fact_version >= 1"
    )
    for name in ("currency", "scale", "program", "geography"):
        op.add_column("knowledge_facts", sa.Column(name, sa.Text()))
    op.create_table(
        "project_numeric_inputs",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column(
            "organization_id", sa.String(128), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("input_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("value_exact", sa.Text(), nullable=False),
        sa.Column("unit", sa.Text()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("input_version >= 1", name="ck_project_numeric_inputs_version"),
        sa.CheckConstraint(
            "status IN ('proposed','approved','revoked')", name="ck_project_numeric_inputs_status"
        ),
    )


def downgrade() -> None:
    op.drop_table("project_numeric_inputs")
    for name in ("geography", "program", "scale", "currency"):
        op.drop_column("knowledge_facts", name)
    op.drop_constraint("ck_knowledge_facts_fact_version", "knowledge_facts", type_="check")
    op.drop_column("knowledge_facts", "fact_version")
    op.drop_constraint("ck_validation_subject_kind", "validation_evaluations", type_="check")
    op.create_check_constraint(
        "ck_validation_subject_kind", "validation_evaluations", "subject_kind IN ('source_version')"
    )
