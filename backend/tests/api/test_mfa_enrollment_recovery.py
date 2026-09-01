import base64
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminAccess, AuditEvent, MfaCredential, MfaRecoveryCode
from app.security.mfa import TotpVerifier, normalize_recovery_code
from app.security.passwords import PasswordManager
from app.security.tokens import hash_secret
from tests.factories.identity import make_organization, make_user


@dataclass
class EnrollmentContext:
    user_id: UUID
    email: str
    secret: bytes
    recovery_codes: list[str]
    csrf_token: str
    clock: dict[str, datetime]


def _decode_totp_secret(value: str) -> bytes:
    padding = "=" * ((8 - len(value) % 8) % 8)
    return base64.b32decode(f"{value}{padding}")


async def _complete_enrollment(
    auth_app: FastAPI,
    auth_client: AsyncClient,
    db_session: AsyncSession,
    *,
    email: str,
) -> EnrollmentContext:
    clock = {"now": datetime(2026, 9, 1, 12, tzinfo=UTC)}
    auth_app.state.clock = lambda: clock["now"]
    user = make_user(
        email_normalized=email,
        password_hash=PasswordManager().hash("correct-password"),
    )
    organization = make_organization()
    db_session.add_all([organization, user])
    await db_session.flush()
    db_session.add(
        AdminAccess(
            user_id=user.id,
            scope="organization_admin",
            organization_id=organization.id,
            status="active",
            granted_at=clock["now"],
        )
    )
    await db_session.commit()
    user_id = user.id
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "correct-password"},
    )
    assert login.status_code == 202
    assert login.json()["status"] == "mfa_enrollment_required"
    start = await auth_client.post("/api/v1/auth/mfa/enrollment/start")
    assert start.status_code == 200
    secret = _decode_totp_secret(start.json()["secret"])
    code = TotpVerifier().generate(secret, clock["now"])
    confirm = await auth_client.post(
        "/api/v1/auth/mfa/enrollment/confirm",
        json={"code": code},
    )
    assert confirm.status_code == 200
    assert confirm.json()["session"]["session"]["mfa_verified"] is True
    return EnrollmentContext(
        user_id=user_id,
        email=email,
        secret=secret,
        recovery_codes=confirm.json()["recovery_codes"],
        csrf_token=confirm.json()["session"]["csrf_token"],
        clock=clock,
    )


async def test_elevated_login_without_credential_gets_limited_enrollment_challenge(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    user = make_user(
        email_normalized="enroll-admin@example.com",
        password_hash=PasswordManager().hash("correct-password"),
    )
    organization = make_organization()
    db_session.add_all([organization, user])
    await db_session.flush()
    db_session.add(
        AdminAccess(
            user_id=user.id,
            scope="organization_admin",
            organization_id=organization.id,
            status="active",
            granted_at=datetime.now(UTC),
        )
    )
    await db_session.commit()

    response = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email_normalized, "password": "correct-password"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "mfa_enrollment_required"
    cookies = response.headers.get_list("set-cookie")
    assert any("horeca_mfa_challenge=" in value for value in cookies)
    assert all("horeca_session=" not in value for value in cookies)


async def test_mfa_enrollment_confirms_totp_and_returns_codes_once(
    auth_app: FastAPI,
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    context = await _complete_enrollment(
        auth_app,
        auth_client,
        db_session,
        email="complete-enrollment@example.com",
    )

    assert len(context.recovery_codes) == 10
    assert len(set(context.recovery_codes)) == 10
    assert all(len(normalize_recovery_code(code)) == 16 for code in context.recovery_codes)
    credential = await db_session.scalar(
        select(MfaCredential).where(MfaCredential.user_id == context.user_id)
    )
    assert credential is not None
    credential_id = credential.id
    assert credential.confirmed_at == context.clock["now"]
    assert context.secret.hex() not in credential.secret_encrypted
    stored_codes = list(
        (
            await db_session.scalars(
                select(MfaRecoveryCode).where(MfaRecoveryCode.mfa_credential_id == credential_id)
            )
        ).all()
    )
    assert len(stored_codes) == 10
    assert {record.code_hash for record in stored_codes} == {
        hash_secret(normalize_recovery_code(code)) for code in context.recovery_codes
    }
    replay = await auth_client.post(
        "/api/v1/auth/mfa/enrollment/confirm",
        json={"code": TotpVerifier().generate(context.secret, context.clock["now"])},
    )
    assert replay.status_code == 401
    assert replay.json()["code"] == "MFA_CHALLENGE_INVALID"
    audits = list((await db_session.scalars(select(AuditEvent))).all())
    serialized_audit = "".join(f"{audit.old_values}{audit.new_values}" for audit in audits)
    assert all(code not in serialized_audit for code in context.recovery_codes)


async def test_unconfirmed_totp_cannot_use_regular_mfa_verify(
    auth_app: FastAPI,
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    now = datetime(2026, 9, 1, 12, tzinfo=UTC)
    auth_app.state.clock = lambda: now
    user = make_user(
        email_normalized="unconfirmed@example.com",
        password_hash=PasswordManager().hash("correct-password"),
    )
    organization = make_organization()
    db_session.add_all([organization, user])
    await db_session.flush()
    db_session.add(
        AdminAccess(
            user_id=user.id,
            scope="organization_admin",
            organization_id=organization.id,
            status="active",
            granted_at=now,
        )
    )
    await db_session.commit()
    login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": user.email_normalized, "password": "correct-password"},
    )
    assert login.status_code == 202
    start = await auth_client.post("/api/v1/auth/mfa/enrollment/start")
    secret = _decode_totp_secret(start.json()["secret"])
    code = TotpVerifier().generate(secret, now)

    regular_verify = await auth_client.post(
        "/api/v1/auth/mfa/verify",
        json={"code": code},
    )

    assert regular_verify.status_code == 401
    assert regular_verify.json()["code"] == "MFA_CHALLENGE_INVALID"


async def test_recovery_code_is_one_time_and_creates_full_session(
    auth_app: FastAPI,
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    context = await _complete_enrollment(
        auth_app,
        auth_client,
        db_session,
        email="recover-admin@example.com",
    )
    recovery_code = context.recovery_codes[0]
    first_login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": context.email, "password": "correct-password"},
    )
    assert first_login.status_code == 202
    recovered = await auth_client.post(
        "/api/v1/auth/mfa/recovery/verify",
        json={"code": recovery_code},
    )
    assert recovered.status_code == 200
    assert recovered.json()["session"]["mfa_verified"] is True
    assert recovery_code not in recovered.text
    first_record = await db_session.scalar(
        select(MfaRecoveryCode).where(
            MfaRecoveryCode.code_hash == hash_secret(normalize_recovery_code(recovery_code))
        )
    )
    assert first_record is not None and first_record.used_at is not None

    second_login = await auth_client.post(
        "/api/v1/auth/login",
        json={"email": context.email, "password": "correct-password"},
    )
    assert second_login.status_code == 202
    replay = await auth_client.post(
        "/api/v1/auth/mfa/recovery/verify",
        json={"code": recovery_code},
    )
    assert replay.status_code == 401
    assert replay.json()["code"] == "MFA_CODE_INVALID"


async def test_recovery_code_regeneration_invalidates_prior_unused_codes(
    auth_app: FastAPI,
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    context = await _complete_enrollment(
        auth_app,
        auth_client,
        db_session,
        email="regenerate-admin@example.com",
    )
    credential = await db_session.scalar(
        select(MfaCredential).where(MfaCredential.user_id == context.user_id)
    )
    assert credential is not None
    credential_id = credential.id
    old_ids = set(
        (
            await db_session.scalars(
                select(MfaRecoveryCode.id).where(MfaRecoveryCode.mfa_credential_id == credential_id)
            )
        ).all()
    )
    context.clock["now"] += timedelta(seconds=30)
    next_code = TotpVerifier().generate(context.secret, context.clock["now"])

    response = await auth_client.post(
        "/api/v1/auth/mfa/recovery-codes/regenerate",
        headers={
            "Origin": "https://frontend.test",
            "X-CSRF-Token": context.csrf_token,
        },
        json={"current_password": "correct-password", "totp_code": next_code},
    )

    assert response.status_code == 200
    replacement_codes = response.json()["recovery_codes"]
    assert len(replacement_codes) == 10
    assert set(replacement_codes).isdisjoint(context.recovery_codes)
    db_session.expire_all()
    old_records = list(
        (
            await db_session.scalars(select(MfaRecoveryCode).where(MfaRecoveryCode.id.in_(old_ids)))
        ).all()
    )
    assert all(record.used_at is not None for record in old_records)
    new_hashes = set(
        (
            await db_session.scalars(
                select(MfaRecoveryCode.code_hash).where(
                    MfaRecoveryCode.mfa_credential_id == credential_id,
                    MfaRecoveryCode.used_at.is_(None),
                )
            )
        ).all()
    )
    assert new_hashes == {hash_secret(normalize_recovery_code(code)) for code in replacement_codes}


async def test_no_self_service_mfa_disable_route(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/api/v1/auth/mfa/disable")

    assert response.status_code == 404
