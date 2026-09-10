from datetime import timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AttentionCase,
    Organization,
    OrganizationMembership,
    RetakeRequirement,
    Session,
)
from app.security.tokens import hash_secret
from tests.api.test_attention_admin_api import FIXED_NOW, _arrange_admin_context
from tests.api.test_employee_reads import _arrange_admin
from tests.factories.assessments import (
    make_assessment_attempt,
    make_assessment_version,
    make_attempt_result,
)
from tests.factories.identity import (
    make_employee_profile,
    make_location,
    make_membership,
    make_organization,
    make_user,
)


async def test_dashboard_empty_and_scoped_location(
    auth_client: AsyncClient, auth_app: FastAPI, db_session: AsyncSession
) -> None:
    organization_id, _ = await _arrange_admin(auth_client, auth_app, db_session)
    response = await auth_client.get(f"/api/v1/organizations/{organization_id}/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["organization_id"] == str(organization_id)
    assert data["location_id"] is None
    for section in ("employees", "training", "final_exam", "attention"):
        assert all(value == 0 for value in data[section].values())
    foreign = make_organization(name="Other venue")
    db_session.add(foreign)
    await db_session.flush()
    location = make_location(foreign)
    db_session.add(location)
    await db_session.commit()
    rejected = await auth_client.get(
        f"/api/v1/organizations/{organization_id}/dashboard",
        params={"location_id": str(location.id)},
    )
    assert rejected.status_code == 404
    assert (
        await auth_client.get(f"/api/v1/organizations/{foreign.id}/dashboard")
    ).status_code == 404


async def test_dashboard_counts_current_work_and_preserves_certification(
    auth_client: AsyncClient, auth_app: FastAPI, db_session: AsyncSession
) -> None:
    context, final, organization_id, _ = await _arrange_admin_context(
        auth_client, auth_app, db_session
    )
    organization = await db_session.get_one(Organization, organization_id)
    other_location = make_location(organization, name="Other room")
    db_session.add(other_location)
    await db_session.flush()
    for index, state in enumerate(("pending", "active", "disabled")):
        user = make_user(email_normalized=f"dashboard-{index}@example.com")
        membership = make_membership(
            organization,
            user,
            status=state,
            activated_at=None if state == "pending" else FIXED_NOW,
            disabled_at=FIXED_NOW if state == "disabled" else None,
            training_participation_status="paused" if state == "active" else "active",
        )
        db_session.add_all([user, membership])
        await db_session.flush()
        db_session.add(
            make_employee_profile(membership, organization_id, location_id=other_location.id)
        )
    for index in range(2):
        db_session.add(
            AttentionCase(
                organization_id=organization_id,
                location_id=context.training.location_id,
                training_id=context.training.id,
                employee_profile_id=context.employee.id,
                case_type="critical_allergen",
                subject_key=f"synthetic-{index}",
                state="open",
            )
        )
        db_session.add(
            RetakeRequirement(
                organization_id=organization_id,
                location_id=context.training.location_id,
                training_id=context.training.id,
                employee_profile_id=context.employee.id,
                assignment_id=context.assignment.id,
                target_assessment_id=final.id,
                reason="management_follow_up",
                state="active",
                management_source_key=f"dashboard-{index}",
                target_policy={"assessment_type": "menu_final_exam", "minimum_result": "passed"},
                confirmed_at=FIXED_NOW,
                confirmed_by_user_id=context.actor.id,
                due_at=FIXED_NOW,
                clock_frozen_at=FIXED_NOW if index == 1 else None,
            )
        )
    await db_session.commit()
    url = f"/api/v1/organizations/{organization_id}/dashboard"
    data = (await auth_client.get(url)).json()
    assert data["employees"] == {"total": 4, "active": 2, "pending": 1, "paused": 1, "disabled": 1}
    assert data["training"] == {"assigned": 1, "in_progress": 0, "completed": 0}
    assert data["final_exam"] == {"certified": 0, "needs_exam": 0, "retake": 1, "overdue_retake": 1}
    assert data["attention"] == {"unresolved": 2, "critical": 2}
    scoped = (await auth_client.get(url, params={"location_id": str(other_location.id)})).json()
    assert scoped["employees"]["total"] == 3
    assert scoped["training"]["assigned"] == scoped["attention"]["unresolved"] == 0
    assert scoped["final_exam"]["retake"] == 0

    context.assignment.status = "completed"
    context.assignment.started_at = FIXED_NOW
    context.assignment.completed_at = FIXED_NOW
    await db_session.commit()
    assert (await auth_client.get(url)).json()["final_exam"]["needs_exam"] == 1
    version = make_assessment_version(
        final,
        context.training_version,
        None,
        question_count=20,
        threshold_percent=70,
        feedback_policy="after_final_submission",
    )
    db_session.add(version)
    await db_session.flush()
    for index, passed in enumerate((True, False)):
        attempt = make_assessment_attempt(
            context.employee,
            context.assignment,
            version,
            status="completed",
            question_count=20,
            completed_at=FIXED_NOW + timedelta(minutes=index),
        )
        db_session.add(attempt)
        await db_session.flush()
        db_session.add(
            make_attempt_result(
                attempt,
                pass_status="passed" if passed else "failed",
                total_count=20,
                correct_count=20 if passed else 0,
                score_basis_points=10000 if passed else 0,
            )
        )
    await db_session.commit()
    final_data = (await auth_client.get(url)).json()["final_exam"]
    assert final_data["certified"] == 1
    assert final_data["needs_exam"] == 0
    await db_session.execute(
        update(RetakeRequirement)
        .where(
            RetakeRequirement.organization_id == organization_id,
        )
        .values(clock_frozen_at=FIXED_NOW)
    )
    await db_session.commit()
    assert (await auth_client.get(url)).json()["final_exam"]["overdue_retake"] == 0
    await db_session.execute(
        update(RetakeRequirement)
        .where(
            RetakeRequirement.organization_id == organization_id,
        )
        .values(clock_frozen_at=None)
    )
    await db_session.commit()
    assert (await auth_client.get(url)).json()["final_exam"]["overdue_retake"] == 1
    await db_session.execute(
        update(AttentionCase)
        .where(
            AttentionCase.organization_id == organization_id,
        )
        .values(
            state="resolved",
            resolved_at=FIXED_NOW,
            resolution_type="admin_follow_up",
            resolution_actor_type="user",
            resolved_by_user_id=context.actor.id,
        )
    )
    await db_session.commit()
    assert (await auth_client.get(url)).json()["attention"] == {"unresolved": 0, "critical": 0}
    membership = await db_session.get_one(OrganizationMembership, context.employee.membership_id)
    membership.training_participation_status = "paused"
    membership.training_paused_at = FIXED_NOW
    await db_session.commit()
    assert (await auth_client.get(url)).json()["final_exam"]["overdue_retake"] == 0
    context.assignment.status = "revoked"
    context.assignment.revoked_at = FIXED_NOW
    context.assignment.revoke_reason = "admin"
    await db_session.commit()
    revoked_data = (await auth_client.get(url)).json()
    assert revoked_data["training"]["completed"] == 0
    assert revoked_data["final_exam"]["certified"] == 0


@pytest.mark.parametrize("case", ["anonymous", "no_mfa", "no_admin"])
async def test_dashboard_requires_organization_admin_and_mfa(
    auth_client: AsyncClient, auth_app: FastAPI, db_session: AsyncSession, case: str
) -> None:
    context, _, organization_id, _ = await _arrange_admin_context(
        auth_client, auth_app, db_session, mfa_verified=case != "no_mfa"
    )
    if case == "anonymous":
        auth_client.cookies.clear()
    if case == "no_admin":
        membership = await db_session.get_one(
            OrganizationMembership, context.employee.membership_id
        )
        session = await db_session.scalar(
            select(Session).where(
                Session.token_hash == hash_secret(auth_client.cookies["horeca_session"]),
            )
        )
        assert session is not None
        session.user_id = membership.user_id
        await db_session.commit()
    response = await auth_client.get(f"/api/v1/organizations/{organization_id}/dashboard")
    assert response.status_code == {"anonymous": 401, "no_mfa": 403, "no_admin": 403}[case]
    assert str(context.employee.id) not in response.text
