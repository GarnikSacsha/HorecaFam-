from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AcademyArticle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "academy_articles"
    __table_args__ = (
        UniqueConstraint("location_id", "slug", name="uq_academy_articles_slug"),
        UniqueConstraint("id", "organization_id", "location_id", name="uq_academy_articles_scope"),
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["cover_asset_id", "organization_id", "location_id"],
            ["assets.id", "assets.organization_id", "assets.location_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("status IN ('draft', 'published')", name="status_allowed"),
        CheckConstraint("revision >= 0 AND position >= 0", name="counters_nonnegative"),
        Index("ix_academy_articles_scope_status", "organization_id", "location_id", "status"),
    )
    organization_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    location_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    title_uk: Mapped[str] = mapped_column(String(200), nullable=False)
    summary_uk: Mapped[str] = mapped_column(String(500), nullable=False)
    body_uk: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default="draft", server_default="draft", nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    all_positions: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    cover_asset_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))


class AcademyArticleAudience(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "academy_article_audiences"
    __table_args__ = (
        UniqueConstraint("article_id", "operational_role_id", name="uq_academy_article_audience"),
        ForeignKeyConstraint(
            ["article_id", "organization_id", "location_id"],
            [
                "academy_articles.id",
                "academy_articles.organization_id",
                "academy_articles.location_id",
            ],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["operational_role_id", "organization_id"],
            ["operational_roles.id", "operational_roles.organization_id"],
            ondelete="RESTRICT",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    location_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    article_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    operational_role_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
