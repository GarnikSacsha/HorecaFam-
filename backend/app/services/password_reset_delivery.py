import base64
import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import BackgroundJob, EmailDelivery, PasswordResetToken
from app.security.tokens import hash_secret


@dataclass(frozen=True)
class PasswordResetEmailMessage:
    email: str
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class PasswordResetEmailAdapterResult:
    provider: str
    provider_message_id: str


class PasswordResetEmailAdapter(Protocol):
    async def send_password_reset(
        self, message: PasswordResetEmailMessage
    ) -> PasswordResetEmailAdapterResult: ...


class PasswordResetTokenManager:
    def __init__(self, keys: list[str]) -> None:
        if not keys:
            raise ValueError("At least one password reset key is required")
        self._keys = keys

    def derive(self, token_id: UUID, *, key_index: int = 0) -> str:
        digest = hmac.new(
            self._keys[key_index].encode("utf-8"),
            f"password-reset:{token_id}".encode(),
            hashlib.sha256,
        ).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")

    def derive_matching(self, token: PasswordResetToken) -> str | None:
        for key_index in range(len(self._keys)):
            raw_token = self.derive(token.id, key_index=key_index)
            if hmac.compare_digest(hash_secret(raw_token), token.token_hash):
                return raw_token
        return None


async def enqueue_password_reset_email(
    db: AsyncSession,
    *,
    token: PasswordResetToken,
    provider: str = "fake",
) -> tuple[BackgroundJob, EmailDelivery]:
    job = BackgroundJob(
        organization_id=None,
        job_type="password_reset_email",
        status="pending",
        payload={"password_reset_token_id": str(token.id)},
        idempotency_key=f"password-reset:{token.id}",
    )
    db.add(job)
    await db.flush()
    delivery = EmailDelivery(
        organization_id=None,
        job_id=job.id,
        invitation_id=None,
        password_reset_token_id=token.id,
        message_type="password_reset_email",
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
    job.last_error_code = "PASSWORD_RESET_SUPERSEDED"
    job.last_error_message = "Password reset email token is no longer active."
    job.failed_at = now
    delivery.status = "failed"
    delivery.error_code = "PASSWORD_RESET_SUPERSEDED"
    delivery.failed_at = now


async def deliver_password_reset_email(
    db: AsyncSession,
    *,
    job_id: UUID,
    token_manager: PasswordResetTokenManager,
    adapter: PasswordResetEmailAdapter,
    now: datetime,
) -> bool:
    job = await db.scalar(select(BackgroundJob).where(BackgroundJob.id == job_id).with_for_update())
    if job is None or job.job_type != "password_reset_email":
        raise RuntimeError("Password reset email job is unavailable")
    if job.status != "pending":
        return False
    delivery = await db.scalar(
        select(EmailDelivery).where(EmailDelivery.job_id == job.id).with_for_update()
    )
    if delivery is None:
        raise RuntimeError("Password reset email delivery is unavailable")
    job.status = "processing"
    job.locked_by = "stage9-password-reset-adapter"
    job.locked_at = now
    job.started_at = job.started_at or now
    job.attempt_count += 1

    token_id = UUID(str(job.payload.get("password_reset_token_id")))
    token = await db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.id == token_id)
        .options(selectinload(PasswordResetToken.user))
        .with_for_update()
    )
    if (
        token is None
        or token.used_at is not None
        or token.revoked_at is not None
        or token.expires_at <= now
    ):
        _fail_superseded(job, delivery, now=now)
        return False
    raw_token = token_manager.derive_matching(token)
    if raw_token is None:
        _fail_superseded(job, delivery, now=now)
        return False

    result = await adapter.send_password_reset(
        PasswordResetEmailMessage(
            email=token.user.email_normalized,
            token=raw_token,
            expires_at=token.expires_at,
        )
    )
    delivery.provider = result.provider
    delivery.provider_message_id = result.provider_message_id
    delivery.status = "accepted"
    delivery.accepted_by_provider_at = now
    job.status = "completed"
    job.completed_at = now
    return True
