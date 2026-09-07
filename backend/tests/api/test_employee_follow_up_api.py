from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
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
from tests.factories.assessments import (
    make_assessment,
    make_assessment_attempt,
    make_assessment_version,
)
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


@pytest.mark.parametrize(
    ("running_assessment", "expected_action"),
    [
        ("interactive", "start_retake"),
        ("practice", "start_retake"),
        ("final_exam", "resume_retake"),
    ],
)
async def test_retake_resume_action_requires_a_matching_assessment(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    running_assessment: str,
    expected_action: str,
) -> None:
    auth_app.state.clock = lambda: FIXED_NOW
    context = await _make_context(db_session)
    membership = await db_session.get_one(OrganizationMembership, context.employee.membership_id)
    exam = make_assessment(context.training, None, assessment_type="menu_final_exam")
    db_session.add(exam)
    await db_session.flush()
    exam_version = make_assessment_version(
        exam,
        context.training_version,
        None,
        question_count=20,
        threshold_percent=70,
        feedback_policy="after_final_submission",
    )
    db_session.add(exam_version)
    await db_session.flush()
    requirement = RetakeRequirement(
        organization_id=context.training.organization_id,
        location_id=context.training.location_id,
        training_id=context.training.id,
        employee_profile_id=context.employee.id,
        assignment_id=context.assignment.id,
        target_assessment_id=exam.id,
        reason="management_follow_up",
        state="active",
        management_source_key="matching-assessment",
        target_policy={"assessment_type": "menu_final_exam", "minimum_result": "passed"},
        confirmed_at=FIXED_NOW,
        confirmed_by_user_id=context.actor.id,
        due_at=FIXED_NOW + timedelta(days=7),
        revision=0,
    )
    context.assignment.status = "completed"
    context.assignment.started_at = context.assignment.completed_at = FIXED_NOW
    running_version = (
        exam_version if running_assessment == "final_exam" else context.assessment_version
    )
    if running_assessment == "practice":
        practice = make_assessment(
            context.training, None, assessment_type="whole_menu_knowledge_check"
        )
        db_session.add(practice)
        await db_session.flush()
        running_version = make_assessment_version(
            practice,
            context.training_version,
            None,
            question_count=10,
            threshold_percent=40,
            feedback_policy="after_final_submission",
        )
        db_session.add(running_version)
        await db_session.flush()
    attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        running_version,
        question_count=running_version.question_count,
        started_at=FIXED_NOW,
        last_activity_at=FIXED_NOW,
        expires_at=FIXED_NOW + timedelta(days=7),
    )
    token = f"matching-follow-up-{uuid4()}"
    session = Session(
        user_id=membership.user_id,
        token_hash=hash_secret(token),
        csrf_token_hash=hash_secret(f"matching-csrf-{uuid4()}"),
        last_seen_at=FIXED_NOW,
        absolute_expires_at=FIXED_NOW + timedelta(days=30),
    )
    db_session.add_all([requirement, attempt, session])
    await db_session.commit()
    requirement_id, target_id = requirement.id, exam.id
    auth_client.cookies.set("horeca_session", token, path="/api/v1")
    response = await auth_client.get("/api/v1/me/training/retake-requirements")
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["id"] == str(requirement_id)
    assert item["target_assessment_id"] == str(target_id)
    assert item["permitted_action"] == expected_action

    requirement.clock_frozen_at = FIXED_NOW
    await db_session.commit()
    frozen = await auth_client.get("/api/v1/me/training/retake-requirements")
    assert frozen.status_code == 200
    assert frozen.json()["items"][0]["permitted_action"] == "wait"
    assert frozen.json()["items"][0]["timing_state"] == "frozen"

    requirement.state = "cancelled"
    requirement.clock_frozen_at = None
    requirement.cancelled_at = FIXED_NOW
    requirement.cancelled_by_user_id = context.actor.id
    requirement.cancellation_comment = "Requirement withdrawn"
    await db_session.commit()
    history = await auth_client.get("/api/v1/me/training/retake-requirements")
    assert history.status_code == 200
    assert history.json()["items"][0]["permitted_action"] == "review_history"
    assert history.json()["items"][0]["timing_state"] is None

    older = RetakeRequirement(
        organization_id=requirement.organization_id,
        location_id=requirement.location_id,
        training_id=requirement.training_id,
        employee_profile_id=requirement.employee_profile_id,
        assignment_id=requirement.assignment_id,
        target_assessment_id=target_id,
        reason="management_follow_up",
        state="cancelled",
        management_source_key="earlier-cancelled-review",
        target_policy=requirement.target_policy,
        confirmed_at=FIXED_NOW,
        confirmed_by_user_id=context.actor.id,
        due_at=FIXED_NOW + timedelta(days=8),
        cancelled_at=FIXED_NOW,
        cancelled_by_user_id=context.actor.id,
        cancellation_comment="Historical cancellation",
        revision=0,
    )
    db_session.add(older)
    await db_session.commit()
    older_id = older.id
    base = "/api/v1/me/training/retake-requirements"
    first_page = await auth_client.get(base, params={"limit": 1})
    assert first_page.status_code == 200
    assert [row["id"] for row in first_page.json()["items"]] == [str(requirement_id)]
    cursor = first_page.json()["next_cursor"]
    assert isinstance(cursor, str)
    second_page = await auth_client.get(base, params={"limit": 1, "cursor": cursor})
    assert second_page.status_code == 200
    assert [row["id"] for row in second_page.json()["items"]] == [str(older_id)]
    assert second_page.json()["next_cursor"] is None
    import base64
    import json

    invalid_payloads: list[object] = [
        {},
        [2, "2031-03-04T09:00:00", str(requirement_id)],
        [2, "bad-date", str(requirement_id)],
    ]
    for payload in invalid_payloads:
        invalid_cursor = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
        rejected = await auth_client.get(base, params={"cursor": invalid_cursor})
        assert rejected.status_code == 422 and rejected.json()["code"] == "INVALID_CURSOR"
    assert (await auth_client.get(base, params={"limit": 1})).json() == first_page.json()
