from uuid import uuid4

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import AuditEvent, EmployeeProfile, Organization, OrganizationMembership, Session
from tests.api.test_employee_profile_update import (
    _arrange_admin_session,
    _arrange_pending_profile,
)
from tests.api.test_employee_reads import FIXED_NOW, _attach_session
from tests.api.test_invitations_accept import arrange_public_invitation
from tests.factories.identity import make_location, make_organization, make_role


async def test_foreign_admin_cannot_probe_employee_or_references(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    own_organization = make_organization(name="Admin scope")
    foreign_organization = make_organization(name="Hidden scope")
    db_session.add_all([own_organization, foreign_organization])
    await db_session.flush()
    _admin_id, csrf_token = await _arrange_admin_session(
        auth_client,
        auth_app,
        db_session,
        organization=own_organization,
    )
    _membership, foreign_profile = await _arrange_pending_profile(
        db_session,
        organization=foreign_organization,
        email="hidden-employee@example.com",
        first_name="Hidden",
    )
    await db_session.commit()
    own_organization_id = own_organization.id
    foreign_organization_id = foreign_organization.id
    foreign_profile_id = foreign_profile.id

    references = await auth_client.get(
        f"/api/v1/organizations/{foreign_organization_id}/operational-roles"
    )
    employee = await auth_client.get(
        f"/api/v1/organizations/{foreign_organization_id}/employees/{foreign_profile_id}"
    )
    patch = await auth_client.patch(
        f"/api/v1/organizations/{foreign_organization_id}/employees/{foreign_profile_id}",
        headers={"Origin": "https://frontend.test", "X-CSRF-Token": csrf_token},
        json={"first_name": "Probed"},
    )
    foreign_filter = await auth_client.get(
        f"/api/v1/organizations/{own_organization_id}/employees",
        params={"location_id": str(uuid4())},
    )

    for response in (references, employee, patch):
        assert response.status_code == 404
        assert response.json()["code"] == "RESOURCE_NOT_FOUND"
        assert "Hidden" not in response.text
        assert "hidden-employee@example.com" not in response.text
    assert foreign_filter.status_code == 200
    assert foreign_filter.json() == {"items": [], "next_cursor": None}
    db_session.expire_all()
    assert (await db_session.get_one(EmployeeProfile, foreign_profile_id)).first_name == "Hidden"
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0


async def test_pending_employee_can_read_own_profile_but_cannot_administer_peers(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization(name="Pending boundary")
    db_session.add(organization)
    await db_session.flush()
    membership, profile = await _arrange_pending_profile(
        db_session,
        organization=organization,
        email="pending-boundary@example.com",
        first_name="Pending",
    )
    user_id = membership.user_id
    await _attach_session(
        auth_client,
        db_session,
        user_id=user_id,
        mfa_verified=False,
    )
    organization_id = organization.id
    profile_id = profile.id

    own = await auth_client.get("/api/v1/me/profile")
    employees = await auth_client.get(f"/api/v1/organizations/{organization_id}/employees")
    update = await auth_client.patch(
        f"/api/v1/organizations/{organization_id}/employees/{profile_id}",
        headers={"Origin": "https://frontend.test", "X-CSRF-Token": "invalid"},
        json={"first_name": "Self assigned"},
    )

    assert own.status_code == 200
    assert [item["id"] for item in own.json()["profiles"]] == [str(profile_id)]
    assert employees.status_code == 403
    assert employees.json()["code"] == "FORBIDDEN"
    assert update.status_code == 403
    assert update.json()["code"] in {"CSRF_INVALID", "FORBIDDEN"}
    db_session.expire_all()
    assert (await db_session.get_one(EmployeeProfile, profile_id)).first_name == "Pending"


async def test_employee_contract_validation_and_openapi_are_exact_and_safe(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization = make_organization(name="Contract organization")
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
        email="contract-profile@example.com",
    )
    await db_session.commit()
    headers = {"Origin": "https://frontend.test", "X-CSRF-Token": csrf_token}
    path = f"/api/v1/organizations/{organization.id}/employees/{profile.id}"

    empty = await auth_client.patch(path, headers=headers, json={})
    blank = await auth_client.patch(path, headers=headers, json={"first_name": "   "})
    extra = await auth_client.patch(path, headers=headers, json={"status": "active"})
    invalid_cursor = await auth_client.get(
        f"/api/v1/organizations/{organization.id}/employees",
        params={"cursor": "not-a-valid-cursor"},
    )

    assert [response.status_code for response in (empty, blank, extra, invalid_cursor)] == [
        422,
        422,
        422,
        422,
    ]
    openapi = auth_app.openapi()
    expected_methods = {
        "/api/v1/organizations/{organization_id}": {"get"},
        "/api/v1/organizations/{organization_id}/locations": {"get"},
        "/api/v1/organizations/{organization_id}/operational-roles": {"get"},
        "/api/v1/organizations/{organization_id}/employees": {"get"},
        "/api/v1/organizations/{organization_id}/employees/{employee_id}": {
            "get",
            "patch",
        },
        "/api/v1/organizations/{organization_id}/employees/{employee_id}/activate": {
            "post",
        },
        "/api/v1/me/profile": {"get"},
    }
    for api_path, methods in expected_methods.items():
        assert set(openapi["paths"][api_path]) == methods
    list_operation = openapi["paths"]["/api/v1/organizations/{organization_id}/employees"]["get"]
    assert {parameter["name"] for parameter in list_operation["parameters"]} == {
        "organization_id",
        "status",
        "location_id",
        "operational_role_id",
        "query",
        "cursor",
        "limit",
    }
    serialized = str({path: openapi["paths"][path] for path in expected_methods})
    for forbidden in (
        "password_hash",
        "token_hash",
        "csrf_token_hash",
        "ip_metadata",
        "user_agent",
        "invitation",
        "assignment",
        "training",
        "result",
        "audit_events",
    ):
        assert forbidden not in serialized

    activation_operation = openapi["paths"][
        "/api/v1/organizations/{organization_id}/employees/{employee_id}/activate"
    ]["post"]
    assert "requestBody" not in activation_operation
    assert {parameter["name"] for parameter in activation_operation["parameters"]} == {
        "organization_id",
        "employee_id",
        "Idempotency-Key",
    }


async def test_activation_requires_session_csrf_mfa_and_same_organization_admin(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    organization = make_organization(name="Activation security organization")
    db_session.add(organization)
    await db_session.flush()
    role = make_role(organization)
    location = make_location(organization)
    db_session.add_all([role, location])
    await db_session.flush()
    target_membership, target_profile = await _arrange_pending_profile(
        db_session,
        organization=organization,
        email="activation-security-target@example.com",
        first_name="Target",
        last_name="Employee",
    )
    target_profile.operational_role_id = role.id
    target_profile.location_id = location.id
    await db_session.commit()
    target_membership_id = target_membership.id
    url = f"/api/v1/organizations/{organization.id}/employees/{target_profile.id}/activate"
    mutation_headers = {
        "Origin": "https://frontend.test",
        "X-CSRF-Token": "untrusted",
        "Idempotency-Key": "activation-security",
    }

    unauthenticated = await auth_client.post(url, headers=mutation_headers)

    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="https://api.test",
    ) as admin_client:
        admin_id, admin_csrf = await _arrange_admin_session(
            admin_client,
            auth_app,
            db_session,
            organization=organization,
        )
        missing_csrf = await admin_client.post(
            url,
            headers={
                "Origin": "https://frontend.test",
                "Idempotency-Key": "activation-missing-csrf",
            },
        )
        admin_session = await db_session.scalar(select(Session).where(Session.user_id == admin_id))
        assert admin_session is not None
        admin_session.mfa_verified_at = None
        await db_session.commit()
        missing_mfa = await admin_client.post(
            url,
            headers={
                "Origin": "https://frontend.test",
                "X-CSRF-Token": admin_csrf,
                "Idempotency-Key": "activation-missing-mfa",
            },
        )

    peer_membership, _peer_profile = await _arrange_pending_profile(
        db_session,
        organization=organization,
        email="activation-security-peer@example.com",
        first_name="Peer",
        last_name="Employee",
    )
    await db_session.commit()
    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="https://api.test",
    ) as employee_client:
        employee_csrf = await _attach_session(
            employee_client,
            db_session,
            user_id=peer_membership.user_id,
            mfa_verified=False,
        )
        non_admin = await employee_client.post(
            url,
            headers={
                "Origin": "https://frontend.test",
                "X-CSRF-Token": employee_csrf,
                "Idempotency-Key": "activation-non-admin",
            },
        )

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "AUTHENTICATION_REQUIRED"
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "CSRF_INVALID"
    assert missing_mfa.status_code == 403
    assert missing_mfa.json()["code"] == "MFA_REQUIRED"
    assert non_admin.status_code == 403
    assert non_admin.json()["code"] == "FORBIDDEN"
    db_session.expire_all()
    stored = await db_session.get_one(OrganizationMembership, target_membership_id)
    assert stored.status == "pending"
    assert stored.activated_at is None
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == 0


async def test_stage4_acceptance_flows_through_admin_setup_to_stage6_activation(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    invitation, raw_token = await arrange_public_invitation(
        db_session,
        auth_settings,
        invited_email="stage-five-chain@example.com",
    )
    organization_id = invitation.organization_id
    organization = await db_session.get_one(Organization, organization_id)
    role = make_role(organization)
    location = make_location(organization)
    db_session.add_all([role, location])
    await db_session.commit()
    role_id = role.id
    location_id = location.id

    accepted = await auth_client.post(
        "/api/v1/invitations/accept",
        json={
            "token": raw_token,
            "acceptance_mode": "activate_access",
            "password": "correct horse battery staple",
        },
    )
    assert accepted.status_code == 201
    employee_id = accepted.json()["membership"]["employee_profile_id"]
    assert (await auth_client.get("/api/v1/auth/session")).status_code == 200
    db_session.expire_all()

    async with AsyncClient(
        transport=ASGITransport(app=auth_app),
        base_url="https://api.test",
    ) as admin_client:
        _admin_id, csrf_token = await _arrange_admin_session(
            admin_client,
            auth_app,
            db_session,
            organization=organization,
        )
        listed = await admin_client.get(
            f"/api/v1/organizations/{organization_id}/employees",
            params={"status": "pending", "query": "stage-five-chain@example.com"},
        )
        updated = await admin_client.patch(
            f"/api/v1/organizations/{organization_id}/employees/{employee_id}",
            headers={"Origin": "https://frontend.test", "X-CSRF-Token": csrf_token},
            json={
                "first_name": "Марія",
                "last_name": "Іваненко",
                "operational_role_id": str(role_id),
                "location_id": str(location_id),
            },
        )
        activated = await admin_client.post(
            f"/api/v1/organizations/{organization_id}/employees/{employee_id}/activate",
            headers={
                "Origin": "https://frontend.test",
                "X-CSRF-Token": csrf_token,
                "Idempotency-Key": "stage4-to-stage6-activation",
            },
        )

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [employee_id]
    assert updated.status_code == 200
    assert updated.json()["membership_status"] == "pending"
    assert updated.json()["profile_complete"] is True
    assert activated.status_code == 200
    assert activated.json()["membership_status"] == "active"
    assert activated.json()["training_participation_status"] == "active"
    assert "set-cookie" not in activated.headers

    session_context = await auth_client.get("/api/v1/auth/session")
    assert session_context.status_code == 200
    assert session_context.json()["organization_access"][0]["membership_status"] == "active"
    own = await auth_client.get("/api/v1/me/profile")
    assert own.status_code == 200
    assert own.json()["profiles"][0]["id"] == employee_id
    assert own.json()["profiles"][0]["first_name"] == "Марія"
    assert own.json()["profiles"][0]["membership_status"] == "active"
    membership_status = await db_session.scalar(
        select(OrganizationMembership.status)
        .join(EmployeeProfile, EmployeeProfile.membership_id == OrganizationMembership.id)
        .where(EmployeeProfile.id == employee_id)
    )
    assert membership_status == "active"
