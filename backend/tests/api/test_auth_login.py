from datetime import UTC, datetime

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminAccess, MfaCredential
from app.security.passwords import PasswordManager
from tests.factories.identity import make_membership, make_organization, make_user


async def _create_employee(db_session: AsyncSession, *, email: str, password: str) -> None:
    user = make_user(
        email_normalized=email,
        password_hash=PasswordManager().hash(password),
    )
    organization = make_organization()
    membership = make_membership(organization, user)
    db_session.add_all([organization, user, membership])
    await db_session.commit()


async def test_valid_employee_login_sets_secure_opaque_cookie(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _create_employee(db_session, email="employee@example.com", password="correct-password")

    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "Employee@Example.com", "password": "correct-password"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "employee@example.com"
    assert response.json()["csrf_token"]
    assert "token" not in response.json()["session"]
    assert "password" not in response.text.lower()
    cookie = response.headers["set-cookie"]
    assert "horeca_session=" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/api/v1" in cookie


async def test_unknown_user_and_wrong_password_are_indistinguishable(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await _create_employee(db_session, email="employee@example.com", password="correct-password")

    unknown = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "wrong-password"},
    )
    wrong = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "employee@example.com", "password": "wrong-password"},
    )

    assert unknown.status_code == wrong.status_code == 401
    for response in (unknown, wrong):
        payload = response.json()
        assert payload["code"] == "INVALID_CREDENTIALS"
        assert payload["field_errors"] == []
        assert "horeca_session=" not in response.headers.get("set-cookie", "")


async def test_malformed_login_email_has_stable_field_error(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "not-an-email", "password": "password"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["field_errors"][0]["field"] == "email"
    assert response.json()["field_errors"][0]["code"] == "INVALID_EMAIL"


async def test_login_rejects_unknown_request_fields(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "employee@example.com", "password": "password", "admin": True},
    )

    assert response.status_code == 422
    assert response.json()["field_errors"][0]["code"] == "extra_forbidden"


async def test_elevated_login_creates_mfa_challenge_without_session(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = make_user(
        email_normalized="admin@example.com",
        password_hash=PasswordManager().hash("correct-password"),
    )
    organization = make_organization()
    db_session.add_all([organization, user])
    await db_session.flush()
    db_session.add_all(
        [
            AdminAccess(
                user_id=user.id,
                scope="organization_admin",
                organization_id=organization.id,
                status="active",
                granted_at=datetime.now(UTC),
            ),
            MfaCredential(
                user_id=user.id,
                type="totp",
                secret_encrypted="encrypted-test-secret",
                confirmed_at=datetime.now(UTC),
            ),
        ]
    )
    await db_session.commit()

    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "correct-password"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "mfa_required"
    cookies = response.headers.get_list("set-cookie")
    assert any("horeca_mfa_challenge=" in value for value in cookies)
    assert all("horeca_session=" not in value for value in cookies)


async def test_login_throttles_known_and_unknown_accounts_equally(
    auth_client: AsyncClient,
) -> None:
    for _ in range(5):
        await auth_client.post(
            "/api/v1/auth/login",
            json={"email": "unknown@example.com", "password": "wrong-password"},
        )

    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 429
    assert response.json()["code"] == "AUTH_RATE_LIMITED"
    assert "unknown@example.com" not in response.text
