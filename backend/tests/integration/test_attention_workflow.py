from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AttentionCase, AttentionCaseSource, CriticalError
from app.services.attention import (
    acknowledge_attention_case,
    project_critical_errors_for_attempt,
    resolve_attention_case,
)
from tests.factories.assessments import (
    make_assessment,
    make_assessment_attempt,
    make_assessment_version,
    make_attempt_question,
    make_attempt_result,
    make_submitted_answer,
)
from tests.factories.menu import (
    make_allergen,
    make_item_allergen,
    make_item_version,
    make_menu,
    make_menu_category,
    make_menu_item,
    make_menu_section,
    make_menu_version,
    make_version_category,
    make_version_section,
)
from tests.integration.test_assessment_persistence import _make_context


@pytest.mark.integration
async def test_critical_projection_is_source_idempotent_and_case_deduplicated(
    db_session: AsyncSession,
) -> None:
    context = await _make_context(db_session)
    menu = make_menu(context.training.organization_id, context.training.location_id)
    section = make_menu_section(menu)
    category = make_menu_category(menu)
    item = make_menu_item(menu)
    allergen = make_allergen()
    menu_version = make_menu_version(menu, context.actor.id)
    db_session.add_all([menu, section, category, item, allergen, menu_version])
    await db_session.flush()
    version_section = make_version_section(menu_version, section)
    db_session.add(version_section)
    await db_session.flush()
    version_category = make_version_category(menu_version, category, version_section)
    db_session.add(version_category)
    await db_session.flush()
    item_version = make_item_version(menu_version, item, version_category)
    db_session.add(item_version)
    await db_session.flush()
    item_allergen = make_item_allergen(menu_version, item_version, allergen)
    db_session.add(item_allergen)

    practice = make_assessment(
        context.training,
        None,
        assessment_type="whole_menu_knowledge_check",
    )
    db_session.add(practice)
    await db_session.flush()
    practice_version = make_assessment_version(
        practice,
        context.training_version,
        None,
        question_count=10,
        threshold_percent=40,
        feedback_policy="after_final_submission",
    )
    db_session.add(practice_version)
    await db_session.flush()

    first_completed_at = datetime.now(UTC).replace(microsecond=0)
    first_attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        practice_version,
        status="completed",
        question_count=10,
        completed_at=first_completed_at,
    )
    db_session.add(first_attempt)
    await db_session.flush()
    first_question = make_attempt_question(
        first_attempt,
        context.question_version,
        is_critical=True,
        provenance_snapshot={
            "sources": [
                {
                    "role": "correct_fact",
                    "menu_item_version_allergen_id": str(item_allergen.id),
                }
            ]
        },
    )
    db_session.add(first_question)
    await db_session.flush()
    first_answer = make_submitted_answer(
        first_attempt,
        first_question,
        is_correct=False,
        is_critical_error=True,
        submitted_at=first_completed_at,
    )
    db_session.add_all(
        [
            first_answer,
            make_attempt_result(
                first_attempt,
                total_count=10,
                correct_count=3,
                score_basis_points=3000,
                pass_status=None,
                critical_error_count=1,
                completed_at=first_completed_at,
            ),
        ]
    )
    await db_session.flush()

    first_errors = await project_critical_errors_for_attempt(
        db_session,
        attempt=first_attempt,
    )
    replayed_errors = await project_critical_errors_for_attempt(
        db_session,
        attempt=first_attempt,
    )
    assert [error.id for error in replayed_errors] == [error.id for error in first_errors]
    assert len(first_errors) == 1
    assert first_errors[0].submitted_answer_id == first_answer.id
    assert first_errors[0].safe_context == {
        "assessment_type": "whole_menu_knowledge_check",
        "attempt_question_position": 0,
    }

    cases = list(await db_session.scalars(select(AttentionCase)))
    assert len(cases) == 1
    first_case_id = cases[0].id
    assert cases[0].state == "open"
    assert await db_session.scalar(select(func.count()).select_from(AttentionCaseSource)) == 1

    acknowledged_at = first_completed_at + timedelta(minutes=30)
    assert await acknowledge_attention_case(
        db_session,
        organization_id=context.training.organization_id,
        case_id=first_case_id,
        actor_user_id=context.actor.id,
        now=acknowledged_at,
    )
    assert not await acknowledge_attention_case(
        db_session,
        organization_id=context.training.organization_id,
        case_id=first_case_id,
        actor_user_id=context.actor.id,
        now=acknowledged_at,
    )
    with pytest.raises(ValueError, match="meaningful comment"):
        await resolve_attention_case(
            db_session,
            organization_id=context.training.organization_id,
            case_id=first_case_id,
            actor_user_id=context.actor.id,
            resolution_type="admin_follow_up",
            comment="  ",
            now=first_completed_at + timedelta(hours=1),
        )
    assert await resolve_attention_case(
        db_session,
        organization_id=context.training.organization_id,
        case_id=first_case_id,
        actor_user_id=context.actor.id,
        resolution_type="admin_follow_up",
        comment="  Проведено індивідуальний розбір.  ",
        now=first_completed_at + timedelta(hours=1),
    )

    second_completed_at = first_completed_at + timedelta(days=1)
    second_attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        practice_version,
        status="completed",
        question_count=10,
        completed_at=second_completed_at,
    )
    db_session.add(second_attempt)
    await db_session.flush()
    second_question = make_attempt_question(
        second_attempt,
        context.question_version,
        is_critical=True,
        provenance_snapshot=first_question.provenance_snapshot,
    )
    db_session.add(second_question)
    await db_session.flush()
    db_session.add_all(
        [
            make_submitted_answer(
                second_attempt,
                second_question,
                is_correct=False,
                is_critical_error=True,
                submitted_at=second_completed_at,
            ),
            make_attempt_result(
                second_attempt,
                total_count=10,
                correct_count=4,
                score_basis_points=4000,
                pass_status=None,
                critical_error_count=1,
                completed_at=second_completed_at,
            ),
        ]
    )
    await db_session.flush()

    second_errors = await project_critical_errors_for_attempt(
        db_session,
        attempt=second_attempt,
    )
    assert len(second_errors) == 1
    case_ids = set(await db_session.scalars(select(AttentionCase.id)))
    assert len(case_ids) == 2
    assert first_case_id in case_ids
    assert await db_session.scalar(select(func.count()).select_from(CriticalError)) == 2
    assert await db_session.scalar(select(func.count()).select_from(AttentionCaseSource)) == 2

    second_case = await db_session.scalar(
        select(AttentionCase).where(AttentionCase.state == "open")
    )
    assert second_case is not None
    clean_completed_at = second_completed_at + timedelta(days=1)
    clean_attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        practice_version,
        status="completed",
        question_count=10,
        completed_at=clean_completed_at,
    )
    db_session.add(clean_attempt)
    await db_session.flush()
    db_session.add(
        make_attempt_result(
            clean_attempt,
            total_count=10,
            correct_count=4,
            score_basis_points=4000,
            pass_status=None,
            critical_error_count=0,
            completed_at=clean_completed_at,
        )
    )
    await db_session.flush()
    with pytest.raises(ValueError, match="not proven"):
        await resolve_attention_case(
            db_session,
            organization_id=context.training.organization_id,
            case_id=second_case.id,
            actor_user_id=context.actor.id,
            resolution_type="clean_retake",
            evidence_attempt_id=clean_attempt.id,
            now=clean_completed_at + timedelta(minutes=1),
        )
    clean_question = make_attempt_question(
        clean_attempt,
        context.question_version,
        is_critical=True,
        provenance_snapshot=first_question.provenance_snapshot,
    )
    db_session.add(clean_question)
    await db_session.flush()
    db_session.add(
        make_submitted_answer(
            clean_attempt,
            clean_question,
            is_correct=True,
            is_critical_error=False,
            submitted_at=clean_completed_at,
        )
    )
    await db_session.flush()
    assert await resolve_attention_case(
        db_session,
        organization_id=context.training.organization_id,
        case_id=second_case.id,
        actor_user_id=context.actor.id,
        resolution_type="clean_retake",
        evidence_attempt_id=clean_attempt.id,
        now=clean_completed_at + timedelta(minutes=1),
    )

    incomplete_attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        practice_version,
        question_count=10,
    )
    db_session.add(incomplete_attempt)
    await db_session.flush()
    assert (
        await project_critical_errors_for_attempt(
            db_session,
            attempt=incomplete_attempt,
        )
        == []
    )
