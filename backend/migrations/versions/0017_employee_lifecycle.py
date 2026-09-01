"""Add bounded Employee lifecycle state.

Revision ID: 0017_employee_lifecycle
Revises: 0016_security_recovery
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_employee_lifecycle"
down_revision: str | None = "0016_security_recovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organization_memberships",
        sa.Column("training_paused_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organization_memberships",
        sa.Column("training_pause_reason_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "organization_memberships",
        sa.Column("training_pause_note", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "organization_memberships",
        sa.Column("planned_resume_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "organization_memberships",
        sa.Column("disabled_reason_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "organization_memberships",
        sa.Column("disabled_note", sa.String(length=500), nullable=True),
    )
    op.execute(
        "UPDATE organization_memberships SET training_paused_at = CURRENT_TIMESTAMP "
        "WHERE training_participation_status = 'paused' AND training_paused_at IS NULL"
    )
    op.create_check_constraint(
        op.f("ck_organization_memberships_training_pause_state"),
        "organization_memberships",
        "(training_participation_status = 'active' "
        "AND training_paused_at IS NULL "
        "AND training_pause_reason_code IS NULL "
        "AND training_pause_note IS NULL "
        "AND planned_resume_at IS NULL) OR "
        "(training_participation_status = 'paused' AND training_paused_at IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_organization_memberships_planned_resume_after_pause"),
        "organization_memberships",
        "planned_resume_at IS NULL OR planned_resume_at > training_paused_at",
    )
    op.create_check_constraint(
        op.f("ck_organization_memberships_pause_reason_code_format"),
        "organization_memberships",
        "training_pause_reason_code IS NULL OR "
        "training_pause_reason_code ~ '^[a-z][a-z0-9_]{0,63}$'",
    )
    op.create_check_constraint(
        op.f("ck_organization_memberships_pause_note_trimmed"),
        "organization_memberships",
        "training_pause_note IS NULL OR "
        "(training_pause_note = btrim(training_pause_note) "
        "AND length(training_pause_note) BETWEEN 1 AND 500)",
    )
    op.create_check_constraint(
        op.f("ck_organization_memberships_disabled_reason_state"),
        "organization_memberships",
        "status = 'disabled' OR (disabled_reason_code IS NULL AND disabled_note IS NULL)",
    )
    op.create_check_constraint(
        op.f("ck_organization_memberships_disabled_reason_code_format"),
        "organization_memberships",
        "disabled_reason_code IS NULL OR disabled_reason_code ~ '^[a-z][a-z0-9_]{0,63}$'",
    )
    op.create_check_constraint(
        op.f("ck_organization_memberships_disabled_note_trimmed"),
        "organization_memberships",
        "disabled_note IS NULL OR "
        "(disabled_note = btrim(disabled_note) AND length(disabled_note) BETWEEN 1 AND 500)",
    )


def downgrade() -> None:
    for name in (
        "disabled_note_trimmed",
        "disabled_reason_code_format",
        "disabled_reason_state",
        "pause_note_trimmed",
        "pause_reason_code_format",
        "planned_resume_after_pause",
        "training_pause_state",
    ):
        op.drop_constraint(
            op.f(f"ck_organization_memberships_{name}"),
            "organization_memberships",
            type_="check",
        )
    for name in (
        "disabled_note",
        "disabled_reason_code",
        "planned_resume_at",
        "training_pause_note",
        "training_pause_reason_code",
        "training_paused_at",
    ):
        op.drop_column("organization_memberships", name)
