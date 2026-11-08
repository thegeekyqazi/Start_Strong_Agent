"""C4-SKL-001 practice skills: guarded scope state plus append-only immutable records."""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Identity,
    Index,
    MetaData,
    String,
    Table,
    Text,
)

revision: str = "0010_practice_skills"
down_revision: str | None = "0009_durable_applications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
metadata = MetaData()
Table("organizations", metadata, Column("id", String(128), primary_key=True))
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


def upgrade() -> None:
    bind = op.get_bind()
    skl_scope_state.create(bind)
    skl_records.create(bind)


def downgrade() -> None:
    bind = op.get_bind()
    skl_records.drop(bind)
    skl_scope_state.drop(bind)
