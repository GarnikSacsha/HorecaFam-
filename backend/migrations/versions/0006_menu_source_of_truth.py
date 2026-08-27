"""Додати версіоноване джерело правди меню без імпорту та публікаційних сервісів.

Revision ID: 0006_menu_source_of_truth
Revises: 0005_invitation_email_outbox
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_menu_source_of_truth"
down_revision: str | None = "0005_invitation_email_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _id_column() -> sa.Column:
    return sa.Column("id", sa.Uuid(), nullable=False)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _stable_identity_table(table_name: str, foreign_key_name: str, scope_name: str) -> None:
    op.create_table(
        table_name,
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("menu_id", sa.Uuid(), nullable=False),
        sa.Column("stable_code", sa.String(100)),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        _id_column(),
        *_timestamps(),
        sa.CheckConstraint(
            "stable_code IS NULL OR "
            "(length(btrim(stable_code)) > 0 AND stable_code = lower(btrim(stable_code)))",
            name=op.f(f"ck_{table_name}_stable_code_normalized"),
        ),
        sa.CheckConstraint(
            "retired_at IS NULL OR retired_at >= created_at",
            name=op.f(f"ck_{table_name}_retired_after_create"),
        ),
        sa.ForeignKeyConstraint(
            ["menu_id", "organization_id", "location_id"],
            ["menus.id", "menus.organization_id", "menus.location_id"],
            name=foreign_key_name,
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table_name}")),
        sa.UniqueConstraint("id", "menu_id", "organization_id", "location_id", name=scope_name),
    )
    op.create_index(op.f(f"ix_{table_name}_menu_id"), table_name, ["menu_id"])
    op.create_index(
        f"uq_{table_name}_stable_code",
        table_name,
        ["menu_id", "stable_code"],
        unique=True,
        postgresql_where=sa.text("stable_code IS NOT NULL"),
    )


def _translation_constraints(table_name: str) -> list[sa.CheckConstraint]:
    return [
        sa.CheckConstraint(
            "locale IN ('uk', 'en')",
            name=op.f(f"ck_{table_name}_locale_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'needs_review', 'ready')",
            name=op.f(f"ck_{table_name}_status_allowed"),
        ),
        sa.CheckConstraint(
            "length(btrim(name)) > 0",
            name=op.f(f"ck_{table_name}_name_not_blank"),
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "menus",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        _id_column(),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_menus_location_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menus")),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            "location_id",
            name="uq_menus_id_organization_location",
        ),
        sa.UniqueConstraint("location_id", name="uq_menus_location_id"),
    )
    op.create_index(op.f("ix_menus_organization_id"), "menus", ["organization_id"])

    _stable_identity_table("menu_sections", "fk_menu_sections_menu_scope", "uq_menu_sections_scope")
    _stable_identity_table(
        "menu_categories", "fk_menu_categories_menu_scope", "uq_menu_categories_scope"
    )
    _stable_identity_table("menu_items", "fk_menu_items_menu_scope", "uq_menu_items_scope")
    _stable_identity_table(
        "menu_components", "fk_menu_components_menu_scope", "uq_menu_components_scope"
    )

    op.create_table(
        "allergens",
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("label_uk", sa.String(200), nullable=False),
        sa.Column("label_en", sa.String(200)),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        _id_column(),
        *_timestamps(),
        sa.CheckConstraint("length(btrim(code)) > 0", name=op.f("ck_allergens_code_not_blank")),
        sa.CheckConstraint("code = lower(btrim(code))", name=op.f("ck_allergens_code_normalized")),
        sa.CheckConstraint(
            "length(btrim(label_uk)) > 0", name=op.f("ck_allergens_label_uk_not_blank")
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')", name=op.f("ck_allergens_status_allowed")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_allergens")),
        sa.UniqueConstraint("code", name=op.f("uq_allergens_code")),
    )

    op.create_table(
        "menu_versions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("menu_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="draft", nullable=False),
        sa.Column("base_version_id", sa.Uuid()),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("published_by_user_id", sa.Uuid()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        _id_column(),
        *_timestamps(),
        sa.CheckConstraint(
            "version_number >= 1", name=op.f("ck_menu_versions_version_number_positive")
        ),
        sa.CheckConstraint("revision >= 0", name=op.f("ck_menu_versions_revision_nonnegative")),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name=op.f("ck_menu_versions_status_allowed"),
        ),
        sa.CheckConstraint(
            "(status = 'draft' AND published_by_user_id IS NULL "
            "AND published_at IS NULL AND archived_at IS NULL) OR "
            "(status = 'published' AND published_by_user_id IS NOT NULL "
            "AND published_at IS NOT NULL AND archived_at IS NULL) OR "
            "(status = 'archived' AND published_by_user_id IS NOT NULL "
            "AND published_at IS NOT NULL AND archived_at IS NOT NULL)",
            name=op.f("ck_menu_versions_lifecycle_timestamps_match"),
        ),
        sa.ForeignKeyConstraint(
            ["base_version_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_versions.id",
                "menu_versions.menu_id",
                "menu_versions.organization_id",
                "menu_versions.location_id",
            ],
            name="fk_menu_versions_base_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("fk_menu_versions_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["menu_id", "organization_id", "location_id"],
            ["menus.id", "menus.organization_id", "menus.location_id"],
            name="fk_menu_versions_menu_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["published_by_user_id"],
            ["users.id"],
            name=op.f("fk_menu_versions_published_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_versions")),
        sa.UniqueConstraint(
            "id", "menu_id", "organization_id", "location_id", name="uq_menu_versions_scope"
        ),
        sa.UniqueConstraint("menu_id", "version_number", name="uq_menu_versions_number"),
    )
    op.create_index(op.f("ix_menu_versions_menu_id"), "menu_versions", ["menu_id"])
    op.create_index(
        "uq_menu_versions_one_draft",
        "menu_versions",
        ["menu_id"],
        unique=True,
        postgresql_where=sa.text("status = 'draft'"),
    )
    op.create_index(
        "uq_menu_versions_one_published",
        "menu_versions",
        ["menu_id"],
        unique=True,
        postgresql_where=sa.text("status = 'published'"),
    )

    op.create_table(
        "menu_version_sections",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("menu_id", sa.Uuid(), nullable=False),
        sa.Column("menu_version_id", sa.Uuid(), nullable=False),
        sa.Column("menu_section_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        _id_column(),
        *_timestamps(),
        sa.CheckConstraint(
            "position >= 0", name=op.f("ck_menu_version_sections_position_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["menu_section_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_sections.id",
                "menu_sections.menu_id",
                "menu_sections.organization_id",
                "menu_sections.location_id",
            ],
            name="fk_mv_sections_identity_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["menu_version_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_versions.id",
                "menu_versions.menu_id",
                "menu_versions.organization_id",
                "menu_versions.location_id",
            ],
            name="fk_mv_sections_version_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_version_sections")),
        sa.UniqueConstraint(
            "id",
            "menu_version_id",
            "menu_id",
            "organization_id",
            "location_id",
            name="uq_menu_version_sections_scope",
        ),
        sa.UniqueConstraint("menu_version_id", "menu_section_id", name="uq_mv_sections_identity"),
        sa.UniqueConstraint("menu_version_id", "position", name="uq_mv_sections_position"),
    )
    op.create_index(
        op.f("ix_menu_version_sections_menu_version_id"),
        "menu_version_sections",
        ["menu_version_id"],
    )

    op.create_table(
        "menu_version_categories",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("menu_id", sa.Uuid(), nullable=False),
        sa.Column("menu_version_id", sa.Uuid(), nullable=False),
        sa.Column("menu_category_id", sa.Uuid(), nullable=False),
        sa.Column("menu_version_section_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        _id_column(),
        *_timestamps(),
        sa.CheckConstraint(
            "position >= 0", name=op.f("ck_menu_version_categories_position_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["menu_category_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_categories.id",
                "menu_categories.menu_id",
                "menu_categories.organization_id",
                "menu_categories.location_id",
            ],
            name="fk_mv_categories_identity_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "menu_version_section_id",
                "menu_version_id",
                "menu_id",
                "organization_id",
                "location_id",
            ],
            [
                "menu_version_sections.id",
                "menu_version_sections.menu_version_id",
                "menu_version_sections.menu_id",
                "menu_version_sections.organization_id",
                "menu_version_sections.location_id",
            ],
            name="fk_mv_categories_section_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["menu_version_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_versions.id",
                "menu_versions.menu_id",
                "menu_versions.organization_id",
                "menu_versions.location_id",
            ],
            name="fk_mv_categories_version_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_version_categories")),
        sa.UniqueConstraint(
            "id",
            "menu_version_id",
            "menu_id",
            "organization_id",
            "location_id",
            name="uq_menu_version_categories_scope",
        ),
        sa.UniqueConstraint(
            "menu_version_id", "menu_category_id", name="uq_mv_categories_identity"
        ),
        sa.UniqueConstraint(
            "menu_version_section_id", "position", name="uq_mv_categories_position"
        ),
    )
    op.create_index(
        op.f("ix_menu_version_categories_menu_version_id"),
        "menu_version_categories",
        ["menu_version_id"],
    )

    op.create_table(
        "menu_component_versions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("menu_id", sa.Uuid(), nullable=False),
        sa.Column("menu_version_id", sa.Uuid(), nullable=False),
        sa.Column("menu_component_id", sa.Uuid(), nullable=False),
        _id_column(),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["menu_component_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_components.id",
                "menu_components.menu_id",
                "menu_components.organization_id",
                "menu_components.location_id",
            ],
            name="fk_menu_component_versions_identity_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["menu_version_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_versions.id",
                "menu_versions.menu_id",
                "menu_versions.organization_id",
                "menu_versions.location_id",
            ],
            name="fk_menu_component_versions_version_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_component_versions")),
        sa.UniqueConstraint(
            "id",
            "menu_version_id",
            "menu_id",
            "organization_id",
            "location_id",
            name="uq_menu_component_versions_scope",
        ),
        sa.UniqueConstraint("menu_version_id", "menu_component_id", name="uq_mc_versions_identity"),
    )
    op.create_index(
        op.f("ix_menu_component_versions_menu_version_id"),
        "menu_component_versions",
        ["menu_version_id"],
    )

    op.create_table(
        "menu_item_versions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("menu_id", sa.Uuid(), nullable=False),
        sa.Column("menu_version_id", sa.Uuid(), nullable=False),
        sa.Column("menu_item_id", sa.Uuid(), nullable=False),
        sa.Column("menu_version_category_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("availability", sa.String(32), server_default="available", nullable=False),
        sa.Column("price_minor", sa.Integer()),
        sa.Column("currency", sa.String(3), server_default="UAH", nullable=False),
        sa.Column("component_data_status", sa.String(24), server_default="unknown", nullable=False),
        sa.Column("allergen_data_status", sa.String(24), server_default="unknown", nullable=False),
        sa.Column("source_kind", sa.String(16), server_default="manual", nullable=False),
        sa.Column("source_reference", sa.String(500)),
        sa.Column("source_item_key", sa.String(200)),
        sa.Column("verified_by_user_id", sa.Uuid()),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        _id_column(),
        *_timestamps(),
        sa.CheckConstraint(
            "position >= 0", name=op.f("ck_menu_item_versions_position_nonnegative")
        ),
        sa.CheckConstraint(
            "availability IN ('available', 'temporarily_unavailable', 'seasonal', 'discontinued')",
            name=op.f("ck_menu_item_versions_availability_allowed"),
        ),
        sa.CheckConstraint(
            "price_minor IS NULL OR price_minor >= 0",
            name=op.f("ck_menu_item_versions_price_nonnegative"),
        ),
        sa.CheckConstraint(
            "currency ~ '^[A-Z]{3}$'",
            name=op.f("ck_menu_item_versions_currency_iso_format"),
        ),
        sa.CheckConstraint(
            "component_data_status IN ('unknown', 'confirmed_none', 'confirmed_present')",
            name=op.f("ck_menu_item_versions_component_status_allowed"),
        ),
        sa.CheckConstraint(
            "allergen_data_status IN ('unknown', 'confirmed_none', 'confirmed_present')",
            name=op.f("ck_menu_item_versions_allergen_status_allowed"),
        ),
        sa.CheckConstraint(
            "source_kind IN ('manual', 'json_import')",
            name=op.f("ck_menu_item_versions_source_kind_allowed"),
        ),
        sa.CheckConstraint(
            "source_reference IS NULL OR length(btrim(source_reference)) > 0",
            name=op.f("ck_menu_item_versions_source_reference_not_blank"),
        ),
        sa.CheckConstraint(
            "source_item_key IS NULL OR length(btrim(source_item_key)) > 0",
            name=op.f("ck_menu_item_versions_source_item_key_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_items.id",
                "menu_items.menu_id",
                "menu_items.organization_id",
                "menu_items.location_id",
            ],
            name="fk_menu_item_versions_identity_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "menu_version_category_id",
                "menu_version_id",
                "menu_id",
                "organization_id",
                "location_id",
            ],
            [
                "menu_version_categories.id",
                "menu_version_categories.menu_version_id",
                "menu_version_categories.menu_id",
                "menu_version_categories.organization_id",
                "menu_version_categories.location_id",
            ],
            name="fk_menu_item_versions_category_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["menu_version_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_versions.id",
                "menu_versions.menu_id",
                "menu_versions.organization_id",
                "menu_versions.location_id",
            ],
            name="fk_menu_item_versions_version_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["verified_by_user_id"],
            ["users.id"],
            name=op.f("fk_menu_item_versions_verified_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_item_versions")),
        sa.UniqueConstraint(
            "id",
            "menu_version_id",
            "menu_id",
            "organization_id",
            "location_id",
            name="uq_menu_item_versions_scope",
        ),
        sa.UniqueConstraint(
            "menu_version_category_id", "position", name="uq_menu_item_versions_position"
        ),
        sa.UniqueConstraint(
            "menu_version_id", "menu_item_id", name="uq_menu_item_versions_identity"
        ),
    )
    op.create_index(
        "ix_menu_item_versions_lookup",
        "menu_item_versions",
        ["menu_version_id", "menu_version_category_id", "availability", "position"],
    )

    op.create_table(
        "menu_version_section_translations",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("menu_id", sa.Uuid(), nullable=False),
        sa.Column("menu_version_id", sa.Uuid(), nullable=False),
        sa.Column("menu_version_section_id", sa.Uuid(), nullable=False),
        sa.Column("locale", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), server_default="draft", nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        _id_column(),
        *_timestamps(),
        *_translation_constraints("menu_version_section_translations"),
        sa.ForeignKeyConstraint(
            [
                "menu_version_section_id",
                "menu_version_id",
                "menu_id",
                "organization_id",
                "location_id",
            ],
            [
                "menu_version_sections.id",
                "menu_version_sections.menu_version_id",
                "menu_version_sections.menu_id",
                "menu_version_sections.organization_id",
                "menu_version_sections.location_id",
            ],
            name="fk_mv_section_translations_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_version_section_translations")),
        sa.UniqueConstraint(
            "menu_version_section_id", "locale", name="uq_mv_section_translation_locale"
        ),
    )

    op.create_table(
        "menu_version_category_translations",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("menu_id", sa.Uuid(), nullable=False),
        sa.Column("menu_version_id", sa.Uuid(), nullable=False),
        sa.Column("menu_version_category_id", sa.Uuid(), nullable=False),
        sa.Column("locale", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), server_default="draft", nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        _id_column(),
        *_timestamps(),
        *_translation_constraints("menu_version_category_translations"),
        sa.ForeignKeyConstraint(
            [
                "menu_version_category_id",
                "menu_version_id",
                "menu_id",
                "organization_id",
                "location_id",
            ],
            [
                "menu_version_categories.id",
                "menu_version_categories.menu_version_id",
                "menu_version_categories.menu_id",
                "menu_version_categories.organization_id",
                "menu_version_categories.location_id",
            ],
            name="fk_mv_category_translations_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_version_category_translations")),
        sa.UniqueConstraint(
            "menu_version_category_id", "locale", name="uq_mv_category_translation_locale"
        ),
    )

    op.create_table(
        "menu_item_version_translations",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("menu_id", sa.Uuid(), nullable=False),
        sa.Column("menu_version_id", sa.Uuid(), nullable=False),
        sa.Column("menu_item_version_id", sa.Uuid(), nullable=False),
        sa.Column("locale", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), server_default="draft", nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        _id_column(),
        *_timestamps(),
        *_translation_constraints("menu_item_version_translations"),
        sa.ForeignKeyConstraint(
            [
                "menu_item_version_id",
                "menu_version_id",
                "menu_id",
                "organization_id",
                "location_id",
            ],
            [
                "menu_item_versions.id",
                "menu_item_versions.menu_version_id",
                "menu_item_versions.menu_id",
                "menu_item_versions.organization_id",
                "menu_item_versions.location_id",
            ],
            name="fk_menu_item_translations_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_item_version_translations")),
        sa.UniqueConstraint(
            "menu_item_version_id", "locale", name="uq_menu_item_translation_locale"
        ),
    )
    op.create_index(
        "ix_menu_item_translation_search",
        "menu_item_version_translations",
        ["locale", sa.text("lower(name)")],
    )

    op.create_table(
        "menu_component_version_translations",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("menu_id", sa.Uuid(), nullable=False),
        sa.Column("menu_version_id", sa.Uuid(), nullable=False),
        sa.Column("menu_component_version_id", sa.Uuid(), nullable=False),
        sa.Column("locale", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), server_default="draft", nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        _id_column(),
        *_timestamps(),
        *_translation_constraints("menu_component_version_translations"),
        sa.ForeignKeyConstraint(
            [
                "menu_component_version_id",
                "menu_version_id",
                "menu_id",
                "organization_id",
                "location_id",
            ],
            [
                "menu_component_versions.id",
                "menu_component_versions.menu_version_id",
                "menu_component_versions.menu_id",
                "menu_component_versions.organization_id",
                "menu_component_versions.location_id",
            ],
            name="fk_mc_translations_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_component_version_translations")),
        sa.UniqueConstraint("menu_component_version_id", "locale", name="uq_mc_translation_locale"),
    )
    op.create_index(
        "ix_menu_component_translation_search",
        "menu_component_version_translations",
        ["locale", sa.text("lower(name)")],
    )

    op.create_table(
        "menu_item_version_components",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("menu_id", sa.Uuid(), nullable=False),
        sa.Column("menu_version_id", sa.Uuid(), nullable=False),
        sa.Column("menu_item_version_id", sa.Uuid(), nullable=False),
        sa.Column("menu_component_version_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("optional", sa.Boolean()),
        sa.Column("source_kind", sa.String(16), server_default="manual", nullable=False),
        sa.Column("source_reference", sa.String(500)),
        sa.Column("source_item_key", sa.String(200)),
        sa.Column("verified_by_user_id", sa.Uuid()),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        _id_column(),
        *_timestamps(),
        sa.CheckConstraint(
            "position >= 0", name=op.f("ck_menu_item_version_components_position_nonnegative")
        ),
        sa.CheckConstraint(
            "source_kind IN ('manual', 'json_import')",
            name=op.f("ck_menu_item_version_components_source_kind_allowed"),
        ),
        sa.CheckConstraint(
            "source_reference IS NULL OR length(btrim(source_reference)) > 0",
            name=op.f("ck_menu_item_version_components_source_reference_not_blank"),
        ),
        sa.CheckConstraint(
            "source_item_key IS NULL OR length(btrim(source_item_key)) > 0",
            name=op.f("ck_menu_item_version_components_source_item_key_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            [
                "menu_component_version_id",
                "menu_version_id",
                "menu_id",
                "organization_id",
                "location_id",
            ],
            [
                "menu_component_versions.id",
                "menu_component_versions.menu_version_id",
                "menu_component_versions.menu_id",
                "menu_component_versions.organization_id",
                "menu_component_versions.location_id",
            ],
            name="fk_menu_item_components_component_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "menu_item_version_id",
                "menu_version_id",
                "menu_id",
                "organization_id",
                "location_id",
            ],
            [
                "menu_item_versions.id",
                "menu_item_versions.menu_version_id",
                "menu_item_versions.menu_id",
                "menu_item_versions.organization_id",
                "menu_item_versions.location_id",
            ],
            name="fk_menu_item_components_item_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["verified_by_user_id"],
            ["users.id"],
            name=op.f("fk_menu_item_version_components_verified_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_item_version_components")),
        sa.UniqueConstraint(
            "menu_item_version_id", "menu_component_version_id", name="uq_menu_item_component"
        ),
        sa.UniqueConstraint(
            "menu_item_version_id", "position", name="uq_menu_item_component_position"
        ),
    )

    op.create_table(
        "menu_item_version_allergens",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("menu_id", sa.Uuid(), nullable=False),
        sa.Column("menu_version_id", sa.Uuid(), nullable=False),
        sa.Column("menu_item_version_id", sa.Uuid(), nullable=False),
        sa.Column("allergen_id", sa.Uuid(), nullable=False),
        sa.Column("source_kind", sa.String(16), server_default="manual", nullable=False),
        sa.Column("source_reference", sa.String(500)),
        sa.Column("source_item_key", sa.String(200)),
        sa.Column("verified_by_user_id", sa.Uuid()),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        _id_column(),
        *_timestamps(),
        sa.CheckConstraint(
            "source_kind IN ('manual', 'json_import')",
            name=op.f("ck_menu_item_version_allergens_source_kind_allowed"),
        ),
        sa.CheckConstraint(
            "source_reference IS NULL OR length(btrim(source_reference)) > 0",
            name=op.f("ck_menu_item_version_allergens_source_reference_not_blank"),
        ),
        sa.CheckConstraint(
            "source_item_key IS NULL OR length(btrim(source_item_key)) > 0",
            name=op.f("ck_menu_item_version_allergens_source_item_key_not_blank"),
        ),
        sa.ForeignKeyConstraint(
            ["allergen_id"],
            ["allergens.id"],
            name=op.f("fk_menu_item_version_allergens_allergen_id_allergens"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "menu_item_version_id",
                "menu_version_id",
                "menu_id",
                "organization_id",
                "location_id",
            ],
            [
                "menu_item_versions.id",
                "menu_item_versions.menu_version_id",
                "menu_item_versions.menu_id",
                "menu_item_versions.organization_id",
                "menu_item_versions.location_id",
            ],
            name="fk_menu_item_allergens_item_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["verified_by_user_id"],
            ["users.id"],
            name=op.f("fk_menu_item_version_allergens_verified_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_item_version_allergens")),
        sa.UniqueConstraint("menu_item_version_id", "allergen_id", name="uq_menu_item_allergen"),
    )

    op.create_table(
        "menu_version_item_deltas",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("location_id", sa.Uuid(), nullable=False),
        sa.Column("menu_id", sa.Uuid(), nullable=False),
        sa.Column("menu_version_id", sa.Uuid(), nullable=False),
        sa.Column("base_version_id", sa.Uuid()),
        sa.Column("menu_item_id", sa.Uuid(), nullable=False),
        sa.Column("delta_kind", sa.String(16), server_default="unchanged", nullable=False),
        sa.Column("training_impact", sa.String(16), server_default="none", nullable=False),
        sa.Column(
            "changed_field_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        _id_column(),
        *_timestamps(),
        sa.CheckConstraint(
            "delta_kind IN ('added', 'changed', 'removed', 'unchanged')",
            name=op.f("ck_menu_version_item_deltas_delta_kind_allowed"),
        ),
        sa.CheckConstraint(
            "training_impact IN ('none', 'review', 'required')",
            name=op.f("ck_menu_version_item_deltas_training_impact_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(changed_field_codes) = 'array'",
            name=op.f("ck_menu_version_item_deltas_changed_fields_array"),
        ),
        sa.ForeignKeyConstraint(
            ["base_version_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_versions.id",
                "menu_versions.menu_id",
                "menu_versions.organization_id",
                "menu_versions.location_id",
            ],
            name="fk_menu_deltas_base_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_items.id",
                "menu_items.menu_id",
                "menu_items.organization_id",
                "menu_items.location_id",
            ],
            name="fk_menu_deltas_item_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["menu_version_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_versions.id",
                "menu_versions.menu_id",
                "menu_versions.organization_id",
                "menu_versions.location_id",
            ],
            name="fk_menu_deltas_version_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_version_item_deltas")),
        sa.UniqueConstraint("menu_version_id", "menu_item_id", name="uq_menu_version_item_delta"),
    )


def downgrade() -> None:
    op.drop_table("menu_version_item_deltas")
    op.drop_table("menu_item_version_allergens")
    op.drop_table("menu_item_version_components")
    op.drop_table("menu_component_version_translations")
    op.drop_table("menu_item_version_translations")
    op.drop_table("menu_version_category_translations")
    op.drop_table("menu_version_section_translations")
    op.drop_table("menu_item_versions")
    op.drop_table("menu_component_versions")
    op.drop_table("menu_version_categories")
    op.drop_table("menu_version_sections")
    op.drop_table("menu_versions")
    op.drop_table("allergens")
    op.drop_table("menu_components")
    op.drop_table("menu_items")
    op.drop_table("menu_categories")
    op.drop_table("menu_sections")
    op.drop_table("menus")
