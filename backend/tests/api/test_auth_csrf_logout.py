from http.cookies import SimpleCookie

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent, Session
from app.security.passwords import PasswordManager
from app.security.tokens import hash_secret
from tests.factories.identity import make_user


async def _login(
    auth_client: AsyncClient,
    db_session: AsyncSession,
    *,
    email: str,
) -> tuple[str, str]:
    user = make_user(
        email_normalized=email,
        password_hash=PasswordManager().hash("correct-password"),
    )
    db_session.add(user)
    await db_session.commit()
    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct-password"},
    )
    assert response.status_code == 200
    return auth_client.cookies["horeca_session"], response.json()["csrf_token"]


async def _stored_session(
    db_session: AsyncSession,
    raw_session_token: str,
) -> Session:
    db_session.expire_all()
    record = await db_session.scalar(
        select(Session).where(Session.token_hash == hash_secret(raw_session_token))
    )
    assert record is not None
    return record


async def test_logout_revokes_only_current_session_and_clears_cookie(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    raw_token, csrf_token = await _login(
        auth_client,
        db_session,
        email="logout@example.com",
    )

    response = await auth_client.post(
        "/api/v1/auth/logout",
        headers={
            "Origin": "https://frontend.test",
            "X-CSRF-Token": csrf_token,
        },
    )

    assert response.status_code == 204
    assert response.content == b""
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    cleared = cookie["horeca_session"]
    assert cleared["max-age"] == "0"
    assert cleared["path"] == "/api/v1"
    assert cleared["secure"]
    assert cleared["httponly"]
    assert raw_token not in response.text
    record = await _stored_session(db_session, raw_token)
    assert record.revoked_at is not None
    assert record.revoke_reason == "logout"
    audit = await db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "session_revoked",
            AuditEvent.target_id == record.id,
        )
    )
    assert audit is not None
    assert audit.outcome == "success"


async def test_logout_without_csrf_does_not_revoke_session(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    raw_token, _csrf_token = await _login(
        auth_client,
        db_session,
        email="missing-csrf@example.com",
    )

    response = await auth_client.post("/api/v1/auth/logout")

    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_INVALID"
    assert (await _stored_session(db_session, raw_token)).revoked_at is None


async def test_logout_with_invalid_csrf_does_not_revoke_session(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    raw_token, _csrf_token = await _login(
        auth_client,
        db_session,
        email="invalid-csrf@example.com",
    )

    response = await auth_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": "not-the-issued-token"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_INVALID"
    assert (await _stored_session(db_session, raw_token)).revoked_at is None


async def test_csrf_token_from_another_session_is_rejected(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _first_raw_token, first_csrf = await _login(
        auth_client,
        db_session,
        email="first-session@example.com",
    )
    second_raw_token, _second_csrf = await _login(
        auth_client,
        db_session,
        email="second-session@example.com",
    )

    response = await auth_client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": first_csrf},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_INVALID"
    assert (await _stored_session(db_session, second_raw_token)).revoked_at is None


async def test_foreign_origin_is_rejected_before_logout_mutation(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    raw_token, csrf_token = await _login(
        auth_client,
        db_session,
        email="foreign-origin@example.com",
    )

    response = await auth_client.post(
        "/api/v1/auth/logout",
        headers={
            "Origin": "https://attacker.test",
            "X-CSRF-Token": csrf_token,
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_INVALID"
    assert (await _stored_session(db_session, raw_token)).revoked_at is None


async def test_credentialed_cors_preflight_allows_only_configured_origin(
    auth_client: AsyncClient,
) -> None:
    allowed = await auth_client.options(
        "/api/v1/auth/logout",
        headers={
            "Origin": "https://frontend.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-CSRF-Token",
        },
    )
    denied = await auth_client.options(
        "/api/v1/auth/logout",
        headers={
            "Origin": "https://attacker.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-CSRF-Token",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://frontend.test"
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
