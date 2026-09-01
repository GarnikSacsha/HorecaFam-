import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent, EmployeeProfile, Organization, OrganizationMembership, Session
from app.security.tokens import hash_secret
from tests.factories.auth import make_admin_access
from tests.factories.identity import (
    make_location,
    make_membership,
    make_organization,
    make_role,
    make_user,
)

FIXED_NOW = datetime(2031, 1, 10, 12, 0, tzinfo=UTC)


async def _arrange_lifecycle_context(
    client: AsyncClient,
    app: FastAPI,
    db: AsyncSession,
) -> tuple[Organization, OrganizationMembership, EmployeeProfile, str]:
    app.state.clock = lambda: FIXED_NOW
    organization = make_organization(name="Lifecycle organization")
    admin = make_user(email_normalized=f"lifecycle-admin-{uuid4()}@example.com")
    employee = make_user(email_normalized=f"lifecycle-employee-{uuid4()}@example.com")
    membership = make_membership(
        organization,
        employee,
        status="active",
        activated_at=FIXED_NOW - timedelta(days=30),
    )
    db.add_all([organization, admin, employee, membership])
    await db.flush()
    db.add(make_admin_access(admin, scope="organization_admin", organization=organization))
    role = make_role(organization)
    location = make_location(organization)
    db.add_all([role, location])
    await db.flush()
    profile = EmployeeProfile(
        membership_id=membership.id,
        organization_id=organization.id,
        first_name="Iryna",
        last_name="Koval",
        operational_role_id=role.id,
        location_id=location.id,
    )
    raw_admin_session = f"lifecycle-admin-session-{uuid4()}"
    csrf_token = f"lifecycle-csrf-{uuid4()}"
    db.add_all(
        [
            profile,
            Session(
                user_id=admin.id,
                token_hash=hash_secret(raw_admin_session),
                csrf_token_hash=hash_secret(csrf_token),
                last_seen_at=FIXED_NOW,
                absolute_expires_at=FIXED_NOW + timedelta(days=30),
                mfa_verified_at=FIXED_NOW,
            ),
            Session(
                user_id=employee.id,
                token_hash=hash_secret(f"employee-session-{uuid4()}"),
                csrf_token_hash=hash_secret(f"employee-csrf-{uuid4()}"),
                last_seen_at=FIXED_NOW,
                absolute_expires_at=FIXED_NOW + timedelta(days=30),
            ),
        ]
    )
    await db.commit()
    client.cookies.set("horeca_session", raw_admin_session, path="/api/v1")
    return organization, membership, profile, csrf_token


def _headers(csrf_token: str, key: str) -> dict[str, str]:
    return {
        "Origin": "https://frontend.test",
        "X-CSRF-Token": csrf_token,
        "Idempotency-Key": key,
    }


async def test_admin_disables_active_employee_and_revokes_sessions(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization, membership, profile, csrf_token = await _arrange_lifecycle_context(
        auth_client, auth_app, db_session
    )
    membership_id = membership.id
    employee_user_id = membership.user_id

    response = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/employees/{profile.id}/disable",
        headers=_headers(csrf_token, "disable-active-employee"),
        json={"reason_code": "leave", "note": "Approved leave"},
    )

    assert response.status_code == 200
    assert response.json()["membership_status"] == "disabled"
    assert response.json()["training_participation_status"] == "active"
    db_session.expire_all()
    stored = await db_session.get_one(OrganizationMembership, membership_id)
    assert stored.disabled_at == FIXED_NOW
    employee_sessions = list(
        await db_session.scalars(select(Session).where(Session.user_id == employee_user_id))
    )
    assert employee_sessions and all(row.revoked_at == FIXED_NOW for row in employee_sessions)
    audit = await db_session.scalar(
        select(AuditEvent).where(AuditEvent.action == "employee_disabled")
    )
    assert audit is not None
    assert audit.new_values is not None
    assert audit.new_values["reason_code"] == "leave"
    assert "Approved leave" not in str(audit.new_values)


async def test_pause_replays_once_and_resume_clears_bounded_reason_state(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization, membership, profile, csrf_token = await _arrange_lifecycle_context(
        auth_client, auth_app, db_session
    )
    membership_id = membership.id
    planned_resume_at = FIXED_NOW + timedelta(days=5)
    url = f"/api/v1/organizations/{organization.id}/employees/{profile.id}/pause"
    body = {
        "reason_code": "scheduled_leave",
        "note": "  Agreed schedule  ",
        "planned_resume_at": planned_resume_at.isoformat(),
    }
    headers = _headers(csrf_token, "pause-replay")

    first = await auth_client.post(url, headers=headers, json=body)
    replay = await auth_client.post(url, headers=headers, json=body)

    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json()
    assert first.json()["training_participation_status"] == "paused"
    assert first.json()["training_pause_note"] == "Agreed schedule"
    assert first.json()["planned_resume_at"] == planned_resume_at.isoformat().replace("+00:00", "Z")
    assert (
        len(
            list(
                await db_session.scalars(
                    select(AuditEvent).where(AuditEvent.action == "employee_training_paused")
                )
            )
        )
        == 1
    )

    resumed = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/employees/{profile.id}/resume",
        headers=_headers(csrf_token, "resume-employee"),
    )

    assert resumed.status_code == 200
    assert resumed.json()["training_participation_status"] == "active"
    assert resumed.json()["training_paused_at"] is None
    assert resumed.json()["training_pause_reason_code"] is None
    assert resumed.json()["training_pause_note"] is None
    assert resumed.json()["planned_resume_at"] is None
    db_session.expire_all()
    stored = await db_session.get_one(OrganizationMembership, membership_id)
    assert stored.training_participation_status == "active"


async def test_reactivate_preserves_an_existing_pause_and_original_activation(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization, membership, profile, csrf_token = await _arrange_lifecycle_context(
        auth_client, auth_app, db_session
    )
    original_activated_at = membership.activated_at
    assert original_activated_at is not None

    paused = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/employees/{profile.id}/pause",
        headers=_headers(csrf_token, "pause-before-disable"),
        json={"reason_code": "leave"},
    )
    disabled = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/employees/{profile.id}/disable",
        headers=_headers(csrf_token, "disable-paused"),
        json={"reason_code": "access_review"},
    )
    reactivated = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/employees/{profile.id}/reactivate",
        headers=_headers(csrf_token, "reactivate-paused"),
    )

    assert paused.status_code == disabled.status_code == reactivated.status_code == 200
    assert disabled.json()["training_participation_status"] == "paused"
    assert reactivated.json()["membership_status"] == "active"
    assert reactivated.json()["training_participation_status"] == "paused"
    assert reactivated.json()["training_paused_at"] == paused.json()["training_paused_at"]
    assert reactivated.json()["activated_at"] == original_activated_at.isoformat().replace(
        "+00:00", "Z"
    )
    assert reactivated.json()["disabled_reason_code"] is None


async def test_lifecycle_invalid_transition_and_planned_resume_are_stable_conflicts(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization, _membership, profile, csrf_token = await _arrange_lifecycle_context(
        auth_client, auth_app, db_session
    )

    resume = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/employees/{profile.id}/resume",
        headers=_headers(csrf_token, "resume-active"),
    )
    stale_plan = await auth_client.post(
        f"/api/v1/organizations/{organization.id}/employees/{profile.id}/pause",
        headers=_headers(csrf_token, "pause-stale-plan"),
        json={"planned_resume_at": (FIXED_NOW - timedelta(minutes=1)).isoformat()},
    )

    assert resume.status_code == 409
    assert resume.json()["code"] == "EMPLOYEE_LIFECYCLE_INVALID_TRANSITION"
    assert stale_plan.status_code == 409
    assert stale_plan.json()["code"] == "EMPLOYEE_PLANNED_RESUME_INVALID"
    assert await db_session.scalar(select(AuditEvent)) is None


async def test_concurrent_disable_with_different_keys_has_one_transition(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization, _membership, profile, csrf_token = await _arrange_lifecycle_context(
        auth_client, auth_app, db_session
    )
    url = f"/api/v1/organizations/{organization.id}/employees/{profile.id}/disable"

    responses = await asyncio.gather(
        auth_client.post(
            url,
            headers=_headers(csrf_token, "disable-concurrent-one"),
            json={"reason_code": "access_review"},
        ),
        auth_client.post(
            url,
            headers=_headers(csrf_token, "disable-concurrent-two"),
            json={"reason_code": "access_review"},
        ),
    )

    assert sorted(response.status_code for response in responses) == [200, 409]
    conflict = next(response for response in responses if response.status_code == 409)
    assert conflict.json()["code"] == "EMPLOYEE_LIFECYCLE_INVALID_TRANSITION"
    assert (
        len(
            list(
                await db_session.scalars(
                    select(AuditEvent).where(AuditEvent.action == "employee_disabled")
                )
            )
        )
        == 1
    )
