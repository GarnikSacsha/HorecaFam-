from datetime import timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import Invitation
from tests.api.test_invitations_create_validate import (
    FIXED_NOW,
    authorize_organization_admin,
    create_invitation_and_token,
)
from tests.factories import make_organization


async def test_list_projects_expiry_and_never_returns_token_fields(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    invitation, token = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
    )
    auth_app.state.clock = lambda: FIXED_NOW + timedelta(days=4)
    url = f"/api/v1/organizations/{invitation.organization_id}/invitations"
    response = await auth_client.get(url)
    assert response.status_code == 200
    body = response.json()
    assert body["next_cursor"] is None
    assert body["items"][0]["status"] == "expired"
    assert set(body["items"][0]) == {
        "id",
        "organization_id",
        "email",
        "status",
        "expires_at",
        "created_at",
        "updated_at",
    }
    assert token not in response.text
    other = make_organization()
    db_session.add(other)
    await db_session.flush()
    db_session.add(
        Invitation(
            organization_id=other.id,
            email_normalized="other-tenant@example.com",
            token_hash="a" * 64,
            invited_by_user_id=invitation.invited_by_user_id,
            expires_at=FIXED_NOW + timedelta(days=3),
        )
    )
    await db_session.commit()
    isolated = await auth_client.get(url)
    assert [item["id"] for item in isolated.json()["items"]] == [str(invitation.id)]
    assert "other-tenant@example.com" not in isolated.text
    denied = await auth_client.get(f"/api/v1/organizations/{other.id}/invitations")
    assert denied.status_code == 404


async def test_list_pagination_and_invalid_limits(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    invitation, _ = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
    )
    url = f"/api/v1/organizations/{invitation.organization_id}/invitations"
    created = await auth_client.post(
        url,
        json={"email": "second@example.com"},
        headers={
            "Origin": "https://frontend.test",
            "X-CSRF-Token": "csrf-invitation-admin@example.com",
            "Idempotency-Key": "second-invitation",
        },
    )
    assert created.status_code == 201
    first = (await auth_client.get(url, params={"limit": 1})).json()
    assert len(first["items"]) == 1
    assert first["next_cursor"]
    second = (
        await auth_client.get(url, params={"limit": 1, "cursor": first["next_cursor"]})
    ).json()
    assert len(second["items"]) == 1
    assert second["next_cursor"] is None
    assert first["items"][0]["id"] != second["items"][0]["id"]
    invalid_params: list[dict[str, str | int]] = [
        {"limit": 0},
        {"limit": 101},
        {"cursor": "invalid"},
    ]
    for params in invalid_params:
        assert (await auth_client.get(url, params=params)).status_code == 422


@pytest.mark.parametrize("is_admin,mfa_verified", [(False, True), (True, False)])
async def test_list_requires_admin_and_mfa(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    is_admin: bool,
    mfa_verified: bool,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization()
    db_session.add(organization)
    await db_session.flush()
    await authorize_organization_admin(
        db_session, auth_client, organization, is_admin=is_admin, mfa_verified=mfa_verified
    )
    url = f"/api/v1/organizations/{organization.id}/invitations"
    assert (await auth_client.get(url)).status_code == (403 if is_admin else 404)
    auth_client.cookies.clear()
    assert (await auth_client.get(url)).status_code == 401
