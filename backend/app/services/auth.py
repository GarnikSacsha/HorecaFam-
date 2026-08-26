import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.email import normalize_email
from app.core.errors import APIError
from app.models import (
    AdminAccess,
    AuditEvent,
    AuthRateLimitBucket,
    MfaChallenge,
    MfaCredential,
    User,
)
from app.security.passwords import PasswordManager
from app.security.tokens import generate_opaque_token, hash_secret
from app.services.sessions import IssuedSession, create_session

LOGIN_WINDOW = timedelta(minutes=15)
LOGIN_BLOCK = timedelta(minutes=15)
LOGIN_FAILURE_LIMIT = 5
MFA_CHALLENGE_LIFETIME = timedelta(minutes=5)


@dataclass(frozen=True)
class LoginOutcome:
    kind: Literal["session", "mfa_required"]
    user: User
    session: IssuedSession | None = None
    challenge_token: str | None = None
    challenge_expires_at: datetime | None = None


def _rate_subject(email: str, settings: Settings) -> str:
    key = settings.auth_throttle_hmac_key
    if key is None:
        raise RuntimeError("Auth security settings were not validated")
    return hmac.new(
        key.get_secret_value().encode("utf-8"),
        email.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


async def _rate_bucket(
    db: AsyncSession,
    subject_hash: str,
) -> AuthRateLimitBucket | None:
    bucket = await db.scalar(
        select(AuthRateLimitBucket)
        .where(
            AuthRateLimitBucket.action == "login",
            AuthRateLimitBucket.subject_hash == subject_hash,
        )
        .with_for_update()
    )
    return bucket


async def _register_failure(
    db: AsyncSession,
    *,
    bucket: AuthRateLimitBucket | None,
    subject_hash: str,
    now: datetime,
) -> bool:
    if bucket is None or now - bucket.window_started_at >= LOGIN_WINDOW:
        bucket = AuthRateLimitBucket(
            action="login",
            subject_hash=subject_hash,
            window_started_at=now,
            failure_count=1,
        )
        db.add(bucket)
    else:
        bucket.failure_count += 1
    if bucket.failure_count >= LOGIN_FAILURE_LIMIT:
        bucket.blocked_until = now + LOGIN_BLOCK
    await db.commit()
    return bucket.blocked_until is not None


async def login(
    db: AsyncSession,
    *,
    email: str,
    password: str,
    settings: Settings,
    passwords: PasswordManager,
    now: datetime,
    request_id: UUID,
    user_agent: str | None,
) -> LoginOutcome:
    settings.validate_auth_security()
    normalized_email = normalize_email(email)
    subject_hash = _rate_subject(normalized_email, settings)
    bucket = await _rate_bucket(db, subject_hash)
    if bucket is not None and bucket.blocked_until is not None and bucket.blocked_until > now:
        raise APIError(
            status_code=429,
            code="AUTH_RATE_LIMITED",
            message="Забагато спроб. Спробуйте пізніше.",
        )

    user = await db.scalar(select(User).where(User.email_normalized == normalized_email))
    encoded_hash = user.password_hash if user is not None else None
    if not passwords.verify_or_dummy(encoded_hash, password):
        blocked = await _register_failure(
            db,
            bucket=bucket,
            subject_hash=subject_hash,
            now=now,
        )
        if blocked:
            raise APIError(
                status_code=429,
                code="AUTH_RATE_LIMITED",
                message="Забагато спроб. Спробуйте пізніше.",
            )
        raise APIError(
            status_code=401,
            code="INVALID_CREDENTIALS",
            message="Неправильна електронна пошта або пароль.",
        )

    if user is None or user.password_hash is None:
        raise RuntimeError("Credential verification returned an impossible result")
    if bucket is not None:
        await db.delete(bucket)
    if passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash(password)

    elevated = (
        await db.scalar(
            select(AdminAccess.id).where(
                AdminAccess.user_id == user.id,
                AdminAccess.status == "active",
            )
        )
        is not None
    )
    if elevated:
        credential = await db.scalar(
            select(MfaCredential.id).where(
                MfaCredential.user_id == user.id,
                MfaCredential.confirmed_at.is_not(None),
                MfaCredential.disabled_at.is_(None),
            )
        )
        if credential is None:
            await db.commit()
            raise APIError(
                status_code=403,
                code="MFA_NOT_CONFIGURED",
                message="Для цього доступу потрібне налаштоване MFA.",
            )
        await db.execute(
            update(MfaChallenge)
            .where(MfaChallenge.user_id == user.id, MfaChallenge.used_at.is_(None))
            .values(used_at=now)
        )
        raw_challenge = generate_opaque_token()
        expires_at = now + MFA_CHALLENGE_LIFETIME
        challenge = MfaChallenge(
            user_id=user.id,
            token_hash=hash_secret(raw_challenge),
            expires_at=expires_at,
        )
        db.add(challenge)
        await db.flush()
        db.add(
            AuditEvent(
                actor_user_id=user.id,
                actor_type="user",
                action="mfa_challenge_created",
                target_type="mfa_challenge",
                target_id=challenge.id,
                request_id=request_id,
                outcome="success",
            )
        )
        await db.commit()
        return LoginOutcome(
            kind="mfa_required",
            user=user,
            challenge_token=raw_challenge,
            challenge_expires_at=expires_at,
        )

    hmac_key = settings.auth_throttle_hmac_key
    if hmac_key is None:
        raise RuntimeError("Auth security settings were not validated")
    issued = await create_session(
        db,
        user=user,
        now=now,
        hmac_key=hmac_key,
        elevated=False,
        request_id=request_id,
        user_agent=user_agent,
    )
    await db.commit()
    return LoginOutcome(kind="session", user=user, session=issued)
