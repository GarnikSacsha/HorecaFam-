import asyncio
from datetime import timedelta
from uuid import uuid4

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import APIError
from app.models import AuthRateLimitBucket, MfaChallenge, Session
from app.security.passwords import PasswordManager
from app.security.tokens import hash_secret
from app.services.auth import authenticate_password, verify_mfa
from app.services.auth_security import lock_auth_email, lock_auth_user
from app.services.password_recovery import reset_password
from tests.api.test_auth_mfa_rbac import FIXED_NOW, _begin_mfa, _create_elevated_user, _totp_code
from tests.api.test_password_recovery import _request_reset_and_derive_token
from tests.factories.identity import make_user


async def test_mfa_budget_survives_new_login_and_alternate_verifiers(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    user, _, _ = await _create_elevated_user(
        db_session,
        auth_settings,
        email="shared-mfa@example.com",
        scope="platform_operator",
    )
    email = user.email_normalized
    wrong = "000000" if _totp_code() != "000000" else "999999"
    for index in range(5):
        await _begin_mfa(auth_client, email)
        route, code = (
            ("verify", wrong) if index % 2 == 0 else ("recovery/verify", "AAAA-BBBB-CCCC-DDDD")
        )
        response = await auth_client.post(f"/api/v1/auth/mfa/{route}", json={"code": code})
        assert response.status_code == 401
    await _begin_mfa(auth_client, email)
    denied = await auth_client.post("/api/v1/auth/mfa/verify", json={"code": _totp_code()})
    assert denied.status_code == 429
    assert denied.json()["code"] == "AUTH_RATE_LIMITED"
    auth_app.state.clock = lambda: FIXED_NOW + timedelta(minutes=16)
    await _begin_mfa(auth_client, email)
    from app.security.mfa import TotpVerifier
    from tests.api.test_auth_mfa_rbac import TOTP_SECRET

    allowed = await auth_client.post(
        "/api/v1/auth/mfa/verify",
        json={
            "code": TotpVerifier().generate(TOTP_SECRET, FIXED_NOW + timedelta(minutes=16)),
        },
    )
    assert allowed.status_code == 200


async def test_reset_revokes_preexisting_mfa_authority(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    user, _, _ = await _create_elevated_user(
        db_session,
        auth_settings,
        email="reset-mfa@example.com",
        scope="platform_operator",
    )
    raw = await _begin_mfa(auth_client, user.email_normalized)
    _, token = await _request_reset_and_derive_token(
        auth_client, db_session, auth_settings, email=user.email_normalized
    )
    response = await auth_client.post(
        "/api/v1/auth/password/reset", json={"token": token, "new_password": "replacement-password"}
    )
    assert response.status_code == 204
    denied = await auth_client.post("/api/v1/auth/mfa/verify", json={"code": _totp_code()})
    assert denied.status_code == 401
    assert denied.json()["code"] == "MFA_CHALLENGE_INVALID"
    db_session.expire_all()
    challenge = await db_session.scalar(
        select(MfaChallenge).where(MfaChallenge.token_hash == hash_secret(raw))
    )
    assert challenge is not None and challenge.used_at is not None
    assert await db_session.scalar(select(Session.id).where(Session.revoked_at.is_(None))) is None


async def test_current_password_budget_is_durable_and_preserves_account(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    user = make_user(
        email_normalized="reauth-budget@example.com",
        password_hash=PasswordManager().hash("correct-password"),
    )
    db_session.add(user)
    await db_session.commit()
    login = await auth_client.post(
        "/api/v1/auth/login", json={"email": user.email_normalized, "password": "correct-password"}
    )
    assert login.status_code == 200
    headers = {"X-CSRF-Token": login.json()["csrf_token"], "Origin": "https://frontend.test"}
    for _ in range(5):
        response = await auth_client.post(
            "/api/v1/auth/password/change",
            headers=headers,
            json={"current_password": "wrong-password", "new_password": "replacement-password"},
        )
        assert response.status_code == 401
    denied = await auth_client.post(
        "/api/v1/auth/password/change",
        headers=headers,
        json={"current_password": "correct-password", "new_password": "replacement-password"},
    )
    assert denied.status_code == 429
    auth_app.state.clock = lambda: FIXED_NOW + timedelta(minutes=16)
    allowed = await auth_client.post(
        "/api/v1/auth/password/change",
        headers=headers,
        json={"current_password": "correct-password", "new_password": "replacement-password"},
    )
    assert allowed.status_code == 204


async def test_change_password_revokes_challenge_but_keeps_current_session(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    user, _, _ = await _create_elevated_user(
        db_session, auth_settings, email="change-mfa@example.com", scope="platform_operator"
    )
    await _begin_mfa(auth_client, user.email_normalized)
    verified = await auth_client.post("/api/v1/auth/mfa/verify", json={"code": _totp_code()})
    assert verified.status_code == 200
    csrf = verified.json()["csrf_token"]
    login = await auth_client.post(
        "/api/v1/auth/login", json={"email": user.email_normalized, "password": "correct-password"}
    )
    assert login.status_code == 202
    changed = await auth_client.post(
        "/api/v1/auth/password/change",
        headers={"X-CSRF-Token": csrf, "Origin": "https://frontend.test"},
        json={"current_password": "correct-password", "new_password": "replacement-password"},
    )
    assert changed.status_code == 204
    denied = await auth_client.post("/api/v1/auth/mfa/verify", json={"code": _totp_code()})
    assert denied.status_code == 401
    assert denied.json()["code"] == "MFA_CHALLENGE_INVALID"
    current = await auth_client.get("/api/v1/auth/session")
    assert current.status_code == 200


async def test_reset_serializes_against_waiting_mfa_verification(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    user, _, _ = await _create_elevated_user(
        db_session, auth_settings, email="race-reset@example.com", scope="platform_operator"
    )
    user_id = user.id
    raw = await _begin_mfa(auth_client, user.email_normalized)
    _, token = await _request_reset_and_derive_token(
        auth_client, db_session, auth_settings, email=user.email_normalized
    )
    await db_session.rollback()

    async def competing_verify() -> str:
        async with auth_app.state.session_factory() as db:
            try:
                await verify_mfa(
                    db,
                    raw_challenge=raw,
                    code=_totp_code(),
                    settings=auth_settings,
                    now=FIXED_NOW,
                    request_id=uuid4(),
                    user_agent=None,
                )
                return "unexpected_session"
            except APIError as error:
                await db.rollback()
                return error.code

    async with auth_app.state.session_factory() as db:
        await lock_auth_user(db, user_id)
        waiter = asyncio.create_task(competing_verify())
        await asyncio.sleep(0.05)
        assert not waiter.done()
        await reset_password(
            db,
            raw_token=token,
            new_password="replacement-password",
            settings=auth_settings,
            passwords=auth_app.state.password_manager,
            now=FIXED_NOW,
            request_id=uuid4(),
        )
    assert await asyncio.wait_for(waiter, 5) == "MFA_CHALLENGE_INVALID"
    assert await db_session.scalar(select(Session.id).where(Session.revoked_at.is_(None))) is None


async def test_parallel_mfa_failures_keep_exact_shared_budget(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    user, _, _ = await _create_elevated_user(
        db_session, auth_settings, email="parallel-mfa@example.com", scope="platform_operator"
    )
    raw = await _begin_mfa(auth_client, user.email_normalized)
    wrong = "000000" if _totp_code() != "000000" else "999999"

    async def attempt() -> str:
        async with auth_app.state.session_factory() as db:
            try:
                await verify_mfa(
                    db,
                    raw_challenge=raw,
                    code=wrong,
                    settings=auth_settings,
                    now=FIXED_NOW,
                    request_id=uuid4(),
                    user_agent=None,
                )
            except APIError as error:
                await db.rollback()
                return error.code
            return "unexpected_session"

    results = await asyncio.wait_for(asyncio.gather(*(attempt() for _ in range(8))), 10)
    assert results.count("MFA_CODE_INVALID") == 5
    assert results.count("MFA_CHALLENGE_INVALID") == 3
    bucket = await db_session.scalar(
        select(AuthRateLimitBucket).where(AuthRateLimitBucket.action == "mfa")
    )
    assert bucket is not None and bucket.failure_count == 5


async def test_password_change_preserves_session_activity(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    user = make_user(
        email_normalized="session-activity@example.com",
        password_hash=PasswordManager().hash("correct-password"),
    )
    db_session.add(user)
    await db_session.commit()
    login = await auth_client.post(
        "/api/v1/auth/login", json={"email": user.email_normalized, "password": "correct-password"}
    )
    assert login.status_code == 200
    auth_app.state.clock = lambda: FIXED_NOW + timedelta(days=13)
    changed = await auth_client.post(
        "/api/v1/auth/password/change",
        headers={"X-CSRF-Token": login.json()["csrf_token"], "Origin": "https://frontend.test"},
        json={"current_password": "correct-password", "new_password": "replacement-password"},
    )
    assert changed.status_code == 204
    record = await db_session.scalar(select(Session).where(Session.user_id == user.id))
    assert record is not None and record.last_seen_at == FIXED_NOW + timedelta(days=13)
    auth_app.state.clock = lambda: FIXED_NOW + timedelta(days=15)
    assert (await auth_client.get("/api/v1/auth/session")).status_code == 200


async def test_busy_login_rejects_without_waiting_for_account_lock(
    auth_app: FastAPI,
    auth_settings: Settings,
) -> None:
    async with auth_app.state.session_factory() as owner:
        await lock_auth_email(owner, "busy-login@example.com")
        async with auth_app.state.session_factory() as contender:
            try:
                await asyncio.wait_for(
                    authenticate_password(
                        contender,
                        email="busy-login@example.com",
                        password="correct-password",
                        settings=auth_settings,
                        passwords=auth_app.state.password_manager,
                        now=FIXED_NOW,
                    ),
                    timeout=1,
                )
            except APIError as error:
                assert error.code == "AUTH_RATE_LIMITED"
                assert error.status_code == 429
            else:
                raise AssertionError("Busy login must be rejected")
            finally:
                await contender.rollback()
        await owner.rollback()
