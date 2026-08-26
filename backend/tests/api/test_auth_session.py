from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Session
from app.security.passwords import PasswordManager
from app.security.tokens import hash_secret
from tests.factories.identity import make_membership, make_organization, make_user


async def _login(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> tuple[str, str]:
    user = make_user(password_hash=PasswordManager().hash("correct-password"))
    organization = make_organization()
    membership = make_membership(organization, user)
    db_session.add_all([organization, user, membership])
    await db_session.commit()
    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email_normalized, "password": "correct-password"},
    )
    return str(user.id), response.json()["csrf_token"]


async def test_authenticated_client_reads_safe_session_context(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user_id, csrf_token = await _login(auth_client, db_session)

    response = await auth_client.get("/api/v1/auth/session")

    assert response.status_code == 200
    assert response.json()["user"]["id"] == user_id
    assert response.json()["csrf_token"] == csrf_token
    assert response.json()["organization_access"][0]["membership_status"] == "active"
    assert "token_hash" not in response.text
    assert "password_hash" not in response.text


async def test_missing_session_cookie_is_rejected(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/api/v1/auth/session")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"


async def test_expired_session_is_rejected(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    raw_token = "expired-session-token"
    user = make_user()
    db_session.add(user)
    await db_session.flush()
    now = datetime.now(UTC)
    db_session.add(
        Session(
            user_id=user.id,
            token_hash=hash_secret(raw_token),
            csrf_token_hash="b" * 64,
            last_seen_at=now - timedelta(days=15),
            absolute_expires_at=now + timedelta(days=1),
        )
    )
    await db_session.commit()
    auth_client.cookies.set("horeca_session", raw_token)

    response = await auth_client.get("/api/v1/auth/session")

    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"
