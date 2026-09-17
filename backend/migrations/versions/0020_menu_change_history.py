"""Зберігаємо бізнес-зміни меню окремо від технічних подій."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_menu_change_history"
down_revision: str | None = "0019_auth_security_budgets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "menu_change_events",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.UUID(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "menu_version_id",
            sa.UUID(),
            sa.ForeignKey("menu_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "menu_item_id",
            sa.UUID(),
            sa.ForeignKey("menu_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("actor_email", sa.String(320), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("item_name", sa.String(200), nullable=False),
        sa.Column("old_values", postgresql.JSONB()),
        sa.Column("new_values", postgresql.JSONB()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("action IN ('created', 'updated', 'removed')", name="action_allowed"),
    )
    op.create_index(
        "ix_menu_change_events_page", "menu_change_events", ["organization_id", "created_at", "id"]
    )


def downgrade() -> None:
    op.drop_table("menu_change_events")
