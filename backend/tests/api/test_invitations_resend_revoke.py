import asyncio
from datetime import timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import (
    AuditEvent,
    BackgroundJob,
    EmailDelivery,
    InvitationRateLimitBucket,
)
from app.security.invitation_tokens import InvitationTokenManager
from tests.api.test_invitations_create_validate import (
    FIXED_NOW,
    create_invitation_and_token,
)
from tests.factories import make_organization


def mutation_headers(*, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {
        "Origin": "https://frontend.test",
        "X-CSRF-Token": "csrf-invitation-admin@example.com",
    }
    if idempotency_key is not None:
        headers["Idempotency-Key"] = idempotency_key
    return headers


async def test_organization_admin_resends_pending_invitation(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    invitation, _old_token = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
    )
    auth_app.state.clock = lambda: FIXED_NOW

    response = await auth_client.post(
        f"/api/v1/organizations/{invitation.organization_id}/invitations/{invitation.id}/resend",
        headers=mutation_headers(idempotency_key="resend-invitation-1"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"


async def test_resend_rotates_token_resets_expiry_and_commits_one_outbox_audit(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    invitation, old_token = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
    )
    resend_now = FIXED_NOW + timedelta(days=1)
    auth_app.state.clock = lambda: resend_now

    response = await auth_client.post(
        f"/api/v1/organizations/{invitation.organization_id}/invitations/{invitation.id}/resend",
        headers=mutation_headers(idempotency_key="rotate-once"),
    )

    assert response.status_code == 200
    await db_session.refresh(invitation)
    rotated = invitation
    manager = InvitationTokenManager(auth_settings.invitation_token_hmac_keys)
    new_token = manager.derive(
        rotated.id,
        token_version=rotated.token_version,
        key_index=rotated.token_key_index,
    )
    assert rotated.token_version == 2
    assert rotated.expires_at == resend_now + timedelta(hours=72)
    assert new_token != old_token
    assert await db_session.scalar(select(func.count()).select_from(BackgroundJob)) == 2
    assert await db_session.scalar(select(func.count()).select_from(EmailDelivery)) == 2
    audit = await db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "invitation_resent",
            AuditEvent.target_id == invitation.id,
        )
    )
    assert audit is not None
    assert audit.old_values is not None and audit.old_values["token_version"] == 1
    assert audit.new_values is not None and audit.new_values["token_version"] == 2
    assert old_token not in response.text
    assert new_token not in response.text
    assert old_token not in str(audit.old_values)
    assert new_token not in str(audit.new_values)

    old_validation = await auth_client.post(
        "/api/v1/invitations/validate",
        json={"token": old_token},
    )
    new_validation = await auth_client.post(
        "/api/v1/invitations/validate",
        json={"token": new_token},
    )
    assert old_validation.status_code == 404
    assert old_validation.json()["code"] == "INVITATION_NOT_FOUND"
    assert new_validation.status_code == 200

    revoke_response = await auth_client.post(
        f"/api/v1/organizations/{invitation.organization_id}/invitations/{invitation.id}/revoke",
        headers=mutation_headers(),
    )
    revoked_validation = await auth_client.post(
        "/api/v1/invitations/validate",
        json={"token": new_token},
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["status"] == "revoked"
    assert revoked_validation.status_code == 410
    assert revoked_validation.json()["code"] == "INVITATION_REVOKED"


async def test_resend_same_idempotency_key_replays_without_rotation_or_duplicate_job(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    invitation, _old_token = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
    )
    url = f"/api/v1/organizations/{invitation.organization_id}/invitations/{invitation.id}/resend"
    headers = mutation_headers(idempotency_key="same-resend")

    responses = [await auth_client.post(url, headers=headers) for _ in range(5)]

    assert [response.status_code for response in responses] == [200] * 5
    assert all(response.json() == responses[0].json() for response in responses)
    await db_session.refresh(invitation)
    stored = invitation
    assert stored.token_version == 2
    assert await db_session.scalar(select(func.count()).select_from(BackgroundJob)) == 2
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "invitation_resent")
        )
        == 1
    )
    rate_bucket = await db_session.scalar(
        select(InvitationRateLimitBucket).where(InvitationRateLimitBucket.action == "resend")
    )
    assert rate_bucket is not None and rate_bucket.request_count == 1


async def test_concurrent_resend_same_key_has_one_rotation(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    invitation, _old_token = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
    )
    url = f"/api/v1/organizations/{invitation.organization_id}/invitations/{invitation.id}/resend"
    headers = mutation_headers(idempotency_key="concurrent-resend")

    first, second = await asyncio.gather(
        auth_client.post(url, headers=headers),
        auth_client.post(url, headers=headers),
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    await db_session.refresh(invitation)
    stored = invitation
    assert stored.token_version == 2
    assert await db_session.scalar(select(func.count()).select_from(BackgroundJob)) == 2


async def test_resend_same_key_for_another_invitation_is_rejected(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    first_invitation, _old_token = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
    )
    create_second = await auth_client.post(
        f"/api/v1/organizations/{first_invitation.organization_id}/invitations",
        headers=mutation_headers(idempotency_key="create-second-invitation"),
        json={"email": "second-invitation@example.com"},
    )
    assert create_second.status_code == 201
    first_resend = await auth_client.post(
        f"/api/v1/organizations/{first_invitation.organization_id}"
        f"/invitations/{first_invitation.id}/resend",
        headers=mutation_headers(idempotency_key="shared-resend-key"),
    )

    reused = await auth_client.post(
        f"/api/v1/organizations/{first_invitation.organization_id}"
        f"/invitations/{create_second.json()['id']}/resend",
        headers=mutation_headers(idempotency_key="shared-resend-key"),
    )

    assert first_resend.status_code == 200
    assert reused.status_code == 409
    assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert await db_session.scalar(select(func.count()).select_from(BackgroundJob)) == 3


async def test_resend_renews_derived_expired_pending_invitation(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    invitation, _old_token = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
    )
    invitation.expires_at = invitation.created_at + timedelta(seconds=1)
    await db_session.commit()
    resend_now = invitation.expires_at + timedelta(seconds=1)
    auth_app.state.clock = lambda: resend_now

    response = await auth_client.post(
        f"/api/v1/organizations/{invitation.organization_id}/invitations/{invitation.id}/resend",
        headers=mutation_headers(idempotency_key="renew-expired"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    await db_session.refresh(invitation)
    assert invitation.token_version == 2
    assert invitation.expires_at == resend_now + timedelta(hours=72)


@pytest.mark.parametrize(
    ("invitation_status", "expected_code"),
    [
        ("revoked", "INVITATION_REVOKED"),
        ("accepted", "INVITATION_ALREADY_ACCEPTED"),
    ],
)
async def test_resend_rejects_terminal_invitation_state(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
    invitation_status: str,
    expected_code: str,
) -> None:
    invitation, _old_token = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
    )
    invitation.status = invitation_status
    if invitation_status == "revoked":
        invitation.revoked_at = FIXED_NOW
    else:
        invitation.accepted_at = FIXED_NOW
    await db_session.commit()

    response = await auth_client.post(
        f"/api/v1/organizations/{invitation.organization_id}/invitations/{invitation.id}/resend",
        headers=mutation_headers(idempotency_key="terminal-resend"),
    )

    assert response.status_code == 409
    assert response.json()["code"] == expected_code
    assert await db_session.scalar(select(func.count()).select_from(BackgroundJob)) == 1


async def test_resend_rate_limit_blocks_fourth_admin_invitation_request(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    invitation, _old_token = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
    )
    url = f"/api/v1/organizations/{invitation.organization_id}/invitations/{invitation.id}/resend"
    responses = [
        await auth_client.post(
            url,
            headers=mutation_headers(idempotency_key=f"resend-rate-{index}"),
        )
        for index in range(4)
    ]

    assert [response.status_code for response in responses[:3]] == [200] * 3
    assert responses[3].status_code == 429
    assert responses[3].json()["code"] == "AUTH_RATE_LIMITED"
    await db_session.refresh(invitation)
    stored = invitation
    assert stored.token_version == 4
    assert await db_session.scalar(select(func.count()).select_from(BackgroundJob)) == 4


async def test_revoke_is_naturally_idempotent_and_invalidates_validation(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    invitation, raw_token = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
    )
    url = f"/api/v1/organizations/{invitation.organization_id}/invitations/{invitation.id}/revoke"

    first = await auth_client.post(url, headers=mutation_headers())
    second = await auth_client.post(url, headers=mutation_headers())

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert first.json()["status"] == "revoked"
    validation = await auth_client.post(
        "/api/v1/invitations/validate",
        json={"token": raw_token},
    )
    assert validation.status_code == 410
    assert validation.json()["code"] == "INVITATION_REVOKED"
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "invitation_revoked")
        )
        == 1
    )


async def test_concurrent_revoke_creates_one_transition_audit(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    invitation, _raw_token = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
    )
    url = f"/api/v1/organizations/{invitation.organization_id}/invitations/{invitation.id}/revoke"

    first, second = await asyncio.gather(
        auth_client.post(url, headers=mutation_headers()),
        auth_client.post(url, headers=mutation_headers()),
    )

    assert first.status_code == second.status_code == 200
    assert first.json()["status"] == second.json()["status"] == "revoked"
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "invitation_revoked")
        )
        == 1
    )


async def test_revoke_rejects_accepted_invitation(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    invitation, _raw_token = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
    )
    invitation.status = "accepted"
    invitation.accepted_at = FIXED_NOW
    await db_session.commit()

    response = await auth_client.post(
        f"/api/v1/organizations/{invitation.organization_id}/invitations/{invitation.id}/revoke",
        headers=mutation_headers(),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "INVITATION_ALREADY_ACCEPTED"
    assert (
        await db_session.scalar(
            select(AuditEvent.id).where(AuditEvent.action == "invitation_revoked")
        )
        is None
    )


@pytest.mark.parametrize("action", ["resend", "revoke"])
async def test_resend_and_revoke_hide_foreign_organization(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
    action: str,
) -> None:
    invitation, _raw_token = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
    )
    foreign = make_organization(name="Foreign organization")
    db_session.add(foreign)
    await db_session.commit()
    headers = mutation_headers(idempotency_key="foreign-resend" if action == "resend" else None)

    response = await auth_client.post(
        f"/api/v1/organizations/{foreign.id}/invitations/{invitation.id}/{action}",
        headers=headers,
    )

    assert response.status_code == 404
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"
    await db_session.refresh(invitation)
    stored = invitation
    assert stored.status == "pending" and stored.token_version == 1


@pytest.mark.parametrize("action", ["resend", "revoke"])
async def test_resend_and_revoke_require_valid_csrf(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
    action: str,
) -> None:
    invitation, _raw_token = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
    )
    headers = {"Idempotency-Key": "missing-csrf"} if action == "resend" else {}

    response = await auth_client.post(
        f"/api/v1/organizations/{invitation.organization_id}/invitations/{invitation.id}/{action}",
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_INVALID"
    await db_session.refresh(invitation)
    stored = invitation
    assert stored.status == "pending" and stored.token_version == 1


def test_invitation_openapi_includes_resend_and_revoke_but_not_accept(
    auth_app: FastAPI,
) -> None:
    paths = auth_app.openapi()["paths"]

    assert "/api/v1/organizations/{organization_id}/invitations/{invitation_id}/resend" in paths
    assert "/api/v1/organizations/{organization_id}/invitations/{invitation_id}/revoke" in paths
    assert "/api/v1/invitations/accept" not in paths
