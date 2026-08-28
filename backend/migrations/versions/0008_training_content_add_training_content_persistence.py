"""Додати версіонований навчальний контент і приватні метадані зображень.

Revision ID: 0008_training_content
Revises: 0007_menu_import_review
Create Date: 2026-08-28 13:10:21.345957
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_training_content"
down_revision: str | None = "0007_menu_import_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="pending_upload", nullable=False),
        sa.Column("object_key", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("upload_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name=op.f("ck_assets_mime_type_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('pending_upload', 'ready', 'failed', 'archived')",
            name=op.f("ck_assets_status_allowed"),
        ),
        sa.CheckConstraint("length(sha256) = 64", name=op.f("ck_assets_sha256_length")),
        sa.CheckConstraint(
            "size_bytes BETWEEN 1 AND 5242880", name=op.f("ck_assets_size_bytes_range")
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_assets_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_assets_location_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assets")),
        sa.UniqueConstraint("id", "organization_id", "location_id", name="uq_assets_scope"),
        sa.UniqueConstraint("object_key", name="uq_assets_object_key"),
    )
    op.create_index(
        "ix_assets_scope_status",
        "assets",
        ["organization_id", "location_id", "status"],
        unique=False,
    )
    op.create_index("ix_assets_sha256", "assets", ["sha256"], unique=False)
    op.create_table(
        "trainings",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_trainings_location_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trainings")),
        sa.UniqueConstraint("id", "organization_id", "location_id", name="uq_trainings_scope"),
        sa.UniqueConstraint("location_id", name="uq_trainings_location_id"),
    )
    op.create_index(
        op.f("ix_trainings_organization_id"), "trainings", ["organization_id"], unique=False
    )
    op.create_table(
        "training_modules",
        sa.Column("training_id", sa.UUID(), nullable=False),
        sa.Column("domain_type", sa.String(length=32), server_default="menu", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "domain_type IN ('menu')", name=op.f("ck_training_modules_domain_type_allowed")
        ),
        sa.ForeignKeyConstraint(
            ["training_id"],
            ["trainings.id"],
            name=op.f("fk_training_modules_training_id_trainings"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_modules")),
        sa.UniqueConstraint("id", "training_id", name="uq_training_modules_scope"),
        sa.UniqueConstraint("training_id", "domain_type", name="uq_training_modules_domain"),
    )
    op.create_index(
        op.f("ix_training_modules_training_id"), "training_modules", ["training_id"], unique=False
    )
    op.create_table(
        "training_versions",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("training_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'draft'"), nullable=False
        ),
        sa.Column("base_version_id", sa.UUID(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=False),
        sa.Column("published_by_user_id", sa.UUID(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(status = 'draft' AND published_by_user_id IS NULL "
            "AND published_at IS NULL AND archived_at IS NULL) OR "
            "(status = 'published' AND published_by_user_id IS NOT NULL "
            "AND published_at IS NOT NULL AND archived_at IS NULL) OR "
            "(status = 'archived' AND published_by_user_id IS NOT NULL "
            "AND published_at IS NOT NULL AND archived_at IS NOT NULL)",
            name=op.f("ck_training_versions_lifecycle_timestamps_match"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name=op.f("ck_training_versions_status_allowed"),
        ),
        sa.CheckConstraint("revision >= 0", name=op.f("ck_training_versions_revision_nonnegative")),
        sa.CheckConstraint(
            "version_number >= 1", name=op.f("ck_training_versions_version_number_positive")
        ),
        sa.ForeignKeyConstraint(
            ["base_version_id", "training_id", "organization_id", "location_id"],
            [
                "training_versions.id",
                "training_versions.training_id",
                "training_versions.organization_id",
                "training_versions.location_id",
            ],
            name="fk_training_versions_base_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_training_versions_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["published_by_user_id"],
            ["users.id"],
            name=op.f("fk_training_versions_published_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["training_id", "organization_id", "location_id"],
            ["trainings.id", "trainings.organization_id", "trainings.location_id"],
            name="fk_training_versions_training_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_versions")),
        sa.UniqueConstraint(
            "id", "training_id", "organization_id", "location_id", name="uq_training_versions_scope"
        ),
        sa.UniqueConstraint("training_id", "version_number", name="uq_training_versions_number"),
    )
    op.create_index(
        "ix_training_versions_current",
        "training_versions",
        ["training_id", "status", "version_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_training_versions_training_id"), "training_versions", ["training_id"], unique=False
    )
    op.create_index(
        "uq_training_versions_one_draft",
        "training_versions",
        ["training_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
    )
    op.create_index(
        "uq_training_versions_one_published",
        "training_versions",
        ["training_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
    )
    op.create_table(
        "lessons",
        sa.Column("training_module_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["training_module_id"],
            ["training_modules.id"],
            name=op.f("fk_lessons_training_module_id_training_modules"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lessons")),
        sa.UniqueConstraint("id", "training_module_id", name="uq_lessons_scope"),
    )
    op.create_index(
        op.f("ix_lessons_training_module_id"), "lessons", ["training_module_id"], unique=False
    )
    op.create_table(
        "training_module_versions",
        sa.Column("training_id", sa.UUID(), nullable=False),
        sa.Column("training_version_id", sa.UUID(), nullable=False),
        sa.Column("training_module_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "position >= 0", name=op.f("ck_training_module_versions_position_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["training_module_id", "training_id"],
            ["training_modules.id", "training_modules.training_id"],
            name="fk_tmv_module_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["training_version_id"],
            ["training_versions.id"],
            name=op.f("fk_training_module_versions_training_version_id_training_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_module_versions")),
        sa.UniqueConstraint("id", "training_version_id", name="uq_tmv_scope"),
        sa.UniqueConstraint("training_version_id", "position", name="uq_tmv_position"),
        sa.UniqueConstraint("training_version_id", "training_module_id", name="uq_tmv_identity"),
    )
    op.create_index(
        op.f("ix_training_module_versions_training_version_id"),
        "training_module_versions",
        ["training_version_id"],
        unique=False,
    )
    op.create_table(
        "training_version_menu_dependencies",
        sa.Column("training_version_id", sa.UUID(), nullable=False),
        sa.Column("menu_version_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["menu_version_id"],
            ["menu_versions.id"],
            name=op.f("fk_training_version_menu_dependencies_menu_version_id_menu_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["training_version_id"],
            ["training_versions.id"],
            name=op.f(
                "fk_training_version_menu_dependencies_training_version_id_training_versions"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_version_menu_dependencies")),
        sa.UniqueConstraint(
            "training_version_id", "menu_version_id", name="uq_tvmd_training_menu_version"
        ),
        sa.UniqueConstraint("training_version_id", name="uq_tvmd_training_version"),
    )
    op.create_index(
        op.f("ix_training_version_menu_dependencies_menu_version_id"),
        "training_version_menu_dependencies",
        ["menu_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_training_version_menu_dependencies_training_version_id"),
        "training_version_menu_dependencies",
        ["training_version_id"],
        unique=False,
    )
    op.create_table(
        "lesson_versions",
        sa.Column("training_module_version_id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes BETWEEN 1 AND 240",
            name=op.f("ck_lesson_versions_estimated_minutes_range"),
        ),
        sa.CheckConstraint("position >= 0", name=op.f("ck_lesson_versions_position_nonnegative")),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["lessons.id"],
            name=op.f("fk_lesson_versions_lesson_id_lessons"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["training_module_version_id"],
            ["training_module_versions.id"],
            name=op.f("fk_lesson_versions_training_module_version_id_training_module_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lesson_versions")),
        sa.UniqueConstraint("id", "training_module_version_id", name="uq_lesson_versions_scope"),
        sa.UniqueConstraint(
            "training_module_version_id", "lesson_id", name="uq_lesson_versions_identity"
        ),
        sa.UniqueConstraint(
            "training_module_version_id", "position", name="uq_lesson_versions_position"
        ),
    )
    op.create_index(
        op.f("ix_lesson_versions_training_module_version_id"),
        "lesson_versions",
        ["training_module_version_id"],
        unique=False,
    )
    op.create_table(
        "training_module_translations",
        sa.Column("training_module_version_id", sa.UUID(), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="ready", nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "locale IN ('uk', 'en')", name=op.f("ck_training_module_translations_locale_allowed")
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'ready', 'failed', 'stale')",
            name=op.f("ck_training_module_translations_status_allowed"),
        ),
        sa.CheckConstraint(
            "description IS NULL OR length(description) <= 2000",
            name=op.f("ck_training_module_translations_description_length"),
        ),
        sa.CheckConstraint(
            "length(btrim(title)) BETWEEN 1 AND 200",
            name=op.f("ck_training_module_translations_title_length"),
        ),
        sa.CheckConstraint(
            "source_revision >= 0",
            name=op.f("ck_training_module_translations_source_revision_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["training_module_version_id"],
            ["training_module_versions.id"],
            name=op.f(
                "fk_training_module_translations_training_module_version_id_training_module_versions"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_module_translations")),
        sa.UniqueConstraint("training_module_version_id", "locale", name="uq_tmt_locale"),
    )
    op.create_index(
        op.f("ix_training_module_translations_training_module_version_id"),
        "training_module_translations",
        ["training_module_version_id"],
        unique=False,
    )
    op.create_table(
        "lesson_content_blocks",
        sa.Column("lesson_version_id", sa.UUID(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("menu_item_id", sa.UUID(), nullable=True),
        sa.Column("asset_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(type = 'menu_item_card' AND menu_item_id IS NOT NULL "
            "AND asset_id IS NULL) OR "
            "(type = 'image' AND asset_id IS NOT NULL AND menu_item_id IS NULL) OR "
            "(type NOT IN ('menu_item_card', 'image') AND menu_item_id IS NULL "
            "AND asset_id IS NULL)",
            name=op.f("ck_lesson_content_blocks_relational_payload_matches_type"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'", name=op.f("ck_lesson_content_blocks_payload_object")
        ),
        sa.CheckConstraint(
            "type IN ('heading', 'text', 'list', 'callout', 'menu_item_card', "
            "'image', 'external_video')",
            name=op.f("ck_lesson_content_blocks_type_allowed"),
        ),
        sa.CheckConstraint(
            "position >= 0", name=op.f("ck_lesson_content_blocks_position_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            name=op.f("fk_lesson_content_blocks_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_version_id"],
            ["lesson_versions.id"],
            name=op.f("fk_lesson_content_blocks_lesson_version_id_lesson_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id"],
            ["menu_items.id"],
            name=op.f("fk_lesson_content_blocks_menu_item_id_menu_items"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lesson_content_blocks")),
        sa.UniqueConstraint("lesson_version_id", "position", name="uq_lcb_position"),
    )
    op.create_index(
        op.f("ix_lesson_content_blocks_lesson_version_id"),
        "lesson_content_blocks",
        ["lesson_version_id"],
        unique=False,
    )
    op.create_table(
        "lesson_translations",
        sa.Column("lesson_version_id", sa.UUID(), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="ready", nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "locale IN ('uk', 'en')", name=op.f("ck_lesson_translations_locale_allowed")
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'ready', 'failed', 'stale')",
            name=op.f("ck_lesson_translations_status_allowed"),
        ),
        sa.CheckConstraint(
            "description IS NULL OR length(description) <= 2000",
            name=op.f("ck_lesson_translations_description_length"),
        ),
        sa.CheckConstraint(
            "length(btrim(title)) BETWEEN 1 AND 200",
            name=op.f("ck_lesson_translations_title_length"),
        ),
        sa.CheckConstraint(
            "source_revision >= 0", name=op.f("ck_lesson_translations_source_revision_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["lesson_version_id"],
            ["lesson_versions.id"],
            name=op.f("fk_lesson_translations_lesson_version_id_lesson_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lesson_translations")),
        sa.UniqueConstraint("lesson_version_id", "locale", name="uq_lesson_translations_locale"),
    )
    op.create_index(
        op.f("ix_lesson_translations_lesson_version_id"),
        "lesson_translations",
        ["lesson_version_id"],
        unique=False,
    )
    op.create_table(
        "lesson_content_block_translations",
        sa.Column("lesson_content_block_id", sa.UUID(), nullable=False),
        sa.Column("locale", sa.String(length=8), server_default="en", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("translated_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "jsonb_typeof(translated_payload) = 'object'",
            name=op.f("ck_lesson_content_block_translations_payload_object"),
        ),
        sa.CheckConstraint(
            "locale IN ('en')", name=op.f("ck_lesson_content_block_translations_locale_allowed")
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'ready', 'failed', 'stale')",
            name=op.f("ck_lesson_content_block_translations_status_allowed"),
        ),
        sa.CheckConstraint(
            "source_revision >= 0",
            name=op.f("ck_lesson_content_block_translations_source_rev_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["lesson_content_block_id"],
            ["lesson_content_blocks.id"],
            name=op.f(
                "fk_lesson_content_block_translations_lesson_content_block_id_lesson_content_blocks"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_lesson_content_block_translations")),
        sa.UniqueConstraint("lesson_content_block_id", "locale", name="uq_lcbt_locale"),
    )
    op.create_index(
        op.f("ix_lesson_content_block_translations_lesson_content_block_id"),
        "lesson_content_block_translations",
        ["lesson_content_block_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_lesson_content_block_translations_lesson_content_block_id"),
        table_name="lesson_content_block_translations",
    )
    op.drop_table("lesson_content_block_translations")
    op.drop_index(
        op.f("ix_lesson_translations_lesson_version_id"), table_name="lesson_translations"
    )
    op.drop_table("lesson_translations")
    op.drop_index(
        op.f("ix_lesson_content_blocks_lesson_version_id"), table_name="lesson_content_blocks"
    )
    op.drop_table("lesson_content_blocks")
    op.drop_index(
        op.f("ix_training_module_translations_training_module_version_id"),
        table_name="training_module_translations",
    )
    op.drop_table("training_module_translations")
    op.drop_index(
        op.f("ix_lesson_versions_training_module_version_id"), table_name="lesson_versions"
    )
    op.drop_table("lesson_versions")
    op.drop_index(
        op.f("ix_training_version_menu_dependencies_training_version_id"),
        table_name="training_version_menu_dependencies",
    )
    op.drop_index(
        op.f("ix_training_version_menu_dependencies_menu_version_id"),
        table_name="training_version_menu_dependencies",
    )
    op.drop_table("training_version_menu_dependencies")
    op.drop_index(
        op.f("ix_training_module_versions_training_version_id"),
        table_name="training_module_versions",
    )
    op.drop_table("training_module_versions")
    op.drop_index(op.f("ix_lessons_training_module_id"), table_name="lessons")
    op.drop_table("lessons")
    op.drop_index(
        "uq_training_versions_one_published",
        table_name="training_versions",
        postgresql_where=sa.text("status = 'published'"),
    )
    op.drop_index(
        "uq_training_versions_one_draft",
        table_name="training_versions",
        postgresql_where=sa.text("status = 'draft'"),
    )
    op.drop_index(op.f("ix_training_versions_training_id"), table_name="training_versions")
    op.drop_index("ix_training_versions_current", table_name="training_versions")
    op.drop_table("training_versions")
    op.drop_index(op.f("ix_training_modules_training_id"), table_name="training_modules")
    op.drop_table("training_modules")
    op.drop_index(op.f("ix_trainings_organization_id"), table_name="trainings")
    op.drop_table("trainings")
    op.drop_index("ix_assets_sha256", table_name="assets")
    op.drop_index("ix_assets_scope_status", table_name="assets")
    op.drop_table("assets")
