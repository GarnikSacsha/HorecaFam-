from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EmployeeProfile, Organization, Session
from app.security.tokens import hash_secret
from tests.factories.auth import make_admin_access
from tests.factories.identity import (
    make_location,
    make_membership,
    make_organization,
    make_role,
    make_user,
)

FIXED_NOW = datetime(2030, 8, 27, 12, 0, tzinfo=UTC)


async def _attach_session(
    client: AsyncClient,
    db: AsyncSession,
    *,
    user_id: UUID,
    mfa_verified: bool,
) -> str:
    raw_session = f"employee-read-session-{uuid4()}"
    csrf_token = f"employee-read-csrf-{uuid4()}"
    db.add(
        Session(
            user_id=user_id,
            token_hash=hash_secret(raw_session),
            csrf_token_hash=hash_secret(csrf_token),
            last_seen_at=FIXED_NOW,
            absolute_expires_at=FIXED_NOW + timedelta(days=30),
            mfa_verified_at=FIXED_NOW if mfa_verified else None,
        )
    )
    await db.commit()
    client.cookies.set("horeca_session", raw_session, path="/api/v1")
    return csrf_token


async def _arrange_admin(
    client: AsyncClient,
    app: FastAPI,
    db: AsyncSession,
) -> tuple[UUID, UUID]:
    app.state.clock = lambda: FIXED_NOW
    organization = make_organization(name="Bacara Kyiv")
    admin = make_user(email_normalized=f"admin-{uuid4()}@example.com")
    db.add_all([organization, admin])
    await db.flush()
    db.add(
        make_admin_access(
            admin,
            scope="organization_admin",
            organization=organization,
        )
    )
    await _attach_session(client, db, user_id=admin.id, mfa_verified=True)
    return organization.id, admin.id


async def test_admin_reads_exact_organization_locations_and_roles(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, _admin_id = await _arrange_admin(auth_client, auth_app, db_session)
    organization = await db_session.get_one(Organization, organization_id)
    db_session.add_all(
        [
            make_location(
                organization,
                name="Зала Б",
                status="archived",
                address="вул. Друга, 2",
            ),
            make_location(
                organization,
                name="Зала А",
                address="вул. Перша, 1",
            ),
            make_role(organization, code="runner", name_uk="Ранер"),
            make_role(
                organization,
                code="waiter",
                name_uk="Офіціант",
                status="archived",
            ),
        ]
    )
    await db_session.commit()

    organization_response = await auth_client.get(f"/api/v1/organizations/{organization_id}")
    locations_response = await auth_client.get(f"/api/v1/organizations/{organization_id}/locations")
    roles_response = await auth_client.get(
        f"/api/v1/organizations/{organization_id}/operational-roles"
    )

    assert organization_response.status_code == 200
    assert organization_response.json() == {
        "id": str(organization_id),
        "name": "Bacara Kyiv",
        "status": "active",
        "default_locale": "uk",
        "timezone": "Europe/Kyiv",
    }
    assert [item["name"] for item in locations_response.json()] == ["Зала А", "Зала Б"]
    assert {item["status"] for item in locations_response.json()} == {"active", "archived"}
    assert [item["name_uk"] for item in roles_response.json()] == ["Офіціант", "Ранер"]
    assert {item["status"] for item in roles_response.json()} == {"active", "archived"}


async def test_admin_lists_filters_pages_and_reads_employee_detail(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, _admin_id = await _arrange_admin(auth_client, auth_app, db_session)
    organization = await db_session.get_one(Organization, organization_id)
    role = make_role(organization)
    location = make_location(organization)
    first_user = make_user(email_normalized="first.employee@example.com")
    second_user = make_user(email_normalized="second.employee@example.com")
    first_membership = make_membership(
        organization,
        first_user,
        status="pending",
        activated_at=None,
    )
    second_membership = make_membership(
        organization,
        second_user,
        status="pending",
        activated_at=None,
    )
    db_session.add_all(
        [role, location, first_user, second_user, first_membership, second_membership]
    )
    await db_session.flush()
    first_profile = EmployeeProfile(
        membership_id=first_membership.id,
        organization_id=organization_id,
        first_name="Ірина",
        last_name="Перша",
        operational_role_id=role.id,
        location_id=location.id,
        created_at=FIXED_NOW - timedelta(minutes=2),
    )
    second_profile = EmployeeProfile(
        membership_id=second_membership.id,
        organization_id=organization_id,
        first_name="Богдан",
        last_name=None,
        created_at=FIXED_NOW - timedelta(minutes=1),
    )
    db_session.add_all([first_profile, second_profile])
    await db_session.commit()

    first_page = await auth_client.get(
        f"/api/v1/organizations/{organization_id}/employees",
        params={"status": "pending", "limit": 1},
    )

    assert first_page.status_code == 200
    assert [item["id"] for item in first_page.json()["items"]] == [str(second_profile.id)]
    assert first_page.json()["next_cursor"]
    second_page = await auth_client.get(
        f"/api/v1/organizations/{organization_id}/employees",
        params={"cursor": first_page.json()["next_cursor"], "limit": 1},
    )
    assert second_page.status_code == 200
    assert [item["id"] for item in second_page.json()["items"]] == [str(first_profile.id)]
    assert second_page.json()["next_cursor"] is None

    filtered = await auth_client.get(
        f"/api/v1/organizations/{organization_id}/employees",
        params={
            "query": " FIRST.EMPLOYEE ",
            "location_id": str(location.id),
            "operational_role_id": str(role.id),
        },
    )
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()["items"]] == [str(first_profile.id)]
    assert filtered.json()["items"][0]["profile_complete"] is True
    assert filtered.json()["items"][0]["operational_role"]["code"] == "waiter"
    assert filtered.json()["items"][0]["location"]["name"] == "Test Location"

    detail = await auth_client.get(
        f"/api/v1/organizations/{organization_id}/employees/{first_profile.id}"
    )
    assert detail.status_code == 200
    assert detail.json()["id"] == str(first_profile.id)
    assert detail.json()["membership_status"] == "pending"
    assert detail.json()["membership_created_at"]
    assert detail.json()["activated_at"] is None
    assert detail.json()["disabled_at"] is None
    assert "password_hash" not in detail.text
    assert "token_hash" not in detail.text


async def test_pending_employee_reads_only_own_operational_profile(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization(name="Own organization")
    own_user = make_user(email_normalized="own.employee@example.com")
    peer_user = make_user(email_normalized="peer.employee@example.com")
    own_membership = make_membership(
        organization,
        own_user,
        status="pending",
        activated_at=None,
    )
    peer_membership = make_membership(
        organization,
        peer_user,
        status="pending",
        activated_at=None,
    )
    db_session.add_all([organization, own_user, peer_user, own_membership, peer_membership])
    await db_session.flush()
    own_profile = EmployeeProfile(
        membership_id=own_membership.id,
        organization_id=organization.id,
        first_name="Своя",
    )
    peer_profile = EmployeeProfile(
        membership_id=peer_membership.id,
        organization_id=organization.id,
        first_name="Чужа",
    )
    db_session.add_all([own_profile, peer_profile])
    await _attach_session(auth_client, db_session, user_id=own_user.id, mfa_verified=False)

    response = await auth_client.get("/api/v1/me/profile")

    assert response.status_code == 200
    assert response.json() == {
        "profiles": [
            {
                "id": str(own_profile.id),
                "organization": {"id": str(organization.id), "name": "Own organization"},
                "membership_status": "pending",
                "first_name": "Своя",
                "last_name": None,
                "operational_role": None,
                "location": None,
                "profile_complete": False,
                "updated_at": response.json()["profiles"][0]["updated_at"],
            }
        ]
    }
    assert peer_user.email_normalized not in response.text
    assert str(peer_profile.id) not in response.text


async def test_reference_reads_require_mfa_and_hide_foreign_organization(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    own_organization = make_organization(name="Own admin organization")
    foreign_organization = make_organization(name="Foreign organization")
    admin = make_user(email_normalized="non-elevated-admin@example.com")
    db_session.add_all([own_organization, foreign_organization, admin])
    await db_session.flush()
    db_session.add(
        make_admin_access(
            admin,
            scope="organization_admin",
            organization=own_organization,
        )
    )
    await _attach_session(auth_client, db_session, user_id=admin.id, mfa_verified=False)

    own_response = await auth_client.get(f"/api/v1/organizations/{own_organization.id}/locations")
    foreign_response = await auth_client.get(
        f"/api/v1/organizations/{foreign_organization.id}/locations"
    )

    assert own_response.status_code == 403
    assert own_response.json()["code"] == "MFA_REQUIRED"
    assert foreign_response.status_code == 404
    assert foreign_response.json()["code"] == "RESOURCE_NOT_FOUND"
