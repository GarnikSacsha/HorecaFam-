"""Add password and MFA recovery persistence.

Revision ID: 0016_security_recovery
Revises: 0015_attention_retakes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016_security_recovery"
down_revision: str | None = "0015_attention_retakes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CURRENT_JOB_TYPES = (
    "job_type IN ('invitation_email', 'training_assignment_notification', "
    "'training_rollout_notification', 'password_reset_email')"
)
PREVIOUS_JOB_TYPES = (
    "job_type IN ('invitation_email', 'training_assignment_notification', "
    "'training_rollout_notification')"
)
CURRENT_JOB_PAYLOAD = (
    "jsonb_typeof(payload) = 'object' AND ("
    "(job_type = 'invitation_email' "
    "AND jsonb_typeof(payload->'invitation_id') = 'string' "
    "AND jsonb_typeof(payload->'token_version') = 'number' "
    "AND payload - ARRAY['invitation_id', 'token_version'] = '{}'::jsonb) OR "
    "(job_type = 'training_assignment_notification' "
    "AND jsonb_typeof(payload->'assignment_id') = 'string' "
    "AND jsonb_typeof(payload->'template_code') = 'string' "
    "AND length(payload->>'template_code') BETWEEN 1 AND 64 "
    "AND payload->>'locale' IN ('uk', 'en') "
    "AND payload - ARRAY['assignment_id', 'template_code', 'locale'] = '{}'::jsonb) OR "
    "(job_type = 'training_rollout_notification' "
    "AND jsonb_typeof(payload->'rollout_id') = 'string' "
    "AND jsonb_typeof(payload->'assignment_id') = 'string' "
    "AND jsonb_typeof(payload->'template_code') = 'string' "
    "AND length(payload->>'template_code') BETWEEN 1 AND 64 "
    "AND payload->>'locale' IN ('uk', 'en') "
    "AND payload - ARRAY['rollout_id', 'assignment_id', 'template_code', 'locale'] "
    "= '{}'::jsonb) OR "
    "(job_type = 'password_reset_email' "
    "AND jsonb_typeof(payload->'password_reset_token_id') = 'string' "
    "AND payload - ARRAY['password_reset_token_id'] = '{}'::jsonb))"
)
PREVIOUS_JOB_PAYLOAD = CURRENT_JOB_PAYLOAD.replace(
    " OR (job_type = 'password_reset_email' "
    "AND jsonb_typeof(payload->'password_reset_token_id') = 'string' "
    "AND payload - ARRAY['password_reset_token_id'] = '{}'::jsonb)",
    "",
)


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "length(token_hash) = 64", name=op.f("ck_password_reset_tokens_token_hash_length")
        ),
        sa.CheckConstraint(
            "expires_at > created_at", name=op.f("ck_password_reset_tokens_expiry_after_creation")
        ),
        sa.CheckConstraint(
            "num_nonnulls(used_at, revoked_at) <= 1",
            name=op.f("ck_password_reset_tokens_single_terminal_state"),
        ),
        sa.CheckConstraint(
            "used_at IS NULL OR used_at >= created_at",
            name=op.f("ck_password_reset_tokens_used_after_creation"),
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name=op.f("ck_password_reset_tokens_revoked_after_creation"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_reset_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_password_reset_tokens_token_hash")),
    )
    op.create_index(
        "ix_password_reset_tokens_user_active",
        "password_reset_tokens",
        ["user_id", "expires_at"],
        postgresql_where=sa.text("used_at IS NULL AND revoked_at IS NULL"),
    )
    op.create_table(
        "mfa_recovery_codes",
        sa.Column("mfa_credential_id", sa.Uuid(), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "length(code_hash) = 64", name=op.f("ck_mfa_recovery_codes_code_hash_length")
        ),
        sa.CheckConstraint(
            "used_at IS NULL OR used_at >= created_at",
            name=op.f("ck_mfa_recovery_codes_used_after_creation"),
        ),
        sa.ForeignKeyConstraint(["mfa_credential_id"], ["mfa_credentials.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mfa_recovery_codes")),
        sa.UniqueConstraint("code_hash", name=op.f("uq_mfa_recovery_codes_code_hash")),
    )
    op.create_index(
        "ix_mfa_recovery_codes_credential_unused",
        "mfa_recovery_codes",
        ["mfa_credential_id", "created_at"],
        postgresql_where=sa.text("used_at IS NULL"),
    )

    op.drop_constraint(
        op.f("ck_background_jobs_job_type_allowed"), "background_jobs", type_="check"
    )
    op.drop_constraint(
        op.f("ck_background_jobs_payload_matches_job_type"), "background_jobs", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_background_jobs_job_type_allowed"), "background_jobs", CURRENT_JOB_TYPES
    )
    op.create_check_constraint(
        op.f("ck_background_jobs_payload_matches_job_type"), "background_jobs", CURRENT_JOB_PAYLOAD
    )

    op.alter_column(
        "email_deliveries", "organization_id", existing_type=postgresql.UUID(), nullable=True
    )
    op.alter_column(
        "email_deliveries", "invitation_id", existing_type=postgresql.UUID(), nullable=True
    )
    op.add_column("email_deliveries", sa.Column("password_reset_token_id", sa.Uuid()))
    op.create_foreign_key(
        "fk_email_deliveries_job",
        "email_deliveries",
        "background_jobs",
        ["job_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_email_deliveries_password_reset_token",
        "email_deliveries",
        "password_reset_tokens",
        ["password_reset_token_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(
        op.f("ck_email_deliveries_message_type_allowed"), "email_deliveries", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_email_deliveries_message_type_allowed"),
        "email_deliveries",
        "message_type IN ('invitation_email', 'password_reset_email')",
    )
    op.create_check_constraint(
        op.f("ck_email_deliveries_exactly_one_source"),
        "email_deliveries",
        "num_nonnulls(invitation_id, password_reset_token_id) = 1",
    )
    op.create_check_constraint(
        op.f("ck_email_deliveries_source_matches_message_type"),
        "email_deliveries",
        "(message_type = 'invitation_email' AND organization_id IS NOT NULL "
        "AND invitation_id IS NOT NULL AND password_reset_token_id IS NULL) OR "
        "(message_type = 'password_reset_email' AND organization_id IS NULL "
        "AND invitation_id IS NULL AND password_reset_token_id IS NOT NULL)",
    )
    op.create_index(
        "ix_email_deliveries_password_reset_created",
        "email_deliveries",
        ["password_reset_token_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_email_deliveries_password_reset_created", table_name="email_deliveries")
    op.drop_constraint(
        op.f("ck_email_deliveries_source_matches_message_type"), "email_deliveries", type_="check"
    )
    op.drop_constraint(
        op.f("ck_email_deliveries_exactly_one_source"), "email_deliveries", type_="check"
    )
    op.drop_constraint(
        op.f("ck_email_deliveries_message_type_allowed"), "email_deliveries", type_="check"
    )
    op.drop_constraint(
        "fk_email_deliveries_password_reset_token", "email_deliveries", type_="foreignkey"
    )
    op.drop_constraint("fk_email_deliveries_job", "email_deliveries", type_="foreignkey")
    op.execute(sa.text("DELETE FROM email_deliveries WHERE password_reset_token_id IS NOT NULL"))
    op.create_check_constraint(
        op.f("ck_email_deliveries_message_type_allowed"),
        "email_deliveries",
        "message_type = 'invitation_email'",
    )
    op.drop_column("email_deliveries", "password_reset_token_id")
    op.alter_column(
        "email_deliveries", "invitation_id", existing_type=postgresql.UUID(), nullable=False
    )
    op.alter_column(
        "email_deliveries", "organization_id", existing_type=postgresql.UUID(), nullable=False
    )

    op.drop_constraint(
        op.f("ck_background_jobs_payload_matches_job_type"), "background_jobs", type_="check"
    )
    op.drop_constraint(
        op.f("ck_background_jobs_job_type_allowed"), "background_jobs", type_="check"
    )
    op.execute(sa.text("DELETE FROM background_jobs WHERE job_type = 'password_reset_email'"))
    op.create_check_constraint(
        op.f("ck_background_jobs_job_type_allowed"), "background_jobs", PREVIOUS_JOB_TYPES
    )
    op.create_check_constraint(
        op.f("ck_background_jobs_payload_matches_job_type"), "background_jobs", PREVIOUS_JOB_PAYLOAD
    )

    op.drop_index("ix_mfa_recovery_codes_credential_unused", table_name="mfa_recovery_codes")
    op.drop_table("mfa_recovery_codes")
    op.drop_index("ix_password_reset_tokens_user_active", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
