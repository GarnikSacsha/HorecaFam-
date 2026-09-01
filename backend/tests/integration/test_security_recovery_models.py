from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import app.models as models
from tests.factories.auth import make_mfa_recovery_code, make_password_reset_token
from tests.factories.identity import make_user


async def assert_integrity_error(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()


@pytest.mark.integration
async def test_security_recovery_schema_is_migration_managed(
    db_session: AsyncSession,
) -> None:
    for relation_name in ("password_reset_tokens", "mfa_recovery_codes"):
        relation = await db_session.scalar(
            text("SELECT to_regclass(:relation_name)"),
            {"relation_name": relation_name},
        )
        assert relation == relation_name


@pytest.mark.integration
async def test_password_reset_token_requires_one_terminal_state(
    db_session: AsyncSession,
) -> None:
    user = make_user()
    db_session.add(user)
    await db_session.flush()
    now = datetime.now(UTC)
    db_session.add(make_password_reset_token(user, used_at=now, revoked_at=now))

    await assert_integrity_error(db_session)


@pytest.mark.integration
async def test_mfa_recovery_code_hash_is_unique(
    db_session: AsyncSession,
) -> None:
    user = make_user()
    db_session.add(user)
    await db_session.flush()
    credential = models.MfaCredential(
        user_id=user.id,
        type="totp",
        secret_encrypted="encrypted-test-secret",
        confirmed_at=datetime.now(UTC),
    )
    db_session.add(credential)
    await db_session.flush()
    db_session.add_all(
        [
            make_mfa_recovery_code(credential, code_hash="c" * 64),
            make_mfa_recovery_code(credential, code_hash="c" * 64),
        ]
    )

    await assert_integrity_error(db_session)


@pytest.mark.integration
async def test_password_reset_delivery_has_exactly_one_source(
    db_session: AsyncSession,
) -> None:
    user = make_user()
    db_session.add(user)
    await db_session.flush()
    now = datetime.now(UTC)
    reset_token = make_password_reset_token(
        user,
        token_hash="t" * 64,
        expires_at=now + timedelta(minutes=30),
    )
    db_session.add(reset_token)
    await db_session.flush()
    job = models.BackgroundJob(
        organization_id=None,
        job_type="password_reset_email",
        status="pending",
        payload={"password_reset_token_id": str(reset_token.id)},
        idempotency_key=f"password-reset:{reset_token.id}",
    )
    db_session.add(job)
    await db_session.flush()
    db_session.add(
        models.EmailDelivery(
            organization_id=None,
            job_id=job.id,
            invitation_id=None,
            password_reset_token_id=reset_token.id,
            message_type="password_reset_email",
            provider="fake",
            status="pending",
        )
    )

    await db_session.commit()
