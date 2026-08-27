"""Додати транзакційний email outbox для запрошень Stage 3.

Revision ID: 0005_invitation_email_outbox
Revises: 0004_invitation_lifecycle
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_invitation_email_outbox"
down_revision: str | None = "0004_invitation_lifecycle"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_invitations_id_organization_id",
        "invitations",
        ["id", "organization_id"],
    )

    op.create_table(
        "background_jobs",
        sa.Column("organization_id", sa.Uuid()),
        sa.Column("job_type", sa.String(64), server_default="invitation_email", nullable=False),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column(
            "next_run_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("locked_by", sa.String(255)),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(64)),
        sa.Column("last_error_message", sa.String(500)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "job_type = 'invitation_email'",
            name=op.f("ck_background_jobs_job_type_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name=op.f("ck_background_jobs_status_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' "
            "AND payload ? 'invitation_id' "
            "AND payload ? 'token_version'",
            name=op.f("ck_background_jobs_invitation_payload_required"),
        ),
        sa.CheckConstraint(
            "priority >= 0",
            name=op.f("ck_background_jobs_priority_nonnegative"),
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 5 AND attempt_count <= max_attempts",
            name=op.f("ck_background_jobs_attempt_counts_allowed"),
        ),
        sa.CheckConstraint(
            "status <> 'processing' OR "
            "(locked_by IS NOT NULL AND locked_at IS NOT NULL AND started_at IS NOT NULL)",
            name=op.f("ck_background_jobs_processing_lease_present"),
        ),
        sa.CheckConstraint(
            "status <> 'completed' OR completed_at IS NOT NULL",
            name=op.f("ck_background_jobs_completed_at_present"),
        ),
        sa.CheckConstraint(
            "status <> 'failed' OR failed_at IS NOT NULL",
            name=op.f("ck_background_jobs_failed_at_present"),
        ),
        sa.CheckConstraint(
            "NOT (completed_at IS NOT NULL AND failed_at IS NOT NULL)",
            name=op.f("ck_background_jobs_terminal_timestamp_exclusive"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_background_jobs_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_background_jobs")),
        sa.UniqueConstraint(
            "id",
            "organization_id",
            name="uq_background_jobs_id_organization_id",
        ),
        sa.UniqueConstraint(
            "job_type",
            "idempotency_key",
            name="uq_background_jobs_type_key",
        ),
    )
    op.create_index(
        op.f("ix_background_jobs_organization_id"),
        "background_jobs",
        ["organization_id"],
    )
    op.create_index(
        "ix_background_jobs_claim",
        "background_jobs",
        ["status", "next_run_at", "priority", "created_at"],
    )

    op.create_table(
        "email_deliveries",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("message_type", sa.String(64), server_default="invitation_email", nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("provider_message_id", sa.String(255)),
        sa.Column("status", sa.String(16), server_default="pending", nullable=False),
        sa.Column("accepted_by_provider_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("bounced_at", sa.DateTime(timezone=True)),
        sa.Column("failed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(64)),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "message_type = 'invitation_email'",
            name=op.f("ck_email_deliveries_message_type_allowed"),
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'delivered', 'bounced', 'failed')",
            name=op.f("ck_email_deliveries_status_allowed"),
        ),
        sa.CheckConstraint(
            "status <> 'accepted' OR accepted_by_provider_at IS NOT NULL",
            name=op.f("ck_email_deliveries_accepted_at_present"),
        ),
        sa.CheckConstraint(
            "status <> 'delivered' OR delivered_at IS NOT NULL",
            name=op.f("ck_email_deliveries_delivered_at_present"),
        ),
        sa.CheckConstraint(
            "status <> 'bounced' OR bounced_at IS NOT NULL",
            name=op.f("ck_email_deliveries_bounced_at_present"),
        ),
        sa.CheckConstraint(
            "status <> 'failed' OR failed_at IS NOT NULL",
            name=op.f("ck_email_deliveries_failed_at_present"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id", "organization_id"],
            ["background_jobs.id", "background_jobs.organization_id"],
            name="fk_email_deliveries_job_organization",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["invitation_id", "organization_id"],
            ["invitations.id", "invitations.organization_id"],
            name="fk_email_deliveries_invitation_organization",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_deliveries")),
        sa.UniqueConstraint("job_id", name="uq_email_deliveries_job_id"),
    )
    op.create_index(
        "ix_email_deliveries_invitation_created",
        "email_deliveries",
        ["invitation_id", "created_at"],
    )
    op.create_index(
        "ix_email_deliveries_provider_message",
        "email_deliveries",
        ["provider", "provider_message_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_deliveries_provider_message", table_name="email_deliveries")
    op.drop_index("ix_email_deliveries_invitation_created", table_name="email_deliveries")
    op.drop_table("email_deliveries")
    op.drop_index("ix_background_jobs_claim", table_name="background_jobs")
    op.drop_index(op.f("ix_background_jobs_organization_id"), table_name="background_jobs")
    op.drop_table("background_jobs")
    op.drop_constraint(
        "uq_invitations_id_organization_id",
        "invitations",
        type_="unique",
    )
