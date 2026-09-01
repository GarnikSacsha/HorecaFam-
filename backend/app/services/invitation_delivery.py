import hmac
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BackgroundJob, EmailDelivery, Invitation
from app.security.invitation_tokens import InvitationTokenManager
from app.security.tokens import hash_secret


@dataclass(frozen=True)
class InvitationEmailMessage:
    organization_id: UUID
    invitation_id: UUID
    email: str
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class EmailAdapterResult:
    provider: str
    provider_message_id: str


class InvitationEmailAdapter(Protocol):
    async def send_invitation(self, message: InvitationEmailMessage) -> EmailAdapterResult: ...


async def enqueue_invitation_email(
    db: AsyncSession,
    *,
    invitation: Invitation,
    provider: str = "fake",
) -> tuple[BackgroundJob, EmailDelivery]:
    job = BackgroundJob(
        organization_id=invitation.organization_id,
        job_type="invitation_email",
        status="pending",
        payload={
            "invitation_id": str(invitation.id),
            "token_version": invitation.token_version,
        },
        idempotency_key=f"invitation:{invitation.id}:v{invitation.token_version}",
    )
    db.add(job)
    await db.flush()
    delivery = EmailDelivery(
        organization_id=invitation.organization_id,
        job_id=job.id,
        invitation_id=invitation.id,
        message_type="invitation_email",
        provider=provider,
        status="pending",
    )
    db.add(delivery)
    await db.flush()
    return job, delivery


def _fail_superseded(
    job: BackgroundJob,
    delivery: EmailDelivery,
    *,
    now: datetime,
) -> None:
    job.status = "failed"
    job.last_error_code = "INVITATION_SUPERSEDED"
    job.last_error_message = "Invitation email job version is no longer current."
    job.failed_at = now
    delivery.status = "failed"
    delivery.error_code = "INVITATION_SUPERSEDED"
    delivery.failed_at = now


async def deliver_invitation_email(
    db: AsyncSession,
    *,
    job_id: UUID,
    token_manager: InvitationTokenManager,
    adapter: InvitationEmailAdapter,
    now: datetime,
) -> bool:
    job = await db.scalar(select(BackgroundJob).where(BackgroundJob.id == job_id).with_for_update())
    if job is None or job.job_type != "invitation_email":
        raise RuntimeError("Invitation email job is unavailable")
    if job.status != "pending":
        return False
    delivery = await db.scalar(
        select(EmailDelivery).where(EmailDelivery.job_id == job.id).with_for_update()
    )
    if delivery is None:
        raise RuntimeError("Invitation email delivery is unavailable")
    job.status = "processing"
    job.locked_by = "stage3-invitation-adapter"
    job.locked_at = now
    job.started_at = job.started_at or now
    job.attempt_count += 1
    invitation_id = UUID(str(job.payload.get("invitation_id")))
    token_version = int(job.payload.get("token_version", 0))
    invitation = await db.scalar(
        select(Invitation)
        .where(
            Invitation.id == invitation_id,
            Invitation.organization_id == job.organization_id,
        )
        .with_for_update()
    )
    if invitation is None:
        raise RuntimeError("Invitation email source is unavailable")
    if (
        invitation.status != "pending"
        or invitation.expires_at <= now
        or invitation.token_version != token_version
    ):
        _fail_superseded(job, delivery, now=now)
        return False

    raw_token = token_manager.derive(
        invitation.id,
        token_version=invitation.token_version,
        key_index=invitation.token_key_index,
    )
    if not hmac.compare_digest(hash_secret(raw_token), invitation.token_hash):
        _fail_superseded(job, delivery, now=now)
        return False

    result = await adapter.send_invitation(
        InvitationEmailMessage(
            organization_id=invitation.organization_id,
            invitation_id=invitation.id,
            email=invitation.email_normalized,
            token=raw_token,
            expires_at=invitation.expires_at,
        )
    )
    delivery.provider = result.provider
    delivery.provider_message_id = result.provider_message_id
    delivery.status = "accepted"
    delivery.accepted_by_provider_at = now
    job.status = "completed"
    job.completed_at = now
    return True


async def deliver_claimed_invitation_email(
    db: AsyncSession,
    *,
    job_id: UUID,
    token_manager: InvitationTokenManager,
    adapter: InvitationEmailAdapter,
    now: datetime,
) -> bool:
    job = await db.scalar(select(BackgroundJob).where(BackgroundJob.id == job_id))
    if job is None or job.job_type != "invitation_email" or job.status != "processing":
        raise RuntimeError("Claimed Invitation email Job is unavailable")
    delivery = await db.scalar(
        select(EmailDelivery).where(EmailDelivery.job_id == job.id).with_for_update()
    )
    if delivery is None or delivery.message_type != "invitation_email":
        raise RuntimeError("Invitation email delivery is unavailable")
    invitation_id = UUID(str(job.payload.get("invitation_id")))
    token_version = int(job.payload.get("token_version", 0))
    invitation = await db.scalar(
        select(Invitation)
        .where(
            Invitation.id == invitation_id,
            Invitation.organization_id == job.organization_id,
        )
        .with_for_update()
    )
    if (
        invitation is None
        or invitation.status != "pending"
        or invitation.expires_at <= now
        or invitation.token_version != token_version
    ):
        delivery.status = "failed"
        delivery.error_code = "INVITATION_SUPERSEDED"
        delivery.failed_at = now
        return False
    raw_token = token_manager.derive(
        invitation.id,
        token_version=invitation.token_version,
        key_index=invitation.token_key_index,
    )
    if not hmac.compare_digest(hash_secret(raw_token), invitation.token_hash):
        delivery.status = "failed"
        delivery.error_code = "INVITATION_SUPERSEDED"
        delivery.failed_at = now
        return False
    result = await adapter.send_invitation(
        InvitationEmailMessage(
            organization_id=invitation.organization_id,
            invitation_id=invitation.id,
            email=invitation.email_normalized,
            token=raw_token,
            expires_at=invitation.expires_at,
        )
    )
    delivery.provider = result.provider
    delivery.provider_message_id = result.provider_message_id
    delivery.status = "accepted"
    delivery.accepted_by_provider_at = now
    delivery.error_code = None
    delivery.failed_at = None
    return True
