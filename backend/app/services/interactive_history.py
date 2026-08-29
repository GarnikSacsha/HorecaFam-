from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    AssessmentAttempt,
    AssessmentQuestionPool,
    AssessmentReadiness,
    AssessmentVersion,
    AttemptResult,
    EmployeeProfile,
    LessonCompletion,
    LessonVersion,
    OrganizationMembership,
    QuestionVersion,
    TrainingAssignment,
    TrainingModuleVersion,
)
from app.schemas.assessment import (
    InteractiveResultSummaryResponse,
    LessonInteractiveTrainingSummaryResponse,
)
from app.services.interactive_attempts import get_interactive_attempt

HISTORY_LIMIT = 20


def _not_found() -> APIError:
    return APIError(status_code=404, code="RESOURCE_NOT_FOUND", message="Ресурс не знайдено.")


async def _current_scope(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    lesson_id: UUID,
) -> tuple[str, TrainingAssignment, LessonVersion]:
    participation = await db.scalar(
        select(OrganizationMembership.training_participation_status)
        .join(
            EmployeeProfile,
            EmployeeProfile.membership_id == OrganizationMembership.id,
        )
        .where(
            EmployeeProfile.id == employee_profile_id,
            EmployeeProfile.organization_id == organization_id,
            EmployeeProfile.location_id == location_id,
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == "active",
        )
    )
    if participation is None:
        raise _not_found()
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
                TrainingAssignment.status != "revoked",
                LessonVersion.lesson_id == lesson_id,
            )
            .order_by(TrainingAssignment.assigned_at.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        raise _not_found()
    assignment, lesson_version = row._tuple()
    return participation, assignment, lesson_version


async def _published_assessment(
    db: AsyncSession,
    *,
    assignment: TrainingAssignment,
    lesson_version: LessonVersion,
) -> tuple[AssessmentVersion | None, AssessmentReadiness | None]:
    assessment = await db.scalar(
        select(AssessmentVersion)
        .where(
            AssessmentVersion.organization_id == assignment.organization_id,
            AssessmentVersion.location_id == assignment.location_id,
            AssessmentVersion.training_version_id == assignment.training_version_id,
            AssessmentVersion.lesson_version_id == lesson_version.id,
            AssessmentVersion.status == "published",
        )
        .order_by(AssessmentVersion.version_number.desc())
        .limit(1)
    )
    if assessment is None:
        return None, None
    readiness = await db.scalar(
        select(AssessmentReadiness).where(
            AssessmentReadiness.assessment_version_id == assessment.id
        )
    )
    return assessment, readiness


def _result_summary(
    *,
    attempt: AssessmentAttempt,
    result: AttemptResult,
    current_assessment_version_id: UUID | None,
) -> InteractiveResultSummaryResponse:
    return InteractiveResultSummaryResponse(
        result_id=result.id,
        attempt_id=attempt.id,
        assessment_version_id=attempt.assessment_version_id,
        completed_at=result.completed_at,
        correct_count=result.correct_count,
        total_count=5,
        score_basis_points=result.score_basis_points,
        knowledge_level=result.knowledge_level,
        is_current=attempt.assessment_version_id == current_assessment_version_id,
    )


async def get_lesson_interactive_training_summary(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    employee_profile_id: UUID,
    lesson_id: UUID,
    session_id: UUID,
) -> LessonInteractiveTrainingSummaryResponse:
    participation, assignment, lesson_version = await _current_scope(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        lesson_id=lesson_id,
    )
    completion_exists = (
        await db.scalar(
            select(LessonCompletion.id).where(
                LessonCompletion.assignment_id == assignment.id,
                LessonCompletion.lesson_version_id == lesson_version.id,
            )
        )
        is not None
    )
    assessment, readiness = await _published_assessment(
        db,
        assignment=assignment,
        lesson_version=lesson_version,
    )
    eligible_count = 0
    if assessment is not None:
        eligible_count = (
            await db.scalar(
                select(func.count())
                .select_from(AssessmentQuestionPool)
                .join(
                    QuestionVersion,
                    QuestionVersion.id == AssessmentQuestionPool.question_version_id,
                )
                .where(
                    AssessmentQuestionPool.assessment_version_id == assessment.id,
                    AssessmentQuestionPool.eligible.is_(True),
                    QuestionVersion.status == "published",
                )
            )
            or 0
        )

    availability = "ready"
    reason_codes: list[str] = []
    if not completion_exists:
        availability = "unavailable"
        reason_codes.append("LESSON_NOT_COMPLETED")
    elif assessment is None:
        availability = "preparing"
        reason_codes.append("ASSESSMENT_NOT_PUBLISHED")
    elif readiness is None or readiness.status == "processing":
        availability = "preparing"
        reason_codes.append("ASSESSMENT_PROCESSING")
    elif readiness.status == "blocked" or eligible_count < 5:
        availability = "unavailable"
        reason_codes.extend(readiness.blocking_codes or ["ASSESSMENT_POOL_INVALID"])
    elif readiness.status == "warning":
        reason_codes.extend(readiness.warning_codes)
    if participation == "paused":
        availability = "paused"
        reason_codes.insert(0, "TRAINING_PAUSED")

    current_assessment_id = assessment.id if assessment is not None else None
    active_attempt = None
    if current_assessment_id is not None:
        active = await db.scalar(
            select(AssessmentAttempt).where(
                AssessmentAttempt.organization_id == organization_id,
                AssessmentAttempt.employee_profile_id == employee_profile_id,
                AssessmentAttempt.assignment_id == assignment.id,
                AssessmentAttempt.assessment_version_id == current_assessment_id,
                AssessmentAttempt.status == "in_progress",
            )
        )
        if active is not None:
            active_attempt = await get_interactive_attempt(
                db,
                organization_id=organization_id,
                location_id=location_id,
                employee_profile_id=employee_profile_id,
                attempt_id=active.id,
                session_id=session_id,
            )

    history_rows = list(
        (
            await db.execute(
                select(AssessmentAttempt, AttemptResult)
                .join(AttemptResult, AttemptResult.attempt_id == AssessmentAttempt.id)
                .join(
                    AssessmentVersion,
                    AssessmentVersion.id == AssessmentAttempt.assessment_version_id,
                )
                .where(
                    AssessmentAttempt.organization_id == organization_id,
                    AssessmentAttempt.employee_profile_id == employee_profile_id,
                    AssessmentAttempt.status == "completed",
                    AssessmentVersion.lesson_id == lesson_id,
                )
                .order_by(AttemptResult.completed_at.desc())
                .limit(HISTORY_LIMIT)
            )
        ).all()
    )
    history = [
        _result_summary(
            attempt=attempt,
            result=result,
            current_assessment_version_id=current_assessment_id,
        )
        for attempt, result in history_rows
    ]
    latest = None
    best = None
    if current_assessment_id is not None:
        current_query = (
            select(AssessmentAttempt, AttemptResult)
            .join(AttemptResult, AttemptResult.attempt_id == AssessmentAttempt.id)
            .where(
                AssessmentAttempt.organization_id == organization_id,
                AssessmentAttempt.employee_profile_id == employee_profile_id,
                AssessmentAttempt.assessment_version_id == current_assessment_id,
                AssessmentAttempt.status == "completed",
            )
        )
        latest_row = (
            await db.execute(current_query.order_by(AttemptResult.completed_at.desc()).limit(1))
        ).first()
        best_row = (
            await db.execute(
                current_query.order_by(
                    AttemptResult.score_basis_points.desc(),
                    AttemptResult.completed_at.desc(),
                ).limit(1)
            )
        ).first()
        if latest_row is not None:
            latest = _result_summary(
                attempt=latest_row[0],
                result=latest_row[1],
                current_assessment_version_id=current_assessment_id,
            )
        if best_row is not None:
            best = _result_summary(
                attempt=best_row[0],
                result=best_row[1],
                current_assessment_version_id=current_assessment_id,
            )

    return LessonInteractiveTrainingSummaryResponse(
        lesson_id=lesson_id,
        lesson_version_id=lesson_version.id,
        assessment_version_id=current_assessment_id,
        availability=availability,
        can_start=availability == "ready",
        reason_codes=reason_codes,
        readiness_status=readiness.status if readiness is not None else None,
        active_attempt=active_attempt,
        latest=latest,
        best=best,
        history=history,
    )
