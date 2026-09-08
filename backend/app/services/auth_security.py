import hashlib
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import APIError
from app.models import AuthRateLimitBucket, MfaChallenge, Session, User
from app.security.tokens import hash_secret

FAILURE_WINDOW = timedelta(minutes=15)
FAILURE_LIMIT = 5


async def lock_auth_email(db: AsyncSession, email: str, *, wait: bool = True) -> None:
    # Спільний порядок із прийняттям запрошення захищає також ще відсутній User.
    key = int.from_bytes(
        hashlib.sha256(f"user-email:{email}".encode()).digest()[:8], "big", signed=True
    )
    with db.no_autoflush:
        if wait:
            await db.execute(select(func.pg_advisory_xact_lock(key)))
        elif not await db.scalar(select(func.pg_try_advisory_xact_lock(key))):
            # Публічний вхід не тримає з'єднання в черзі за зайнятим обліковим записом.
            raise APIError(
                status_code=429,
                code="AUTH_RATE_LIMITED",
                message="Забагато спроб. Спробуйте пізніше.",
            )


async def lock_auth_user(db: AsyncSession, user_id: UUID) -> User:
    with db.no_autoflush:
        email = await db.scalar(select(User.email_normalized).where(User.id == user_id))
        if email is None:
            raise RuntimeError("Authentication user is unavailable")
        await lock_auth_email(db, email)
        user = await db.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    if user is None:
        raise RuntimeError("Authentication user is unavailable")
    return user


async def load_locked_challenge(db: AsyncSession, raw_challenge: str) -> MfaChallenge | None:
    token_hash = hash_secret(raw_challenge)
    with db.no_autoflush:
        user_id = await db.scalar(
            select(MfaChallenge.user_id).where(MfaChallenge.token_hash == token_hash)
        )
    if user_id is None:
        return None
    await lock_auth_user(db, user_id)
    challenge: MfaChallenge | None = await db.scalar(
        select(MfaChallenge)
        .where(MfaChallenge.token_hash == token_hash)
        .options(selectinload(MfaChallenge.user))
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return challenge


async def check_failure_budget(
    db: AsyncSession, *, user_id: UUID, action: str, now: datetime
) -> AuthRateLimitBucket:
    # Викликається після блокування User; новий challenge або Session не оновлює бюджет.
    subject = hash_secret(f"{action}:{user_id}")
    bucket = await db.scalar(
        select(AuthRateLimitBucket)
        .where(AuthRateLimitBucket.action == action, AuthRateLimitBucket.subject_hash == subject)
        .with_for_update()
    )
    if bucket is None:
        bucket = AuthRateLimitBucket(
            action=action, subject_hash=subject, window_started_at=now, failure_count=0
        )
        db.add(bucket)
    elif bucket.blocked_until is not None and bucket.blocked_until > now:
        raise APIError(
            status_code=429, code="AUTH_RATE_LIMITED", message="Забагато спроб. Спробуйте пізніше."
        )
    elif now - bucket.window_started_at >= FAILURE_WINDOW:
        bucket.window_started_at = now
        bucket.failure_count = 0
        bucket.blocked_until = None
    await db.flush()
    return bucket


async def record_failure(db: AsyncSession, bucket: AuthRateLimitBucket, now: datetime) -> None:
    bucket.failure_count += 1
    if bucket.failure_count >= FAILURE_LIMIT:
        bucket.blocked_until = now + FAILURE_WINDOW
    # Відмова HTTP відкочує транзакцію, тому бюджет фіксується до повернення помилки.
    await db.commit()


async def revoke_mfa_challenges(db: AsyncSession, user_id: UUID, now: datetime) -> None:
    await db.execute(
        update(MfaChallenge)
        .where(MfaChallenge.user_id == user_id, MfaChallenge.used_at.is_(None))
        .values(used_at=now)
    )


async def require_live_session(db: AsyncSession, record: Session, now: datetime) -> None:
    # Dependency могла прочитати Session до конкурентного скидання пароля.
    await db.refresh(record)
    if record.revoked_at is not None or record.absolute_expires_at <= now:
        raise APIError(
            status_code=401, code="AUTHENTICATION_REQUIRED", message="Потрібна автентифікація."
        )
    record.last_seen_at = max(record.last_seen_at, now)
