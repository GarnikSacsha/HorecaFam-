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
    AssetStatus,
    TrainingDomain,
    TrainingTranslationStatus,
    TrainingVersionStatus,
)


def _uuid() -> PostgreSQLUUID[UUID]:
    return PostgreSQLUUID(as_uuid=True)


class Training(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "trainings"
    __table_args__ = (
        UniqueConstraint("location_id", name="uq_trainings_location_id"),
        UniqueConstraint("id", "organization_id", "location_id", name="uq_trainings_scope"),
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_trainings_location_organization",
            ondelete="RESTRICT",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False, index=True)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)


class TrainingVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "training_versions"
    __table_args__ = (
        UniqueConstraint("training_id", "version_number", name="uq_training_versions_number"),
        UniqueConstraint(
            "id", "training_id", "organization_id", "location_id", name="uq_training_versions_scope"
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            "location_id",
            name="uq_training_versions_audience_scope",
        ),
        CheckConstraint("version_number >= 1", name="version_number_positive"),
        CheckConstraint("revision >= 0", name="revision_nonnegative"),
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="status_allowed"),
        CheckConstraint(
            "(status = 'draft' AND published_by_user_id IS NULL AND published_at IS NULL "
            "AND archived_at IS NULL) OR "
            "(status = 'published' AND published_by_user_id IS NOT NULL "
            "AND published_at IS NOT NULL AND archived_at IS NULL) OR "
            "(status = 'archived' AND published_by_user_id IS NOT NULL "
            "AND published_at IS NOT NULL AND archived_at IS NOT NULL)",
            name="lifecycle_timestamps_match",
        ),
        ForeignKeyConstraint(
            ["training_id", "organization_id", "location_id"],
            ["trainings.id", "trainings.organization_id", "trainings.location_id"],
            name="fk_training_versions_training_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
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
        Index(
            "uq_training_versions_one_draft",
            "training_id",
            unique=True,
            postgresql_where=text("status = 'draft'"),
        ),
        Index(
            "uq_training_versions_one_published",
            "training_id",
            unique=True,
            postgresql_where=text("status = 'published'"),
        ),
        Index("ix_training_versions_current", "training_id", "status", "version_number"),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    training_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TrainingVersionStatus.DRAFT.value,
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


class TrainingModule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "training_modules"
    __table_args__ = (
        UniqueConstraint("training_id", "domain_type", name="uq_training_modules_domain"),
        UniqueConstraint("id", "training_id", name="uq_training_modules_scope"),
        CheckConstraint("domain_type IN ('menu')", name="domain_type_allowed"),
    )

    training_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("trainings.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    domain_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default=TrainingDomain.MENU.value, server_default="menu"
    )


class TrainingModuleVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "training_module_versions"
    __table_args__ = (
        UniqueConstraint("training_version_id", "training_module_id", name="uq_tmv_identity"),
        UniqueConstraint("training_version_id", "position", name="uq_tmv_position"),
        UniqueConstraint("id", "training_version_id", name="uq_tmv_scope"),
        CheckConstraint("position >= 0", name="position_nonnegative"),
        ForeignKeyConstraint(
            ["training_module_id", "training_id"],
            ["training_modules.id", "training_modules.training_id"],
            name="fk_tmv_module_scope",
            ondelete="RESTRICT",
        ),
    )

    training_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    training_version_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("training_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    training_module_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )


class TrainingModuleTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "training_module_translations"
    __table_args__ = (
        UniqueConstraint("training_module_version_id", "locale", name="uq_tmt_locale"),
        CheckConstraint("locale IN ('uk', 'en')", name="locale_allowed"),
        CheckConstraint("status IN ('pending', 'ready', 'failed', 'stale')", name="status_allowed"),
        CheckConstraint("length(btrim(title)) BETWEEN 1 AND 200", name="title_length"),
        CheckConstraint(
            "description IS NULL OR length(description) <= 2000", name="description_length"
        ),
        CheckConstraint("source_revision >= 0", name="source_revision_nonnegative"),
    )

    training_module_version_id: Mapped[UUID] = mapped_column(
        _uuid(),
        ForeignKey("training_module_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TrainingTranslationStatus.READY.value,
        server_default="ready",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


class Lesson(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("id", "training_module_id", name="uq_lessons_scope"),)

    training_module_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("training_modules.id", ondelete="RESTRICT"), nullable=False, index=True
    )


class LessonVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lesson_versions"
    __table_args__ = (
        UniqueConstraint(
            "training_module_version_id", "lesson_id", name="uq_lesson_versions_identity"
        ),
        UniqueConstraint(
            "training_module_version_id", "position", name="uq_lesson_versions_position"
        ),
        UniqueConstraint("id", "training_module_version_id", name="uq_lesson_versions_scope"),
        UniqueConstraint("id", "lesson_id", name="uq_lesson_versions_lesson_scope"),
        CheckConstraint("position >= 0", name="position_nonnegative"),
        CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes BETWEEN 1 AND 240",
            name="estimated_minutes_range",
        ),
    )

    training_module_version_id: Mapped[UUID] = mapped_column(
        _uuid(),
        ForeignKey("training_module_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    lesson_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("lessons.id", ondelete="RESTRICT"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    estimated_minutes: Mapped[int | None] = mapped_column(Integer)


class LessonTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lesson_translations"
    __table_args__ = (
        UniqueConstraint("lesson_version_id", "locale", name="uq_lesson_translations_locale"),
        CheckConstraint("locale IN ('uk', 'en')", name="locale_allowed"),
        CheckConstraint("status IN ('pending', 'ready', 'failed', 'stale')", name="status_allowed"),
        CheckConstraint("length(btrim(title)) BETWEEN 1 AND 200", name="title_length"),
        CheckConstraint(
            "description IS NULL OR length(description) <= 2000", name="description_length"
        ),
        CheckConstraint("source_revision >= 0", name="source_revision_nonnegative"),
    )

    lesson_version_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("lesson_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    locale: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TrainingTranslationStatus.READY.value,
        server_default="ready",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("object_key", name="uq_assets_object_key"),
        UniqueConstraint("id", "organization_id", "location_id", name="uq_assets_scope"),
        CheckConstraint(
            "status IN ('pending_upload', 'ready', 'failed', 'archived')", name="status_allowed"
        ),
        CheckConstraint(
            "mime_type IN ('image/jpeg', 'image/png', 'image/webp')", name="mime_type_allowed"
        ),
        CheckConstraint("size_bytes BETWEEN 1 AND 5242880", name="size_bytes_range"),
        CheckConstraint("length(sha256) = 64", name="sha256_length"),
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_assets_location_organization",
            ondelete="RESTRICT",
        ),
        Index("ix_assets_scope_status", "organization_id", "location_id", "status"),
        Index("ix_assets_sha256", "sha256"),
    )

    organization_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    location_id: Mapped[UUID] = mapped_column(_uuid(), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
        default=AssetStatus.PENDING_UPLOAD.value,
        server_default="pending_upload",
    )
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    upload_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LessonContentBlock(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lesson_content_blocks"
    __table_args__ = (
        UniqueConstraint("lesson_version_id", "position", name="uq_lcb_position"),
        CheckConstraint("position >= 0", name="position_nonnegative"),
        CheckConstraint(
            "type IN ('heading', 'text', 'list', 'callout', 'menu_item_card', "
            "'image', 'external_video')",
            name="type_allowed",
        ),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_object"),
        CheckConstraint(
            "(type = 'menu_item_card' AND menu_item_id IS NOT NULL AND asset_id IS NULL) OR "
            "(type = 'image' AND asset_id IS NOT NULL AND menu_item_id IS NULL) OR "
            "(type NOT IN ('menu_item_card', 'image') AND menu_item_id IS NULL "
            "AND asset_id IS NULL)",
            name="relational_payload_matches_type",
        ),
    )

    lesson_version_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("lesson_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    menu_item_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("menu_items.id", ondelete="RESTRICT")
    )
    asset_id: Mapped[UUID | None] = mapped_column(
        _uuid(), ForeignKey("assets.id", ondelete="RESTRICT")
    )


class LessonContentBlockTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lesson_content_block_translations"
    __table_args__ = (
        UniqueConstraint("lesson_content_block_id", "locale", name="uq_lcbt_locale"),
        CheckConstraint("locale IN ('en')", name="locale_allowed"),
        CheckConstraint("status IN ('pending', 'ready', 'failed', 'stale')", name="status_allowed"),
        CheckConstraint("jsonb_typeof(translated_payload) = 'object'", name="payload_object"),
        CheckConstraint("source_revision >= 0", name="source_rev_nonnegative"),
    )

    lesson_content_block_id: Mapped[UUID] = mapped_column(
        _uuid(),
        ForeignKey("lesson_content_blocks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    locale: Mapped[str] = mapped_column(
        String(8), nullable=False, default="en", server_default="en"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TrainingTranslationStatus.PENDING.value,
        server_default="pending",
    )
    translated_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    source_revision: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )


class TrainingVersionMenuDependency(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "training_version_menu_dependencies"
    __table_args__ = (
        UniqueConstraint("training_version_id", name="uq_tvmd_training_version"),
        UniqueConstraint(
            "training_version_id", "menu_version_id", name="uq_tvmd_training_menu_version"
        ),
    )

    training_version_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("training_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    menu_version_id: Mapped[UUID] = mapped_column(
        _uuid(), ForeignKey("menu_versions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
