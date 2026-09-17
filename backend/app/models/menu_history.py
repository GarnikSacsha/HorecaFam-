from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class MenuChangeEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "menu_change_events"
    __table_args__ = (
        CheckConstraint("action IN ('created', 'updated', 'removed')", name="action_allowed"),
        Index("ix_menu_change_events_page", "organization_id", "created_at", "id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    location_id: Mapped[UUID] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    menu_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("menu_versions.id", ondelete="RESTRICT")
    )
    menu_item_id: Mapped[UUID] = mapped_column(ForeignKey("menu_items.id", ondelete="RESTRICT"))
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    actor_email: Mapped[str] = mapped_column(String(320))
    action: Mapped[str] = mapped_column(String(16))
    item_name: Mapped[str] = mapped_column(String(200))
    old_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
