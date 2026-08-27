import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import (
    ApiIdempotencyRecord,
    AuditEvent,
    BackgroundJob,
    EmailDelivery,
    Invitation,
    InvitationRateLimitBucket,
    Organization,
    Session,
    User,
)
from app.security.invitation_tokens import InvitationTokenManager
from app.security.tokens import hash_secret
from tests.factories import make_membership, make_organization, make_user
from tests.factories.auth import make_admin_access

FIXED_NOW = datetime.now(UTC).replace(microsecond=0)


async def authorize_organization_admin(
    db_session: AsyncSession,
    auth_client: AsyncClient,
    organization: Organization,
    *,
    mfa_verified: bool = True,
    is_admin: bool = True,
    user_email: str = "invitation-admin@example.com",
) -> tuple[User, dict[str, str]]:
    user = make_user(email_normalized=user_email)
    db_session.add(user)
    await db_session.flush()
    if is_admin:
        db_session.add(
            make_admin_access(
                user,
                scope="organization_admin",
                organization_id=organization.id,
            )
        )
    raw_session = f"session-{user_email}"
    csrf_token = f"csrf-{user_email}"
    db_session.add(
        Session(
            user_id=user.id,
            token_hash=hash_secret(raw_session),
            csrf_token_hash=hash_secret(csrf_token),
            last_seen_at=FIXED_NOW,
            absolute_expires_at=FIXED_NOW + timedelta(days=30),
            mfa_verified_at=FIXED_NOW if mfa_verified else None,
        )
    )
    await db_session.commit()
    auth_client.cookies.set("horeca_session", raw_session)
    return user, {
        "Origin": "https://frontend.test",
        "X-CSRF-Token": csrf_token,
        "Idempotency-Key": "create-invitation-1",
    }


async def test_organization_admin_creates_invitation(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization(name="Create invitation organization")
    db_session.add(organization)
    await db_session.flush()
    _admin, headers = await authorize_organization_admin(
        db_session,
        auth_client,
        organization,
    )

    response = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/invitations",
        headers=headers,
        json={"email": " Employee@Example.COM "},
    )

    assert response.status_code == 201
    assert response.json()["email"] == "employee@example.com"
    assert response.json()["status"] == "pending"


async def test_create_commits_invitation_outbox_audit_and_idempotency_atomically(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization(name="Atomic invitation organization")
    db_session.add(organization)
    await db_session.flush()
    admin, headers = await authorize_organization_admin(
        db_session,
        auth_client,
        organization,
    )

    response = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/invitations",
        headers=headers,
        json={"email": "employee@example.com"},
    )

    assert response.status_code == 201
    invitation_id = response.json()["id"]
    invitation = await db_session.get(Invitation, invitation_id)
    assert invitation is not None
    manager = InvitationTokenManager(auth_settings.invitation_token_hmac_keys)
    raw_token = manager.derive(
        invitation.id,
        token_version=invitation.token_version,
        key_index=invitation.token_key_index,
    )
    assert invitation.token_hash == hash_secret(raw_token)
    assert invitation.expires_at == FIXED_NOW + timedelta(hours=72)
    job = await db_session.scalar(
        select(BackgroundJob).where(
            BackgroundJob.payload["invitation_id"].as_string() == str(invitation.id)
        )
    )
    assert job is not None
    delivery = await db_session.scalar(select(EmailDelivery).where(EmailDelivery.job_id == job.id))
    audit = await db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.action == "invitation_created",
            AuditEvent.target_id == invitation.id,
        )
    )
    idempotency = await db_session.scalar(
        select(ApiIdempotencyRecord).where(
            ApiIdempotencyRecord.organization_id == organization.id,
            ApiIdempotencyRecord.actor_user_id == admin.id,
        )
    )
    assert delivery is not None
    assert audit is not None
    assert idempotency is not None and idempotency.resource_id == invitation.id
    assert raw_token not in response.text
    assert raw_token not in str(job.payload)
    assert "token_hash" not in response.text
    assert set(response.json()) == {
        "id",
        "organization_id",
        "email",
        "status",
        "expires_at",
        "created_at",
        "updated_at",
    }


async def test_create_idempotency_replays_without_duplicate_side_effects(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization()
    db_session.add(organization)
    await db_session.flush()
    _admin, headers = await authorize_organization_admin(
        db_session,
        auth_client,
        organization,
    )
    url = f"/api/v1/organizations/{organization.id}/invitations"

    first = await auth_client.post(url, headers=headers, json={"email": "same@example.com"})
    second = await auth_client.post(url, headers=headers, json={"email": "same@example.com"})

    assert first.status_code == second.status_code == 201
    assert first.json() == second.json()
    assert await db_session.scalar(select(func.count()).select_from(Invitation)) == 1
    assert await db_session.scalar(select(func.count()).select_from(BackgroundJob)) == 1
    assert await db_session.scalar(select(func.count()).select_from(EmailDelivery)) == 1
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "invitation_created")
        )
        == 1
    )


async def test_concurrent_create_replay_commits_one_logical_invitation(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization()
    db_session.add(organization)
    await db_session.flush()
    _admin, headers = await authorize_organization_admin(
        db_session,
        auth_client,
        organization,
    )
    url = f"/api/v1/organizations/{organization.id}/invitations"

    first, second = await asyncio.gather(
        auth_client.post(url, headers=headers, json={"email": "concurrent@example.com"}),
        auth_client.post(url, headers=headers, json={"email": "concurrent@example.com"}),
    )

    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert await db_session.scalar(select(func.count()).select_from(Invitation)) == 1
    assert await db_session.scalar(select(func.count()).select_from(BackgroundJob)) == 1


async def test_concurrent_different_keys_preserve_one_pending_invitation(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization()
    db_session.add(organization)
    await db_session.flush()
    _admin, headers = await authorize_organization_admin(
        db_session,
        auth_client,
        organization,
    )
    second_headers = {**headers, "Idempotency-Key": "concurrent-second-key"}
    url = f"/api/v1/organizations/{organization.id}/invitations"

    responses = await asyncio.gather(
        auth_client.post(url, headers=headers, json={"email": "one-pending@example.com"}),
        auth_client.post(
            url,
            headers=second_headers,
            json={"email": "one-pending@example.com"},
        ),
    )

    assert sorted(response.status_code for response in responses) == [201, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["code"] == "INVITATION_ALREADY_PENDING"
    assert await db_session.scalar(select(func.count()).select_from(Invitation)) == 1


async def test_create_rejects_reused_key_with_changed_request(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization()
    db_session.add(organization)
    await db_session.flush()
    _admin, headers = await authorize_organization_admin(
        db_session,
        auth_client,
        organization,
    )
    url = f"/api/v1/organizations/{organization.id}/invitations"
    first = await auth_client.post(url, headers=headers, json={"email": "first@example.com"})

    changed = await auth_client.post(url, headers=headers, json={"email": "second@example.com"})

    assert first.status_code == 201
    assert changed.status_code == 409
    assert changed.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert await db_session.scalar(select(func.count()).select_from(Invitation)) == 1


async def test_create_rejects_another_pending_invitation_with_different_key(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization()
    db_session.add(organization)
    await db_session.flush()
    _admin, headers = await authorize_organization_admin(
        db_session,
        auth_client,
        organization,
    )
    url = f"/api/v1/organizations/{organization.id}/invitations"
    first = await auth_client.post(url, headers=headers, json={"email": "same@example.com"})
    headers["Idempotency-Key"] = "create-invitation-2"

    duplicate = await auth_client.post(url, headers=headers, json={"email": "same@example.com"})

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "INVITATION_ALREADY_PENDING"
    assert await db_session.scalar(select(func.count()).select_from(Invitation)) == 1


@pytest.mark.parametrize(
    ("membership_status", "expected_code"),
    [
        ("active", "MEMBERSHIP_ALREADY_ACTIVE"),
        ("pending", "MEMBERSHIP_ALREADY_PENDING"),
        ("disabled", "MEMBERSHIP_DISABLED"),
    ],
)
async def test_create_rejects_existing_membership_states(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    membership_status: str,
    expected_code: str,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization()
    invited_user = make_user(email_normalized="member@example.com")
    membership_values: dict[str, Any] = {"status": membership_status}
    if membership_status == "pending":
        membership_values["activated_at"] = None
    if membership_status == "disabled":
        membership_values["disabled_at"] = FIXED_NOW
    db_session.add_all(
        [
            organization,
            invited_user,
            make_membership(organization, invited_user, **membership_values),
        ]
    )
    await db_session.flush()
    _admin, headers = await authorize_organization_admin(
        db_session,
        auth_client,
        organization,
    )

    response = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/invitations",
        headers=headers,
        json={"email": invited_user.email_normalized},
    )

    assert response.status_code == 409
    assert response.json()["code"] == expected_code
    assert await db_session.scalar(select(func.count()).select_from(Invitation)) == 0


async def create_invitation_and_token(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
    *,
    invited_email: str = "validate@example.com",
) -> tuple[Invitation, str]:
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization(name="Validation organization")
    db_session.add(organization)
    await db_session.flush()
    _admin, headers = await authorize_organization_admin(
        db_session,
        auth_client,
        organization,
    )
    response = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/invitations",
        headers=headers,
        json={"email": invited_email},
    )
    assert response.status_code == 201
    invitation = await db_session.get(Invitation, response.json()["id"])
    assert invitation is not None
    manager = InvitationTokenManager(auth_settings.invitation_token_hmac_keys)
    return invitation, manager.derive(
        invitation.id,
        token_version=invitation.token_version,
        key_index=invitation.token_key_index,
    )


async def test_public_validate_returns_safe_capability_context(
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
    audit_count_before = await db_session.scalar(select(func.count()).select_from(AuditEvent))

    response = await auth_client.post(
        "/api/v1/invitations/validate",
        json={"token": raw_token},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "valid",
        "organization_id": str(invitation.organization_id),
        "organization_name": "Validation organization",
        "email_masked": "v***@example.com",
        "acceptance_mode": "activate_access",
        "expires_at": invitation.expires_at.isoformat().replace("+00:00", "Z"),
    }
    assert raw_token not in response.text
    assert invitation.email_normalized not in response.text
    assert (
        await db_session.scalar(select(func.count()).select_from(AuditEvent)) == audit_count_before
    )


async def test_public_validate_detects_existing_account_without_membership(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    db_session.add(make_user(email_normalized="existing@example.com"))
    await db_session.commit()
    _invitation, raw_token = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
        invited_email="existing@example.com",
    )

    response = await auth_client.post(
        "/api/v1/invitations/validate",
        json={"token": raw_token},
    )

    assert response.status_code == 200
    assert response.json()["acceptance_mode"] == "accept_existing_account"


@pytest.mark.parametrize(
    ("state", "expected_status", "expected_code"),
    [
        ("expired", 410, "INVITATION_EXPIRED"),
        ("revoked", 410, "INVITATION_REVOKED"),
        ("accepted", 409, "INVITATION_ALREADY_ACCEPTED"),
    ],
)
async def test_public_validate_returns_stable_lifecycle_errors(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
    state: str,
    expected_status: int,
    expected_code: str,
) -> None:
    invitation, raw_token = await create_invitation_and_token(
        auth_client,
        auth_app,
        auth_settings,
        db_session,
    )
    if state == "expired":
        invitation.expires_at = invitation.created_at + timedelta(seconds=1)
        auth_app.state.clock = lambda: invitation.expires_at
    elif state == "revoked":
        invitation.status = "revoked"
        invitation.revoked_at = FIXED_NOW
    else:
        invitation.status = "accepted"
        invitation.accepted_at = FIXED_NOW
    await db_session.commit()

    response = await auth_client.post(
        "/api/v1/invitations/validate",
        json={"token": raw_token},
    )

    assert response.status_code == expected_status
    assert response.json()["code"] == expected_code


async def test_public_validate_unknown_token_is_non_enumerating(
    auth_client: AsyncClient,
) -> None:
    response = await auth_client.post(
        "/api/v1/invitations/validate",
        json={"token": "malformed-or-unknown-token"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "INVITATION_NOT_FOUND"


async def test_validate_rate_limit_blocks_eleventh_failed_fingerprint(
    auth_client: AsyncClient,
    auth_app: FastAPI,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    responses = [
        await auth_client.post(
            "/api/v1/invitations/validate",
            json={"token": "same-invalid-token"},
        )
        for _ in range(11)
    ]

    assert [response.status_code for response in responses[:10]] == [404] * 10
    assert responses[10].status_code == 429
    assert responses[10].json()["code"] == "AUTH_RATE_LIMITED"


async def test_successful_validate_clears_matching_failure_bucket(
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
    token_fingerprint = hash_secret(raw_token)
    db_session.add(
        InvitationRateLimitBucket(
            action="validate",
            subject_hash=token_fingerprint,
            window_started_at=FIXED_NOW,
            request_count=3,
        )
    )
    await db_session.commit()

    response = await auth_client.post(
        "/api/v1/invitations/validate",
        json={"token": raw_token},
    )

    assert response.status_code == 200
    assert (
        await db_session.scalar(
            select(InvitationRateLimitBucket.id).where(
                InvitationRateLimitBucket.action == "validate",
                InvitationRateLimitBucket.subject_hash == token_fingerprint,
            )
        )
        is None
    )
    assert response.json()["organization_id"] == str(invitation.organization_id)


async def test_create_rate_limit_blocks_eleventh_admin_organization_request(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization()
    db_session.add(organization)
    await db_session.flush()
    _admin, headers = await authorize_organization_admin(
        db_session,
        auth_client,
        organization,
    )
    url = f"/api/v1/organizations/{organization.id}/invitations"
    responses = []
    for index in range(11):
        request_headers = {**headers, "Idempotency-Key": f"rate-key-{index}"}
        responses.append(
            await auth_client.post(
                url,
                headers=request_headers,
                json={"email": f"rate-{index}@example.com"},
            )
        )

    assert [response.status_code for response in responses[:10]] == [201] * 10
    assert responses[10].status_code == 429
    assert responses[10].json()["code"] == "AUTH_RATE_LIMITED"
    assert await db_session.scalar(select(func.count()).select_from(Invitation)) == 10


async def test_create_requires_csrf_mfa_admin_scope_and_idempotency_header(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization()
    db_session.add(organization)
    await db_session.flush()
    _admin, headers = await authorize_organization_admin(
        db_session,
        auth_client,
        organization,
        mfa_verified=False,
    )
    url = f"/api/v1/organizations/{organization.id}/invitations"

    no_mfa = await auth_client.post(url, headers=headers, json={"email": "one@example.com"})
    assert no_mfa.status_code == 403
    assert no_mfa.json()["code"] == "MFA_REQUIRED"

    auth_client.cookies.clear()
    organization_two = make_organization(name="Second organization")
    db_session.add(organization_two)
    await db_session.flush()
    _admin_two, valid_headers = await authorize_organization_admin(
        db_session,
        auth_client,
        organization_two,
        user_email="second-admin@example.com",
    )
    no_csrf_headers = {"Idempotency-Key": "missing-csrf"}
    no_csrf = await auth_client.post(
        f"/api/v1/organizations/{organization_two.id}/invitations",
        headers=no_csrf_headers,
        json={"email": "two@example.com"},
    )
    assert no_csrf.status_code == 403
    assert no_csrf.json()["code"] == "CSRF_INVALID"

    missing_key_headers = {
        "Origin": valid_headers["Origin"],
        "X-CSRF-Token": valid_headers["X-CSRF-Token"],
    }
    missing_key = await auth_client.post(
        f"/api/v1/organizations/{organization_two.id}/invitations",
        headers=missing_key_headers,
        json={"email": "three@example.com"},
    )
    assert missing_key.status_code == 422
    assert missing_key.json()["code"] == "VALIDATION_ERROR"
    assert await db_session.scalar(select(func.count()).select_from(Invitation)) == 0


async def test_create_hides_foreign_organization_from_admin(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    own = make_organization(name="Own")
    foreign = make_organization(name="Foreign")
    db_session.add_all([own, foreign])
    await db_session.flush()
    _admin, headers = await authorize_organization_admin(db_session, auth_client, own)

    response = await auth_client.post(
        f"/api/v1/organizations/{foreign.id}/invitations",
        headers=headers,
        json={"email": "foreign@example.com"},
    )

    assert response.status_code == 404
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"
    assert await db_session.scalar(select(func.count()).select_from(Invitation)) == 0


async def test_create_denies_employee_without_admin_grant(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization()
    db_session.add(organization)
    await db_session.flush()
    employee, headers = await authorize_organization_admin(
        db_session,
        auth_client,
        organization,
        is_admin=False,
    )
    db_session.add(make_membership(organization, employee))
    await db_session.commit()

    response = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/invitations",
        headers=headers,
        json={"email": "denied@example.com"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert await db_session.scalar(select(func.count()).select_from(Invitation)) == 0


async def test_cors_preflight_allows_idempotency_and_csrf_headers(
    auth_client: AsyncClient,
) -> None:
    response = await auth_client.options(
        "/api/v1/organizations/00000000-0000-0000-0000-000000000001/invitations",
        headers={
            "Origin": "https://frontend.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "idempotency-key,x-csrf-token,content-type",
        },
    )

    assert response.status_code == 200
    allowed_headers = response.headers["access-control-allow-headers"].lower()
    assert "idempotency-key" in allowed_headers
    assert "x-csrf-token" in allowed_headers


def test_invitation_openapi_exposes_only_stage_3_create_and_validate_contracts(
    auth_app: FastAPI,
) -> None:
    schema = auth_app.openapi()
    create_operation = schema["paths"]["/api/v1/organizations/{organization_id}/invitations"][
        "post"
    ]
    validate_operation = schema["paths"]["/api/v1/invitations/validate"]["post"]
    idempotency_parameter = next(
        parameter
        for parameter in create_operation["parameters"]
        if parameter["name"] == "Idempotency-Key"
    )

    assert idempotency_parameter["in"] == "header"
    assert idempotency_parameter["required"] is True
    assert validate_operation["requestBody"]["required"] is True
    assert "/api/v1/invitations/accept" not in schema["paths"]
    invitation_properties = schema["components"]["schemas"]["InvitationResponse"]["properties"]
    validation_properties = schema["components"]["schemas"]["InvitationValidationResponse"][
        "properties"
    ]
    forbidden_fields = {
        "token",
        "token_hash",
        "token_version",
        "token_key_index",
        "idempotency_key",
        "payload",
        "provider",
    }
    assert forbidden_fields.isdisjoint(invitation_properties)
    assert forbidden_fields.isdisjoint(validation_properties)
