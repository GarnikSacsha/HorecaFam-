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
    AuditEvent,
    EmployeeProfile,
    Organization,
    OrganizationMembership,
    Session,
)
from app.security.tokens import hash_secret
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

    response = await auth_client.post(
        f"/api/v1/organizations/{organization_id}/employees/{profile_id}/activate",
        headers=_activation_headers(csrf_token),
    )

    assert response.status_code == 200
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
