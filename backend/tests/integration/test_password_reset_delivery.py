from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import BackgroundJob, EmailDelivery, PasswordResetToken
from app.security.passwords import PasswordManager
from app.services.password_recovery import request_password_reset
from app.services.password_reset_delivery import (
    PasswordResetEmailAdapterResult,
    PasswordResetEmailMessage,
    PasswordResetTokenManager,
    deliver_password_reset_email,
)
from tests.factories.identity import make_user


@dataclass
class RecordingAdapter:
    message: PasswordResetEmailMessage | None = None

    async def send_password_reset(
        self, message: PasswordResetEmailMessage
    ) -> PasswordResetEmailAdapterResult:
        self.message = message
        return PasswordResetEmailAdapterResult(
            provider="fake",
            provider_message_id="reset-message-1",
        )


async def test_password_reset_delivery_reconstructs_only_active_token(
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    user = make_user(
        email_normalized="delivery@example.com",
        password_hash=PasswordManager().hash("correct-password"),
    )
    db_session.add(user)
    await db_session.commit()
    await request_password_reset(
        db_session,
        email=user.email_normalized,
        settings=auth_settings,
        now=now,
        request_id=user.id,
    )
    token = await db_session.scalar(select(PasswordResetToken))
    job = await db_session.scalar(select(BackgroundJob))
    assert token is not None and job is not None
    manager = PasswordResetTokenManager(
        [key.get_secret_value() for key in auth_settings.password_reset_token_hmac_keys]
    )
    adapter = RecordingAdapter()

    delivered = await deliver_password_reset_email(
        db_session,
        job_id=job.id,
        token_manager=manager,
        adapter=adapter,
        now=now + timedelta(seconds=1),
    )
    await db_session.commit()

    assert delivered is True
    assert adapter.message is not None
    assert adapter.message.email == user.email_normalized
    assert adapter.message.token != token.token_hash
    assert manager.derive_matching(token) == adapter.message.token
    delivery = await db_session.scalar(select(EmailDelivery).where(EmailDelivery.job_id == job.id))
    assert delivery is not None
    assert delivery.status == "accepted"
    assert delivery.provider_message_id == "reset-message-1"


async def test_password_reset_delivery_suppresses_revoked_token(
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    user = make_user(
        email_normalized="superseded-delivery@example.com",
        password_hash=PasswordManager().hash("correct-password"),
    )
    db_session.add(user)
    await db_session.commit()
    await request_password_reset(
        db_session,
        email=user.email_normalized,
        settings=auth_settings,
        now=now,
        request_id=user.id,
    )
    token = await db_session.scalar(select(PasswordResetToken))
    job = await db_session.scalar(select(BackgroundJob))
    assert token is not None and job is not None
    token.revoked_at = now + timedelta(seconds=1)
    await db_session.commit()
    adapter = RecordingAdapter()
    manager = PasswordResetTokenManager(
        [key.get_secret_value() for key in auth_settings.password_reset_token_hmac_keys]
    )

    delivered = await deliver_password_reset_email(
        db_session,
        job_id=job.id,
        token_manager=manager,
        adapter=adapter,
        now=now + timedelta(seconds=2),
    )
    await db_session.commit()

    assert delivered is False
    assert adapter.message is None
    delivery = await db_session.scalar(select(EmailDelivery).where(EmailDelivery.job_id == job.id))
    assert delivery is not None
    assert delivery.status == "failed"
    assert delivery.error_code == "PASSWORD_RESET_SUPERSEDED"
