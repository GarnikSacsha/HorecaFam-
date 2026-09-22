from datetime import UTC, datetime
from typing import TypedDict
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    AssessmentVersion,
    MenuItemVersion,
    MenuItemVersionTranslation,
    QuestionCandidate,
    QuestionVersion,
    TrainingVersionMenuDependency,
)
from app.schemas.assessment import (
    AuthoredQuestionRequest,
    FinalExamQuotaPolicy,
    FinalExamVersionRequest,
    QuestionCandidateBatchItem,
)
from app.services.final_exam_configuration import create_final_exam_version
from app.services.final_exam_readiness import ensure_final_exam_readiness, get_final_exam_readiness
from app.services.question_authoring import create_authored_question
from app.services.question_generation import (
    candidate_source_fingerprint_is_current,
    generate_question_candidates,
)
from app.services.question_review import approve_question_candidate_batch
from tests.factories.menu import (
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
from tests.factories.training import make_content_block
from tests.integration.test_assessment_persistence import AssessmentContext, _make_context


class MutationScope(TypedDict):
    organization_id: UUID
    location_id: UUID
    actor_user_id: UUID
    request_id: UUID
    now: datetime


async def authored_context(
    db: AsyncSession,
    counts: tuple[int, int, int, int] = (10, 4, 3, 3),
) -> tuple[AssessmentContext, list[AuthoredQuestionRequest], list[UUID]]:
    context = await _make_context(db)
    now = datetime.now(UTC)
    menu = make_menu(context.training.organization_id, context.training.location_id)
    db.add(menu)
    await db.flush()
    version = make_menu_version(
        menu,
        context.actor.id,
        status="published",
        published_by_user_id=context.actor.id,
        published_at=now,
    )
    section = make_menu_section(menu)
    db.add_all([version, section])
    await db.flush()
    version_section = make_version_section(version, section)
    db.add(version_section)
    db.add(
        TrainingVersionMenuDependency(
            training_version_id=context.training_version.id, menu_version_id=version.id
        )
    )
    await db.flush()
    requests: list[AuthoredQuestionRequest] = []
    categories = []
    for group, count in enumerate(counts):
        category = make_menu_category(menu, stable_code=f"group-{group}")
        db.add(category)
        await db.flush()
        version_category = make_version_category(version, category, version_section, position=group)
        db.add(version_category)
        await db.flush()
        categories.append(version_category.id)
        for index in range(count):
            position = len(requests)
            item = make_menu_item(menu, stable_code=f"item-{group}-{index}")
            db.add(item)
            await db.flush()
            item_version = make_item_version(
                version,
                item,
                version_category,
                position=index,
                verified_by_user_id=context.actor.id,
                verified_at=now,
            )
            db.add(item_version)
            await db.flush()
            db.add_all(
                [
                    make_item_translation(
                        version,
                        item_version,
                        name=f"Страва {position}",
                        description="Подається з рисом і зеленню.",
                    ),
                    make_content_block(
                        context.lesson_version,
                        position=position,
                        type="menu_item_card",
                        menu_item_id=item.id,
                        payload={},
                    ),
                ]
            )
            requests.append(
                AuthoredQuestionRequest.model_validate(
                    {
                        "training_version_id": context.training_version.id,
                        "lesson_version_id": context.lesson_version.id,
                        "prompt_payload": {
                            "stem": f"З чим подають страву {position}?",
                            "selection_mode": "single",
                            "options": [
                                {"stable_key": str(i), "text": label}
                                for i, label in enumerate(
                                    ("З рисом", "З картоплею", "З пастою", "З гречкою")
                                )
                            ],
                        },
                        "answer_payload": {"correct_option_keys": ["0"]},
                        "explanation_payload": {
                            "text": "В описі зазначено рис.",
                            "authoring": {
                                "menu_version_id": version.id,
                                "menu_item_version_id": item_version.id,
                                "source_quote": "Подається з рисом і зеленню.",
                                "option_rationales": {
                                    str(i): "Відповідає опису."
                                    if i == 0
                                    else "Не відповідає опису гарніру."
                                    for i in range(4)
                                },
                            },
                        },
                    }
                )
            )
    await db.commit()
    return context, requests, categories


@pytest.mark.integration
async def test_authoring_preserves_review_source_and_idempotency(db_session: AsyncSession) -> None:
    context, requests, _ = await authored_context(db_session)
    payload = requests[0]
    scope: MutationScope = dict(
        organization_id=context.training.organization_id,
        location_id=context.training.location_id,
        actor_user_id=context.actor.id,
        request_id=uuid4(),
        now=datetime.now(UTC),
    )
    created = await create_authored_question(
        db_session, **scope, payload=payload, idempotency_key="first"
    )
    replay = await create_authored_question(
        db_session, **scope, payload=payload, idempotency_key="first"
    )
    assert created.id == replay.id
    assert created.status == "needs_review"
    assert created.explanation_payload["authoring"]
    assert (
        await db_session.scalar(
            select(QuestionVersion).where(QuestionVersion.candidate_id == created.id)
        )
        is None
    )
    with pytest.raises(APIError) as error:
        await create_authored_question(
            db_session, **scope, payload=requests[1], idempotency_key="first"
        )
    assert error.value.code == "IDEMPOTENCY_KEY_REUSED"
    evidence = payload.explanation_payload.authoring
    assert evidence is not None
    await generate_question_candidates(
        db_session,
        organization_id=context.training.organization_id,
        location_id=context.training.location_id,
        menu_version_id=evidence.menu_version_id,
        training_version_id=context.training_version.id,
    )
    candidate = await db_session.get_one(QuestionCandidate, created.id)
    assert candidate.status == "needs_review"
    assert await candidate_source_fingerprint_is_current(db_session, candidate)
    evidence = payload.explanation_payload.authoring
    assert evidence is not None
    translation = await db_session.scalar(
        select(MenuItemVersionTranslation).where(
            MenuItemVersionTranslation.menu_item_version_id == evidence.menu_item_version_id
        )
    )
    assert translation is not None
    translation.description = "Опис змінився."
    await db_session.flush()
    assert not await candidate_source_fingerprint_is_current(db_session, candidate)
    with pytest.raises(APIError) as stale:
        await approve_question_candidate_batch(
            db_session,
            **scope,
            items=[QuestionCandidateBatchItem(candidate_id=created.id, expected_revision=0)],
        )
    assert stale.value.code == "QUESTION_CANDIDATE_STALE"


@pytest.mark.integration
@pytest.mark.parametrize("invalid", ["quote", "lesson", "unverified", "foreign"])
async def test_authored_sources_fail_closed(db_session: AsyncSession, invalid: str) -> None:
    context, requests, _ = await authored_context(db_session)
    payload = requests[0]
    evidence = payload.explanation_payload.authoring
    assert evidence is not None
    organization_id = context.training.organization_id
    if invalid == "quote":
        evidence.source_quote = "Вигаданий опис"
    elif invalid == "lesson":
        payload.lesson_version_id = uuid4()
    elif invalid == "foreign":
        organization_id = uuid4()
    else:
        item = await db_session.get_one(MenuItemVersion, evidence.menu_item_version_id)
        item.verified_by_user_id = None
        item.verified_at = None
        await db_session.flush()
    with pytest.raises(APIError) as error:
        await create_authored_question(
            db_session,
            organization_id=organization_id,
            location_id=context.training.location_id,
            actor_user_id=context.actor.id,
            payload=payload,
            idempotency_key="invalid",
            request_id=uuid4(),
            now=datetime.now(UTC),
        )
    assert error.value.code == (
        "RESOURCE_NOT_FOUND" if invalid == "foreign" else "QUESTION_PROVENANCE_INVALID"
    )


@pytest.mark.integration
@pytest.mark.parametrize("rotation", [False, True])
async def test_curated_version_is_immutable_replayable_and_preserves_old_bank(
    db_session: AsyncSession,
    rotation: bool,
) -> None:
    context, requests, categories = await authored_context(
        db_session, (30, 12, 8, 10) if rotation else (10, 4, 3, 3)
    )
    scope: MutationScope = dict(
        organization_id=context.training.organization_id,
        location_id=context.training.location_id,
        actor_user_id=context.actor.id,
        request_id=uuid4(),
        now=datetime.now(UTC),
    )
    created = [
        await create_authored_question(
            db_session, **scope, payload=payload, idempotency_key=f"question-{index}"
        )
        for index, payload in enumerate(requests)
    ]
    await approve_question_candidate_batch(
        db_session,
        **scope,
        items=[
            QuestionCandidateBatchItem(candidate_id=row.id, expected_revision=0) for row in created
        ],
    )
    question_ids = list(
        await db_session.scalars(
            select(QuestionVersion.id).where(
                QuestionVersion.candidate_id.in_([row.id for row in created])
            )
        )
    )
    for question in await db_session.scalars(
        select(QuestionVersion).where(QuestionVersion.id.in_(question_ids))
    ):
        assert "authoring" not in question.explanation_payload
    readonly = dict(
        organization_id=context.training.organization_id, location_id=context.training.location_id
    )
    old = await get_final_exam_readiness(
        db_session, **readonly, training_version_id=context.training_version.id
    )
    assert old.assessment_version_id is not None
    assert old.eligible_count == 0
    old_version = await db_session.get_one(AssessmentVersion, old.assessment_version_id)
    old_policy = dict(old_version.sampling_configuration)
    policy = FinalExamQuotaPolicy.model_validate(
        {
            "question_version_ids": question_ids,
            "buckets": [
                {"key": key, "count": count, "category_ids": [category]}
                for (key, count), category in zip(
                    (("food", 10), ("drinks", 4), ("desserts", 3), ("other", 3)),
                    categories,
                    strict=True,
                )
            ],
        }
    )
    payload = FinalExamVersionRequest(
        expected_assessment_version_id=old.assessment_version_id, policy=policy
    )
    result = await create_final_exam_version(
        db_session,
        **scope,
        training_version_id=context.training_version.id,
        payload=payload,
        idempotency_key="version",
    )
    assert result.assessment_version_id != old.assessment_version_id
    assert result.status == ("ready" if rotation else "warning")
    assert result.eligible_count == len(requests)
    replay = await create_final_exam_version(
        db_session,
        **scope,
        training_version_id=context.training_version.id,
        payload=payload,
        idempotency_key="version",
    )
    assert replay.assessment_version_id == result.assessment_version_id
    assert old_version.sampling_configuration == old_policy and old_version.status == "published"
    with pytest.raises(APIError) as conflict:
        await create_final_exam_version(
            db_session,
            **scope,
            training_version_id=context.training_version.id,
            payload=payload,
            idempotency_key="another",
        )
    assert conflict.value.code == "REVISION_CONFLICT"
    refreshed = await ensure_final_exam_readiness(
        db_session,
        **readonly,
        training_version_id=context.training_version.id,
        actor_user_id=context.actor.id,
        now=datetime.now(UTC),
    )
    assert refreshed.assessment_version_id == result.assessment_version_id
    assert refreshed.eligible_count == len(requests)
    from app.models import Assessment, OrganizationMembership, User
    from app.schemas.assessment import MultipleChoiceSubmission
    from app.services.final_exam_answers import save_final_exam_answer
    from app.services.final_exam_attempts import start_or_resume_final_exam_attempt
    from app.services.final_exam_results import finish_final_exam_attempt
    from tests.factories.assessments import make_assessment_attempt, make_assessment_eligibility
    from tests.factories.auth import make_session

    membership = await db_session.get_one(OrganizationMembership, context.employee.membership_id)
    employee_user = await db_session.get_one(User, membership.user_id)
    session = make_session(employee_user)
    practice_version = await db_session.scalar(
        select(AssessmentVersion)
        .join(Assessment, Assessment.id == AssessmentVersion.assessment_id)
        .where(
            AssessmentVersion.training_version_id == context.training_version.id,
            Assessment.assessment_type == "whole_menu_knowledge_check",
        )
    )
    assert practice_version is not None
    practice_attempt = make_assessment_attempt(
        context.employee,
        context.assignment,
        practice_version,
        question_count=10,
        status="completed",
        completed_at=scope["now"],
    )
    context.assignment.status = "completed"
    context.assignment.started_at = context.assignment.completed_at = scope["now"]
    db_session.add_all([session, practice_attempt])
    await db_session.flush()
    exam = await db_session.get_one(Assessment, old_version.assessment_id)
    db_session.add(
        make_assessment_eligibility(context.employee, context.assignment, exam, practice_attempt)
    )
    await db_session.commit()
    started = await start_or_resume_final_exam_attempt(
        db_session,
        **readonly,
        employee_profile_id=context.employee.id,
        actor_user_id=employee_user.id,
        session_id=session.id,
        presentation_locale="uk",
        idempotency_key="new-exam",
        request_id=uuid4(),
        now=scope["now"],
    )
    assert started.attempt.assessment_version_id == result.assessment_version_id
    assert len(started.attempt.questions) == 20
    assert "authoring" not in started.model_dump_json()
    for index, attempt_question in enumerate(started.attempt.questions):
        option = next(
            option
            for option in attempt_question.options
            if option.payload["text"]
            == ("З рисом" if index < (13 if rotation else 19) else "З пастою")
        )
        await save_final_exam_answer(
            db_session,
            **readonly,
            employee_profile_id=context.employee.id,
            actor_user_id=employee_user.id,
            session_id=session.id,
            attempt_id=started.attempt.id,
            attempt_question_id=attempt_question.id,
            answer_payload=MultipleChoiceSubmission(mechanic="recognition", option_ids=[option.id]),
            lease_generation=started.attempt.lease_generation,
            idempotency_key=f"answer-{index}",
            request_id=uuid4(),
            now=scope["now"],
        )
    finished = await finish_final_exam_attempt(
        db_session,
        **readonly,
        employee_profile_id=context.employee.id,
        actor_user_id=employee_user.id,
        session_id=session.id,
        attempt_id=started.attempt.id,
        lease_generation=started.attempt.lease_generation,
        idempotency_key="finish",
        request_id=uuid4(),
        now=scope["now"],
    )
    assert finished.result.correct_count == (13 if rotation else 19)
    assert finished.result.score_basis_points == (6500 if rotation else 9500)
    assert result.assessment_version_id is not None
    next_payload = FinalExamVersionRequest(
        expected_assessment_version_id=result.assessment_version_id, policy=policy
    )
    next_version = await create_final_exam_version(
        db_session,
        **scope,
        training_version_id=context.training_version.id,
        payload=next_payload,
        idempotency_key="version-after-certification",
    )
    assert next_version.assessment_version_id != result.assessment_version_id
    repeated_finish = await finish_final_exam_attempt(
        db_session,
        **readonly,
        employee_profile_id=context.employee.id,
        actor_user_id=employee_user.id,
        session_id=session.id,
        attempt_id=started.attempt.id,
        lease_generation=started.attempt.lease_generation,
        idempotency_key="finish",
        request_id=uuid4(),
        now=scope["now"],
    )
    assert repeated_finish.result == finished.result
    assert repeated_finish.certification == finished.certification
    if rotation:
        from app.models import AttemptQuestion

        restarted = await start_or_resume_final_exam_attempt(
            db_session,
            **readonly,
            employee_profile_id=context.employee.id,
            actor_user_id=employee_user.id,
            session_id=session.id,
            presentation_locale="uk",
            idempotency_key="retake-after-version-change",
            request_id=uuid4(),
            now=scope["now"],
        )
        previous_ids = set(
            await db_session.scalars(
                select(AttemptQuestion.question_version_id).where(
                    AttemptQuestion.attempt_id == started.attempt.id
                )
            )
        )
        next_ids = set(
            await db_session.scalars(
                select(AttemptQuestion.question_version_id).where(
                    AttemptQuestion.attempt_id == restarted.attempt.id
                )
            )
        )
        assert restarted.attempt.assessment_version_id == next_version.assessment_version_id
        assert len(next_ids) == 20
        assert not previous_ids & next_ids, "Version rollover repeated the previous completed exam"
        return
    with pytest.raises(APIError) as certified:
        await start_or_resume_final_exam_attempt(
            db_session,
            **readonly,
            employee_profile_id=context.employee.id,
            actor_user_id=employee_user.id,
            session_id=session.id,
            presentation_locale="uk",
            idempotency_key="not-an-automatic-retake",
            request_id=uuid4(),
            now=scope["now"],
        )
    assert certified.value.code == "FINAL_EXAM_ALREADY_PASSED"


@pytest.mark.integration
async def test_active_old_exam_resumes_even_when_new_bank_is_blocked(
    db_session: AsyncSession,
) -> None:
    from app.models import OrganizationMembership, User
    from app.services.final_exam_attempts import start_or_resume_final_exam_attempt
    from tests.factories.assessments import (
        make_assessment,
        make_assessment_attempt,
        make_assessment_readiness,
        make_assessment_version,
        make_attempt_device_lease,
    )
    from tests.factories.auth import make_session

    context = await _make_context(db_session)
    now = datetime.now(UTC)
    membership = await db_session.get_one(OrganizationMembership, context.employee.membership_id)
    user = await db_session.get_one(User, membership.user_id)
    session = make_session(user)
    exam = make_assessment(context.training, None, assessment_type="menu_final_exam")
    context.assignment.status = "completed"
    context.assignment.started_at = context.assignment.completed_at = now
    db_session.add_all([session, exam])
    await db_session.flush()
    versions = [
        make_assessment_version(
            exam,
            context.training_version,
            None,
            version_number=number,
            question_count=20,
            threshold_percent=70,
            feedback_policy="after_final_submission",
        )
        for number in (1, 2)
    ]
    db_session.add_all(versions)
    await db_session.flush()
    old = make_assessment_attempt(
        context.employee, context.assignment, versions[0], question_count=20
    )
    db_session.add(old)
    db_session.add_all(
        [
            make_assessment_readiness(
                version, required_count=20, status="blocked", eligible_count=0
            )
            for version in versions
        ]
    )
    await db_session.flush()
    db_session.add(make_attempt_device_lease(old, session))
    await db_session.commit()
    resumed = await start_or_resume_final_exam_attempt(
        db_session,
        organization_id=context.training.organization_id,
        location_id=context.training.location_id,
        employee_profile_id=context.employee.id,
        actor_user_id=user.id,
        session_id=session.id,
        presentation_locale="uk",
        idempotency_key="resume-old",
        request_id=uuid4(),
        now=now,
    )
    assert resumed.attempt.id == old.id
    assert resumed.attempt.assessment_version_id == versions[0].id
    assert not resumed.created
