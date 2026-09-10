import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthRateLimitBucket, InvitationRateLimitBucket
from app.security.passwords import PasswordManager
from app.services.maintenance import cleanup_security_records
from tests.factories.identity import make_user


@pytest.mark.parametrize("route", ["login", "forgot", "reset", "validate", "accept"])
async def test_distinct_public_subjects_cannot_grow_beyond_capacity(
    route: str,
    auth_app: FastAPI,
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    now = datetime(2031, 1, 2, tzinfo=UTC)
    auth_app.state.clock = lambda: now
    invitation = route in {"validate", "accept"}
    model = InvitationRateLimitBucket if invitation else AuthRateLimitBucket
    action = "validate" if invitation else "login"
    db_session.add_all(
        model(action=action, subject_hash=f"{i:064x}", window_started_at=now) for i in range(4095)
    )
    await db_session.commit()

    def request(index: int) -> tuple[str, dict[str, str]]:
        if route == "login":
            return "/api/v1/auth/login", {
                "email": f"absent-{index}@example.com",
                "password": "invalid-password",
            }
        if route == "forgot":
            return "/api/v1/auth/password/forgot", {"email": f"absent-{index}@example.com"}
        if route == "reset":
            return "/api/v1/auth/password/reset", {
                "token": f"invalid-reset-token-{index:032d}",
                "new_password": "valid-new-password",
            }
        body = {"token": f"invalid-invitation-{index}"}
        if route == "accept":
            body.update(acceptance_mode="activate_access", password="valid-new-password")
        return f"/api/v1/invitations/{route}", body

    path, body = request(0)
    first = await auth_client.post(path, json=body)
    assert (
        first.status_code
        == {"login": 401, "forgot": 202, "reset": 400, "validate": 404, "accept": 404}[route]
    )
    path, body = request(1)
    denied = await auth_client.post(path, json=body)
    assert denied.status_code == 429
    assert denied.json()["code"] == "AUTH_RATE_LIMITED"
    assert await db_session.scalar(select(func.count()).select_from(model)) == 4096
    # Чинний ключ зберігає власний бюджет навіть за заповненого сховища.
    path, body = request(0)
    repeat = await auth_client.post(path, json=body)
    assert repeat.status_code == first.status_code
    now += timedelta(minutes=16)
    path, body = request(2)
    recovered = await auth_client.post(path, json=body)
    assert recovered.status_code == first.status_code
    count = await db_session.scalar(select(func.count()).select_from(model))
    assert count is not None and count <= 4096


@pytest.mark.parametrize("model", [AuthRateLimitBucket, InvitationRateLimitBucket])
async def test_security_cleanup_retires_buckets_but_preserves_active_blocks(
    model: type[AuthRateLimitBucket] | type[InvitationRateLimitBucket],
    db_session: AsyncSession,
) -> None:
    cutoff = datetime(2031, 1, 2, tzinfo=UTC)
    action = "login" if model is AuthRateLimitBucket else "validate"
    old = model(
        action=action, subject_hash="a" * 64, window_started_at=cutoff - timedelta(minutes=16)
    )
    blocked = model(
        action=action,
        subject_hash="b" * 64,
        window_started_at=cutoff - timedelta(hours=1),
        blocked_until=cutoff + timedelta(minutes=1),
    )
    recent = model(action=action, subject_hash="c" * 64, window_started_at=cutoff)
    db_session.add_all([old, blocked, recent])
    await db_session.commit()
    old_id, blocked_id, recent_id = old.id, blocked.id, recent.id
    await cleanup_security_records(db_session, cutoff_at=cutoff, batch_size=1)
    await db_session.commit()
    db_session.expire_all()
    assert await db_session.get(model, old_id) is None
    assert await db_session.get(model, blocked_id) is not None
    assert await db_session.get(model, recent_id) is not None


@pytest.mark.parametrize("invitation", [False, True])
async def test_competing_new_subjects_cannot_overbook_last_slot(
    invitation: bool,
    auth_app: FastAPI,
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    auth_app.state.clock = lambda: now
    model = InvitationRateLimitBucket if invitation else AuthRateLimitBucket
    action = "validate" if invitation else "password_reset"
    db_session.add_all(
        model(action=action, subject_hash=f"{i:064x}", window_started_at=now) for i in range(4095)
    )
    await db_session.commit()
    path = "/api/v1/invitations/validate" if invitation else "/api/v1/auth/password/reset"

    async def attempt(index: int) -> int:
        body = {"token": f"concurrent-invalid-token-{index:032d}"}
        if not invitation:
            body["new_password"] = "valid-new-password"
        return (await auth_client.post(path, json=body)).status_code

    responses = await asyncio.wait_for(asyncio.gather(*(attempt(i) for i in range(8))), 10)
    assert responses.count(404 if invitation else 400) == 1
    assert responses.count(429) == 7
    assert await db_session.scalar(select(func.count()).select_from(model)) == 4096


async def test_simultaneous_unknown_reset_token_is_controlled_and_counts_admitted_attempts(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    responses = await asyncio.gather(
        *(
            auth_client.post(
                "/api/v1/auth/password/reset",
                json={
                    "token": "same-unknown-reset-token-0000000000000000",
                    "new_password": "valid-new-password",
                },
            )
            for _ in range(8)
        )
    )
    assert all(response.status_code in {400, 429} for response in responses)
    bucket = await db_session.scalar(select(AuthRateLimitBucket))
    assert bucket is not None
    assert bucket.failure_count == sum(response.status_code == 400 for response in responses)
    assert await db_session.scalar(select(func.count()).select_from(AuthRateLimitBucket)) == 1


@pytest.mark.parametrize("model", [AuthRateLimitBucket, InvitationRateLimitBucket])
async def test_cleanup_skips_budget_locked_by_active_request(
    model: type[AuthRateLimitBucket] | type[InvitationRateLimitBucket],
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    bucket = model(
        action="login" if model is AuthRateLimitBucket else "validate",
        subject_hash="d" * 64,
        window_started_at=now - timedelta(hours=1),
    )
    db_session.add(bucket)
    await db_session.commit()
    bucket_id = bucket.id
    async with auth_app.state.session_factory() as owner:
        locked = await owner.scalar(select(model).where(model.id == bucket_id).with_for_update())
        assert locked is not None
        await asyncio.wait_for(cleanup_security_records(db_session, cutoff_at=now), 5)
        await db_session.commit()
        locked.window_started_at = now
        locked.blocked_until = now + timedelta(minutes=15)
        await owner.commit()
    await cleanup_security_records(db_session, cutoff_at=now)
    await db_session.commit()
    db_session.expire_all()
    retained = await db_session.get_one(model, bucket_id)
    assert isinstance(retained, (AuthRateLimitBucket, InvitationRateLimitBucket))
    assert retained.blocked_until == now + timedelta(minutes=15)


@pytest.mark.parametrize("invitation", [False, True])
async def test_public_capacity_reclaims_public_rows_despite_older_private_budgets(
    invitation: bool,
    auth_app: FastAPI,
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    auth_app.state.clock = lambda: now
    model = InvitationRateLimitBucket if invitation else AuthRateLimitBucket
    public_action = "validate" if invitation else "password_forgot"
    private_action = "create" if invitation else "mfa"
    db_session.add_all(
        model(
            action=public_action,
            subject_hash=f"{i:064x}",
            window_started_at=now - timedelta(minutes=16),
        )
        for i in range(4096)
    )
    db_session.add_all(
        model(
            action=private_action,
            subject_hash=f"{i:064x}",
            window_started_at=now - timedelta(days=1),
        )
        for i in range(64)
    )
    await db_session.commit()
    for index in range(2):
        if invitation:
            response = await auth_client.post(
                "/api/v1/invitations/validate",
                json={
                    "token": f"invalid-new-token-{index}",
                },
            )
        else:
            response = await auth_client.post(
                "/api/v1/auth/password/forgot",
                json={
                    "email": f"unknown-{index}@example.com",
                },
            )
        assert response.status_code == (404 if invitation else 202)
    assert (
        await db_session.scalar(
            select(func.count()).select_from(model).where(model.action == private_action)
        )
        == 64
    )


async def test_valid_login_needs_no_new_budget_at_public_capacity(
    auth_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    db_session.add_all(
        AuthRateLimitBucket(
            action="login",
            subject_hash=f"{i:064x}",
            window_started_at=now,
        )
        for i in range(4096)
    )
    db_session.add(
        make_user(
            email_normalized="legitimate@example.com",
            password_hash=PasswordManager().hash("correct-password"),
        )
    )
    await db_session.commit()
    response = await auth_client.post(
        "/api/v1/auth/login",
        json={
            "email": "legitimate@example.com",
            "password": "correct-password",
        },
    )
    assert response.status_code == 200
    assert await db_session.scalar(select(func.count()).select_from(AuthRateLimitBucket)) == 4096
