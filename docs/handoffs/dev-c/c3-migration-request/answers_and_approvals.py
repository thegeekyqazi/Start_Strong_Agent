"""DRAFT migration request from Dev C for Dev A to sequence (C3 spec s3). UNNUMBERED.

NOT ACTIVE: this file lives outside ``migrations/versions`` on purpose. Dev A owns migration
sequencing (ownership.md). Earlier drafts were numbered 0003, then 0004, then 0005; each
number was taken by Dev A's own migrations (0005_validation_receipts and
0006_numeric_validation are on main; 0007_pack_replacement is in A4's open PR #15). So the
revision ID and down-revision are now placeholders for Dev A to assign at sequencing time.

``down_revision`` is a deliberately invalid placeholder: if this file were copied into
``migrations/versions`` unchanged, Alembic would fail with an unknown-revision error
instead of silently creating a second head. Dev A sets both values, copies the file and
updates ``REQUIRED_MIGRATION_REVISION`` in ``strongstart_api/db.py``. Until then C3 uses its
labelled in-memory fixture store.

Tables mirror ``features/applications/store.py``: immutable answer versions, one decision
per version, review notes, reviewer proposals, exports and SEC-10 audit events, all scoped
to ``organizations``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "assign_by_dev_a_answers_and_approvals"
down_revision: str | None = "SET_BY_DEV_A_TO_CURRENT_HEAD"  # fails closed if applied as-is
branch_labels: str | None = None
depends_on: str | None = None

_ORG = sa.ForeignKey("organizations.id", ondelete="RESTRICT")


def upgrade() -> None:
    op.create_table(
        "answer_versions",
        sa.Column("answer_version_id", sa.String(128), primary_key=True),
        sa.Column("organization_id", sa.String(128), _ORG, nullable=False),
        sa.Column("answer_id", sa.String(128), nullable=False),
        sa.Column("question_id", sa.String(128), nullable=False),
        sa.Column("question_version", sa.Integer, nullable=False),
        sa.Column("answer_version", sa.Integer, nullable=False),
        sa.Column("evidence_bundle_id", sa.String(128), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("content_sha256", sa.CHAR(64), nullable=False),
        sa.Column("snapshot_sha256", sa.CHAR(64), nullable=False),
        sa.Column("rendered", sa.JSON, nullable=False),
        sa.Column("dependencies", sa.JSON, nullable=False),
        sa.Column("check_report", sa.JSON, nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "question_id", "answer_version"),
        sa.CheckConstraint("answer_version >= 1", name="ck_answer_version_positive"),
    )
    op.create_table(
        "approval_records",
        sa.Column("approval_id", sa.String(128), primary_key=True),
        sa.Column("organization_id", sa.String(128), _ORG, nullable=False),
        sa.Column(
            "answer_version_id",
            sa.String(128),
            sa.ForeignKey("answer_versions.answer_version_id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,  # one decision per exact version (JOB-02)
        ),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("content_sha256", sa.CHAR(64), nullable=False),
        sa.Column("snapshot_sha256", sa.CHAR(64), nullable=False),
        sa.Column("reviewer_id", sa.String(128), nullable=False),
        sa.Column("reviewer_is_fixture_identity", sa.Boolean, nullable=False),
        sa.Column("acknowledged_review_items", sa.Boolean, nullable=False),
        sa.Column("note", sa.Text, nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("decision IN ('approve', 'reject')", name="ck_decision_value"),
    )
    op.create_table(
        "review_notes",
        sa.Column("note_id", sa.String(128), primary_key=True),
        sa.Column("organization_id", sa.String(128), _ORG, nullable=False),
        sa.Column("answer_version_id", sa.String(128), nullable=False),
        sa.Column("author_id", sa.String(128), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "reviewer_proposals",
        sa.Column("proposal_id", sa.String(128), primary_key=True),
        sa.Column("organization_id", sa.String(128), _ORG, nullable=False),
        sa.Column("answer_version_id", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "answer_exports",
        sa.Column("export_id", sa.String(128), primary_key=True),
        sa.Column("organization_id", sa.String(128), _ORG, nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("docx_sha256", sa.CHAR(64), nullable=False),
        sa.Column("audit_sha256", sa.CHAR(64), nullable=False),
        sa.Column("docx", sa.LargeBinary, nullable=False),
        sa.Column("audit", sa.LargeBinary, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "answer_audit_events",
        sa.Column("event_id", sa.String(128), primary_key=True),
        sa.Column("organization_id", sa.String(128), _ORG, nullable=False),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("object_type", sa.String(64), nullable=False),
        sa.Column("object_id", sa.String(128), nullable=False),
        sa.Column("object_version", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(64), nullable=False),
        sa.Column("details", sa.JSON, nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "applied_change_sets",
        sa.Column("organization_id", sa.String(128), _ORG, primary_key=True),
        sa.Column("change_set_id", sa.String(128), primary_key=True),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "applied_change_sets",
        "answer_audit_events",
        "answer_exports",
        "reviewer_proposals",
        "review_notes",
        "approval_records",
        "answer_versions",
    ):
        op.drop_table(table)
