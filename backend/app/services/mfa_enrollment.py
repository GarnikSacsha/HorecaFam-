from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from cryptography.fernet import InvalidToken
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.errors import APIError
from app.models import (
    AdminAccess,
    AuditEvent,
    MfaChallenge,
    MfaCredential,
    MfaRecoveryCode,
    Session,
    User,
)
from app.security.mfa import (
    MfaSecretCipher,
    TotpVerifier,
    build_totp_uri,
    encode_totp_secret,
    generate_recovery_codes,
    generate_totp_secret,
    normalize_recovery_code,
)
from app.security.passwords import PasswordManager
from app.security.tokens import hash_secret
from app.services.sessions import RECENT_MFA_WINDOW, IssuedSession, create_session


@dataclass(frozen=True)
class MfaEnrollmentStartOutcome:
    secret: str
    otpauth_uri: str
    expires_at: datetime


@dataclass(frozen=True)
class MfaEnrollmentConfirmOutcome:
    user: User
    session: IssuedSession
    recovery_codes: list[str]


@dataclass(frozen=True)
class MfaRecoveryOutcome:
    user: User
    session: IssuedSession


def _challenge_error() -> APIError:
    return APIError(
        status_code=401,
        code="MFA_CHALLENGE_INVALID",
        message="MFA-виклик недійсний або завершився.",
    )


def _code_error() -> APIError:
    return APIError(
        status_code=401,
        code="MFA_CODE_INVALID",
        message="Неправильний код MFA.",
    )


def _cipher(settings: Settings) -> MfaSecretCipher:
    settings.validate_auth_security()
    return MfaSecretCipher([key.get_secret_value() for key in settings.mfa_encryption_keys])


async def _load_challenge(
    db: AsyncSession,
    *,
    raw_challenge: str | None,
    settings: Settings,
    now: datetime,
) -> MfaChallenge:
    settings.validate_auth_security()
    if raw_challenge is None:
        raise _challenge_error()
    challenge = await db.scalar(
        select(MfaChallenge)
        .where(MfaChallenge.token_hash == hash_secret(raw_challenge))
        .options(selectinload(MfaChallenge.user))
        .with_for_update()
    )
    if (
        challenge is None
        or challenge.used_at is not None
        or challenge.expires_at <= now
        or challenge.failed_attempts >= 5
    ):
        raise _challenge_error()
    elevated = await db.scalar(
        select(AdminAccess.id).where(
            AdminAccess.user_id == challenge.user_id,
            AdminAccess.status == "active",
        )
    )
    if elevated is None:
        raise _challenge_error()
    return challenge


async def _active_credential(
    db: AsyncSession,
    *,
    user_id: UUID,
    confirmed: bool,
) -> MfaCredential | None:
    confirmed_filter = (
        MfaCredential.confirmed_at.is_not(None)
        if confirmed
        else MfaCredential.confirmed_at.is_(None)
    )
    credential: MfaCredential | None = await db.scalar(
        select(MfaCredential)
        .where(
            MfaCredential.user_id == user_id,
            confirmed_filter,
            MfaCredential.disabled_at.is_(None),
        )
        .order_by(MfaCredential.created_at.desc())
        .with_for_update()
    )
    return credential


def _new_recovery_records(
    credential: MfaCredential,
    *,
    now: datetime,
) -> tuple[list[str], list[MfaRecoveryCode]]:
    raw_codes = generate_recovery_codes()
    records = [
        MfaRecoveryCode(
            mfa_credential_id=credential.id,
            code_hash=hash_secret(normalize_recovery_code(code)),
            created_at=now,
        )
        for code in raw_codes
    ]
    return raw_codes, records


async def start_mfa_enrollment(
    db: AsyncSession,
    *,
    raw_challenge: str | None,
    settings: Settings,
    now: datetime,
    request_id: UUID,
) -> MfaEnrollmentStartOutcome:
    challenge = await _load_challenge(
        db,
        raw_challenge=raw_challenge,
        settings=settings,
        now=now,
    )
    if await _active_credential(db, user_id=challenge.user_id, confirmed=True) is not None:
        raise APIError(
            status_code=409,
            code="MFA_ALREADY_CONFIGURED",
            message="MFA вже налаштовано.",
        )
    await db.execute(
        update(MfaCredential)
        .where(
            MfaCredential.user_id == challenge.user_id,
            MfaCredential.confirmed_at.is_(None),
            MfaCredential.disabled_at.is_(None),
        )
        .values(disabled_at=now)
    )
    secret = generate_totp_secret()
    credential = MfaCredential(
        user_id=challenge.user_id,
        type="totp",
        secret_encrypted=_cipher(settings).encrypt(secret),
        created_at=now,
    )
    db.add(credential)
    await db.flush()
    db.add(
        AuditEvent(
            actor_user_id=challenge.user_id,
            actor_type="user",
            action="mfa_enrollment_started",
            target_type="mfa_credential",
            target_id=credential.id,
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return MfaEnrollmentStartOutcome(
        secret=encode_totp_secret(secret),
        otpauth_uri=build_totp_uri(secret, account_name=challenge.user.email_normalized),
        expires_at=challenge.expires_at,
    )


async def confirm_mfa_enrollment(
    db: AsyncSession,
    *,
    raw_challenge: str | None,
    code: str,
    settings: Settings,
    now: datetime,
    request_id: UUID,
    user_agent: str | None,
) -> MfaEnrollmentConfirmOutcome:
    challenge = await _load_challenge(
        db,
        raw_challenge=raw_challenge,
        settings=settings,
        now=now,
    )
    credential = await _active_credential(db, user_id=challenge.user_id, confirmed=False)
    if credential is None:
        raise APIError(
            status_code=409,
            code="MFA_ENROLLMENT_NOT_STARTED",
            message="Спочатку почніть налаштування MFA.",
        )
    try:
        secret = _cipher(settings).decrypt(credential.secret_encrypted)
    except InvalidToken as exception:
        challenge.used_at = now
        await db.commit()
        raise _challenge_error() from exception
    counter = TotpVerifier().verify(
        secret,
        code,
        now,
        last_used_counter=credential.last_used_counter,
    )
    if counter is None:
        challenge.failed_attempts += 1
        await db.commit()
        raise _code_error()

    credential.confirmed_at = now
    credential.last_used_counter = counter
    challenge.used_at = now
    raw_codes, recovery_records = _new_recovery_records(credential, now=now)
    db.add_all(recovery_records)
    hmac_key = settings.auth_throttle_hmac_key
    if hmac_key is None:
        raise RuntimeError("Auth security settings were not validated")
    issued = await create_session(
        db,
        user=challenge.user,
        now=now,
        hmac_key=hmac_key,
        has_elevated_access=True,
        mfa_verified=True,
        request_id=request_id,
        user_agent=user_agent,
    )
    db.add(
        AuditEvent(
            actor_user_id=challenge.user_id,
            actor_type="user",
            action="mfa_enrollment_confirmed",
            target_type="mfa_credential",
            target_id=credential.id,
            new_values={"recovery_code_count": len(raw_codes)},
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return MfaEnrollmentConfirmOutcome(
        user=challenge.user,
        session=issued,
        recovery_codes=raw_codes,
    )


async def verify_mfa_recovery_code(
    db: AsyncSession,
    *,
    raw_challenge: str | None,
    code: str,
    settings: Settings,
    now: datetime,
    request_id: UUID,
    user_agent: str | None,
) -> MfaRecoveryOutcome:
    challenge = await _load_challenge(
        db,
        raw_challenge=raw_challenge,
        settings=settings,
        now=now,
    )
    credential = await _active_credential(db, user_id=challenge.user_id, confirmed=True)
    if credential is None:
        raise _challenge_error()
    recovery_code = await db.scalar(
        select(MfaRecoveryCode)
        .where(
            MfaRecoveryCode.mfa_credential_id == credential.id,
            MfaRecoveryCode.code_hash == hash_secret(normalize_recovery_code(code)),
            MfaRecoveryCode.used_at.is_(None),
        )
        .with_for_update()
    )
    if recovery_code is None:
        challenge.failed_attempts += 1
        await db.commit()
        raise _code_error()

    recovery_code.used_at = now
    challenge.used_at = now
    hmac_key = settings.auth_throttle_hmac_key
    if hmac_key is None:
        raise RuntimeError("Auth security settings were not validated")
    issued = await create_session(
        db,
        user=challenge.user,
        now=now,
        hmac_key=hmac_key,
        has_elevated_access=True,
        mfa_verified=True,
        request_id=request_id,
        user_agent=user_agent,
    )
    db.add(
        AuditEvent(
            actor_user_id=challenge.user_id,
            actor_type="user",
            action="mfa_recovery_completed",
            target_type="mfa_credential",
            target_id=credential.id,
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return MfaRecoveryOutcome(user=challenge.user, session=issued)


async def regenerate_mfa_recovery_codes(
    db: AsyncSession,
    *,
    current_session: Session,
    user: User,
    current_password: str,
    totp_code: str,
    settings: Settings,
    passwords: PasswordManager,
    now: datetime,
    request_id: UUID,
) -> list[str]:
    elevated = await db.scalar(
        select(AdminAccess.id).where(
            AdminAccess.user_id == user.id,
            AdminAccess.status == "active",
        )
    )
    if elevated is None or current_session.mfa_verified_at is None:
        raise APIError(status_code=403, code="MFA_REQUIRED", message="Потрібна MFA-перевірка.")
    if now - current_session.mfa_verified_at > RECENT_MFA_WINDOW:
        raise APIError(
            status_code=403,
            code="RECENT_MFA_REQUIRED",
            message="Потрібне нещодавнє підтвердження MFA.",
        )
    if user.password_hash is None or not passwords.verify(user.password_hash, current_password):
        raise APIError(
            status_code=401,
            code="CURRENT_PASSWORD_INVALID",
            message="Поточний пароль неправильний.",
        )
    credential = await _active_credential(db, user_id=user.id, confirmed=True)
    if credential is None:
        raise _challenge_error()
    try:
        secret = _cipher(settings).decrypt(credential.secret_encrypted)
    except InvalidToken as exception:
        raise _challenge_error() from exception
    counter = TotpVerifier().verify(
        secret,
        totp_code,
        now,
        last_used_counter=credential.last_used_counter,
    )
    if counter is None:
        raise _code_error()

    credential.last_used_counter = counter
    invalidated = list(
        (
            await db.scalars(
                update(MfaRecoveryCode)
                .where(
                    MfaRecoveryCode.mfa_credential_id == credential.id,
                    MfaRecoveryCode.used_at.is_(None),
                )
                .values(used_at=now)
                .returning(MfaRecoveryCode.id)
            )
        ).all()
    )
    raw_codes, recovery_records = _new_recovery_records(credential, now=now)
    db.add_all(recovery_records)
    db.add(
        AuditEvent(
            actor_user_id=user.id,
            actor_type="user",
            action="mfa_recovery_codes_regenerated",
            target_type="mfa_credential",
            target_id=credential.id,
            new_values={
                "invalidated_code_count": len(invalidated),
                "recovery_code_count": len(raw_codes),
            },
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return raw_codes
