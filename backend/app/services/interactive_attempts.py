from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    AssessmentAttempt,
    AssessmentQuestionPool,
    AssessmentReadiness,
    AssessmentVersion,
    AttemptDeviceLease,
    AttemptOption,
    AttemptQuestion,
    AuditEvent,
    LessonCompletion,
    LessonVersion,
    QuestionCandidate,
    QuestionOption,
    QuestionOptionTranslation,
    QuestionSourceLink,
    QuestionVersion,
    QuestionVersionTranslation,
    SubmittedAnswer,
    TrainingAssignment,
    TrainingModuleVersion,
)
from app.schemas.assessment import (
    InteractiveAttemptOptionResponse,
    InteractiveAttemptQuestionResponse,
    InteractiveAttemptResponse,
    InteractiveAttemptStartResponse,
    InteractiveAttemptTakeoverResponse,
    InteractiveConfirmedAnswerResponse,
    InteractiveFeedbackResponse,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)

ATTEMPT_INACTIVITY = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class PoolCandidate:
    question_version_id: UUID
    coverage_key: str
    mechanic: str


def _ordered_selection(candidates: list[PoolCandidate], offset: int) -> list[PoolCandidate]:
    ordered = sorted(
        candidates,
        key=lambda row: (row.coverage_key, row.mechanic, str(row.question_version_id)),
    )
    if ordered:
        offset %= len(ordered)
        ordered = ordered[offset:] + ordered[:offset]
    selected: list[PoolCandidate] = []
    used_coverage: set[str] = set()
    for row in ordered:
        if row.coverage_key in used_coverage:
            continue
        selected.append(row)
        used_coverage.add(row.coverage_key)
        if len(selected) == 5:
            return selected
    for row in ordered:
        if row in selected:
            continue
        selected.append(row)
        if len(selected) == 5:
            return selected
    return selected


def select_attempt_questions(
    candidates: list[PoolCandidate],
    *,
    previous_order: list[UUID],
) -> list[PoolCandidate]:
    distinct = {row.question_version_id for row in candidates}
    if len(distinct) < 5:
        return []
    selected = _ordered_selection(candidates, 0)
    if len(candidates) > 5 and [row.question_version_id for row in selected] == previous_order:
        for offset in range(1, len(candidates)):
            rotated = _ordered_selection(candidates, offset)
            if [row.question_version_id for row in rotated] != previous_order:
                return rotated
    return selected


def _error(status_code: int, code: str, message: str) -> APIError:
    return APIError(status_code=status_code, code=code, message=message)


def _not_found() -> APIError:
    return _error(404, "RESOURCE_NOT_FOUND", "Ресурс не знайдено.")


def _unavailable() -> APIError:
    return _error(
        409,
        "INTERACTIVE_TRAINING_UNAVAILABLE",
        "Інтерактивне тренування зараз недоступне.",
    )


def _not_ready() -> APIError:
    return _error(409, "ASSESSMENT_NOT_READY", "Питання для тренування ще готуються.")


async def _owned_attempt(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    attempt_id: UUID,
    lock: bool = False,
) -> AssessmentAttempt:
    query = select(AssessmentAttempt).where(
        AssessmentAttempt.id == attempt_id,
        AssessmentAttempt.organization_id == organization_id,
        AssessmentAttempt.location_id == location_id,
        AssessmentAttempt.employee_profile_id == employee_profile_id,
    )
    if lock:
        query = query.with_for_update()
    attempt = await db.scalar(query)
    if attempt is None:
        raise _not_found()
    return attempt


async def _attempt_response(
    db: AsyncSession,
    attempt: AssessmentAttempt,
    *,
    session_id: UUID,
) -> InteractiveAttemptResponse:
    assessment_version = await db.get(AssessmentVersion, attempt.assessment_version_id)
    if assessment_version is None:
        raise RuntimeError("Attempt assessment version is unavailable")
    lease = await db.scalar(
        select(AttemptDeviceLease).where(AttemptDeviceLease.attempt_id == attempt.id)
    )
    if lease is None:
        raise RuntimeError("Attempt device lease is unavailable")
    question_rows = list(
        await db.scalars(
            select(AttemptQuestion)
            .where(AttemptQuestion.attempt_id == attempt.id)
            .order_by(AttemptQuestion.position)
        )
    )
    answer_ids = set(
        await db.scalars(
            select(SubmittedAnswer.attempt_question_id).where(
                SubmittedAnswer.attempt_id == attempt.id
            )
        )
    )
    questions: list[InteractiveAttemptQuestionResponse] = []
    for question in question_rows:
        options = list(
            await db.scalars(
                select(AttemptOption)
                .where(AttemptOption.attempt_question_id == question.id)
                .order_by(AttemptOption.position)
            )
        )
        confirmed_answer = await db.scalar(
            select(SubmittedAnswer).where(
                SubmittedAnswer.attempt_id == attempt.id,
                SubmittedAnswer.attempt_question_id == question.id,
            )
        )
        confirmed_response = None
        feedback = None
        if confirmed_answer is not None:
            confirmed_response = InteractiveConfirmedAnswerResponse(
                id=confirmed_answer.id,
                answer_payload=confirmed_answer.answer_payload,
                is_correct=confirmed_answer.is_correct,
                submitted_at=confirmed_answer.submitted_at,
            )
            feedback = InteractiveFeedbackResponse(
                is_correct=confirmed_answer.is_correct,
                correct_option_ids=sorted(
                    (option.id for option in options if option.is_correct), key=str
                ),
                explanation_payload=question.explanation_payload,
            )
        questions.append(
            InteractiveAttemptQuestionResponse(
                id=question.id,
                position=question.position,
                mechanic=question.mechanic,
                prompt_payload=question.prompt_payload,
                options=[
                    InteractiveAttemptOptionResponse(
                        id=option.id,
                        position=option.position,
                        payload=option.payload,
                    )
                    for option in options
                ],
                answered=question.id in answer_ids,
                confirmed_answer=confirmed_response,
                feedback=feedback,
            )
        )
    return InteractiveAttemptResponse(
        id=attempt.id,
        lesson_id=assessment_version.lesson_id,
        lesson_version_id=assessment_version.lesson_version_id,
        assessment_version_id=assessment_version.id,
        status=attempt.status,
        presentation_locale=attempt.presentation_locale,
        started_at=attempt.started_at,
        expires_at=attempt.expires_at,
        lease_generation=lease.generation,
        writable=lease.session_id == session_id,
        questions=questions,
    )


async def get_interactive_attempt(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    attempt_id: UUID,
    session_id: UUID,
) -> InteractiveAttemptResponse:
    attempt = await _owned_attempt(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        attempt_id=attempt_id,
    )
    return await _attempt_response(db, attempt, session_id=session_id)


async def _assignment_lesson(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    lesson_id: UUID,
) -> tuple[TrainingAssignment, LessonVersion]:
    row = (
        await db.execute(
            select(TrainingAssignment, LessonVersion)
            .join(
                TrainingModuleVersion,
                TrainingModuleVersion.training_version_id == TrainingAssignment.training_version_id,
            )
            .join(
                LessonVersion,
                LessonVersion.training_module_version_id == TrainingModuleVersion.id,
            )
            .where(
                TrainingAssignment.organization_id == organization_id,
                TrainingAssignment.location_id == location_id,
                TrainingAssignment.employee_profile_id == employee_profile_id,
                TrainingAssignment.status == "assigned",
                LessonVersion.lesson_id == lesson_id,
            )
            .with_for_update(of=TrainingAssignment)
        )
    ).first()
    if row is None:
        raise _not_found()
    return row._tuple()


async def _assessment_ready(
    db: AsyncSession,
    *,
    assignment: TrainingAssignment,
    lesson_version: LessonVersion,
) -> tuple[AssessmentVersion, AssessmentReadiness]:
    completion = await db.scalar(
        select(LessonCompletion).where(
            LessonCompletion.assignment_id == assignment.id,
            LessonCompletion.lesson_version_id == lesson_version.id,
        )
    )
    if completion is None:
        raise _unavailable()
    row = (
        await db.execute(
            select(AssessmentVersion, AssessmentReadiness)
            .join(
                AssessmentReadiness,
                AssessmentReadiness.assessment_version_id == AssessmentVersion.id,
            )
            .where(
                AssessmentVersion.training_version_id == assignment.training_version_id,
                AssessmentVersion.lesson_version_id == lesson_version.id,
                AssessmentVersion.status == "published",
            )
        )
    ).first()
    if row is None or row[1].status not in {"ready", "warning"}:
        raise _not_ready()
    return row._tuple()


async def _previous_order(
    db: AsyncSession,
    *,
    employee_profile_id: UUID,
    assessment_version_id: UUID,
) -> list[UUID]:
    previous = await db.scalar(
        select(AssessmentAttempt)
        .where(
            AssessmentAttempt.employee_profile_id == employee_profile_id,
            AssessmentAttempt.assessment_version_id == assessment_version_id,
            AssessmentAttempt.status == "completed",
        )
        .order_by(AssessmentAttempt.completed_at.desc())
        .limit(1)
    )
    if previous is None:
        return []
    return list(
        await db.scalars(
            select(AttemptQuestion.question_version_id)
            .where(AttemptQuestion.attempt_id == previous.id)
            .order_by(AttemptQuestion.position)
        )
    )


async def _snapshot_question(
    db: AsyncSession,
    *,
    attempt: AssessmentAttempt,
    pool: AssessmentQuestionPool,
    question_version: QuestionVersion,
    position: int,
) -> None:
    translation = await db.scalar(
        select(QuestionVersionTranslation).where(
            QuestionVersionTranslation.question_version_id == question_version.id,
            QuestionVersionTranslation.locale == attempt.presentation_locale,
        )
    )
    if translation is None and attempt.presentation_locale != "uk":
        translation = await db.scalar(
            select(QuestionVersionTranslation).where(
                QuestionVersionTranslation.question_version_id == question_version.id,
                QuestionVersionTranslation.locale == "uk",
            )
        )
    source_rows = list(
        await db.scalars(
            select(QuestionSourceLink).where(
                QuestionSourceLink.question_version_id == question_version.id
            )
        )
    )
    candidate = await db.get(QuestionCandidate, question_version.candidate_id)
    attempt_question = AttemptQuestion(
        attempt_id=attempt.id,
        question_version_id=question_version.id,
        position=position,
        mechanic=question_version.mechanic,
        prompt_payload=(
            translation.prompt_payload
            if translation is not None
            else question_version.prompt_payload
        ),
        grading_payload=question_version.grading_payload,
        explanation_payload=(
            translation.explanation_payload
            if translation is not None
            else question_version.explanation_payload
        ),
        is_critical=question_version.is_critical,
        coverage_key=pool.coverage_key,
        presentation_locale=attempt.presentation_locale,
        provenance_snapshot={
            "source_fingerprint": question_version.source_fingerprint,
            "sources": [
                {
                    "role": source.source_role,
                    "menu_item_version_id": (
                        str(source.menu_item_version_id)
                        if source.menu_item_version_id is not None
                        else None
                    ),
                    "menu_item_version_component_id": (
                        str(source.menu_item_version_component_id)
                        if source.menu_item_version_component_id is not None
                        else None
                    ),
                    "menu_item_version_allergen_id": (
                        str(source.menu_item_version_allergen_id)
                        if source.menu_item_version_allergen_id is not None
                        else None
                    ),
                }
                for source in source_rows
            ],
        },
        version_snapshot={
            "assessment_version_id": str(attempt.assessment_version_id),
            "question_version_id": str(question_version.id),
            "candidate_id": str(question_version.candidate_id),
            "generation_rule_id": (
                str(candidate.generation_rule_id) if candidate is not None else None
            ),
        },
    )
    db.add(attempt_question)
    await db.flush()
    options = list(
        await db.scalars(
            select(QuestionOption)
            .where(QuestionOption.question_version_id == question_version.id)
            .order_by(QuestionOption.position)
        )
    )
    for option in options:
        option_translation = await db.scalar(
            select(QuestionOptionTranslation).where(
                QuestionOptionTranslation.question_option_id == option.id,
                QuestionOptionTranslation.locale == attempt.presentation_locale,
            )
        )
        if option_translation is None and attempt.presentation_locale != "uk":
            option_translation = await db.scalar(
                select(QuestionOptionTranslation).where(
                    QuestionOptionTranslation.question_option_id == option.id,
                    QuestionOptionTranslation.locale == "uk",
                )
            )
        db.add(
            AttemptOption(
                attempt_question_id=attempt_question.id,
                source_option_id=option.id,
                position=option.position,
                payload=(
                    option_translation.payload if option_translation is not None else option.payload
                ),
                is_correct=option.is_correct,
            )
        )


async def start_or_resume_interactive_attempt(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    actor_user_id: UUID,
    session_id: UUID,
    lesson_id: UUID,
    presentation_locale: str,
    idempotency_key: str,
    request_id: UUID,
    now: datetime,
) -> InteractiveAttemptStartResponse:
    fingerprint = request_fingerprint(
        {"lesson_id": str(lesson_id), "presentation_locale": presentation_locale}
    )
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="interactive_attempt_start",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay is not None:
        replay_attempt = await _owned_attempt(
            db,
            organization_id=organization_id,
            location_id=location_id,
            employee_profile_id=employee_profile_id,
            attempt_id=replay.resource_id,
        )
        return InteractiveAttemptStartResponse(
            attempt=await _attempt_response(db, replay_attempt, session_id=session_id),
            created=False,
            replayed=True,
        )
    assignment, lesson_version = await _assignment_lesson(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        lesson_id=lesson_id,
    )
    assessment_version, _readiness = await _assessment_ready(
        db,
        assignment=assignment,
        lesson_version=lesson_version,
    )
    attempt = await db.scalar(
        select(AssessmentAttempt).where(
            AssessmentAttempt.employee_profile_id == employee_profile_id,
            AssessmentAttempt.assignment_id == assignment.id,
            AssessmentAttempt.assessment_version_id == assessment_version.id,
            AssessmentAttempt.status == "in_progress",
        )
    )
    created = False
    if attempt is None:
        pool_rows = list(
            (
                await db.execute(
                    select(AssessmentQuestionPool, QuestionVersion)
                    .join(
                        QuestionVersion,
                        QuestionVersion.id == AssessmentQuestionPool.question_version_id,
                    )
                    .where(
                        AssessmentQuestionPool.assessment_version_id == assessment_version.id,
                        AssessmentQuestionPool.eligible.is_(True),
                        QuestionVersion.status == "published",
                    )
                )
            ).all()
        )
        selected = select_attempt_questions(
            [
                PoolCandidate(
                    question_version_id=question.id,
                    coverage_key=pool.coverage_key,
                    mechanic=pool.mechanic,
                )
                for pool, question in pool_rows
            ],
            previous_order=await _previous_order(
                db,
                employee_profile_id=employee_profile_id,
                assessment_version_id=assessment_version.id,
            ),
        )
        if len(selected) != 5:
            raise _not_ready()
        row_by_id = {question.id: (pool, question) for pool, question in pool_rows}
        attempt = AssessmentAttempt(
            organization_id=organization_id,
            location_id=location_id,
            training_id=assignment.training_id,
            employee_profile_id=employee_profile_id,
            assignment_id=assignment.id,
            assessment_version_id=assessment_version.id,
            status="in_progress",
            presentation_locale=presentation_locale,
            question_count=5,
            snapshot_schema_version=1,
            started_at=now,
            last_activity_at=now,
            expires_at=now + ATTEMPT_INACTIVITY,
        )
        db.add(attempt)
        await db.flush()
        for position, selected_row in enumerate(selected):
            pool, question = row_by_id[selected_row.question_version_id]
            await _snapshot_question(
                db,
                attempt=attempt,
                pool=pool,
                question_version=question,
                position=position,
            )
        db.add(
            AttemptDeviceLease(
                attempt_id=attempt.id,
                session_id=session_id,
                generation=1,
                acquired_at=now,
                last_seen_at=now,
            )
        )
        db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_type="user",
                action="interactive_attempt_started",
                target_type="assessment_attempt",
                target_id=attempt.id,
                old_values=None,
                new_values={
                    "assessment_version_id": str(assessment_version.id),
                    "question_count": 5,
                    "presentation_locale": presentation_locale,
                },
                request_id=request_id,
                outcome="success",
            )
        )
        created = True
    await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="interactive_attempt_start",
        key=idempotency_key,
        fingerprint=fingerprint,
        resource_type="assessment_attempt",
        resource_id=attempt.id,
        response_status=200,
        now=now,
    )
    await db.commit()
    return InteractiveAttemptStartResponse(
        attempt=await _attempt_response(db, attempt, session_id=session_id),
        created=created,
        replayed=False,
    )


async def takeover_interactive_attempt(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    actor_user_id: UUID,
    session_id: UUID,
    attempt_id: UUID,
    idempotency_key: str,
    request_id: UUID,
    now: datetime,
) -> InteractiveAttemptTakeoverResponse:
    fingerprint = request_fingerprint({"attempt_id": str(attempt_id)})
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="interactive_attempt_takeover",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    attempt = await _owned_attempt(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        attempt_id=attempt_id,
        lock=replay is None,
    )
    lease = await db.scalar(
        select(AttemptDeviceLease)
        .where(AttemptDeviceLease.attempt_id == attempt.id)
        .with_for_update()
    )
    if lease is None:
        raise RuntimeError("Attempt device lease is unavailable")
    if replay is not None:
        return InteractiveAttemptTakeoverResponse(
            attempt_id=attempt.id,
            lease_generation=lease.generation,
            replayed=True,
        )
    if attempt.status != "in_progress":
        raise _error(409, "ATTEMPT_ALREADY_COMPLETED", "Спробу вже завершено.")
    lease.session_id = session_id
    lease.generation += 1
    lease.acquired_at = now
    lease.last_seen_at = now
    attempt.last_activity_at = now
    await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="interactive_attempt_takeover",
        key=idempotency_key,
        fingerprint=fingerprint,
        resource_type="assessment_attempt",
        resource_id=attempt.id,
        response_status=200,
        now=now,
    )
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="interactive_attempt_taken_over",
            target_type="assessment_attempt",
            target_id=attempt.id,
            old_values=None,
            new_values={"lease_generation": lease.generation},
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return InteractiveAttemptTakeoverResponse(
        attempt_id=attempt.id,
        lease_generation=lease.generation,
        replayed=False,
    )
