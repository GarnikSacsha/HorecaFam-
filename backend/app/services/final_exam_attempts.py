from datetime import UTC, datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentEligibility,
    AssessmentQuestionPool,
    AssessmentReadiness,
    AssessmentVersion,
    AttemptDeviceLease,
    AttemptOption,
    AttemptQuestion,
    AttemptResult,
    AttentionCaseSource,
    AuditEvent,
    CriticalError,
    EmployeeProfile,
    MenuItemVersion,
    MenuItemVersionAllergen,
    OrganizationMembership,
    QuestionCandidate,
    QuestionGenerationRule,
    QuestionSourceLink,
    QuestionVersion,
    SubmittedAnswer,
    TrainingAssignment,
)
from app.schemas.assessment import (
    FinalExamAttemptOptionResponse,
    FinalExamAttemptQuestionResponse,
    FinalExamAttemptResponse,
    FinalExamAttemptStartResponse,
    FinalExamAttemptTakeoverResponse,
    FinalExamCertificationResponse,
    FinalExamSavedAnswerResponse,
    FinalExamSummaryResponse,
)
from app.services.employee_follow_up import (
    current_employee_requirement,
    employee_attention_summary,
    employee_requirement_response,
)
from app.services.final_exam_readiness import (
    FinalExamPoolCandidate,
    select_final_exam_questions,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.interactive_attempts import (
    ATTEMPT_INACTIVITY,
    _previous_order,
    _require_active_training_participation,
    _snapshot_question,
)


def _error(status_code: int, code: str, message: str) -> APIError:
    return APIError(status_code=status_code, code=code, message=message)


def _not_found() -> APIError:
    return _error(404, "RESOURCE_NOT_FOUND", "Ресурс не знайдено.")


async def _owned_final_exam_attempt(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    attempt_id: UUID,
    lock: bool = False,
) -> AssessmentAttempt:
    query = (
        select(AssessmentAttempt)
        .join(AssessmentVersion, AssessmentVersion.id == AssessmentAttempt.assessment_version_id)
        .join(Assessment, Assessment.id == AssessmentVersion.assessment_id)
        .where(
            AssessmentAttempt.id == attempt_id,
            AssessmentAttempt.organization_id == organization_id,
            AssessmentAttempt.location_id == location_id,
            AssessmentAttempt.employee_profile_id == employee_profile_id,
            Assessment.assessment_type == "menu_final_exam",
        )
    )
    if lock:
        query = query.with_for_update(of=AssessmentAttempt)
    attempt = await db.scalar(query)
    if attempt is None:
        raise _not_found()
    return attempt


async def _attempt_response(
    db: AsyncSession,
    attempt: AssessmentAttempt,
    *,
    session_id: UUID,
) -> FinalExamAttemptResponse:
    lease = await db.scalar(
        select(AttemptDeviceLease).where(AttemptDeviceLease.attempt_id == attempt.id)
    )
    if lease is None:
        raise RuntimeError("Final Exam attempt device lease is unavailable")
    question_rows = list(
        await db.scalars(
            select(AttemptQuestion)
            .where(AttemptQuestion.attempt_id == attempt.id)
            .order_by(AttemptQuestion.position)
        )
    )
    questions: list[FinalExamAttemptQuestionResponse] = []
    answered_count = 0
    for question in question_rows:
        options = list(
            await db.scalars(
                select(AttemptOption)
                .where(AttemptOption.attempt_question_id == question.id)
                .order_by(AttemptOption.position)
            )
        )
        saved = await db.scalar(
            select(SubmittedAnswer).where(
                SubmittedAnswer.attempt_id == attempt.id,
                SubmittedAnswer.attempt_question_id == question.id,
            )
        )
        saved_response = None
        if saved is not None:
            answered_count += 1
            saved_response = FinalExamSavedAnswerResponse(
                id=saved.id,
                answer_payload=saved.answer_payload,
                submitted_at=saved.submitted_at,
            )
        questions.append(
            FinalExamAttemptQuestionResponse(
                id=question.id,
                position=question.position,
                mechanic=question.mechanic,
                prompt_payload=question.prompt_payload,
                coverage_key=question.coverage_key,
                options=[
                    FinalExamAttemptOptionResponse(
                        id=option.id,
                        position=option.position,
                        payload=option.payload,
                    )
                    for option in options
                ],
                saved_answer=saved_response,
            )
        )
    return FinalExamAttemptResponse(
        id=attempt.id,
        assignment_id=attempt.assignment_id,
        assessment_version_id=attempt.assessment_version_id,
        status=cast(Literal["in_progress", "completed", "expired", "invalidated"], attempt.status),
        presentation_locale=cast(Literal["uk", "en"], attempt.presentation_locale),
        started_at=attempt.started_at,
        last_activity_at=attempt.last_activity_at,
        expires_at=attempt.expires_at,
        lease_generation=lease.generation,
        writable=attempt.status == "in_progress" and lease.session_id == session_id,
        answered_count=answered_count,
        questions=questions,
    )


async def get_final_exam_attempt(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    attempt_id: UUID,
    session_id: UUID,
) -> FinalExamAttemptResponse:
    attempt = await _owned_final_exam_attempt(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        attempt_id=attempt_id,
    )
    return await _attempt_response(db, attempt, session_id=session_id)


async def _current_assignment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    lock: bool = False,
) -> TrainingAssignment | None:
    query = select(TrainingAssignment).where(
        TrainingAssignment.organization_id == organization_id,
        TrainingAssignment.location_id == location_id,
        TrainingAssignment.employee_profile_id == employee_profile_id,
        TrainingAssignment.status != "revoked",
    )
    if lock:
        query = query.with_for_update()
    return cast(TrainingAssignment | None, await db.scalar(query))


async def _ready_version(
    db: AsyncSession,
    assignment: TrainingAssignment,
) -> tuple[Assessment, AssessmentVersion, AssessmentReadiness] | None:
    row = (
        await db.execute(
            select(Assessment, AssessmentVersion, AssessmentReadiness)
            .join(AssessmentVersion, AssessmentVersion.assessment_id == Assessment.id)
            .join(
                AssessmentReadiness,
                AssessmentReadiness.assessment_version_id == AssessmentVersion.id,
            )
            .where(
                Assessment.training_id == assignment.training_id,
                Assessment.assessment_type == "menu_final_exam",
                AssessmentVersion.training_version_id == assignment.training_version_id,
                AssessmentVersion.status == "published",
            )
        )
    ).first()
    return None if row is None else row._tuple()


async def _certification(
    db: AsyncSession,
    *,
    employee_profile_id: UUID,
    training_id: UUID,
) -> FinalExamCertificationResponse | None:
    row = (
        await db.execute(
            select(AttemptResult, AssessmentAttempt)
            .join(AssessmentAttempt, AssessmentAttempt.id == AttemptResult.attempt_id)
            .join(
                AssessmentVersion, AssessmentVersion.id == AssessmentAttempt.assessment_version_id
            )
            .join(Assessment, Assessment.id == AssessmentVersion.assessment_id)
            .where(
                AssessmentAttempt.employee_profile_id == employee_profile_id,
                AssessmentAttempt.training_id == training_id,
                Assessment.assessment_type == "menu_final_exam",
                AttemptResult.pass_status == "passed",
            )
            .order_by(AttemptResult.completed_at, AttemptResult.id)
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    result, attempt = row._tuple()
    return FinalExamCertificationResponse(
        result_id=result.id,
        attempt_id=attempt.id,
        certified_at=result.completed_at,
    )


async def get_final_exam_summary(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    session_id: UUID,
    now: datetime | None = None,
) -> FinalExamSummaryResponse:
    effective_now = now or datetime.now(UTC)
    participation = await db.scalar(
        select(OrganizationMembership.training_participation_status)
        .join(EmployeeProfile, EmployeeProfile.membership_id == OrganizationMembership.id)
        .where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == "active",
            EmployeeProfile.id == employee_profile_id,
            EmployeeProfile.location_id == location_id,
        )
    )
    assignment = await _current_assignment(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
    )
    if participation is None or assignment is None:
        return FinalExamSummaryResponse(
            availability="no_assignment",
            can_start=False,
            reason_codes=["ASSIGNMENT_UNAVAILABLE"],
            readiness_status=None,
            active_attempt=None,
            certification=None,
            attention_summary=await employee_attention_summary(
                db,
                organization_id=organization_id,
                employee_profile_id=employee_profile_id,
            ),
        )
    ready = await _ready_version(db, assignment)
    certification = await _certification(
        db,
        employee_profile_id=employee_profile_id,
        training_id=assignment.training_id,
    )
    active_attempt = None
    if ready is not None:
        active = await db.scalar(
            select(AssessmentAttempt).where(
                AssessmentAttempt.employee_profile_id == employee_profile_id,
                AssessmentAttempt.assignment_id == assignment.id,
                AssessmentAttempt.assessment_version_id == ready[1].id,
                AssessmentAttempt.status == "in_progress",
            )
        )
        if active is not None:
            active_attempt = await _attempt_response(db, active, session_id=session_id)
    readiness_status = (
        cast(Literal["processing", "ready", "warning", "blocked"], ready[2].status)
        if ready is not None
        else None
    )
    current_requirement = await current_employee_requirement(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        training_id=assignment.training_id,
        target_assessment_id=ready[0].id if ready is not None else None,
    )
    if active_attempt is not None:
        availability = "in_progress"
        reasons = []
    elif participation == "paused":
        availability = "paused"
        reasons = ["TRAINING_PAUSED"]
    elif certification is not None and current_requirement is not None:
        if ready is None or ready[2].status not in {"ready", "warning"}:
            availability = "preparing"
            reasons = ["RETAKE_TARGET_UNAVAILABLE"]
        else:
            availability = "eligible"
            reasons = ["AUTHORIZED_RETAKE"]
    elif certification is not None:
        availability = "certified"
        reasons = ["FINAL_EXAM_ALREADY_PASSED"]
    elif assignment.status != "completed":
        availability = "training_incomplete"
        reasons = ["TRAINING_INCOMPLETE"]
    elif ready is None:
        availability = "preparing"
        reasons = ["ASSESSMENT_NOT_READY"]
    else:
        eligibility = await db.scalar(
            select(AssessmentEligibility).where(
                AssessmentEligibility.employee_profile_id == employee_profile_id,
                AssessmentEligibility.assignment_id == assignment.id,
                AssessmentEligibility.target_assessment_id == ready[0].id,
                AssessmentEligibility.status == "earned",
            )
        )
        if eligibility is None:
            availability = "practice_required"
            reasons = ["PRACTICE_ELIGIBILITY_REQUIRED"]
        elif ready[2].status not in {"ready", "warning"}:
            availability = "preparing"
            reasons = ["ASSESSMENT_NOT_READY"]
        else:
            availability = "eligible"
            reasons = []
    latest_pass_status = await db.scalar(
        select(AttemptResult.pass_status)
        .join(AssessmentAttempt, AssessmentAttempt.id == AttemptResult.attempt_id)
        .join(AssessmentVersion, AssessmentVersion.id == AssessmentAttempt.assessment_version_id)
        .join(Assessment, Assessment.id == AssessmentVersion.assessment_id)
        .where(
            AssessmentAttempt.employee_profile_id == employee_profile_id,
            AssessmentAttempt.training_id == assignment.training_id,
            Assessment.assessment_type == "menu_final_exam",
        )
        .order_by(AttemptResult.completed_at.desc(), AttemptResult.id.desc())
        .limit(1)
    )
    return FinalExamSummaryResponse(
        availability=cast(
            Literal[
                "no_assignment",
                "training_incomplete",
                "practice_required",
                "preparing",
                "eligible",
                "in_progress",
                "paused",
                "certified",
            ],
            availability,
        ),
        can_start=availability == "eligible",
        reason_codes=reasons,
        readiness_status=readiness_status,
        active_attempt=active_attempt,
        certification=certification,
        retake_available=current_requirement is not None
        or (certification is None and latest_pass_status == "failed"),
        current_retake_requirement=(
            await employee_requirement_response(
                db,
                current_requirement,
                now=effective_now,
            )
            if current_requirement is not None
            else None
        ),
        attention_summary=await employee_attention_summary(
            db,
            organization_id=organization_id,
            employee_profile_id=employee_profile_id,
            training_id=assignment.training_id,
        ),
    )


async def start_or_resume_final_exam_attempt(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    actor_user_id: UUID,
    session_id: UUID,
    presentation_locale: str,
    idempotency_key: str,
    request_id: UUID,
    now: datetime,
) -> FinalExamAttemptStartResponse:
    await _require_active_training_participation(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
    )
    fingerprint = request_fingerprint({"presentation_locale": presentation_locale})
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="final_exam_attempt_start",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay is not None:
        replay_attempt = await _owned_final_exam_attempt(
            db,
            organization_id=organization_id,
            location_id=location_id,
            employee_profile_id=employee_profile_id,
            attempt_id=replay.resource_id,
        )
        return FinalExamAttemptStartResponse(
            attempt=await _attempt_response(db, replay_attempt, session_id=session_id),
            created=False,
            replayed=True,
        )
    assignment = await _current_assignment(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        lock=True,
    )
    if assignment is None:
        raise _not_found()
    if assignment.status != "completed":
        raise _error(409, "TRAINING_INCOMPLETE", "Спочатку завершіть навчання.")
    ready = await _ready_version(db, assignment)
    if ready is None or ready[2].status not in {"ready", "warning"}:
        raise _error(409, "ASSESSMENT_NOT_READY", "Фінальний іспит ще готується.")
    certification = await _certification(
        db,
        employee_profile_id=employee_profile_id,
        training_id=assignment.training_id,
    )
    authorized_requirement = await current_employee_requirement(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        training_id=assignment.training_id,
        target_assessment_id=ready[0].id,
    )
    if certification is not None and authorized_requirement is None:
        raise _error(
            409,
            "FINAL_EXAM_ALREADY_PASSED",
            "Фінальний іспит уже складено; нову спробу має дозволити активна вимога.",
        )
    if certification is None:
        eligibility = await db.scalar(
            select(AssessmentEligibility).where(
                AssessmentEligibility.employee_profile_id == employee_profile_id,
                AssessmentEligibility.assignment_id == assignment.id,
                AssessmentEligibility.target_assessment_id == ready[0].id,
                AssessmentEligibility.status == "earned",
            )
        )
        if eligibility is None:
            raise _error(409, "PRACTICE_ELIGIBILITY_REQUIRED", "Спочатку пройдіть Practice.")
    version = ready[1]
    attempt = await db.scalar(
        select(AssessmentAttempt).where(
            AssessmentAttempt.employee_profile_id == employee_profile_id,
            AssessmentAttempt.assignment_id == assignment.id,
            AssessmentAttempt.assessment_version_id == version.id,
            AssessmentAttempt.status == "in_progress",
        )
    )
    created = False
    if attempt is not None and now >= attempt.expires_at:
        attempt.status = "expired"
        attempt.invalidation_code = "INACTIVITY_TIMEOUT"
        await db.flush()
        attempt = None
    if attempt is None:
        rows = list(
            (
                await db.execute(
                    select(
                        AssessmentQuestionPool,
                        QuestionVersion,
                        MenuItemVersion.menu_item_id,
                        MenuItemVersion.menu_version_category_id,
                        QuestionGenerationRule.code,
                    )
                    .join(
                        QuestionVersion,
                        QuestionVersion.id == AssessmentQuestionPool.question_version_id,
                    )
                    .join(QuestionCandidate, QuestionCandidate.id == QuestionVersion.candidate_id)
                    .join(
                        QuestionGenerationRule,
                        QuestionGenerationRule.id == QuestionCandidate.generation_rule_id,
                    )
                    .join(
                        QuestionSourceLink,
                        (QuestionSourceLink.question_version_id == QuestionVersion.id)
                        & (QuestionSourceLink.source_role == "explanation_source"),
                    )
                    .join(
                        MenuItemVersion,
                        MenuItemVersion.id == QuestionSourceLink.menu_item_version_id,
                    )
                    .where(
                        AssessmentQuestionPool.assessment_version_id == version.id,
                        AssessmentQuestionPool.eligible.is_(True),
                        QuestionVersion.status == "published",
                    )
                )
            ).all()
        )
        by_id = {
            question.id: (pool, question, menu_item_id, category_id, family)
            for pool, question, menu_item_id, category_id, family in rows
        }
        selected = select_final_exam_questions(
            [
                FinalExamPoolCandidate(
                    question_version_id=question.id,
                    menu_item_key=str(menu_item_id),
                    section_key=str(category_id),
                    family=family,
                    mechanic=question.mechanic,
                    is_critical=question.is_critical,
                )
                for _pool, question, menu_item_id, category_id, family in by_id.values()
            ],
            previous_question_ids=await _previous_order(
                db,
                employee_profile_id=employee_profile_id,
                assessment_version_id=version.id,
            ),
        )
        if authorized_requirement is not None and authorized_requirement.reason == "critical_error":
            source_identity = (
                await db.execute(
                    select(CriticalError.menu_item_id, CriticalError.allergen_id)
                    .join(
                        AttentionCaseSource,
                        AttentionCaseSource.critical_error_id == CriticalError.id,
                    )
                    .where(
                        AttentionCaseSource.attention_case_id
                        == authorized_requirement.source_attention_case_id
                    )
                    .order_by(CriticalError.occurred_at.desc(), CriticalError.id.desc())
                    .limit(1)
                )
            ).one_or_none()
            if source_identity is None:
                raise _error(
                    409,
                    "RETAKE_TARGET_UNAVAILABLE",
                    "Для цільової перескладання немає безпечного актуального питання.",
                )
            menu_item_id, allergen_id = source_identity
            matching_ids = set(
                await db.scalars(
                    select(QuestionSourceLink.question_version_id)
                    .join(
                        MenuItemVersionAllergen,
                        MenuItemVersionAllergen.id
                        == QuestionSourceLink.menu_item_version_allergen_id,
                    )
                    .join(
                        MenuItemVersion,
                        MenuItemVersion.id == MenuItemVersionAllergen.menu_item_version_id,
                    )
                    .where(
                        QuestionSourceLink.question_version_id.in_(by_id),
                        QuestionSourceLink.source_role == "correct_fact",
                        MenuItemVersion.menu_item_id == menu_item_id,
                        MenuItemVersionAllergen.allergen_id == allergen_id,
                    )
                )
            )
            matching_candidates = [candidate for candidate in by_id if candidate in matching_ids]
            if not matching_candidates:
                raise _error(
                    409,
                    "RETAKE_TARGET_UNAVAILABLE",
                    "Для цільової перескладання немає безпечного актуального питання.",
                )
            if not any(item.question_version_id in matching_ids for item in selected):
                replacement_id = min(matching_candidates, key=str)
                replacement = next(
                    FinalExamPoolCandidate(
                        question_version_id=question.id,
                        menu_item_key=str(candidate_menu_item_id),
                        section_key=str(category_id),
                        family=family,
                        mechanic=question.mechanic,
                        is_critical=question.is_critical,
                    )
                    for (
                        _pool,
                        question,
                        candidate_menu_item_id,
                        category_id,
                        family,
                    ) in by_id.values()
                    if question.id == replacement_id
                )
                selected[-1] = replacement
        if len(selected) != 20:
            raise _error(409, "ASSESSMENT_NOT_READY", "Фінальний іспит ще готується.")
        attempt = AssessmentAttempt(
            organization_id=organization_id,
            location_id=location_id,
            training_id=assignment.training_id,
            employee_profile_id=employee_profile_id,
            assignment_id=assignment.id,
            assessment_version_id=version.id,
            status="in_progress",
            presentation_locale=presentation_locale,
            question_count=20,
            snapshot_schema_version=1,
            started_at=now,
            last_activity_at=now,
            expires_at=now + ATTEMPT_INACTIVITY,
        )
        db.add(attempt)
        await db.flush()
        for position, selected_row in enumerate(selected):
            pool, question, _menu_item_id, _category_id, _family = by_id[
                selected_row.question_version_id
            ]
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
                action="final_exam_attempt_started",
                target_type="assessment_attempt",
                target_id=attempt.id,
                old_values=None,
                new_values={"assessment_version_id": str(version.id), "question_count": 20},
                request_id=request_id,
                outcome="success",
            )
        )
        created = True
    await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="final_exam_attempt_start",
        key=idempotency_key,
        fingerprint=fingerprint,
        resource_type="assessment_attempt",
        resource_id=attempt.id,
        response_status=200,
        now=now,
    )
    await db.commit()
    return FinalExamAttemptStartResponse(
        attempt=await _attempt_response(db, attempt, session_id=session_id),
        created=created,
        replayed=False,
    )


async def takeover_final_exam_attempt(
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
) -> FinalExamAttemptTakeoverResponse:
    await _require_active_training_participation(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
    )
    fingerprint = request_fingerprint({"attempt_id": str(attempt_id)})
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="final_exam_attempt_takeover",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    attempt = await _owned_final_exam_attempt(
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
        raise RuntimeError("Final Exam attempt device lease is unavailable")
    if replay is not None:
        return FinalExamAttemptTakeoverResponse(
            attempt_id=attempt.id, lease_generation=lease.generation, replayed=True
        )
    if attempt.status != "in_progress":
        raise _error(409, "ATTEMPT_ALREADY_COMPLETED", "Спробу вже завершено.")
    if now >= attempt.expires_at:
        raise _error(409, "ATTEMPT_EXPIRED", "Час активності спроби вичерпано.")
    lease.session_id = session_id
    lease.generation += 1
    lease.acquired_at = now
    lease.last_seen_at = now
    attempt.last_activity_at = now
    attempt.expires_at = now + ATTEMPT_INACTIVITY
    await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="final_exam_attempt_takeover",
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
            action="final_exam_attempt_taken_over",
            target_type="assessment_attempt",
            target_id=attempt.id,
            old_values=None,
            new_values={"lease_generation": lease.generation},
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return FinalExamAttemptTakeoverResponse(
        attempt_id=attempt.id,
        lease_generation=lease.generation,
        replayed=False,
    )
