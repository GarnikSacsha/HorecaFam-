from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AttentionCase,
    OrganizationMembership,
    RetakeRequirement,
    Session,
    User,
)
from app.security.tokens import hash_secret
from tests.factories.assessments import make_assessment
from tests.integration.test_assessment_persistence import _make_context

FIXED_NOW = datetime(2031, 3, 4, 9, 0, tzinfo=UTC)


async def test_employee_sees_only_own_confirmed_safe_follow_up_state(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    context = await _make_context(db_session)
    membership = await db_session.get_one(OrganizationMembership, context.employee.membership_id)
    employee_user = await db_session.get_one(User, membership.user_id)
    final_exam = make_assessment(
        context.training,
        None,
        assessment_type="menu_final_exam",
    )
    db_session.add(final_exam)
    await db_session.flush()
    proposed = RetakeRequirement(
        organization_id=context.training.organization_id,
        location_id=context.training.location_id,
        training_id=context.training.id,
        employee_profile_id=context.employee.id,
        assignment_id=context.assignment.id,
        target_assessment_id=final_exam.id,
        reason="management_follow_up",
        state="proposed",
        management_source_key="private-proposal",
        target_policy={"assessment_type": "menu_final_exam", "minimum_result": "passed"},
        proposed_at=FIXED_NOW,
        proposed_by_user_id=context.actor.id,
        due_at=FIXED_NOW + timedelta(days=7),
        revision=0,
    )
    active = RetakeRequirement(
        organization_id=context.training.organization_id,
        location_id=context.training.location_id,
        training_id=context.training.id,
        employee_profile_id=context.employee.id,
        assignment_id=context.assignment.id,
        target_assessment_id=final_exam.id,
        reason="management_follow_up",
        state="active",
        management_source_key="manager-check-in",
        target_policy={
            "assessment_type": "menu_final_exam",
            "minimum_result": "passed",
            "internal_note": "must never be returned",
        },
        confirmed_at=FIXED_NOW,
        confirmed_by_user_id=context.actor.id,
        due_at=FIXED_NOW + timedelta(hours=24),
        revision=0,
    )
    critical_case = AttentionCase(
        organization_id=context.training.organization_id,
        location_id=context.training.location_id,
        training_id=context.training.id,
        employee_profile_id=context.employee.id,
        case_type="critical_allergen",
        subject_key=f"menu_item:{uuid4()}:allergen:{uuid4()}",
        state="open",
        revision=0,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    raw_session = f"employee-follow-up-{uuid4()}"
    csrf = f"employee-follow-up-csrf-{uuid4()}"
    employee_session = Session(
        user_id=employee_user.id,
        token_hash=hash_secret(raw_session),
        csrf_token_hash=hash_secret(csrf),
        last_seen_at=FIXED_NOW,
        absolute_expires_at=FIXED_NOW + timedelta(days=30),
    )
    db_session.add_all([proposed, active, critical_case, employee_session])
    await db_session.commit()
    auth_client.cookies.set("horeca_session", raw_session, path="/api/v1")

    requirements = await auth_client.get("/api/v1/me/training/retake-requirements")
    summary = await auth_client.get("/api/v1/me/training/final-exam")

    assert requirements.status_code == 200
    assert [item["id"] for item in requirements.json()["items"]] == [str(active.id)]
    safe_payload = requirements.text
    for forbidden in (
        "internal_note",
        "target_policy",
        "management_source_key",
        "confirmed_by_user_id",
        "cancellation_comment",
        "subject_key",
    ):
        assert forbidden not in safe_payload
    item = requirements.json()["items"][0]
    assert item["timing_state"] == "approaching"
    assert item["permitted_action"] == "start_retake"

    assert summary.status_code == 200
    assert summary.json()["current_retake_requirement"]["id"] == str(active.id)
    assert summary.json()["attention_summary"] == {
        "open_count": 1,
        "has_critical_follow_up": True,
        "has_overdue_follow_up": False,
    }
    assert "internal_note" not in summary.text


async def test_employee_follow_up_requires_an_active_employee_session(
    auth_client: AsyncClient,
) -> None:
    response = await auth_client.get("/api/v1/me/training/retake-requirements")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_REQUIRED"
