from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

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

FIXED_NOW = datetime(2030, 8, 27, 13, 0, tzinfo=UTC)


async def _arrange_admin_session(
    client: AsyncClient,
    app: FastAPI,
    db: AsyncSession,
    *,
    organization: Organization,
) -> tuple[UUID, str]:
    app.state.clock = lambda: FIXED_NOW
    admin = make_user(email_normalized=f"profile-admin-{uuid4()}@example.com")
    db.add(admin)
    await db.flush()
    db.add(
        make_admin_access(
            admin,
            scope="organization_admin",
            organization=organization,
        )
    )
    raw_session = f"profile-session-{uuid4()}"
    csrf_token = f"profile-csrf-{uuid4()}"
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


async def _arrange_pending_profile(
    db: AsyncSession,
    *,
    organization: Organization,
    email: str,
    first_name: str | None = None,
    last_name: str | None = None,
) -> tuple[OrganizationMembership, EmployeeProfile]:
    user = make_user(email_normalized=email)
    membership = make_membership(
        organization,
        user,
        status="pending",
        activated_at=None,
    )
    db.add_all([user, membership])
    await db.flush()
    profile = EmployeeProfile(
        membership_id=membership.id,
        organization_id=membership.organization_id,
        first_name=first_name,
        last_name=last_name,
    )
    db.add(profile)
    await db.flush()
    return membership, profile


async def test_admin_updates_pending_profile_with_safe_atomic_audit(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization = make_organization(name="Profile organization")
    db_session.add(organization)
    await db_session.flush()
    admin_id, csrf_token = await _arrange_admin_session(
        auth_client,
        auth_app,
        db_session,
        organization=organization,
    )
    role = make_role(organization)
    location = make_location(organization)
    db_session.add_all([role, location])
    await db_session.flush()
    membership, profile = await _arrange_pending_profile(
        db_session,
        organization=organization,
        email="pending-update@example.com",
    )
    await db_session.commit()
    organization_id = organization.id
    membership_id = membership.id
    profile_id = profile.id
    role_id = role.id
    location_id = location.id

    response = await auth_client.patch(
        f"/api/v1/organizations/{organization_id}/employees/{profile_id}",
        headers={"Origin": "https://frontend.test", "X-CSRF-Token": csrf_token},
        json={
            "first_name": "  Ірина  ",
            "last_name": "  Коваль  ",
            "operational_role_id": str(role.id),
            "location_id": str(location.id),
        },
    )

    assert response.status_code == 200
    assert response.json()["first_name"] == "Ірина"
    assert response.json()["last_name"] == "Коваль"
    assert response.json()["operational_role"]["id"] == str(role_id)
    assert response.json()["location"]["id"] == str(location_id)
    assert response.json()["profile_complete"] is True
    assert response.json()["membership_status"] == "pending"
    db_session.expire_all()
    stored_membership = await db_session.get_one(OrganizationMembership, membership_id)
    stored_profile = await db_session.get_one(EmployeeProfile, profile_id)
    assert stored_membership.status == "pending"
    assert stored_membership.activated_at is None
    assert stored_profile.first_name == "Ірина"
    audit = await db_session.scalar(
        select(AuditEvent).where(AuditEvent.action == "employee_profile_updated")
    )
    assert audit is not None
    assert audit.organization_id == organization_id
    assert audit.actor_user_id == admin_id
    assert audit.target_type == "employee_profile"
    assert audit.target_id == profile_id
    assert audit.outcome == "success"
    assert audit.old_values == {
        "first_name_changed": True,
        "last_name_changed": True,
        "operational_role_id": None,
        "location_id": None,
    }
    assert audit.new_values == {
        "first_name_changed": True,
        "last_name_changed": True,
        "operational_role_id": str(role_id),
        "location_id": str(location_id),
        "training_applicability_effects": ["not_applicable"],
        "assignment_count": 0,
        "revoked_assignment_count": 0,
        "notification_count": 0,
    }
    assert "Ірина" not in str(audit.old_values)
    assert "Ірина" not in str(audit.new_values)

    retry = await auth_client.patch(
        f"/api/v1/organizations/{organization_id}/employees/{profile_id}",
        headers={"Origin": "https://frontend.test", "X-CSRF-Token": csrf_token},
        json={
            "first_name": "Ірина",
            "last_name": "Коваль",
            "operational_role_id": str(role_id),
            "location_id": str(location_id),
        },
    )
    assert retry.status_code == 200
    assert retry.json()["membership_status"] == "pending"
    assert retry.json()["profile_complete"] is True
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 2


async def test_pending_profile_patch_distinguishes_omitted_field_from_explicit_null(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization = make_organization(name="Clear profile organization")
    db_session.add(organization)
    await db_session.flush()
    _admin_id, csrf_token = await _arrange_admin_session(
        auth_client,
        auth_app,
        db_session,
        organization=organization,
    )
    _membership, profile = await _arrange_pending_profile(
        db_session,
        organization=organization,
        email="pending-clear@example.com",
        first_name="До",
        last_name="Залишити",
    )
    await db_session.commit()

    response = await auth_client.patch(
        f"/api/v1/organizations/{organization.id}/employees/{profile.id}",
        headers={"Origin": "https://frontend.test", "X-CSRF-Token": csrf_token},
        json={"first_name": None},
    )

    assert response.status_code == 200
    assert response.json()["first_name"] is None
    assert response.json()["last_name"] == "Залишити"
    assert response.json()["profile_complete"] is False


@pytest.mark.parametrize(
    ("membership_status", "activated_at", "disabled_at"),
    [
        ("active", FIXED_NOW - timedelta(days=1), None),
        ("disabled", None, FIXED_NOW - timedelta(days=1)),
    ],
)
async def test_non_pending_profile_remains_editable_without_rewriting_disabled_access(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    membership_status: str,
    activated_at: datetime | None,
    disabled_at: datetime | None,
) -> None:
    organization = make_organization(name=f"{membership_status} profile organization")
    user = make_user(email_normalized=f"{membership_status}-profile@example.com")
    membership = make_membership(
        organization,
        user,
        status=membership_status,
        activated_at=activated_at,
        disabled_at=disabled_at,
    )
    db_session.add_all([organization, user, membership])
    await db_session.flush()
    profile = EmployeeProfile(
        membership_id=membership.id,
        organization_id=organization.id,
        first_name="Original",
    )
    db_session.add(profile)
    await db_session.flush()
    _admin_id, csrf_token = await _arrange_admin_session(
        auth_client,
        auth_app,
        db_session,
        organization=organization,
    )
    organization_id = organization.id
    profile_id = profile.id

    response = await auth_client.patch(
        f"/api/v1/organizations/{organization_id}/employees/{profile_id}",
        headers={"Origin": "https://frontend.test", "X-CSRF-Token": csrf_token},
        json={"first_name": "Changed"},
    )

    assert response.status_code == 200
    db_session.expire_all()
    assert (await db_session.get_one(EmployeeProfile, profile_id)).first_name == "Changed"
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 1


async def test_profile_patch_rejects_inactive_and_foreign_references_without_mutation(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization = make_organization(name="Reference validation organization")
    foreign_organization = make_organization(name="Foreign reference organization")
    db_session.add_all([organization, foreign_organization])
    await db_session.flush()
    _admin_id, csrf_token = await _arrange_admin_session(
        auth_client,
        auth_app,
        db_session,
        organization=organization,
    )
    archived_role = make_role(organization, status="archived")
    foreign_location = make_location(foreign_organization)
    db_session.add_all([archived_role, foreign_location])
    await db_session.flush()
    _membership, profile = await _arrange_pending_profile(
        db_session,
        organization=organization,
        email="reference-rejection@example.com",
        first_name="Original",
    )
    await db_session.commit()
    organization_id = organization.id
    profile_id = profile.id
    archived_role_id = archived_role.id
    foreign_location_id = foreign_location.id
    headers = {"Origin": "https://frontend.test", "X-CSRF-Token": csrf_token}

    inactive = await auth_client.patch(
        f"/api/v1/organizations/{organization_id}/employees/{profile_id}",
        headers=headers,
        json={"operational_role_id": str(archived_role_id)},
    )
    foreign = await auth_client.patch(
        f"/api/v1/organizations/{organization_id}/employees/{profile_id}",
        headers=headers,
        json={"location_id": str(foreign_location_id)},
    )

    assert inactive.status_code == 409
    assert inactive.json()["code"] == "REFERENCE_INACTIVE"
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "RESOURCE_NOT_FOUND"
    db_session.expire_all()
    stored = await db_session.get_one(EmployeeProfile, profile_id)
    assert stored.first_name == "Original"
    assert stored.operational_role_id is None
    assert stored.location_id is None
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0


async def test_profile_patch_requires_csrf_without_mutation(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization = make_organization(name="CSRF profile organization")
    db_session.add(organization)
    await db_session.flush()
    await _arrange_admin_session(
        auth_client,
        auth_app,
        db_session,
        organization=organization,
    )
    _membership, profile = await _arrange_pending_profile(
        db_session,
        organization=organization,
        email="csrf-profile@example.com",
        first_name="Original",
    )
    await db_session.commit()
    organization_id = organization.id
    profile_id = profile.id

    response = await auth_client.patch(
        f"/api/v1/organizations/{organization_id}/employees/{profile_id}",
        json={"first_name": "Changed"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_INVALID"
    db_session.expire_all()
    assert (await db_session.get_one(EmployeeProfile, profile_id)).first_name == "Original"
