"""Окремі бюджети MFA та повторної автентифікації не залежать від нового входу."""

from collections.abc import Sequence

from alembic import op

revision: str = "0019_auth_security_budgets"
down_revision: str | None = "0018_job_runtime"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_auth_rate_limit_buckets_action_allowed"), "auth_rate_limit_buckets", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_auth_rate_limit_buckets_action_allowed"),
        "auth_rate_limit_buckets",
        "action IN ('login', 'password_forgot', 'password_reset', 'mfa', 'reauth')",
    )


def downgrade() -> None:
    # Нові бюджети зберігаються: downgrade відхиляється, доки вони існують.
    op.drop_constraint(
        op.f("ck_auth_rate_limit_buckets_action_allowed"), "auth_rate_limit_buckets", type_="check"
    )
    op.create_check_constraint(
        op.f("ck_auth_rate_limit_buckets_action_allowed"),
        "auth_rate_limit_buckets",
        "action IN ('login', 'password_forgot', 'password_reset')",
    )
