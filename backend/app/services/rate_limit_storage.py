import hashlib
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import AuthRateLimitBucket, InvitationRateLimitBucket

RateBucketModel = type[AuthRateLimitBucket] | type[InvitationRateLimitBucket]
PUBLIC_BUCKET_CAPACITY = 4096
RATE_WINDOW = timedelta(minutes=15)
RECLAIM_BATCH_SIZE = 64


def _limited() -> APIError:
    return APIError(
        status_code=429, code="AUTH_RATE_LIMITED", message="Забагато спроб. Спробуйте пізніше."
    )


async def lock_rate_subject(db: AsyncSession, subject: str) -> None:
    key = int.from_bytes(hashlib.sha256(subject.encode()).digest()[:8], "big", signed=True)
    # Не тримаємо з'єднання в черзі під час напливу публічних запитів.
    with db.no_autoflush:
        if not await db.scalar(select(func.pg_try_advisory_xact_lock(key))):
            raise _limited()


async def retire_rate_buckets(
    db: AsyncSession,
    *,
    model: RateBucketModel,
    cutoff_at: datetime,
    batch_size: int,
    actions: tuple[str, ...] | None = None,
) -> int:
    # Блокування рядка не дозволяє видалити бюджет, який паралельно поновлюється.
    ids = list(
        await db.scalars(
            select(model.id)
            .where(
                model.window_started_at <= cutoff_at - RATE_WINDOW,
                (model.blocked_until.is_(None)) | (model.blocked_until <= cutoff_at),
                model.action.in_(actions) if actions is not None else true(),
            )
            .order_by(model.window_started_at, model.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
    )
    if ids:
        await db.execute(delete(model).where(model.id.in_(ids)))
    return len(ids)


async def reserve_public_bucket(db: AsyncSession, *, model: RateBucketModel, now: datetime) -> None:
    # Усі публічні вставки тримають цей замок до commit; count та insert є атомарними.
    await lock_rate_subject(db, f"rate-capacity:{model.__tablename__}")
    actions = (
        ("login", "password_forgot", "password_reset")
        if model is AuthRateLimitBucket
        else ("validate",)
    )
    count_query = select(func.count()).select_from(model).where(model.action.in_(actions))
    count = await db.scalar(count_query)
    if count is not None and count >= PUBLIC_BUCKET_CAPACITY:
        await retire_rate_buckets(
            db, model=model, cutoff_at=now, batch_size=RECLAIM_BATCH_SIZE, actions=actions
        )
        count = await db.scalar(count_query)
        if count is not None and count >= PUBLIC_BUCKET_CAPACITY:
            raise _limited()
