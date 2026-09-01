import hashlib
import hmac
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.email import normalize_email
from app.core.errors import APIError
from app.models import (
    AdminAccess,
    AuditEvent,
    AuthRateLimitBucket,
    PasswordResetToken,
    Session,
    User,
)
from app.security.passwords import PasswordManager
from app.security.tokens import hash_secret
from app.services.password_reset_delivery import (
    PasswordResetTokenManager,
    enqueue_password_reset_email,
)
from app.services.sessions import RECENT_MFA_WINDOW

PASSWORD_RESET_LIFETIME = timedelta(minutes=30)
PASSWORD_RATE_WINDOW = timedelta(minutes=15)
PASSWORD_RATE_BLOCK = timedelta(minutes=15)
PASSWORD_RATE_LIMIT = 5


def _rate_subject(value: str, settings: Settings) -> str:
    key = settings.auth_throttle_hmac_key
    if key is None:
        raise RuntimeError("Auth security settings were not validated")
    return hmac.new(
        key.get_secret_value().encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _rate_limited_error() -> APIError:
    return APIError(
        status_code=429,
        code="AUTH_RATE_LIMITED",
        message="Забагато спроб. Спробуйте пізніше.",
    )


async def _consume_rate_limit(
    db: AsyncSession,
    *,
    action: str,
    subject_hash: str,
    now: datetime,
) -> AuthRateLimitBucket:
    bucket = await db.scalar(
        select(AuthRateLimitBucket)
        .where(
            AuthRateLimitBucket.action == action,
            AuthRateLimitBucket.subject_hash == subject_hash,
        )
        .with_for_update()
    )
    if bucket is None:
        bucket = AuthRateLimitBucket(
            action=action,
            subject_hash=subject_hash,
            window_started_at=now,
            failure_count=1,
        )
        db.add(bucket)
        return bucket
    if bucket.blocked_until is not None and bucket.blocked_until > now:
        raise _rate_limited_error()
    if now - bucket.window_started_at >= PASSWORD_RATE_WINDOW:
        bucket.window_started_at = now
        bucket.failure_count = 1
        bucket.blocked_until = None
        return bucket
    if bucket.failure_count >= PASSWORD_RATE_LIMIT:
        bucket.blocked_until = now + PASSWORD_RATE_BLOCK
        await db.commit()
        raise _rate_limited_error()
    bucket.failure_count += 1
    return bucket


def _token_manager(settings: Settings) -> PasswordResetTokenManager:
    settings.validate_password_reset_security()
    return PasswordResetTokenManager(
        [key.get_secret_value() for key in settings.password_reset_token_hmac_keys]
    )


async def request_password_reset(
    db: AsyncSession,
    *,
    email: str,
    settings: Settings,
    now: datetime,
    request_id: UUID,
) -> None:
    settings.validate_auth_security()
    manager = _token_manager(settings)
    normalized_email = normalize_email(email)
    await _consume_rate_limit(
        db,
        action="password_forgot",
        subject_hash=_rate_subject(normalized_email, settings),
        now=now,
    )
    user = await db.scalar(
        select(User).where(User.email_normalized == normalized_email).with_for_update()
    )
    if user is None or user.password_hash is None:
        hash_secret(manager.derive(uuid4()))
        await db.commit()
        return

    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    token_id = uuid4()
    raw_token = manager.derive(token_id)
    token = PasswordResetToken(
        id=token_id,
        user_id=user.id,
        token_hash=hash_secret(raw_token),
        expires_at=now + PASSWORD_RESET_LIFETIME,
        created_at=now,
    )
    db.add(token)
    await db.flush()
    await enqueue_password_reset_email(db, token=token)
    db.add(
        AuditEvent(
            actor_type="system",
            action="password_reset_requested",
            target_type="password_reset_token",
            target_id=token.id,
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()


def _invalid_reset_token_error() -> APIError:
    return APIError(
        status_code=400,
        code="PASSWORD_RESET_TOKEN_INVALID",
        message="Посилання для зміни пароля недійсне або завершилося.",
    )


async def reset_password(
    db: AsyncSession,
    *,
    raw_token: str,
    new_password: str,
    settings: Settings,
    passwords: PasswordManager,
    now: datetime,
    request_id: UUID,
) -> None:
    settings.validate_auth_security()
    _token_manager(settings)
    token_hash = hash_secret(raw_token)
    bucket = await _consume_rate_limit(
        db,
        action="password_reset",
        subject_hash=_rate_subject(token_hash, settings),
        now=now,
    )
    token = await db.scalar(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == token_hash)
        .options(selectinload(PasswordResetToken.user))
        .with_for_update()
    )
    if (
        token is None
        or token.used_at is not None
        or token.revoked_at is not None
        or token.expires_at <= now
    ):
        await db.commit()
        raise _invalid_reset_token_error()

    token.used_at = now
    token.user.password_hash = passwords.hash(new_password)
    await db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == token.user_id,
            PasswordResetToken.id != token.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    revoked = list(
        (
            await db.scalars(
                update(Session)
                .where(Session.user_id == token.user_id, Session.revoked_at.is_(None))
                .values(revoked_at=now, revoke_reason="password_reset")
                .returning(Session.id)
            )
        ).all()
    )
    await db.delete(bucket)
    db.add(
        AuditEvent(
            actor_user_id=token.user_id,
            actor_type="user",
            action="password_reset_completed",
            target_type="user",
            target_id=token.user_id,
            new_values={"revoked_session_count": len(revoked)},
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()


async def change_password(
    db: AsyncSession,
    *,
    current_session: Session,
    user: User,
    current_password: str,
    new_password: str,
    passwords: PasswordManager,
    now: datetime,
    request_id: UUID,
) -> None:
    elevated = (
        await db.scalar(
            select(AdminAccess.id).where(
                AdminAccess.user_id == user.id,
                AdminAccess.status == "active",
            )
        )
        is not None
    )
    if elevated and (
        current_session.mfa_verified_at is None
        or now - current_session.mfa_verified_at > RECENT_MFA_WINDOW
    ):
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

    user.password_hash = passwords.hash(new_password)
    revoked = list(
        (
            await db.scalars(
                update(Session)
                .where(
                    Session.user_id == user.id,
                    Session.id != current_session.id,
                    Session.revoked_at.is_(None),
                )
                .values(revoked_at=now, revoke_reason="password_change")
                .returning(Session.id)
            )
        ).all()
    )
    db.add(
        AuditEvent(
            actor_user_id=user.id,
            actor_type="user",
            action="password_changed",
            target_type="user",
            target_id=user.id,
            new_values={"revoked_session_count": len(revoked)},
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
