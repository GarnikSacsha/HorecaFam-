"""Необов’язкові параметри подачі залишають старі позиції без змін."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025_menu_preparation"
down_revision: str | None = "0024_standard_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "menu_item_versions",
        sa.Column("preparation", postgresql.JSONB(none_as_null=True), nullable=True),
    )
    op.create_check_constraint(
        "preparation_object",
        "menu_item_versions",
        "preparation IS NULL OR jsonb_typeof(preparation) = 'object'",
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM menu_item_versions WHERE preparation IS NOT NULL)")
    ):
        raise RuntimeError("Downgrade would discard menu preparation details")
    op.drop_constraint(
        op.f("ck_menu_item_versions_preparation_object"), "menu_item_versions", type_="check"
    )
    op.drop_column("menu_item_versions", "preparation")
