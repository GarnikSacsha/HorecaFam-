from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    FactDataStatus,
    LifecycleStatus,
    MenuAvailability,
    MenuDeltaKind,
    MenuSourceKind,
    MenuVersionStatus,
    TrainingImpact,
    TranslationStatus,
)


def _uuid() -> PostgreSQLUUID[UUID]:
    return PostgreSQLUUID(as_uuid=True)


class Menu(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menus"
    __table_args__ = (
        UniqueConstraint("location_id", name="uq_menus_location_id"),
        UniqueConstraint(
            "id",
            "organization_id",
            "location_id",
            name="uq_menus_id_organization_location",
        ),
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_menus_location_organization",
            ondelete="RESTRICT",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False, index=True)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)


class MenuSection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menu_sections"
    __table_args__ = (
        UniqueConstraint(
            "id", "menu_id", "organization_id", "location_id", name="uq_menu_sections_scope"
        ),
        CheckConstraint(
            "stable_code IS NULL OR "
            "(length(btrim(stable_code)) > 0 AND stable_code = lower(btrim(stable_code)))",
            name="stable_code_normalized",
        ),
        CheckConstraint(
            "retired_at IS NULL OR retired_at >= created_at", name="retired_after_create"
        ),
        ForeignKeyConstraint(
            ["menu_id", "organization_id", "location_id"],
            ["menus.id", "menus.organization_id", "menus.location_id"],
            name="fk_menu_sections_menu_scope",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_menu_sections_stable_code",
            "menu_id",
            "stable_code",
            unique=True,
            postgresql_where=text("stable_code IS NOT NULL"),
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False, index=True)
    stable_code: Mapped[str | None] = mapped_column(String(100))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MenuCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menu_categories"
    __table_args__ = (
        UniqueConstraint(
            "id", "menu_id", "organization_id", "location_id", name="uq_menu_categories_scope"
        ),
        CheckConstraint(
            "stable_code IS NULL OR "
            "(length(btrim(stable_code)) > 0 AND stable_code = lower(btrim(stable_code)))",
            name="stable_code_normalized",
        ),
        CheckConstraint(
            "retired_at IS NULL OR retired_at >= created_at", name="retired_after_create"
        ),
        ForeignKeyConstraint(
            ["menu_id", "organization_id", "location_id"],
            ["menus.id", "menus.organization_id", "menus.location_id"],
            name="fk_menu_categories_menu_scope",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_menu_categories_stable_code",
            "menu_id",
            "stable_code",
            unique=True,
            postgresql_where=text("stable_code IS NOT NULL"),
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False, index=True)
    stable_code: Mapped[str | None] = mapped_column(String(100))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MenuItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menu_items"
    __table_args__ = (
        UniqueConstraint(
            "id", "menu_id", "organization_id", "location_id", name="uq_menu_items_scope"
        ),
        CheckConstraint(
            "stable_code IS NULL OR "
            "(length(btrim(stable_code)) > 0 AND stable_code = lower(btrim(stable_code)))",
            name="stable_code_normalized",
        ),
        CheckConstraint(
            "retired_at IS NULL OR retired_at >= created_at", name="retired_after_create"
        ),
        ForeignKeyConstraint(
            ["menu_id", "organization_id", "location_id"],
            ["menus.id", "menus.organization_id", "menus.location_id"],
            name="fk_menu_items_menu_scope",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_menu_items_stable_code",
            "menu_id",
            "stable_code",
            unique=True,
            postgresql_where=text("stable_code IS NOT NULL"),
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False, index=True)
    stable_code: Mapped[str | None] = mapped_column(String(100))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MenuComponent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menu_components"
    __table_args__ = (
        UniqueConstraint(
            "id", "menu_id", "organization_id", "location_id", name="uq_menu_components_scope"
        ),
        CheckConstraint(
            "stable_code IS NULL OR "
            "(length(btrim(stable_code)) > 0 AND stable_code = lower(btrim(stable_code)))",
            name="stable_code_normalized",
        ),
        CheckConstraint(
            "retired_at IS NULL OR retired_at >= created_at", name="retired_after_create"
        ),
        ForeignKeyConstraint(
            ["menu_id", "organization_id", "location_id"],
            ["menus.id", "menus.organization_id", "menus.location_id"],
            name="fk_menu_components_menu_scope",
            ondelete="RESTRICT",
        ),
        Index(
            "uq_menu_components_stable_code",
            "menu_id",
            "stable_code",
            unique=True,
            postgresql_where=text("stable_code IS NOT NULL"),
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False, index=True)
    stable_code: Mapped[str | None] = mapped_column(String(100))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MenuVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menu_versions"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "menu_id",
            "organization_id",
            "location_id",
            name="uq_menu_versions_scope",
        ),
        UniqueConstraint("menu_id", "version_number", name="uq_menu_versions_number"),
        CheckConstraint("version_number >= 1", name="version_number_positive"),
        CheckConstraint("revision >= 0", name="revision_nonnegative"),
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="status_allowed"),
        CheckConstraint(
            "(status = 'draft' AND published_by_user_id IS NULL "
            "AND published_at IS NULL AND archived_at IS NULL) OR "
            "(status = 'published' AND published_by_user_id IS NOT NULL "
            "AND published_at IS NOT NULL AND archived_at IS NULL) OR "
            "(status = 'archived' AND published_by_user_id IS NOT NULL "
            "AND published_at IS NOT NULL AND archived_at IS NOT NULL)",
            name="lifecycle_timestamps_match",
        ),
        ForeignKeyConstraint(
            ["menu_id", "organization_id", "location_id"],
            ["menus.id", "menus.organization_id", "menus.location_id"],
            name="fk_menu_versions_menu_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
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
        Index(
            "uq_menu_versions_one_draft",
            "menu_id",
            unique=True,
            postgresql_where=text("status = 'draft'"),
        ),
        Index(
            "uq_menu_versions_one_published",
            "menu_id",
            unique=True,
            postgresql_where=text("status = 'published'"),
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=MenuVersionStatus.DRAFT.value,
        server_default=text("'draft'"),
    )
    base_version_id: Mapped[UUID | None] = mapped_column(_uuid())
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_by_user_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MenuVersionSection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menu_version_sections"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "menu_version_id",
            "menu_id",
            "organization_id",
            "location_id",
            name="uq_menu_version_sections_scope",
        ),
        UniqueConstraint("menu_version_id", "menu_section_id", name="uq_mv_sections_identity"),
        UniqueConstraint("menu_version_id", "position", name="uq_mv_sections_position"),
        CheckConstraint("position >= 0", name="position_nonnegative"),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
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
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False, index=True)
    menu_section_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class MenuVersionCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menu_version_categories"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "menu_version_id",
            "menu_id",
            "organization_id",
            "location_id",
            name="uq_menu_version_categories_scope",
        ),
        UniqueConstraint("menu_version_id", "menu_category_id", name="uq_mv_categories_identity"),
        UniqueConstraint("menu_version_section_id", "position", name="uq_mv_categories_position"),
        CheckConstraint("position >= 0", name="position_nonnegative"),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
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
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False, index=True)
    menu_category_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_version_section_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class MenuItemVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menu_item_versions"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "menu_version_id",
            "menu_id",
            "organization_id",
            "location_id",
            name="uq_menu_item_versions_scope",
        ),
        UniqueConstraint("menu_version_id", "menu_item_id", name="uq_menu_item_versions_identity"),
        UniqueConstraint(
            "menu_version_category_id", "position", name="uq_menu_item_versions_position"
        ),
        CheckConstraint("position >= 0", name="position_nonnegative"),
        CheckConstraint(
            "availability IN ('available', 'temporarily_unavailable', 'seasonal', 'discontinued')",
            name="availability_allowed",
        ),
        CheckConstraint("price_minor IS NULL OR price_minor >= 0", name="price_nonnegative"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_iso_format"),
        CheckConstraint(
            "component_data_status IN ('unknown', 'confirmed_none', 'confirmed_present')",
            name="component_status_allowed",
        ),
        CheckConstraint(
            "allergen_data_status IN ('unknown', 'confirmed_none', 'confirmed_present')",
            name="allergen_status_allowed",
        ),
        CheckConstraint("source_kind IN ('manual', 'json_import')", name="source_kind_allowed"),
        CheckConstraint(
            "source_reference IS NULL OR length(btrim(source_reference)) > 0",
            name="source_reference_not_blank",
        ),
        CheckConstraint(
            "source_item_key IS NULL OR length(btrim(source_item_key)) > 0",
            name="source_item_key_not_blank",
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
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
        Index(
            "ix_menu_item_versions_lookup",
            "menu_version_id",
            "menu_version_category_id",
            "availability",
            "position",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_item_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_version_category_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    availability: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=MenuAvailability.AVAILABLE.value,
        server_default=text("'available'"),
    )
    price_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="UAH", server_default="UAH"
    )
    component_data_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=FactDataStatus.UNKNOWN.value, server_default="unknown"
    )
    allergen_data_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=FactDataStatus.UNKNOWN.value, server_default="unknown"
    )
    source_kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default=MenuSourceKind.MANUAL.value, server_default="manual"
    )
    source_reference: Mapped[str | None] = mapped_column(String(500))
    source_item_key: Mapped[str | None] = mapped_column(String(200))
    verified_by_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MenuComponentVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menu_component_versions"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "menu_version_id",
            "menu_id",
            "organization_id",
            "location_id",
            name="uq_menu_component_versions_scope",
        ),
        UniqueConstraint("menu_version_id", "menu_component_id", name="uq_mc_versions_identity"),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
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
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False, index=True)
    menu_component_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)


class MenuVersionSectionTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menu_version_section_translations"
    __table_args__ = (
        UniqueConstraint(
            "menu_version_section_id", "locale", name="uq_mv_section_translation_locale"
        ),
        CheckConstraint("locale IN ('uk', 'en')", name="locale_allowed"),
        CheckConstraint("status IN ('draft', 'needs_review', 'ready')", name="status_allowed"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        ForeignKeyConstraint(
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
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_version_section_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TranslationStatus.DRAFT.value, server_default="draft"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class MenuVersionCategoryTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menu_version_category_translations"
    __table_args__ = (
        UniqueConstraint(
            "menu_version_category_id", "locale", name="uq_mv_category_translation_locale"
        ),
        CheckConstraint("locale IN ('uk', 'en')", name="locale_allowed"),
        CheckConstraint("status IN ('draft', 'needs_review', 'ready')", name="status_allowed"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        ForeignKeyConstraint(
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
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_version_category_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TranslationStatus.DRAFT.value, server_default="draft"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class MenuItemVersionTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menu_item_version_translations"
    __table_args__ = (
        UniqueConstraint("menu_item_version_id", "locale", name="uq_menu_item_translation_locale"),
        CheckConstraint("locale IN ('uk', 'en')", name="locale_allowed"),
        CheckConstraint("status IN ('draft', 'needs_review', 'ready')", name="status_allowed"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        ForeignKeyConstraint(
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
        Index("ix_menu_item_translation_search", "locale", text("lower(name)")),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_item_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TranslationStatus.DRAFT.value, server_default="draft"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class MenuComponentVersionTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menu_component_version_translations"
    __table_args__ = (
        UniqueConstraint("menu_component_version_id", "locale", name="uq_mc_translation_locale"),
        CheckConstraint("locale IN ('uk', 'en')", name="locale_allowed"),
        CheckConstraint("status IN ('draft', 'needs_review', 'ready')", name="status_allowed"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        ForeignKeyConstraint(
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
        Index("ix_menu_component_translation_search", "locale", text("lower(name)")),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_component_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TranslationStatus.DRAFT.value, server_default="draft"
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class MenuItemVersionComponent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menu_item_version_components"
    __table_args__ = (
        UniqueConstraint(
            "menu_item_version_id", "menu_component_version_id", name="uq_menu_item_component"
        ),
        UniqueConstraint(
            "menu_item_version_id", "position", name="uq_menu_item_component_position"
        ),
        CheckConstraint("position >= 0", name="position_nonnegative"),
        CheckConstraint("source_kind IN ('manual', 'json_import')", name="source_kind_allowed"),
        CheckConstraint(
            "source_reference IS NULL OR length(btrim(source_reference)) > 0",
            name="source_reference_not_blank",
        ),
        CheckConstraint(
            "source_item_key IS NULL OR length(btrim(source_item_key)) > 0",
            name="source_item_key_not_blank",
        ),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
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
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_item_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_component_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    optional: Mapped[bool | None] = mapped_column(Boolean)
    source_kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default=MenuSourceKind.MANUAL.value, server_default="manual"
    )
    source_reference: Mapped[str | None] = mapped_column(String(500))
    source_item_key: Mapped[str | None] = mapped_column(String(200))
    verified_by_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Allergen(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "allergens"
    __table_args__ = (
        CheckConstraint("length(btrim(code)) > 0", name="code_not_blank"),
        CheckConstraint("code = lower(btrim(code))", name="code_normalized"),
        CheckConstraint("length(btrim(label_uk)) > 0", name="label_uk_not_blank"),
        CheckConstraint("status IN ('active', 'archived')", name="status_allowed"),
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    label_uk: Mapped[str] = mapped_column(String(200), nullable=False)
    label_en: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=LifecycleStatus.ACTIVE.value, server_default="active"
    )


class MenuItemVersionAllergen(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menu_item_version_allergens"
    __table_args__ = (
        UniqueConstraint("menu_item_version_id", "allergen_id", name="uq_menu_item_allergen"),
        CheckConstraint("source_kind IN ('manual', 'json_import')", name="source_kind_allowed"),
        CheckConstraint(
            "source_reference IS NULL OR length(btrim(source_reference)) > 0",
            name="source_reference_not_blank",
        ),
        CheckConstraint(
            "source_item_key IS NULL OR length(btrim(source_item_key)) > 0",
            name="source_item_key_not_blank",
        ),
        ForeignKeyConstraint(
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
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_item_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    allergen_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("allergens.id", ondelete="RESTRICT"), nullable=False
    )
    source_kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default=MenuSourceKind.MANUAL.value, server_default="manual"
    )
    source_reference: Mapped[str | None] = mapped_column(String(500))
    source_item_key: Mapped[str | None] = mapped_column(String(200))
    verified_by_user_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MenuVersionItemDelta(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "menu_version_item_deltas"
    __table_args__ = (
        UniqueConstraint("menu_version_id", "menu_item_id", name="uq_menu_version_item_delta"),
        CheckConstraint(
            "delta_kind IN ('added', 'changed', 'removed', 'unchanged')",
            name="delta_kind_allowed",
        ),
        CheckConstraint(
            "training_impact IN ('none', 'review', 'required')",
            name="training_impact_allowed",
        ),
        CheckConstraint("jsonb_typeof(changed_field_codes) = 'array'", name="changed_fields_array"),
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
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
        ForeignKeyConstraint(
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
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    menu_version_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    base_version_id: Mapped[UUID | None] = mapped_column(_uuid())
    menu_item_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    delta_kind: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=MenuDeltaKind.UNCHANGED.value,
        server_default="unchanged",
    )
    training_impact: Mapped[str] = mapped_column(
        String(16), nullable=False, default=TrainingImpact.NONE.value, server_default="none"
    )
    changed_field_codes: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
