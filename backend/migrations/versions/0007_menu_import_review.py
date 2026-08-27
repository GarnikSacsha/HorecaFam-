"""Add durable Menu import review records.

Revision ID: 0007_menu_import_review
Revises: 0006_menu_source_of_truth
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_menu_import_review"
down_revision: str | None = "0006_menu_source_of_truth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid() -> postgresql.UUID:
    return postgresql.UUID(as_uuid=True)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "menu_imports",
        sa.Column("organization_id", _uuid(), nullable=False),
        sa.Column("location_id", _uuid(), nullable=False),
        sa.Column("menu_id", _uuid(), nullable=False),
        sa.Column("base_menu_version_id", _uuid(), nullable=True),
        sa.Column("confirmed_menu_version_id", _uuid(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="uploaded"),
        sa.Column("review_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=True),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column("source_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("section_count", sa.Integer(), nullable=False),
        sa.Column("category_count", sa.Integer(), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.Column("added_count", sa.Integer(), nullable=False),
        sa.Column("changed_count", sa.Integer(), nullable=False),
        sa.Column("removed_count", sa.Integer(), nullable=False),
        sa.Column("unchanged_count", sa.Integer(), nullable=False),
        sa.Column("blocker_count", sa.Integer(), nullable=False),
        sa.Column("review_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("created_by_user_id", _uuid(), nullable=False),
        sa.Column("confirmed_by_user_id", _uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("id", _uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "status IN ('uploaded', 'processing', 'ready_for_review', "
            "'confirmed', 'failed', 'stale')",
            name=op.f("ck_menu_imports_status_allowed"),
        ),
        sa.CheckConstraint(
            "review_revision >= 0",
            name=op.f("ck_menu_imports_review_revision_nonnegative"),
        ),
        sa.CheckConstraint(
            "length(btrim(source_filename)) > 0",
            name=op.f("ck_menu_imports_filename_not_blank"),
        ),
        sa.CheckConstraint(
            "length(source_checksum) = 64",
            name=op.f("ck_menu_imports_checksum_sha256_length"),
        ),
        *[
            sa.CheckConstraint(
                f"{column} >= 0",
                name=op.f(f"ck_menu_imports_{column}_nonnegative"),
            )
            for column in (
                "section_count",
                "category_count",
                "item_count",
                "added_count",
                "changed_count",
                "removed_count",
                "unchanged_count",
                "blocker_count",
                "review_count",
                "warning_count",
            )
        ],
        sa.ForeignKeyConstraint(
            ["menu_id", "organization_id", "location_id"],
            ["menus.id", "menus.organization_id", "menus.location_id"],
            name=op.f("fk_menu_imports_menu_scope"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["base_menu_version_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_versions.id",
                "menu_versions.menu_id",
                "menu_versions.organization_id",
                "menu_versions.location_id",
            ],
            name=op.f("fk_menu_imports_base_scope"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_menu_version_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_versions.id",
                "menu_versions.menu_id",
                "menu_versions.organization_id",
                "menu_versions.location_id",
            ],
            name=op.f("fk_menu_imports_confirmed_scope"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_menu_imports_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"],
            ["users.id"],
            name=op.f("fk_menu_imports_confirmed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_imports")),
        sa.UniqueConstraint(
            "id",
            "menu_id",
            "organization_id",
            "location_id",
            name=op.f("uq_menu_imports_scope"),
        ),
    )
    op.create_index(op.f("ix_menu_imports_menu_id"), "menu_imports", ["menu_id"])
    op.create_index(
        "uq_menu_imports_checksum_with_base",
        "menu_imports",
        ["menu_id", "base_menu_version_id", "source_checksum"],
        unique=True,
        postgresql_where=sa.text("base_menu_version_id IS NOT NULL"),
    )
    op.create_index(
        "uq_menu_imports_checksum_without_base",
        "menu_imports",
        ["menu_id", "source_checksum"],
        unique=True,
        postgresql_where=sa.text("base_menu_version_id IS NULL"),
    )

    op.create_table(
        "menu_import_findings",
        sa.Column("organization_id", _uuid(), nullable=False),
        sa.Column("location_id", _uuid(), nullable=False),
        sa.Column("menu_id", _uuid(), nullable=False),
        sa.Column("menu_import_id", _uuid(), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("source_key", sa.String(length=200), nullable=True),
        sa.Column("message_code", sa.String(length=100), nullable=False),
        sa.Column(
            "message_parameters",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "allowed_actions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "resolution_status",
            sa.String(length=16),
            nullable=False,
            server_default="unresolved",
        ),
        sa.Column("resolution_action", sa.String(length=32), nullable=True),
        sa.Column("target_entity_id", _uuid(), nullable=True),
        sa.Column("resolution_comment", sa.String(length=1000), nullable=True),
        sa.Column("resolved_by_user_id", _uuid(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", _uuid(), nullable=False),
        *_timestamps(),
        sa.CheckConstraint(
            "severity IN ('blocker', 'requires_review', 'warning')",
            name=op.f("ck_menu_import_findings_severity_allowed"),
        ),
        sa.CheckConstraint(
            "resolution_status IN ('unresolved', 'resolved')",
            name=op.f("ck_menu_import_findings_resolution_status_allowed"),
        ),
        sa.CheckConstraint(
            "resolution_action IS NULL OR resolution_action IN "
            "('confirm_legitimate', 'map_existing', 'confirm_removal', "
            "'confirm_critical_change', 'exclude_source_record')",
            name=op.f("ck_menu_import_findings_resolution_action_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(allowed_actions) = 'array'",
            name=op.f("ck_menu_import_findings_allowed_actions_array"),
        ),
        sa.CheckConstraint(
            "(resolution_status = 'unresolved' AND resolution_action IS NULL "
            "AND resolved_by_user_id IS NULL AND resolved_at IS NULL) OR "
            "(resolution_status = 'resolved' AND resolution_action IS NOT NULL "
            "AND resolved_by_user_id IS NOT NULL AND resolved_at IS NOT NULL)",
            name=op.f("ck_menu_import_findings_resolution_fields_match"),
        ),
        sa.ForeignKeyConstraint(
            ["menu_import_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_imports.id",
                "menu_imports.menu_id",
                "menu_imports.organization_id",
                "menu_imports.location_id",
            ],
            name=op.f("fk_menu_import_findings_import_scope"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"],
            ["users.id"],
            name=op.f("fk_menu_import_findings_resolved_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_import_findings")),
        sa.UniqueConstraint(
            "id",
            "menu_import_id",
            "menu_id",
            "organization_id",
            "location_id",
            name=op.f("uq_menu_import_findings_scope"),
        ),
    )
    op.create_index(
        op.f("ix_menu_import_findings_menu_import_id"),
        "menu_import_findings",
        ["menu_import_id"],
    )
    op.create_index(
        "ix_menu_import_findings_review",
        "menu_import_findings",
        ["menu_import_id", "severity", "resolution_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_menu_import_findings_review", table_name="menu_import_findings")
    op.drop_index(
        op.f("ix_menu_import_findings_menu_import_id"),
        table_name="menu_import_findings",
    )
    op.drop_table("menu_import_findings")
    op.drop_index("uq_menu_imports_checksum_without_base", table_name="menu_imports")
    op.drop_index("uq_menu_imports_checksum_with_base", table_name="menu_imports")
    op.drop_index(op.f("ix_menu_imports_menu_id"), table_name="menu_imports")
    op.drop_table("menu_imports")
