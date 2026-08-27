from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import (
    AuthRateLimitBucket,
    EmployeeProfile,
    Invitation,
    OrganizationMembership,
    Session,
    User,
)
from app.security.invitation_tokens import InvitationTokenManager
from app.security.passwords import PasswordManager
from app.security.tokens import hash_secret
from tests.factories import make_invitation, make_organization, make_user

FIXED_NOW = datetime(2026, 8, 27, 10, 0, tzinfo=UTC)


async def arrange_public_invitation(
    db_session: AsyncSession,
    auth_settings: Settings,
    *,
    invited_email: str,
) -> tuple[Invitation, str]:
    organization = make_organization(name="HTTP acceptance organization")
    inviter = make_user(email_normalized=f"http-inviter-{uuid4()}@example.com")
    db_session.add_all([organization, inviter])
    await db_session.flush()
    invitation_id = uuid4()
    manager = InvitationTokenManager(auth_settings.invitation_token_hmac_keys)
    raw_token = manager.derive(invitation_id, token_version=1, key_index=0)
    invitation = make_invitation(
        organization,
        inviter,
        id=invitation_id,
        email_normalized=invited_email,
        token_hash=hash_secret(raw_token),
        expires_at=FIXED_NOW + timedelta(hours=72),
    )
    db_session.add(invitation)
    await db_session.commit()
    return invitation, raw_token


async def test_new_user_acceptance_returns_safe_session_and_secure_cookie(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    invitation, raw_token = await arrange_public_invitation(
        db_session,
        auth_settings,
        invited_email="http-new-user@example.com",
    )

    response = await auth_client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "acceptance_mode": "activate_access",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "accepted"
    assert body["acceptance_mode"] == "activate_access"
    assert body["user"]["email"] == "http-new-user@example.com"
    assert body["session"]["mfa_verified"] is False
    assert body["membership"] == {
        "id": body["membership"]["id"],
        "organization_id": str(invitation.organization_id),
        "employee_profile_id": body["membership"]["employee_profile_id"],
        "status": "pending",
    }
    assert body["organization_access"] == [
        {
            "organization_id": str(invitation.organization_id),
            "membership_status": "pending",
            "is_employee": True,
            "is_organization_admin": False,
        }
    ]
    assert body["platform_operator"] is False
    assert body["csrf_token"]
    assert raw_token not in response.text
    assert "password" not in response.text
    assert "token_hash" not in response.text
    cookie = response.headers["set-cookie"]
    assert "horeca_session=" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "Path=/api/v1" in cookie
    assert "SameSite=lax" in cookie
    user = await db_session.scalar(
        select(User).where(User.email_normalized == "http-new-user@example.com")
    )
    assert user is not None
    membership = await db_session.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == invitation.organization_id,
            OrganizationMembership.user_id == user.id,
        )
    )
    assert membership is not None and membership.status == "pending"
    session_context = await auth_client.get("/api/v1/auth/session")
    assert session_context.status_code == 200
    assert session_context.json()["organization_access"] == body["organization_access"]


async def test_existing_user_acceptance_reuses_user_with_one_character_password(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    passwords = PasswordManager()
    existing_user = make_user(
        email_normalized="http-existing@example.com",
        password_hash=passwords.hash("x"),
    )
    db_session.add(existing_user)
    await db_session.commit()
    existing_user_id = existing_user.id
    invitation, raw_token = await arrange_public_invitation(
        db_session,
        auth_settings,
        invited_email=existing_user.email_normalized,
    )

    response = await auth_client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "acceptance_mode": "accept_existing_account",
            "password": "x",
        },
    )

    assert response.status_code == 201
    assert response.json()["acceptance_mode"] == "accept_existing_account"
    assert response.json()["user"]["id"] == str(existing_user_id)
    assert response.json()["membership"]["organization_id"] == str(invitation.organization_id)
    assert (
        await db_session.scalar(
            select(User.id).where(User.email_normalized == existing_user.email_normalized)
        )
        == existing_user_id
    )


@pytest.mark.parametrize("password", ["short7", "x" * 129])
async def test_activate_access_enforces_password_bounds_before_mutation(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
    password: str,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    invitation, raw_token = await arrange_public_invitation(
        db_session,
        auth_settings,
        invited_email="password-bounds@example.com",
    )

    response = await auth_client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "acceptance_mode": "activate_access",
            "password": password,
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    await db_session.refresh(invitation)
    assert invitation.status == "pending"
    assert (
        await db_session.scalar(
            select(User.id).where(User.email_normalized == "password-bounds@example.com")
        )
        is None
    )


async def test_accept_rejects_authoritative_and_unknown_fields_without_mutation(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    invitation, raw_token = await arrange_public_invitation(
        db_session,
        auth_settings,
        invited_email="forbidden-fields@example.com",
    )

    response = await auth_client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "acceptance_mode": "activate_access",
            "password": "correct horse battery staple",
            "email": "attacker@example.com",
            "organization_id": str(uuid4()),
            "status": "active",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    await db_session.refresh(invitation)
    assert invitation.status == "pending"
    assert (
        await db_session.scalar(
            select(User.id).where(User.email_normalized == "attacker@example.com")
        )
        is None
    )


async def test_existing_wrong_password_is_non_enumerating_and_mutation_free(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    passwords = PasswordManager()
    existing_user = make_user(
        email_normalized="http-wrong-password@example.com",
        password_hash=passwords.hash("correct password"),
    )
    db_session.add(existing_user)
    await db_session.commit()
    invitation, raw_token = await arrange_public_invitation(
        db_session,
        auth_settings,
        invited_email=existing_user.email_normalized,
    )

    response = await auth_client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "acceptance_mode": "accept_existing_account",
            "password": "wrong password",
        },
    )

    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"
    assert existing_user.email_normalized not in response.text
    await db_session.refresh(invitation)
    assert invitation.status == "pending"
    assert await db_session.scalar(select(func.count()).select_from(Session)) == 0
    assert await db_session.scalar(select(func.count()).select_from(EmployeeProfile)) == 0
    assert await db_session.scalar(select(func.count()).select_from(AuthRateLimitBucket)) == 1


@pytest.mark.parametrize(
    ("state", "expected_status", "expected_code"),
    [
        ("expired", 410, "INVITATION_EXPIRED"),
        ("revoked", 410, "INVITATION_REVOKED"),
        ("accepted", 409, "INVITATION_ALREADY_ACCEPTED"),
    ],
)
async def test_accept_returns_canonical_lifecycle_errors_without_side_effects(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
    state: str,
    expected_status: int,
    expected_code: str,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    invitation, raw_token = await arrange_public_invitation(
        db_session,
        auth_settings,
        invited_email=f"{state}-acceptance@example.com",
    )
    if state == "expired":
        invitation.expires_at = FIXED_NOW
    else:
        invitation.status = state
        if state == "revoked":
            invitation.revoked_at = FIXED_NOW
        else:
            invitation.accepted_at = FIXED_NOW
    await db_session.commit()

    response = await auth_client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "acceptance_mode": "activate_access",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == expected_status
    assert response.json()["code"] == expected_code
    assert await db_session.scalar(select(func.count()).select_from(Session)) == 0
    assert await db_session.scalar(select(func.count()).select_from(OrganizationMembership)) == 0
    assert await db_session.scalar(select(func.count()).select_from(EmployeeProfile)) == 0


async def test_accept_unknown_token_uses_canonical_not_found_error(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW

    response = await auth_client.post(
        "/api/v1/invitations/accept",
        json={
            "token": "unknown-capability-token",
            "acceptance_mode": "activate_access",
            "password": "correct horse battery staple",
        },
    )

    assert response.status_code == 404
    assert response.json()["code"] == "INVITATION_NOT_FOUND"
    assert await db_session.scalar(select(func.count()).select_from(User)) == 0
    assert await db_session.scalar(select(func.count()).select_from(Session)) == 0


def resolve_schema(openapi: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    reference = schema.get("$ref")
    if reference is None:
        return schema
    return cast(
        dict[str, Any],
        openapi["components"]["schemas"][reference.rsplit("/", maxsplit=1)[-1]],
    )


def test_accept_openapi_exposes_exact_public_discriminated_contract(auth_app: FastAPI) -> None:
    openapi = auth_app.openapi()
    operation = openapi["paths"]["/api/v1/invitations/accept"]["post"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    assert request_schema["discriminator"]["propertyName"] == "acceptance_mode"
    assert len(request_schema["oneOf"]) == 2
    assert "201" in operation["responses"]
    assert not operation.get("security")
    assert all(
        parameter["name"] != "Idempotency-Key" for parameter in operation.get("parameters", [])
    )
    response_schema = resolve_schema(
        openapi,
        operation["responses"]["201"]["content"]["application/json"]["schema"],
    )
    response_properties = response_schema["properties"]
    assert set(response_properties) == {
        "status",
        "acceptance_mode",
        "membership",
        "user",
        "session",
        "organization_access",
        "platform_operator",
        "csrf_token",
    }
    serialized = str(operation)
    for forbidden in (
        "password_hash",
        "token_hash",
        "token_version",
        "token_key_index",
        "audit",
        "idempotency_key",
        "job",
        "delivery",
    ):
        assert forbidden not in serialized
