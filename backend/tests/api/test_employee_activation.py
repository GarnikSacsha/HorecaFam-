import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import AuthorizationContext, require_active_employee
from app.models import (
    ApiIdempotencyRecord,
    AuditEvent,
    EmployeeProfile,
    Organization,
    OrganizationMembership,
    Session,
)
from app.security.tokens import hash_secret
from app.services import employees as employee_service
from app.services.applicability import ActivationApplicabilityResult
from tests.factories.auth import make_admin_access
from tests.factories.identity import (
    make_location,
    make_membership,
    make_organization,
    make_role,
    make_user,
)

FIXED_NOW = datetime(2030, 8, 27, 14, 0, tzinfo=UTC)


async def _arrange_admin_session(
    client: AsyncClient,
    app: FastAPI,
    db: AsyncSession,
    *,
    organization: Organization,
) -> tuple[UUID, str]:
    app.state.clock = lambda: FIXED_NOW
    admin = make_user(email_normalized=f"activation-admin-{uuid4()}@example.com")
    db.add(admin)
    await db.flush()
    db.add(make_admin_access(admin, scope="organization_admin", organization=organization))
    raw_session = f"activation-admin-session-{uuid4()}"
    csrf_token = f"activation-csrf-{uuid4()}"
    db.add(
        Session(
            user_id=admin.id,
            token_hash=hash_secret(raw_session),
            csrf_token_hash=hash_secret(csrf_token),
            last_seen_at=FIXED_NOW,
            absolute_expires_at=FIXED_NOW + timedelta(days=30),
            mfa_verified_at=FIXED_NOW,
        )
    )
    await db.commit()
    client.cookies.set("horeca_session", raw_session, path="/api/v1")
    return admin.id, csrf_token


async def _arrange_profile(
    db: AsyncSession,
    *,
    organization: Organization,
    status: str = "pending",
    complete: bool = True,
    role_status: str = "active",
) -> tuple[OrganizationMembership, EmployeeProfile]:
    employee = make_user(email_normalized=f"activation-employee-{uuid4()}@example.com")
    membership = make_membership(
        organization,
        employee,
        status=status,
        activated_at=FIXED_NOW - timedelta(days=1) if status == "active" else None,
        disabled_at=FIXED_NOW - timedelta(days=1) if status == "disabled" else None,
    )
    db.add_all([employee, membership])
    await db.flush()
    role = make_role(organization, status=role_status)
    location = make_location(organization)
    db.add_all([role, location])
    await db.flush()
    profile = EmployeeProfile(
        membership_id=membership.id,
        organization_id=organization.id,
        first_name="Iryna" if complete else None,
        last_name="Koval" if complete else None,
        operational_role_id=role.id if complete else None,
        location_id=location.id if complete else None,
    )
    db.add(profile)
    await db.flush()
    return membership, profile


def _activation_headers(csrf_token: str, *, key: str = "activate-employee") -> dict[str, str]:
    return {
        "Origin": "https://frontend.test",
        "X-CSRF-Token": csrf_token,
        "Idempotency-Key": key,
    }


async def test_admin_activates_complete_employee_with_exact_response_and_safe_audit(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization = make_organization(name="Activation organization")
    db_session.add(organization)
    await db_session.flush()
    admin_id, csrf_token = await _arrange_admin_session(
        auth_client, auth_app, db_session, organization=organization
    )
    membership, profile = await _arrange_profile(db_session, organization=organization)
    await db_session.commit()
    organization_id = organization.id
    membership_id = membership.id
    profile_id = profile.id
    session_count_before = await db_session.scalar(select(func.count()).select_from(Session))
    applicability_calls: list[tuple[UUID, UUID]] = []

    async def capture_applicability(
        _db: AsyncSession,
        *,
        organization_id: UUID,
        employee_profile_id: UUID,
    ) -> ActivationApplicabilityResult:
        applicability_calls.append((organization_id, employee_profile_id))
        return ActivationApplicabilityResult(0, 0, 0)

    monkeypatch.setattr(
        employee_service,
        "evaluate_activation_applicability",
        capture_applicability,
    )

    response = await auth_client.post(
        f"/api/v1/organizations/{organization_id}/employees/{profile_id}/activate",
        headers=_activation_headers(csrf_token),
    )

    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    assert response.json() == {
        "employee_id": str(profile_id),
        "organization_id": str(organization_id),
        "membership_status": "active",
        "training_participation_status": "active",
        "activated_at": FIXED_NOW.isoformat().replace("+00:00", "Z"),
    }
    db_session.expire_all()
    stored = await db_session.get_one(OrganizationMembership, membership_id)
    assert stored.status == "active"
    assert stored.activated_at == FIXED_NOW
    assert stored.disabled_at is None
    audit = await db_session.scalar(
        select(AuditEvent).where(AuditEvent.action == "employee_activated")
    )
    assert audit is not None
    assert audit.organization_id == organization_id
    assert audit.actor_user_id == admin_id
    assert audit.target_type == "employee_profile"
    assert audit.target_id == profile_id
    assert audit.old_values == {"membership_status": "pending"}
    assert audit.new_values == {"membership_status": "active"}
    assert audit.outcome == "success"
    assert "Iryna" not in str(audit.old_values)
    assert "Iryna" not in str(audit.new_values)
    assert applicability_calls == [(organization_id, profile_id)]
    assert (
        await db_session.scalar(select(func.count()).select_from(Session)) == session_count_before
    )


async def test_activated_employee_immediately_passes_existing_active_employee_guard(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    @auth_app.get("/api/v1/test/stage6/organizations/{organization_id}/employee")
    async def active_employee_probe(
        organization_id: UUID,
        _context: Annotated[AuthorizationContext, Depends(require_active_employee)],
    ) -> dict[str, str]:
        return {"organization_id": str(organization_id)}

    organization = make_organization(name="Active access organization")
    db_session.add(organization)
    await db_session.flush()
    _admin_id, csrf_token = await _arrange_admin_session(
        auth_client, auth_app, db_session, organization=organization
    )
    membership, profile = await _arrange_profile(db_session, organization=organization)
    employee_session = f"activation-employee-session-{uuid4()}"
    db_session.add(
        Session(
            user_id=membership.user_id,
            token_hash=hash_secret(employee_session),
            csrf_token_hash=hash_secret(f"employee-csrf-{uuid4()}"),
            last_seen_at=FIXED_NOW,
            absolute_expires_at=FIXED_NOW + timedelta(days=30),
        )
    )
    await db_session.commit()

    activated = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/employees/{profile.id}/activate",
        headers=_activation_headers(csrf_token, key="activate-for-access"),
    )
    assert activated.status_code == 200
    auth_client.cookies.set("horeca_session", employee_session, path="/api/v1")

    access = await auth_client.get(f"/api/v1/test/stage6/organizations/{organization.id}/employee")

    assert access.status_code == 200
    assert access.json() == {"organization_id": str(organization.id)}


@pytest.mark.parametrize("status", ["active", "disabled"])
async def test_non_pending_employee_cannot_be_activated(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    status: str,
) -> None:
    organization = make_organization(name=f"{status} activation organization")
    db_session.add(organization)
    await db_session.flush()
    _admin_id, csrf_token = await _arrange_admin_session(
        auth_client, auth_app, db_session, organization=organization
    )
    _membership, profile = await _arrange_profile(
        db_session, organization=organization, status=status
    )
    await db_session.commit()

    response = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/employees/{profile.id}/activate",
        headers=_activation_headers(csrf_token, key=f"activate-{status}"),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "EMPLOYEE_ACTIVATION_NOT_ALLOWED"
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0


async def test_incomplete_employee_cannot_be_activated(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization = make_organization(name="Incomplete activation organization")
    db_session.add(organization)
    await db_session.flush()
    _admin_id, csrf_token = await _arrange_admin_session(
        auth_client, auth_app, db_session, organization=organization
    )
    membership, profile = await _arrange_profile(
        db_session, organization=organization, complete=False
    )
    await db_session.commit()
    membership_id = membership.id

    response = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/employees/{profile.id}/activate",
        headers=_activation_headers(csrf_token, key="activate-incomplete"),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "EMPLOYEE_PROFILE_INCOMPLETE"
    db_session.expire_all()
    stored = await db_session.get_one(OrganizationMembership, membership_id)
    assert stored.status == "pending"
    assert stored.activated_at is None
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0


async def test_archived_reference_blocks_activation(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization = make_organization(name="Archived reference activation organization")
    db_session.add(organization)
    await db_session.flush()
    _admin_id, csrf_token = await _arrange_admin_session(
        auth_client, auth_app, db_session, organization=organization
    )
    membership, profile = await _arrange_profile(
        db_session,
        organization=organization,
        role_status="archived",
    )
    await db_session.commit()
    membership_id = membership.id

    response = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/employees/{profile.id}/activate",
        headers=_activation_headers(csrf_token, key="activate-archived-role"),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "REFERENCE_INACTIVE"
    db_session.expire_all()
    assert (await db_session.get_one(OrganizationMembership, membership_id)).status == "pending"
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0


async def test_foreign_employee_is_hidden_from_activation(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    own = make_organization(name="Own activation organization")
    foreign = make_organization(name="Foreign activation organization")
    db_session.add_all([own, foreign])
    await db_session.flush()
    _admin_id, csrf_token = await _arrange_admin_session(
        auth_client, auth_app, db_session, organization=own
    )
    _membership, foreign_profile = await _arrange_profile(db_session, organization=foreign)
    await db_session.commit()

    response = await auth_client.post(
        f"/api/v1/organizations/{own.id}/employees/{foreign_profile.id}/activate",
        headers=_activation_headers(csrf_token, key="activate-foreign"),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0


@pytest.mark.parametrize("key", [None, "   "])
async def test_activation_requires_valid_idempotency_key(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    key: str | None,
) -> None:
    organization = make_organization(name="Idempotency header organization")
    db_session.add(organization)
    await db_session.flush()
    _admin_id, csrf_token = await _arrange_admin_session(
        auth_client, auth_app, db_session, organization=organization
    )
    membership, profile = await _arrange_profile(db_session, organization=organization)
    await db_session.commit()
    membership_id = membership.id
    headers = {
        "Origin": "https://frontend.test",
        "X-CSRF-Token": csrf_token,
    }
    if key is not None:
        headers["Idempotency-Key"] = key

    response = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/employees/{profile.id}/activate",
        headers=headers,
    )

    assert response.status_code == 422
    db_session.expire_all()
    assert (await db_session.get_one(OrganizationMembership, membership_id)).status == "pending"


async def test_activation_replays_same_key_without_duplicate_audit(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization = make_organization(name="Activation replay organization")
    db_session.add(organization)
    await db_session.flush()
    _admin_id, csrf_token = await _arrange_admin_session(
        auth_client, auth_app, db_session, organization=organization
    )
    _membership, profile = await _arrange_profile(db_session, organization=organization)
    await db_session.commit()
    url = f"/api/v1/organizations/{organization.id}/employees/{profile.id}/activate"
    first_headers = _activation_headers(csrf_token, key="  stable-activation-replay  ")
    replay_headers = _activation_headers(csrf_token, key="stable-activation-replay")

    first = await auth_client.post(url, headers=first_headers)
    replay = await auth_client.post(url, headers=replay_headers)

    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json()
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "employee_activated")
        )
        == 1
    )
    assert await db_session.scalar(select(func.count()).select_from(ApiIdempotencyRecord)) == 1


async def test_activation_rejects_same_key_for_different_employee(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization = make_organization(name="Activation key reuse organization")
    db_session.add(organization)
    await db_session.flush()
    _admin_id, csrf_token = await _arrange_admin_session(
        auth_client, auth_app, db_session, organization=organization
    )
    _first_membership, first_profile = await _arrange_profile(db_session, organization=organization)
    second_employee = make_user(email_normalized=f"second-activation-{uuid4()}@example.com")
    second_membership = make_membership(
        organization,
        second_employee,
        status="pending",
        activated_at=None,
    )
    db_session.add_all([second_employee, second_membership])
    await db_session.flush()
    second_profile = EmployeeProfile(
        membership_id=second_membership.id,
        organization_id=organization.id,
        first_name="Olena",
        last_name="Bondar",
        operational_role_id=first_profile.operational_role_id,
        location_id=first_profile.location_id,
    )
    db_session.add(second_profile)
    await db_session.commit()
    second_membership_id = second_membership.id
    headers = _activation_headers(csrf_token, key="reused-activation-target")

    first = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/employees/{first_profile.id}/activate",
        headers=headers,
    )
    reused = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/employees/{second_profile.id}/activate",
        headers=headers,
    )

    assert first.status_code == 200
    assert reused.status_code == 409
    assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    db_session.expire_all()
    assert (
        await db_session.get_one(OrganizationMembership, second_membership_id)
    ).status == "pending"
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "employee_activated")
        )
        == 1
    )


async def test_concurrent_activation_same_key_has_one_transition_and_replay(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization = make_organization(name="Concurrent activation replay organization")
    db_session.add(organization)
    await db_session.flush()
    _admin_id, csrf_token = await _arrange_admin_session(
        auth_client, auth_app, db_session, organization=organization
    )
    _membership, profile = await _arrange_profile(db_session, organization=organization)
    await db_session.commit()
    url = f"/api/v1/organizations/{organization.id}/employees/{profile.id}/activate"
    headers = _activation_headers(csrf_token, key="concurrent-activation-replay")

    first, second = await asyncio.gather(
        auth_client.post(url, headers=headers),
        auth_client.post(url, headers=headers),
    )

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "employee_activated")
        )
        == 1
    )
    assert await db_session.scalar(select(func.count()).select_from(ApiIdempotencyRecord)) == 1


async def test_concurrent_activation_different_keys_has_one_winner(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization = make_organization(name="Concurrent activation conflict organization")
    db_session.add(organization)
    await db_session.flush()
    _admin_id, csrf_token = await _arrange_admin_session(
        auth_client, auth_app, db_session, organization=organization
    )
    _membership, profile = await _arrange_profile(db_session, organization=organization)
    await db_session.commit()
    url = f"/api/v1/organizations/{organization.id}/employees/{profile.id}/activate"

    responses = await asyncio.gather(
        auth_client.post(
            url,
            headers=_activation_headers(csrf_token, key="activation-winner-one"),
        ),
        auth_client.post(
            url,
            headers=_activation_headers(csrf_token, key="activation-winner-two"),
        ),
    )

    assert sorted(response.status_code for response in responses) == [200, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["code"] == "EMPLOYEE_ACTIVATION_NOT_ALLOWED"
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "employee_activated")
        )
        == 1
    )
    assert await db_session.scalar(select(func.count()).select_from(ApiIdempotencyRecord)) == 1
