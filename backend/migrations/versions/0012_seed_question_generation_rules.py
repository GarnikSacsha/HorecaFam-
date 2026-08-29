"""seed deterministic question generation rules

Revision ID: 0012_question_rules
Revises: 0011_candidate_provenance
Create Date: 2026-08-29
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "0012_question_rules"
down_revision: str | None = "0011_candidate_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RULE_ID = UUID("92ee6e6c-a818-5666-a5bc-d8a6be2f14f5")


def upgrade() -> None:
    rules = sa.table(
        "question_generation_rules",
        sa.column("id", sa.UUID()),
        sa.column("code", sa.String()),
        sa.column("version", sa.Integer()),
        sa.column("domain_type", sa.String()),
        sa.column("mechanic", sa.String()),
        sa.column("status", sa.String()),
        sa.column("configuration", sa.JSON()),
    )
    op.bulk_insert(
        rules,
        [
            {
                "id": RULE_ID,
                "code": "menu.category",
                "version": 1,
                "domain_type": "menu",
                "mechanic": "single_choice",
                "status": "active",
                "configuration": {},
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM question_generation_rules "
            "WHERE id = :rule_id AND code = 'menu.category' AND version = 1"
        ).bindparams(rule_id=RULE_ID)
    )
