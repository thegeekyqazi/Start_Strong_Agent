"""DATA-001 durable C state; additive after INT-001, no evidence fixture FKs."""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
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
)

revision: str = "0009_durable_applications"
down_revision: str | None = "0008_browser_bindings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
metadata = MetaData()
Table("organizations", metadata, Column("id", String(128), primary_key=True))
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


def upgrade() -> None:
    for table in APPLICATION_TABLES:
        table.create(op.get_bind())


def downgrade() -> None:
    for table in reversed(APPLICATION_TABLES):
        table.drop(op.get_bind())
