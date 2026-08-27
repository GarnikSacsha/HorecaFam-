from datetime import UTC, datetime, timedelta
from typing import Any

from app.models import BackgroundJob, EmailDelivery, Invitation, Organization, User


def make_invitation(
    organization: Organization,
    inviter: User,
    **overrides: Any,
) -> Invitation:
    values: dict[str, Any] = {
        "organization_id": organization.id,
        "email_normalized": "employee@example.com",
        "token_hash": "a" * 64,
        "token_version": 1,
        "token_key_index": 0,
        "status": "pending",
        "invited_by_user_id": inviter.id,
        "expires_at": datetime.now(UTC) + timedelta(hours=72),
    }
    values.update(overrides)
    return Invitation(**values)


def make_background_job(
    organization: Organization,
    invitation: Invitation,
    **overrides: Any,
) -> BackgroundJob:
    values: dict[str, Any] = {
        "organization_id": organization.id,
        "job_type": "invitation_email",
        "status": "pending",
        "payload": {
            "invitation_id": str(invitation.id),
            "token_version": invitation.token_version,
        },
        "idempotency_key": f"invitation:{invitation.id}:v{invitation.token_version}",
        "priority": 0,
        "attempt_count": 0,
        "max_attempts": 5,
        "next_run_at": datetime.now(UTC),
    }
    values.update(overrides)
    return BackgroundJob(**values)


def make_email_delivery(
    organization: Organization,
    invitation: Invitation,
    job: BackgroundJob,
    **overrides: Any,
) -> EmailDelivery:
    values: dict[str, Any] = {
        "organization_id": organization.id,
        "job_id": job.id,
        "invitation_id": invitation.id,
        "message_type": "invitation_email",
        "provider": "fake",
        "status": "pending",
    }
    values.update(overrides)
    return EmailDelivery(**values)
