from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import EmployeeProfile, Location, OrganizationMembership, Session, User
from app.schemas.assessment import SingleChoiceSubmission
from app.services.final_exam_answers import save_final_exam_answer
from app.services.final_exam_results import finish_final_exam_attempt
from tests.api import test_vertical_slice_acceptance as slice_acceptance
from tests.factories.assessments import (
    make_assessment,
    make_assessment_attempt,
    make_assessment_eligibility,
    make_assessment_readiness,
    make_assessment_version,
    make_attempt_device_lease,
    make_attempt_option,
    make_attempt_question,
    make_question,
    make_question_candidate,
    make_question_generation_rule,
    make_question_option,
    make_question_version,
)
from tests.factories.training import (
    make_lesson,
    make_lesson_version,
    make_training,
    make_training_assignment,
    make_training_module,
    make_training_module_version,
    make_training_version,
)


@pytest.mark.integration
async def test_synthetic_invitation_to_passing_final_result_chain(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    auth_settings: Settings,
    db_session: AsyncSession,
) -> None:
    await slice_acceptance.test_complete_backend_slice_from_admin_login_to_active_employee_access(
        auth_client, auth_app, auth_settings, db_session
    )

    employee_user = await db_session.scalar(
        select(User).where(User.email_normalized == "stage7.employee@example.com")
    )
    admin_user = await db_session.scalar(
        select(User).where(User.email_normalized == "stage7-admin@example.com")
    )
    assert employee_user is not None and admin_user is not None
    membership = await db_session.scalar(
        select(OrganizationMembership).where(OrganizationMembership.user_id == employee_user.id)
    )
    assert membership is not None and membership.status == "active"
    employee = await db_session.scalar(
        select(EmployeeProfile).where(EmployeeProfile.membership_id == membership.id)
    )
    assert employee is not None and employee.location_id is not None
    location = await db_session.get_one(Location, employee.location_id)
    employee_session = await db_session.scalar(
        select(Session).where(
            Session.user_id == employee_user.id,
            Session.revoked_at.is_(None),
        )
    )
    assert employee_session is not None
    now = datetime(2030, 8, 27, 16, 0, tzinfo=UTC)

    training = make_training(membership.organization_id, location.id)
    module = make_training_module(training)
    db_session.add_all([training, module])
    await db_session.flush()
    training_version = make_training_version(
        training,
        admin_user.id,
        status="published",
        published_by_user_id=admin_user.id,
        published_at=now,
    )
    db_session.add(training_version)
    await db_session.flush()
    module_version = make_training_module_version(training_version, module)
    lesson = make_lesson(module)
    db_session.add_all([module_version, lesson])
    await db_session.flush()
    lesson_version = make_lesson_version(module_version, lesson)
    assignment = make_training_assignment(
        employee,
        training,
        training_version,
        status="completed",
        started_at=now,
        completed_at=now,
    )
    rule = make_question_generation_rule(code="synthetic.final.single_choice")
    db_session.add_all([lesson_version, assignment, rule])
    await db_session.flush()

    practice = make_assessment(training, None, assessment_type="whole_menu_knowledge_check")
    final_exam = make_assessment(training, None, assessment_type="menu_final_exam")
    db_session.add_all([practice, final_exam])
    await db_session.flush()
    practice_version = make_assessment_version(
        practice,
        training_version,
        None,
        question_count=10,
        threshold_percent=40,
        feedback_policy="after_final_submission",
    )
    final_version = make_assessment_version(
        final_exam,
        training_version,
        None,
        question_count=20,
        threshold_percent=70,
        feedback_policy="after_final_submission",
    )
    db_session.add_all([practice_version, final_version])
    await db_session.flush()
    db_session.add(
        make_assessment_readiness(
            final_version,
            eligible_count=20,
            required_count=20,
            warning_codes=["REPEAT_ROTATION_LIMITED"],
        )
    )
    qualifying_practice = make_assessment_attempt(
        employee,
        assignment,
        practice_version,
        status="completed",
        question_count=10,
        completed_at=now,
    )
    db_session.add(qualifying_practice)
    await db_session.flush()
    db_session.add(
        make_assessment_eligibility(
            employee,
            assignment,
            final_exam,
            qualifying_practice,
            earned_at=now,
        )
    )

    attempt = make_assessment_attempt(
        employee,
        assignment,
        final_version,
        question_count=20,
        started_at=now,
        last_activity_at=now,
        expires_at=now + timedelta(days=7),
    )
    db_session.add(attempt)
    await db_session.flush()
    db_session.add(make_attempt_device_lease(attempt, employee_session))
    attempt_questions = []
    for index in range(20):
        candidate = make_question_candidate(
            rule,
            training_version,
            lesson_version,
            prompt_payload={"text": f"Synthetic final question {index + 1}"},
            source_fingerprint=f"{index + 1:064x}",
            status="approved",
            is_critical=index == 19,
        )
        question = make_question(candidate)
        db_session.add_all([candidate, question])
        await db_session.flush()
        version = make_question_version(question, candidate, admin_user.id)
        db_session.add(version)
        await db_session.flush()
        options = [make_question_option(version, 0), make_question_option(version, 1)]
        db_session.add_all(options)
        await db_session.flush()
        attempt_question = make_attempt_question(
            attempt,
            version,
            position=index,
            coverage_key=f"synthetic-menu-item-{index + 1}",
        )
        db_session.add(attempt_question)
        await db_session.flush()
        attempt_options = [
            make_attempt_option(attempt_question, options[0]),
            make_attempt_option(attempt_question, options[1]),
        ]
        db_session.add_all(attempt_options)
        attempt_questions.append((attempt_question, attempt_options))
    await db_session.commit()

    for index, (attempt_question, attempt_options) in enumerate(attempt_questions):
        ordered_options = sorted(attempt_options, key=lambda option: option.position)
        chosen = ordered_options[0 if index < 14 else 1]
        answer = await save_final_exam_answer(
            db_session,
            organization_id=membership.organization_id,
            location_id=location.id,
            employee_profile_id=employee.id,
            actor_user_id=employee_user.id,
            session_id=employee_session.id,
            attempt_id=attempt.id,
            attempt_question_id=attempt_question.id,
            answer_payload=SingleChoiceSubmission(
                mechanic="single_choice",
                option_id=chosen.id,
            ),
            lease_generation=1,
            idempotency_key=f"synthetic-final-answer-{index}",
            request_id=employee_session.id,
            now=now + timedelta(minutes=index + 1),
        )
        assert "is_correct" not in answer.model_dump_json()

    finished = await finish_final_exam_attempt(
        db_session,
        organization_id=membership.organization_id,
        location_id=location.id,
        employee_profile_id=employee.id,
        actor_user_id=employee_user.id,
        session_id=employee_session.id,
        attempt_id=attempt.id,
        lease_generation=1,
        idempotency_key="synthetic-final-finish",
        request_id=employee_session.id,
        now=now + timedelta(minutes=30),
    )

    assert finished.result.correct_count == 14
    assert finished.result.total_count == 20
    assert finished.result.pass_status == "passed"
    assert finished.certification is not None
    assert finished.newly_certified is True
