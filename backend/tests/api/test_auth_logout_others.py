import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent
from tests.api.test_auth_csrf_logout import _login, _stored_session


async def test_logout_others_preserves_current_and_other_users_and_replays(
    auth_client: AsyncClient, db_session: AsyncSession
) -> None:
    current_token, csrf = await _login(auth_client, db_session, email="devices@example.com")
    second = await auth_client.post(
        "/api/v1/auth/login", json={"email": "devices@example.com", "password": "correct-password"}
    )
    assert second.status_code == 200
    second_token = auth_client.cookies["horeca_session"]
    other_token, _ = await _login(auth_client, db_session, email="other-devices@example.com")
    auth_client.cookies.clear()
    auth_client.cookies.set("horeca_session", current_token)
    for _ in range(2):
        response = await auth_client.post(
            "/api/v1/auth/logout-all",
            headers={"Origin": "https://frontend.test", "X-CSRF-Token": csrf},
        )
        assert response.status_code == 204
        assert response.content == b""
        assert "set-cookie" not in response.headers
        assert (await auth_client.get("/api/v1/auth/session")).status_code == 200
    assert (await _stored_session(db_session, current_token)).revoked_at is None
    revoked = await _stored_session(db_session, second_token)
    assert revoked.revoked_at is not None
    assert revoked.revoke_reason == "logout_other_devices"
    assert (await _stored_session(db_session, other_token)).revoked_at is None
    events = list(
        await db_session.scalars(
            select(AuditEvent)
            .where(AuditEvent.action == "other_sessions_revoked")
            .order_by(AuditEvent.created_at)
        )
    )
    assert len(events) == 2
    assert sorted(event.new_values["revoked_count"] for event in events if event.new_values) == [
        0,
        1,
    ]
    for token, expected in [(second_token, 401), (other_token, 200)]:
        auth_client.cookies.clear()
        auth_client.cookies.set("horeca_session", token)
        assert (await auth_client.get("/api/v1/auth/session")).status_code == expected


@pytest.mark.parametrize("case", ["anonymous", "missing_csrf", "wrong_csrf", "foreign_origin"])
async def test_logout_others_denies_invalid_request_without_revocation(
    auth_client: AsyncClient, db_session: AsyncSession, case: str
) -> None:
    token, csrf = await _login(auth_client, db_session, email="guarded-devices@example.com")
    headers = {"Origin": "https://frontend.test", "X-CSRF-Token": csrf}
    if case == "anonymous":
        auth_client.cookies.clear()
    elif case == "missing_csrf":
        del headers["X-CSRF-Token"]
    elif case == "wrong_csrf":
        headers["X-CSRF-Token"] = "wrong"
    else:
        headers["Origin"] = "https://attacker.test"
    response = await auth_client.post("/api/v1/auth/logout-all", headers=headers)
    assert response.status_code == (401 if case == "anonymous" else 403)
    assert (await _stored_session(db_session, token)).revoked_at is None
