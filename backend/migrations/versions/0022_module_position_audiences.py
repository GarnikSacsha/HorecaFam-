"""Аудиторії модулів не змінюють наявні версії, уроки та результати."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_module_position_audiences"
down_revision: str | None = "0021_lesson_question_cycles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "training_versions",
        sa.Column("all_positions", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.drop_constraint("uq_training_modules_domain", "training_modules", type_="unique")
    op.drop_constraint(
        op.f("ck_training_modules_domain_type_allowed"), "training_modules", type_="check"
    )
    op.create_check_constraint(
        "domain_type_allowed",
        "training_modules",
        "domain_type IN ('menu', 'service', 'sales', 'venue_standards')",
    )
    op.create_index(
        "uq_training_modules_menu",
        "training_modules",
        ["training_id"],
        unique=True,
        postgresql_where=sa.text("domain_type = 'menu'"),
    )
    op.add_column(
        "training_module_versions",
        sa.Column("all_positions", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_table(
        "training_module_audiences",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("training_version_id", sa.UUID(), nullable=False),
        sa.Column("training_module_version_id", sa.UUID(), nullable=False),
        sa.Column("operational_role_id", sa.UUID(), nullable=False),
        sa.UniqueConstraint(
            "training_module_version_id",
            "operational_role_id",
            name="uq_training_module_audiences_module_role",
        ),
        sa.ForeignKeyConstraint(
            ["training_module_version_id", "training_version_id"],
            ["training_module_versions.id", "training_module_versions.training_version_id"],
            name="fk_training_module_audiences_module_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["training_version_id", "organization_id", "location_id"],
            [
                "training_versions.id",
                "training_versions.organization_id",
                "training_versions.location_id",
            ],
            name="fk_training_module_audiences_version_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["operational_role_id", "organization_id"],
            ["operational_roles.id", "operational_roles.organization_id"],
            name="fk_training_module_audiences_role_scope",
            ondelete="RESTRICT",
        ),
    )


def downgrade() -> None:
    connection = op.get_bind()
    if connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM training_modules WHERE domain_type <> 'menu') "
            "OR EXISTS (SELECT 1 FROM training_module_versions WHERE NOT all_positions) "
            "OR EXISTS (SELECT 1 FROM training_versions WHERE all_positions)"
        )
    ):
        raise RuntimeError("Downgrade would discard position-scoped training")
    op.drop_table("training_module_audiences")
    op.drop_column("training_versions", "all_positions")
    op.drop_column("training_module_versions", "all_positions")
    op.drop_index("uq_training_modules_menu", table_name="training_modules")
    op.drop_constraint(
        op.f("ck_training_modules_domain_type_allowed"), "training_modules", type_="check"
    )
    op.create_check_constraint("domain_type_allowed", "training_modules", "domain_type IN ('menu')")
    op.create_unique_constraint(
        "uq_training_modules_domain", "training_modules", ["training_id", "domain_type"]
    )
