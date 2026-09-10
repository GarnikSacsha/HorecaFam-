from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AttemptOption,
    OrganizationMembership,
    QuestionCandidate,
    QuestionGenerationRule,
    TrainingVersionMenuDependency,
    User,
)
from app.schemas.assessment import MultipleChoiceSubmission, SingleChoiceSubmission
from app.services.practice_answers import save_practice_answer
from app.services.practice_attempts import start_or_resume_practice_attempt
from app.services.practice_results import finish_practice_attempt, has_final_exam_eligibility
from app.services.question_generation import generate_question_candidates
from app.services.question_review import approve_question_candidate, ensure_practice_readiness
from tests.factories.auth import make_session
from tests.factories.menu import (
    make_category_translation,
    make_item_translation,
    make_item_version,
    make_menu,
    make_menu_category,
    make_menu_item,
    make_menu_section,
    make_menu_version,
    make_version_category,
    make_version_section,
)
from tests.factories.training import make_content_block, make_training_version
from tests.integration.test_assessment_persistence import _make_context


@pytest.mark.integration
@pytest.mark.parametrize("family", ["menu.category", "menu.description"])
@pytest.mark.parametrize("correct_count", [3, 4])
async def test_generated_reference_questions_unlock_practice_and_preserve_final_threshold(
    db_session: AsyncSession, family: str, correct_count: int
) -> None:
    context = await _make_context(db_session)
    now = datetime.now(UTC)
    scope = {
        "organization_id": context.training.organization_id,
        "location_id": context.training.location_id,
    }
    menu = make_menu(**scope)
    section = make_menu_section(menu)
    categories = [make_menu_category(menu, stable_code=f"category-{i}") for i in range(2)]
    items = [make_menu_item(menu, stable_code=f"item-{i}") for i in range(10)]
    db_session.add_all([menu, section, *categories, *items])
    await db_session.flush()
    menu_version = make_menu_version(
        menu,
        context.actor.id,
        status="published",
        published_at=now,
        published_by_user_id=context.actor.id,
    )
    db_session.add(menu_version)
    await db_session.flush()
    version_section = make_version_section(menu_version, section)
    db_session.add(version_section)
    await db_session.flush()
    version_categories = [
        make_version_category(menu_version, category, version_section, position=i)
        for i, category in enumerate(categories)
    ]
    db_session.add_all(version_categories)
    await db_session.flush()
    db_session.add_all(
        [
            make_category_translation(menu_version, category, name=f"Category {i}")
            for i, category in enumerate(version_categories)
        ]
    )
    for i, item in enumerate(items):
        version = make_item_version(
            menu_version,
            item,
            version_categories[i % 2],
            position=i,
            verified_by_user_id=context.actor.id,
            verified_at=now,
        )
        db_session.add(version)
        await db_session.flush()
        # Невідомі склад та алергени не доповнюються заради готовності Practice.
        assert version.component_data_status == version.allergen_data_status == "unknown"
        db_session.add_all(
            [
                make_item_translation(
                    menu_version,
                    version,
                    name=f"Synthetic item {i}",
                    description=f"Unique verified description {i}",
                ),
                make_content_block(
                    context.lesson_version,
                    type="menu_item_card",
                    position=i,
                    payload={"menu_item_id": str(item.id)},
                    menu_item_id=item.id,
                ),
            ]
        )
    rule = QuestionGenerationRule(
        code=family,
        version=1,
        domain_type="menu",
        mechanic="single_choice" if family == "menu.category" else "recognition",
        status="active",
        configuration={},
    )
    db_session.add_all(
        [
            rule,
            TrainingVersionMenuDependency(
                training_version_id=context.training_version.id,
                menu_version_id=menu_version.id,
            ),
        ]
    )
    await db_session.flush()
    generation = await generate_question_candidates(
        db_session,
        **scope,
        menu_version_id=menu_version.id,
        training_version_id=context.training_version.id,
    )
    assert generation.created_count == 10
    candidates = list(
        await db_session.scalars(
            select(QuestionCandidate)
            .where(QuestionCandidate.generation_rule_id == rule.id)
            .order_by(QuestionCandidate.id)
        )
    )
    readiness_kwargs = dict(
        **scope,
        training_version_id=context.training_version.id,
        actor_user_id=context.actor.id,
    )
    before_review = await ensure_practice_readiness(db_session, **readiness_kwargs, now=now)
    assert before_review.eligible_count == 0
    for candidate in candidates[:9]:
        await approve_question_candidate(
            db_session,
            **scope,
            candidate_id=candidate.id,
            expected_revision=0,
            edited_payload=None,
            actor_user_id=context.actor.id,
            request_id=candidate.id,
            now=now,
        )
    nine = await ensure_practice_readiness(db_session, **readiness_kwargs, now=now)
    assert nine.eligible_count == 9
    assert nine.status == "blocked"
    assert nine.required_count == 10
    candidate = candidates[9]
    await approve_question_candidate(
        db_session,
        **scope,
        candidate_id=candidate.id,
        expected_revision=0,
        edited_payload=None,
        actor_user_id=context.actor.id,
        request_id=candidate.id,
        now=now,
    )
    ready = await ensure_practice_readiness(db_session, **readiness_kwargs, now=now)
    assert ready.eligible_count == 10
    assert ready.status == "warning"
    assert ready.rotation_supported is False
    assert ready.coverage_evidence["distinct_menu_item_count"] == 10

    employee_user = await db_session.scalar(
        select(User)
        .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
        .where(OrganizationMembership.id == context.employee.membership_id)
    )
    assert employee_user is not None
    auth_session = make_session(employee_user, token_hash="5" * 64, csrf_token_hash="6" * 64)
    db_session.add(auth_session)
    context.assignment.status = "completed"
    context.assignment.started_at = now
    context.assignment.completed_at = now
    await db_session.flush()
    assert not await has_final_exam_eligibility(db_session, assignment=context.assignment)
    employee_scope = dict(
        **scope,
        employee_profile_id=context.employee.id,
        actor_user_id=employee_user.id,
        session_id=auth_session.id,
        request_id=auth_session.id,
    )
    started = await start_or_resume_practice_attempt(
        db_session,
        **employee_scope,
        presentation_locale="uk",
        idempotency_key="reference-practice-start",
        now=now,
    )
    assert len(started.attempt.questions) == 10
    for hidden in ("is_correct", "grading_payload", "explanation_payload", "provenance"):
        assert hidden not in started.model_dump_json()
    for i, question in enumerate(started.attempt.questions):
        option_id = await db_session.scalar(
            select(AttemptOption.id)
            .where(
                AttemptOption.attempt_question_id == question.id,
                AttemptOption.is_correct.is_(i < correct_count),
            )
            .order_by(AttemptOption.id)
            .limit(1)
        )
        assert option_id is not None
        answer = (
            SingleChoiceSubmission(mechanic="single_choice", option_id=option_id)
            if family == "menu.category"
            else MultipleChoiceSubmission(mechanic="recognition", option_ids=[option_id])
        )
        saved = await save_practice_answer(
            db_session,
            **employee_scope,
            attempt_id=started.attempt.id,
            attempt_question_id=question.id,
            answer_payload=answer,
            lease_generation=1,
            idempotency_key=f"reference-answer-{i}",
            now=now,
        )
        assert "is_correct" not in saved.model_dump_json()
    finished = await finish_practice_attempt(
        db_session,
        **employee_scope,
        attempt_id=started.attempt.id,
        lease_generation=1,
        idempotency_key="reference-practice-finish",
        now=now + timedelta(minutes=1),
    )
    assert finished.result.correct_count == correct_count
    assert finished.result.score_basis_points == correct_count * 1000
    assert finished.qualified is (correct_count == 4)
    assert finished.eligibility_earned is (correct_count == 4)
    assert await has_final_exam_eligibility(db_session, assignment=context.assignment) is (
        correct_count == 4
    )

    context.training_version.status = "archived"
    context.training_version.archived_at = now
    await db_session.flush()
    other_version = make_training_version(
        context.training,
        context.actor.id,
        version_number=2,
        status="published",
        published_at=now,
        published_by_user_id=context.actor.id,
    )
    db_session.add(other_version)
    await db_session.flush()
    other_readiness = await ensure_practice_readiness(
        db_session,
        **{**readiness_kwargs, "training_version_id": other_version.id},
        now=now,
    )
    assert other_readiness.eligible_count == 0
    assert other_readiness.status == "blocked"
