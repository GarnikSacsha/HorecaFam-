"""seed deterministic menu question templates

Revision ID: 0013_question_templates
Revises: 0012_question_rules
Create Date: 2026-08-29
"""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "0013_question_templates"
down_revision: str | None = "0012_question_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RULES = (
    (
        UUID("591637a6-90c1-5e70-a841-23729066dcf5"),
        "menu.components",
        "multiple_choice",
    ),
    (
        UUID("519da1ac-066b-512e-8212-d8cd625906d2"),
        "menu.allergens",
        "recognition",
    ),
    (
        UUID("7ed2faf4-0dd2-5cc4-9973-264090a2fbf1"),
        "menu.description",
        "recognition",
    ),
)


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
                "id": rule_id,
                "code": code,
                "version": 1,
                "domain_type": "menu",
                "mechanic": mechanic,
                "status": "active",
                "configuration": {},
            }
            for rule_id, code, mechanic in RULES
        ],
    )


def downgrade() -> None:
    for rule_id, code, _mechanic in RULES:
        op.execute(
            sa.text(
                "DELETE FROM question_generation_rules "
                "WHERE id = :rule_id AND code = :code AND version = 1"
            ).bindparams(rule_id=rule_id, code=code)
        )
