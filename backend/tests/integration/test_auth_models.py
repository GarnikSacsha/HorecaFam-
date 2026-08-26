from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdminAccess,
    AuthRateLimitBucket,
    MfaChallenge,
    MfaCredential,
    Session,
)
from tests.factories.identity import make_organization, make_user


@pytest.mark.integration
async def test_admin_access_requires_scope_consistent_organization(
    db_session: AsyncSession,
) -> None:
    user = make_user()
    organization = make_organization()
    db_session.add_all([user, organization])
    await db_session.flush()
    db_session.add(
        AdminAccess(
            user_id=user.id,
            scope="platform_operator",
            organization_id=organization.id,
            status="active",
            granted_at=datetime.now(UTC),
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.integration
async def test_only_one_active_organization_admin_grant(
    db_session: AsyncSession,
) -> None:
    user = make_user()
    organization = make_organization()
    db_session.add_all([user, organization])
    await db_session.flush()
    granted_at = datetime.now(UTC)
    db_session.add_all(
        [
            AdminAccess(
                user_id=user.id,
                scope="organization_admin",
                organization_id=organization.id,
                status="active",
                granted_at=granted_at,
            ),
            AdminAccess(
                user_id=user.id,
                scope="organization_admin",
                organization_id=organization.id,
                status="active",
                granted_at=granted_at,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.integration
async def test_session_requires_future_absolute_expiry(db_session: AsyncSession) -> None:
    user = make_user()
    db_session.add(user)
    await db_session.flush()
    now = datetime.now(UTC)
    db_session.add(
        Session(
            user_id=user.id,
            token_hash="a" * 64,
            csrf_token_hash="b" * 64,
            last_seen_at=now,
            absolute_expires_at=now - timedelta(seconds=1),
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.integration
async def test_session_token_and_csrf_hashes_are_unique(db_session: AsyncSession) -> None:
    user = make_user()
    db_session.add(user)
    await db_session.flush()
    now = datetime.now(UTC)
    values = {
        "user_id": user.id,
        "token_hash": "a" * 64,
        "csrf_token_hash": "b" * 64,
        "last_seen_at": now,
        "absolute_expires_at": now + timedelta(days=90),
    }
    db_session.add_all([Session(**values), Session(**values)])

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.integration
async def test_only_one_active_confirmed_totp_credential(db_session: AsyncSession) -> None:
    user = make_user()
    db_session.add(user)
    await db_session.flush()
    confirmed_at = datetime.now(UTC)
    db_session.add_all(
        [
            MfaCredential(
                user_id=user.id,
                type="totp",
                secret_encrypted="encrypted-one",
                confirmed_at=confirmed_at,
            ),
            MfaCredential(
                user_id=user.id,
                type="totp",
                secret_encrypted="encrypted-two",
                confirmed_at=confirmed_at,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.integration
async def test_mfa_challenge_limits_failed_attempts(db_session: AsyncSession) -> None:
    user = make_user()
    db_session.add(user)
    await db_session.flush()
    now = datetime.now(UTC)
    db_session.add(
        MfaChallenge(
            user_id=user.id,
            token_hash="c" * 64,
            expires_at=now + timedelta(minutes=5),
            failed_attempts=6,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.integration
async def test_auth_rate_limit_bucket_is_unique_per_action_and_subject(
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    values = {
        "action": "login",
        "subject_hash": "d" * 64,
        "window_started_at": now,
        "failure_count": 1,
    }
    db_session.add_all([AuthRateLimitBucket(**values), AuthRateLimitBucket(**values)])

    with pytest.raises(IntegrityError):
        await db_session.flush()
