from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import Depends, FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    AuthorizationContext,
    require_active_employee,
    require_organization_admin,
    require_platform_operator,
)
from app.core.config import Settings
from app.models import (
    EmployeeProfile,
    MfaChallenge,
    MfaCredential,
    Organization,
    Session,
    User,
)
from app.security.mfa import MfaSecretCipher, TotpVerifier
from app.security.passwords import PasswordManager
from app.security.tokens import generate_opaque_token, hash_secret
from tests.factories.auth import make_admin_access, make_mfa_credential
from tests.factories.identity import make_membership, make_organization, make_user

FIXED_NOW = datetime.now(UTC).replace(microsecond=0)
TOTP_SECRET = b"01234567890123456789"


async def _create_elevated_user(
    db_session: AsyncSession,
    settings: Settings,
    *,
    email: str,
    scope: str = "organization_admin",
    organization: Organization | None = None,
) -> tuple[User, Organization | None, MfaCredential]:
    user = make_user(
        email_normalized=email,
        password_hash=PasswordManager().hash("correct-password"),
    )
    db_session.add(user)
    await db_session.flush()
    access = make_admin_access(
        user,
        scope=scope,
        organization=organization,
    )
    cipher = MfaSecretCipher([key.get_secret_value() for key in settings.mfa_encryption_keys])
    credential = make_mfa_credential(
        user,
        secret_encrypted=cipher.encrypt(TOTP_SECRET),
        confirmed_at=FIXED_NOW - timedelta(days=1),
    )
    db_session.add_all([access, credential])
    await db_session.commit()
    return user, organization, credential


async def _begin_mfa(auth_client: AsyncClient, email: str) -> str:
    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct-password"},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "mfa_required"
    assert "horeca_session" not in auth_client.cookies
    return auth_client.cookies["horeca_mfa_challenge"]


def _totp_code() -> str:
    return TotpVerifier().generate(TOTP_SECRET, FIXED_NOW)


async def test_valid_mfa_consumes_challenge_and_creates_elevated_session(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    user, _organization, credential = await _create_elevated_user(
        db_session,
        auth_settings,
        email="admin-mfa@example.com",
        scope="platform_operator",
    )
    user_id = user.id
    credential_id = credential.id
    raw_challenge = await _begin_mfa(auth_client, user.email_normalized)

    response = await auth_client.post(
        "/api/v1/auth/mfa/verify",
        json={"code": _totp_code()},
    )

    assert response.status_code == 200
    assert response.json()["session"]["mfa_verified"] is True
    assert response.json()["platform_operator"] is True
    assert "horeca_session" in auth_client.cookies
    assert "horeca_mfa_challenge" not in auth_client.cookies
    assert raw_challenge not in response.text
    db_session.expire_all()
    challenge = await db_session.scalar(select(MfaChallenge).where(MfaChallenge.user_id == user_id))
    sessions = list(
        (await db_session.scalars(select(Session).where(Session.user_id == user_id))).all()
    )
    stored_credential = await db_session.get(MfaCredential, credential_id)
    assert challenge is not None and challenge.used_at == FIXED_NOW
    assert len(sessions) == 1
    assert sessions[0].absolute_expires_at == FIXED_NOW + timedelta(days=30)
    assert stored_credential is not None
    assert stored_credential.last_used_counter == int(FIXED_NOW.timestamp()) // 30


async def test_invalid_mfa_code_increments_attempts_without_creating_session(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    user, _organization, _credential = await _create_elevated_user(
        db_session,
        auth_settings,
        email="invalid-mfa@example.com",
        scope="platform_operator",
    )
    user_id = user.id
    await _begin_mfa(auth_client, user.email_normalized)

    response = await auth_client.post(
        "/api/v1/auth/mfa/verify",
        json={"code": "000000" if _totp_code() != "000000" else "999999"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "MFA_CODE_INVALID"
    db_session.expire_all()
    challenge = await db_session.scalar(select(MfaChallenge).where(MfaChallenge.user_id == user_id))
    assert challenge is not None and challenge.failed_attempts == 1
    assert await db_session.scalar(select(Session.id).where(Session.user_id == user_id)) is None


async def test_mfa_challenge_stops_after_five_failed_attempts(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    user, _organization, _credential = await _create_elevated_user(
        db_session,
        auth_settings,
        email="attempt-cap@example.com",
        scope="platform_operator",
    )
    await _begin_mfa(auth_client, user.email_normalized)
    invalid_code = "000000" if _totp_code() != "000000" else "999999"

    responses = [
        await auth_client.post("/api/v1/auth/mfa/verify", json={"code": invalid_code})
        for _ in range(6)
    ]

    assert [response.status_code for response in responses] == [401] * 6
    assert [response.json()["code"] for response in responses[:5]] == ["MFA_CODE_INVALID"] * 5
    assert responses[5].json()["code"] == "MFA_CHALLENGE_INVALID"


async def test_missing_or_consumed_mfa_challenge_is_rejected(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    missing = await auth_client.post(
        "/api/v1/auth/mfa/verify",
        json={"code": _totp_code()},
    )
    assert missing.status_code == 401
    assert missing.json()["code"] == "MFA_CHALLENGE_INVALID"

    user, _organization, _credential = await _create_elevated_user(
        db_session,
        auth_settings,
        email="consumed-mfa@example.com",
        scope="platform_operator",
    )
    raw_challenge = await _begin_mfa(auth_client, user.email_normalized)
    first = await auth_client.post(
        "/api/v1/auth/mfa/verify",
        json={"code": _totp_code()},
    )
    assert first.status_code == 200
    auth_client.cookies.set(
        "horeca_mfa_challenge",
        raw_challenge,
        path="/api/v1",
    )

    reused = await auth_client.post(
        "/api/v1/auth/mfa/verify",
        json={"code": _totp_code()},
    )

    assert reused.status_code == 401
    assert reused.json()["code"] == "MFA_CHALLENGE_INVALID"


async def test_challenge_without_usable_credential_is_rejected(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    user = make_user(email_normalized="orphan-challenge@example.com")
    db_session.add(user)
    await db_session.flush()
    raw_challenge = generate_opaque_token()
    db_session.add(
        MfaChallenge(
            user_id=user.id,
            token_hash=hash_secret(raw_challenge),
            expires_at=FIXED_NOW + timedelta(minutes=5),
        )
    )
    await db_session.commit()
    auth_client.cookies.set(
        "horeca_mfa_challenge",
        raw_challenge,
        path="/api/v1",
    )

    response = await auth_client.post(
        "/api/v1/auth/mfa/verify",
        json={"code": _totp_code()},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "MFA_CHALLENGE_INVALID"


async def test_elevated_login_without_confirmed_mfa_is_limited_to_enrollment(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = make_user(
        email_normalized="unconfigured-mfa@example.com",
        password_hash=PasswordManager().hash("correct-password"),
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(make_admin_access(user))
    await db_session.commit()

    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email_normalized, "password": "correct-password"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "mfa_enrollment_required"
    assert "horeca_mfa_challenge" in auth_client.cookies
    assert "horeca_session" not in auth_client.cookies


async def test_expired_mfa_challenge_uses_non_enumerating_error(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    user, _organization, _credential = await _create_elevated_user(
        db_session,
        auth_settings,
        email="expired-mfa@example.com",
        scope="platform_operator",
    )
    await _begin_mfa(auth_client, user.email_normalized)
    auth_app.state.clock = lambda: FIXED_NOW + timedelta(minutes=6)

    response = await auth_client.post(
        "/api/v1/auth/mfa/verify",
        json={"code": _totp_code()},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "MFA_CHALLENGE_INVALID"


async def test_totp_counter_cannot_be_replayed_across_challenges(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    user, _organization, _credential = await _create_elevated_user(
        db_session,
        auth_settings,
        email="replay-mfa@example.com",
        scope="platform_operator",
    )
    await _begin_mfa(auth_client, user.email_normalized)
    first = await auth_client.post(
        "/api/v1/auth/mfa/verify",
        json={"code": _totp_code()},
    )
    assert first.status_code == 200
    auth_client.cookies.delete("horeca_session")
    await _begin_mfa(auth_client, user.email_normalized)

    replay = await auth_client.post(
        "/api/v1/auth/mfa/verify",
        json={"code": _totp_code()},
    )

    assert replay.status_code == 401
    assert replay.json()["code"] == "MFA_CODE_INVALID"


def _install_rbac_probes(auth_app: FastAPI) -> None:
    @auth_app.get("/api/v1/test/organizations/{organization_id}/employee")
    async def employee_probe(
        organization_id: UUID,
        _context: Annotated[AuthorizationContext, Depends(require_active_employee)],
    ) -> dict[str, str]:
        return {"organization_id": str(organization_id)}

    @auth_app.get("/api/v1/test/organizations/{organization_id}/admin")
    async def organization_admin_probe(
        organization_id: UUID,
        _context: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    ) -> dict[str, str]:
        return {"organization_id": str(organization_id)}

    @auth_app.get("/api/v1/test/platform-operator")
    async def platform_operator_probe(
        _context: Annotated[AuthorizationContext, Depends(require_platform_operator)],
    ) -> dict[str, bool]:
        return {"platform_operator": True}


async def test_organization_rbac_denies_employee_and_hides_foreign_organization(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    _install_rbac_probes(auth_app)
    own_organization = make_organization(name="Own organization")
    foreign_organization = make_organization(name="Foreign organization")
    user = make_user(
        email_normalized="employee-rbac@example.com",
        password_hash=PasswordManager().hash("correct-password"),
    )
    membership = make_membership(own_organization, user)
    db_session.add_all([own_organization, foreign_organization, user, membership])
    await db_session.flush()
    db_session.add(
        EmployeeProfile(
            membership=membership,
            organization_id=own_organization.id,
        )
    )
    await db_session.commit()
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email_normalized, "password": "correct-password"},
    )
    assert login.status_code == 200

    employee = await auth_client.get(f"/api/v1/test/organizations/{own_organization.id}/employee")

    own = await auth_client.get(f"/api/v1/test/organizations/{own_organization.id}/admin")
    foreign = await auth_client.get(f"/api/v1/test/organizations/{foreign_organization.id}/admin")

    assert employee.status_code == 200
    assert own.status_code == 403
    assert own.json()["code"] == "FORBIDDEN"
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "RESOURCE_NOT_FOUND"


async def test_mfa_verified_admin_and_platform_operator_pass_scoped_probes(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    _install_rbac_probes(auth_app)
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization(name="Admin organization")
    db_session.add(organization)
    await db_session.flush()
    admin, _organization, _credential = await _create_elevated_user(
        db_session,
        auth_settings,
        email="admin-rbac@example.com",
        organization=organization,
    )
    await _begin_mfa(auth_client, admin.email_normalized)
    verified = await auth_client.post(
        "/api/v1/auth/mfa/verify",
        json={"code": _totp_code()},
    )
    assert verified.status_code == 200

    allowed = await auth_client.get(f"/api/v1/test/organizations/{organization.id}/admin")
    assert allowed.status_code == 200

    auth_client.cookies.delete("horeca_session")
    operator, _organization, _credential = await _create_elevated_user(
        db_session,
        auth_settings,
        email="operator-rbac@example.com",
        scope="platform_operator",
    )
    await _begin_mfa(auth_client, operator.email_normalized)
    verified = await auth_client.post(
        "/api/v1/auth/mfa/verify",
        json={"code": _totp_code()},
    )
    assert verified.status_code == 200

    platform = await auth_client.get("/api/v1/test/platform-operator")
    assert platform.status_code == 200
