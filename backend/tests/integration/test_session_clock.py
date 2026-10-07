from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.sessions import create_session
from tests.factories.identity import make_user


@pytest.mark.parametrize(("elevated", "lifetime_days"), [(False, 90), (True, 30)])
async def test_session_timestamps_use_the_same_supplied_clock(
    db_session: AsyncSession, elevated: bool, lifetime_days: int
) -> None:
    now = datetime(2000, 1, 1, 12, tzinfo=UTC)
    user = make_user()
    db_session.add(user)
    await db_session.flush()

    issued = await create_session(
        db_session,
        user=user,
        now=now,
        hmac_key=SecretStr("test-only-session-clock-key"),
        has_elevated_access=elevated,
        mfa_verified=elevated,
        request_id=uuid4(),
        user_agent=None,
    )
    await db_session.commit()
    await db_session.refresh(issued.record)

    assert issued.record.created_at == now
    assert issued.record.last_seen_at == now
    assert issued.record.absolute_expires_at == now + timedelta(days=lifetime_days)
    assert issued.record.absolute_expires_at > issued.record.created_at
    assert issued.record.mfa_verified_at == (now if elevated else None)
