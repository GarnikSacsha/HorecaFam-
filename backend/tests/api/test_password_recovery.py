from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import (
    AdminAccess,
    AuditEvent,
    BackgroundJob,
    EmailDelivery,
    PasswordResetToken,
    Session,
    User,
)
from app.security.passwords import PasswordManager
from app.security.tokens import generate_opaque_token, hash_secret
from app.services.password_reset_delivery import PasswordResetTokenManager
from app.services.sessions import derive_csrf_token
from tests.factories.auth import make_session
from tests.factories.identity import make_user


async def test_password_forgot_is_non_enumerating_and_queues_safe_outbox(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = make_user(
        email_normalized="known@example.com",
        password_hash=PasswordManager().hash("correct-password"),
    )
    db_session.add(user)
    await db_session.commit()

    known = await auth_client.post(
        "/api/v1/auth/password/forgot",
        json={"email": "Known@Example.com"},
    )
    unknown = await auth_client.post(
        "/api/v1/auth/password/forgot",
        json={"email": "unknown@example.com"},
    )

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json() == {"status": "accepted"}
    token = await db_session.scalar(select(PasswordResetToken))
    job = await db_session.scalar(select(BackgroundJob))
    delivery = await db_session.scalar(select(EmailDelivery))
    assert token is not None
    assert token.user_id == user.id
    assert job is not None
    assert job.payload == {"password_reset_token_id": str(token.id)}
    assert delivery is not None
    assert delivery.password_reset_token_id == token.id
    combined = f"{known.text}{unknown.text}{job.payload}"
    assert token.token_hash not in combined
    assert "correct-password" not in combined


async def _request_reset_and_derive_token(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    settings: Settings,
    *,
    email: str,
) -> tuple[PasswordResetToken, str]:
    response = await auth_client.post(
        "/api/v1/auth/password/forgot",
        json={"email": email},
    )
    assert response.status_code == 202
    token = await db_session.scalar(
        select(PasswordResetToken).order_by(PasswordResetToken.created_at.desc())
    )
    assert token is not None
    manager = PasswordResetTokenManager(
        [key.get_secret_value() for key in settings.password_reset_token_hmac_keys]
    )
    raw_token = manager.derive_matching(token)
    assert raw_token is not None
    return token, raw_token


async def test_password_reset_is_one_time_and_revokes_all_sessions(
    auth_client: AsyncClient,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    user = make_user(
        email_normalized="reset@example.com",
        password_hash=PasswordManager().hash("old-password"),
    )
    db_session.add(user)
    await db_session.flush()
    first_session = make_session(user, token_hash="1" * 64, csrf_token_hash="2" * 64)
    second_session = make_session(user, token_hash="3" * 64, csrf_token_hash="4" * 64)
    db_session.add_all([first_session, second_session])
    await db_session.commit()
    user_id = user.id
    token, raw_token = await _request_reset_and_derive_token(
        auth_client,
        db_session,
        auth_settings,
        email=user.email_normalized,
    )
    token_id = token.id

    response = await auth_client.post(
        "/api/v1/auth/password/reset",
        json={"token": raw_token, "new_password": "new-password"},
    )
    replay = await auth_client.post(
        "/api/v1/auth/password/reset",
        json={"token": raw_token, "new_password": "another-password"},
    )

    assert response.status_code == 204
    assert replay.status_code == 400
    assert replay.json()["code"] == "PASSWORD_RESET_TOKEN_INVALID"
    db_session.expire_all()
    refreshed_user = await db_session.get(User, user_id)
    refreshed_token = await db_session.get(PasswordResetToken, token_id)
    sessions = list(
        (await db_session.scalars(select(Session).where(Session.user_id == user_id))).all()
    )
    assert refreshed_user is not None
    assert refreshed_user.password_hash is not None
    assert PasswordManager().verify(refreshed_user.password_hash, "new-password")
    assert refreshed_token is not None
    assert refreshed_token.used_at is not None
    assert all(record.revoked_at is not None for record in sessions)
    assert all(record.revoke_reason == "password_reset" for record in sessions)
    audit = await db_session.scalar(
        select(AuditEvent).where(AuditEvent.action == "password_reset_completed")
    )
    assert audit is not None
    assert audit.new_values == {"revoked_session_count": 2}
    assert raw_token not in str(audit.new_values)


async def test_password_forgot_rotates_prior_unused_token(
    auth_client: AsyncClient,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    user = make_user(
        email_normalized="rotate@example.com",
        password_hash=PasswordManager().hash("correct-password"),
    )
    db_session.add(user)
    await db_session.commit()
    first, first_raw = await _request_reset_and_derive_token(
        auth_client,
        db_session,
        auth_settings,
        email=user.email_normalized,
    )
    first_id = first.id
    second, second_raw = await _request_reset_and_derive_token(
        auth_client,
        db_session,
        auth_settings,
        email=user.email_normalized,
    )
    second_id = second.id

    db_session.expire_all()
    refreshed_first = await db_session.get(PasswordResetToken, first_id)
    assert refreshed_first is not None
    assert refreshed_first.revoked_at is not None
    assert second_id != first_id
    assert second_raw != first_raw
    stale = await auth_client.post(
        "/api/v1/auth/password/reset",
        json={"token": first_raw, "new_password": "new-password"},
    )
    assert stale.status_code == 400
    assert stale.json()["code"] == "PASSWORD_RESET_TOKEN_INVALID"


@pytest.mark.parametrize("known_account", [False, True])
async def test_password_forgot_throttles_known_and_unknown_subjects(
    known_account: bool,
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    email = "throttled@example.com"
    if known_account:
        db_session.add(
            make_user(
                email_normalized=email,
                password_hash=PasswordManager().hash("correct-password"),
            )
        )
        await db_session.commit()
    for _ in range(5):
        response = await auth_client.post(
            "/api/v1/auth/password/forgot",
            json={"email": email},
        )
        assert response.status_code == 202

    blocked = await auth_client.post(
        "/api/v1/auth/password/forgot",
        json={"email": email},
    )

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "AUTH_RATE_LIMITED"
    assert email not in blocked.text


async def test_password_reset_rejects_expired_token_without_mutation(
    auth_app: FastAPI,
    auth_client: AsyncClient,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 9, 1, 12, tzinfo=UTC)
    auth_app.state.clock = lambda: now
    user = make_user(
        email_normalized="expired-reset@example.com",
        password_hash=PasswordManager().hash("old-password"),
    )
    db_session.add(user)
    await db_session.commit()
    _token, raw_token = await _request_reset_and_derive_token(
        auth_client,
        db_session,
        auth_settings,
        email=user.email_normalized,
    )
    user_id = user.id
    now += timedelta(minutes=31)

    response = await auth_client.post(
        "/api/v1/auth/password/reset",
        json={"token": raw_token, "new_password": "new-password"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "PASSWORD_RESET_TOKEN_INVALID"
    db_session.expire_all()
    refreshed_user = await db_session.get(User, user_id)
    assert refreshed_user is not None and refreshed_user.password_hash is not None
    assert PasswordManager().verify(refreshed_user.password_hash, "old-password")


async def test_password_change_revokes_other_sessions_but_preserves_current(
    auth_client: AsyncClient,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    user = make_user(
        email_normalized="change@example.com",
        password_hash=PasswordManager().hash("old-password"),
    )
    db_session.add(user)
    await db_session.commit()
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email_normalized, "password": "old-password"},
    )
    assert login.status_code == 200
    current_id = login.json()["session"]["id"]
    other = make_session(
        user,
        token_hash="5" * 64,
        csrf_token_hash="6" * 64,
    )
    db_session.add(other)
    await db_session.commit()
    other_id = other.id
    user_id = user.id

    response = await auth_client.post(
        "/api/v1/auth/password/change",
        headers={
            "Origin": "https://frontend.test",
            "X-CSRF-Token": login.json()["csrf_token"],
        },
        json={"current_password": "old-password", "new_password": "new-password"},
    )

    assert response.status_code == 204
    db_session.expire_all()
    current = await db_session.get(Session, current_id)
    refreshed_other = await db_session.get(Session, other_id)
    refreshed_user = await db_session.get(User, user_id)
    assert current is not None and current.revoked_at is None
    assert refreshed_other is not None and refreshed_other.revoke_reason == "password_change"
    assert refreshed_user is not None and refreshed_user.password_hash is not None
    assert PasswordManager().verify(refreshed_user.password_hash, "new-password")


async def test_password_change_requires_csrf(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = make_user(
        email_normalized="csrf-change@example.com",
        password_hash=PasswordManager().hash("old-password"),
    )
    db_session.add(user)
    await db_session.commit()
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email_normalized, "password": "old-password"},
    )
    assert login.status_code == 200

    response = await auth_client.post(
        "/api/v1/auth/password/change",
        json={"current_password": "old-password", "new_password": "new-password"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_INVALID"


async def test_elevated_password_change_requires_recent_mfa(
    auth_app: FastAPI,
    auth_client: AsyncClient,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 9, 1, 12, tzinfo=UTC)
    auth_app.state.clock = lambda: now
    user = make_user(
        email_normalized="elevated-change@example.com",
        password_hash=PasswordManager().hash("old-password"),
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        AdminAccess(
            user_id=user.id,
            scope="platform_operator",
            status="active",
            granted_at=now - timedelta(days=1),
        )
    )
    raw_session = generate_opaque_token()
    hmac_key = auth_settings.auth_throttle_hmac_key
    assert hmac_key is not None
    csrf_token = derive_csrf_token(raw_session, hmac_key)
    session = make_session(
        user,
        token_hash=hash_secret(raw_session),
        csrf_token_hash=hash_secret(csrf_token),
        mfa_verified_at=now - timedelta(minutes=16),
        last_seen_at=now,
        absolute_expires_at=now + timedelta(days=1),
    )
    db_session.add(session)
    await db_session.commit()
    auth_client.cookies.set("horeca_session", raw_session, path="/api/v1")

    response = await auth_client.post(
        "/api/v1/auth/password/change",
        headers={
            "Origin": "https://frontend.test",
            "X-CSRF-Token": csrf_token,
        },
        json={"current_password": "old-password", "new_password": "new-password"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "RECENT_MFA_REQUIRED"
