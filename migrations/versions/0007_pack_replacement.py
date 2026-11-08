"""Add immutable pack manifests, active pointers and reverse invalidation records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_pack_replacement"
down_revision: str | None = "0006_numeric_validation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pack_manifests",
        sa.Column(
            "pack_version_id",
            sa.String(128),
            sa.ForeignKey("evidence_pack_versions.id"),
            primary_key=True,
        ),
        sa.Column(
            "organization_id", sa.String(128), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("application_context", sa.String(128), nullable=False),
        sa.Column("manifest_sha256", sa.String(64), nullable=False),
        sa.Column("manifest_json", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("char_length(manifest_sha256) = 64", name="ck_pack_manifest_hash"),
        sa.UniqueConstraint(
            "organization_id", "manifest_sha256", name="uq_pack_manifest_org_hash"
        ),
    )
    op.create_index(
        "ix_pack_manifests_context",
        "pack_manifests",
        ["organization_id", "application_context", "created_at"],
    )
    op.create_table(
        "pack_manifest_sources",
        sa.Column(
            "pack_version_id",
            sa.String(128),
            sa.ForeignKey("pack_manifests.pack_version_id"),
            primary_key=True,
        ),
        sa.Column(
            "source_version_id",
            sa.String(128),
            sa.ForeignKey("knowledge_source_versions.id"),
            primary_key=True,
        ),
    )
    op.create_table(
        "pack_policies",
        sa.Column("policy_id", sa.String(128), primary_key=True),
        sa.Column("policy_version", sa.Integer(), primary_key=True),
        sa.Column(
            "organization_id", sa.String(128), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.CheckConstraint("policy_version >= 1", name="ck_pack_policy_version"),
        sa.CheckConstraint("char_length(content_sha256) = 64", name="ck_pack_policy_hash"),
        sa.CheckConstraint("status IN ('approved','revoked')", name="ck_pack_policy_status"),
    )
    op.create_table(
        "pack_manifest_policies",
        sa.Column(
            "pack_version_id",
            sa.String(128),
            sa.ForeignKey("pack_manifests.pack_version_id"),
            primary_key=True,
        ),
        sa.Column("policy_id", sa.String(128), primary_key=True),
        sa.Column("policy_version", sa.Integer(), primary_key=True),
        sa.ForeignKeyConstraint(
            ["policy_id", "policy_version"],
            ["pack_policies.policy_id", "pack_policies.policy_version"],
        ),
    )
    op.create_table(
        "active_pack_contexts",
        sa.Column(
            "organization_id", sa.String(128), sa.ForeignKey("organizations.id"), primary_key=True
        ),
        sa.Column("application_context", sa.String(128), primary_key=True),
        sa.Column(
            "pack_version_id",
            sa.String(128),
            sa.ForeignKey("pack_manifests.pack_version_id"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("updated_by", sa.String(128), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("revision >= 1", name="ck_active_pack_revision"),
    )
    op.create_table(
        "pack_change_sets",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column(
            "organization_id", sa.String(128), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("application_context", sa.String(128), nullable=False),
        sa.Column(
            "previous_pack_version_id",
            sa.String(128),
            sa.ForeignKey("pack_manifests.pack_version_id"),
        ),
        sa.Column(
            "new_pack_version_id",
            sa.String(128),
            sa.ForeignKey("pack_manifests.pack_version_id"),
            nullable=False,
        ),
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_table(
        "pack_changes",
        sa.Column(
            "change_set_id", sa.String(128), sa.ForeignKey("pack_change_sets.id"), primary_key=True
        ),
        sa.Column("ordinal", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("ref_id", sa.String(128), nullable=False),
        sa.Column("previous_version", sa.Text()),
        sa.Column("new_version", sa.Text(), nullable=False),
        sa.CheckConstraint("ordinal >= 0", name="ck_pack_changes_ordinal"),
    )
    op.create_index(
        "ix_pack_changes_dependency", "pack_changes", ["kind", "ref_id", "previous_version"]
    )
    op.create_table(
        "dependency_targets",
        sa.Column(
            "organization_id", sa.String(128), sa.ForeignKey("organizations.id"), primary_key=True
        ),
        sa.Column("target_kind", sa.String(32), primary_key=True),
        sa.Column("target_id", sa.String(128), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("stale_change_set_id", sa.String(128)),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("revision >= 1", name="ck_dependency_target_revision"),
        sa.CheckConstraint("state IN ('current','stale')", name="ck_dependency_target_state"),
    )
    op.create_table(
        "dependency_target_refs",
        sa.Column("organization_id", sa.String(128), primary_key=True),
        sa.Column("target_kind", sa.String(32), primary_key=True),
        sa.Column("target_id", sa.String(128), primary_key=True),
        sa.Column("ordinal", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("ref_id", sa.String(128), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64)),
        sa.ForeignKeyConstraint(
            ["organization_id", "target_kind", "target_id"],
            [
                "dependency_targets.organization_id",
                "dependency_targets.target_kind",
                "dependency_targets.target_id",
            ],
        ),
        sa.CheckConstraint("ordinal >= 0", name="ck_dependency_target_refs_ordinal"),
    )
    op.create_index(
        "ix_dependency_target_refs_reverse",
        "dependency_target_refs",
        ["organization_id", "kind", "ref_id", "version"],
    )
    op.create_table(
        "invalidation_events",
        sa.Column(
            "change_set_id", sa.String(128), sa.ForeignKey("pack_change_sets.id"), primary_key=True
        ),
        sa.Column("target_kind", sa.String(32), primary_key=True),
        sa.Column("target_id", sa.String(128), primary_key=True),
        sa.Column("matched_dependencies_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )


def downgrade() -> None:
    for table in (
        "invalidation_events",
        "dependency_target_refs",
        "dependency_targets",
        "pack_changes",
        "pack_change_sets",
        "active_pack_contexts",
        "pack_manifest_policies",
        "pack_policies",
        "pack_manifest_sources",
        "pack_manifests",
    ):
        op.drop_table(table)
