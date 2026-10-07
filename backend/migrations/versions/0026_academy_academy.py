"""Необов’язкові статті мають власну аудиторію та не змінюють прогрес навчання."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_academy"
down_revision: str | None = "0025_menu_preparation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "academy_articles",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("title_uk", sa.String(length=200), nullable=False),
        sa.Column("summary_uk", sa.String(length=500), nullable=False),
        sa.Column("body_uk", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("position", sa.Integer(), server_default="0", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("all_positions", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("cover_asset_id", sa.UUID(), nullable=True),
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
            "status IN ('draft', 'published')", name=op.f("ck_academy_articles_status_allowed")
        ),
        sa.CheckConstraint(
            "revision >= 0 AND position >= 0", name=op.f("ck_academy_articles_counters_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["cover_asset_id", "organization_id", "location_id"],
            ["assets.id", "assets.organization_id", "assets.location_id"],
            name=op.f("fk_academy_articles_cover_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name=op.f("fk_academy_articles_location_id_locations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_academy_articles")),
        sa.UniqueConstraint(
            "id", "organization_id", "location_id", name="uq_academy_articles_scope"
        ),
        sa.UniqueConstraint("location_id", "slug", name="uq_academy_articles_slug"),
    )
    op.create_index(
        "ix_academy_articles_scope_status",
        "academy_articles",
        ["organization_id", "location_id", "status"],
        unique=False,
    )
    op.create_table(
        "academy_article_audiences",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("operational_role_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id", "organization_id", "location_id"],
            [
                "academy_articles.id",
                "academy_articles.organization_id",
                "academy_articles.location_id",
            ],
            name=op.f("fk_academy_article_audiences_article_id_academy_articles"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["operational_role_id", "organization_id"],
            ["operational_roles.id", "operational_roles.organization_id"],
            name=op.f("fk_academy_article_audiences_operational_role_id_operational_roles"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_academy_article_audiences")),
        sa.UniqueConstraint(
            "article_id", "operational_role_id", name="uq_academy_article_audience"
        ),
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM academy_articles)")):
        raise RuntimeError("Downgrade would discard Academy articles")
    op.drop_table("academy_article_audiences")
    op.drop_index("ix_academy_articles_scope_status", table_name="academy_articles")
    op.drop_table("academy_articles")
