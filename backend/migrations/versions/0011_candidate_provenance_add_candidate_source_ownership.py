"""add candidate provenance ownership

Revision ID: 0011_candidate_provenance
Revises: 0010_interactive_training
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_candidate_provenance"
down_revision: str | None = "0010_interactive_training"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "question_source_links",
        sa.Column("question_candidate_id", sa.UUID(), nullable=True),
    )
    op.alter_column("question_source_links", "question_version_id", nullable=True)
    op.create_check_constraint(
        op.f("ck_question_source_links_exactly_one_owner"),
        "question_source_links",
        "num_nonnulls(question_candidate_id, question_version_id) = 1",
    )
    op.create_foreign_key(
        "fk_question_source_links_candidate_scope",
        "question_source_links",
        "question_candidates",
        ["question_candidate_id", "organization_id", "location_id"],
        ["id", "organization_id", "location_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_question_source_links_candidate_role",
        "question_source_links",
        ["question_candidate_id", "source_role"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_question_source_links_candidate_role", table_name="question_source_links")
    op.drop_constraint(
        "fk_question_source_links_candidate_scope",
        "question_source_links",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("ck_question_source_links_exactly_one_owner"),
        "question_source_links",
        type_="check",
    )
    op.alter_column("question_source_links", "question_version_id", nullable=False)
    op.drop_column("question_source_links", "question_candidate_id")
