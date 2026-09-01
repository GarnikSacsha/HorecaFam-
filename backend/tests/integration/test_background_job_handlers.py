from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.session import create_engine, create_session_factory
from app.models import (
    BackgroundJob,
    BackgroundJobType,
    EmailDelivery,
    Invitation,
    PasswordResetToken,
)
from app.security.invitation_tokens import InvitationTokenManager
from app.security.passwords import PasswordManager
from app.security.tokens import hash_secret
from app.services.background_job_handlers import (
    BackgroundJobHandlers,
    TrainingNotificationMessage,
)
from app.services.background_jobs import ClaimedJob
from app.services.invitation_delivery import (
    EmailAdapterResult,
    InvitationEmailMessage,
    enqueue_invitation_email,
)
from app.services.password_recovery import request_password_reset
from app.services.password_reset_delivery import (
    PasswordResetEmailAdapterResult,
    PasswordResetEmailMessage,
    PasswordResetTokenManager,
)
from app.worker import run_worker_once
from tests.factories import make_invitation, make_organization, make_user


class FlakyInvitationAdapter:
    def __init__(self, *, fail_first: bool) -> None:
        self.fail_first = fail_first
        self.messages: list[InvitationEmailMessage] = []

    async def send_invitation(self, message: InvitationEmailMessage) -> EmailAdapterResult:
        self.messages.append(message)
        if self.fail_first and len(self.messages) == 1:
            raise TimeoutError("ambiguous-provider-response-with-secret")
        return EmailAdapterResult(provider="fake", provider_message_id="message-1")


class UnusedPasswordResetAdapter:
    async def send_password_reset(
        self, message: PasswordResetEmailMessage
    ) -> PasswordResetEmailAdapterResult:
        raise AssertionError(f"Unexpected Password Reset message for {message.email}")


class RecordingPasswordResetAdapter:
    def __init__(self) -> None:
        self.messages: list[PasswordResetEmailMessage] = []

    async def send_password_reset(
        self, message: PasswordResetEmailMessage
    ) -> PasswordResetEmailAdapterResult:
        self.messages.append(message)
        return PasswordResetEmailAdapterResult(
            provider="fake",
            provider_message_id="reset-message-1",
        )


class UnusedTrainingAdapter:
    async def send_training_notification(self, message: TrainingNotificationMessage) -> None:
        raise AssertionError(f"Unexpected Training notification for {message.assignment_id}")


async def setup_invitation_job(
    db_session: AsyncSession,
    *,
    token_manager: InvitationTokenManager,
) -> tuple[Invitation, BackgroundJob, EmailDelivery, str]:
    organization = make_organization()
    inviter = make_user(email_normalized="admin@example.com")
    db_session.add_all([organization, inviter])
    await db_session.flush()
    invitation = make_invitation(organization, inviter)
    db_session.add(invitation)
    await db_session.flush()
    raw_token = token_manager.derive(
        invitation.id,
        token_version=invitation.token_version,
        key_index=invitation.token_key_index,
    )
    invitation.token_hash = hash_secret(raw_token)
    job, delivery = await enqueue_invitation_email(db_session, invitation=invitation)
    await db_session.commit()
    return invitation, job, delivery, raw_token


def handler_registry(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    token_manager: InvitationTokenManager,
    adapter: FlakyInvitationAdapter,
) -> dict[BackgroundJobType, Callable[[ClaimedJob], Awaitable[None]]]:
    return BackgroundJobHandlers(
        session_factory,
        invitation_token_manager=token_manager,
        password_reset_token_manager=PasswordResetTokenManager(["r" * 32]),
        invitation_adapter=adapter,
        password_reset_adapter=UnusedPasswordResetAdapter(),
        training_notification_adapter=UnusedTrainingAdapter(),
    ).registry()


@pytest.mark.integration
async def test_ambiguous_provider_retry_reuses_the_same_valid_invitation_action(
    db_session: AsyncSession,
    migrated_test_database: Settings,
) -> None:
    token_manager = InvitationTokenManager([SecretStr("i" * 32)])
    adapter = FlakyInvitationAdapter(fail_first=True)
    invitation, job, delivery, raw_token = await setup_invitation_job(
        db_session,
        token_manager=token_manager,
    )
    engine = create_engine(migrated_test_database)
    session_factory = create_session_factory(engine)
    handlers = handler_registry(session_factory, token_manager=token_manager, adapter=adapter)
    try:
        assert await run_worker_once(
            session_factory,
            worker_id="worker-a",
            handlers=handlers,
            now=datetime.now(UTC),
        )
        await db_session.refresh(job)
        assert job.status == "pending"
        assert job.last_error_message == "Approved Job handler failed."

        assert await run_worker_once(
            session_factory,
            worker_id="worker-b",
            handlers=handlers,
            now=job.next_run_at,
        )
    finally:
        await engine.dispose()

    await db_session.refresh(job)
    await db_session.refresh(delivery)
    await db_session.refresh(invitation)
    assert job.status == "completed"
    assert delivery.status == "accepted"
    assert invitation.status == "pending"
    assert [message.token for message in adapter.messages] == [raw_token, raw_token]
    assert "ambiguous-provider-response-with-secret" not in (job.last_error_message or "")


@pytest.mark.integration
async def test_stale_invitation_is_suppressed_without_a_provider_call(
    db_session: AsyncSession,
    migrated_test_database: Settings,
) -> None:
    token_manager = InvitationTokenManager([SecretStr("i" * 32)])
    adapter = FlakyInvitationAdapter(fail_first=False)
    invitation, job, delivery, _raw_token = await setup_invitation_job(
        db_session,
        token_manager=token_manager,
    )
    invitation.status = "revoked"
    invitation.revoked_at = datetime.now(UTC)
    await db_session.commit()
    engine = create_engine(migrated_test_database)
    session_factory = create_session_factory(engine)
    try:
        assert await run_worker_once(
            session_factory,
            worker_id="worker-a",
            handlers=handler_registry(
                session_factory,
                token_manager=token_manager,
                adapter=adapter,
            ),
            now=datetime.now(UTC),
        )
    finally:
        await engine.dispose()

    await db_session.refresh(job)
    await db_session.refresh(delivery)
    assert job.status == "completed"
    assert delivery.status == "failed"
    assert delivery.error_code == "INVITATION_SUPERSEDED"
    assert adapter.messages == []


@pytest.mark.integration
async def test_password_reset_handler_reconstructs_active_token_and_finalizes_job(
    auth_settings: Settings,
    db_session: AsyncSession,
    migrated_test_database: Settings,
) -> None:
    now = datetime.now(UTC).replace(microsecond=0)
    user = make_user(
        email_normalized="worker-reset@example.com",
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
    job = await db_session.scalar(
        select(BackgroundJob).where(BackgroundJob.job_type == "password_reset_email")
    )
    assert token is not None and job is not None
    delivery = await db_session.scalar(select(EmailDelivery).where(EmailDelivery.job_id == job.id))
    assert delivery is not None
    reset_manager = PasswordResetTokenManager(
        [key.get_secret_value() for key in auth_settings.password_reset_token_hmac_keys]
    )
    reset_adapter = RecordingPasswordResetAdapter()
    engine = create_engine(migrated_test_database)
    session_factory = create_session_factory(engine)
    handlers = BackgroundJobHandlers(
        session_factory,
        invitation_token_manager=InvitationTokenManager([SecretStr("i" * 32)]),
        password_reset_token_manager=reset_manager,
        invitation_adapter=FlakyInvitationAdapter(fail_first=False),
        password_reset_adapter=reset_adapter,
        training_notification_adapter=UnusedTrainingAdapter(),
    ).registry()
    try:
        assert await run_worker_once(
            session_factory,
            worker_id="worker-reset",
            handlers=handlers,
            now=now.replace(microsecond=999999),
        )
    finally:
        await engine.dispose()

    await db_session.refresh(job)
    await db_session.refresh(delivery)
    assert job.status == "completed"
    assert delivery.status == "accepted"
    assert len(reset_adapter.messages) == 1
    assert reset_adapter.messages[0].email == user.email_normalized
    assert reset_manager.derive_matching(token) == reset_adapter.messages[0].token
