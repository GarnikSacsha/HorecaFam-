from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentVersion,
    AttemptResult,
    EmployeeProfile,
    TrainingAssignment,
)
from app.schemas.assessment import (
    AdminEmployeeResultRow,
    AdminEmployeeResultsDetailResponse,
    AdminResultsOverviewResponse,
    FinalExamFinishResponse,
    FinalExamHistoryResponse,
)
from app.services.final_exam_results import (
    _finish_response,
    get_final_exam_history,
)


def _not_found() -> APIError:
    return APIError(status_code=404, code="RESOURCE_NOT_FOUND", message="Ресурс не знайдено.")


async def _practice_score(
    db: AsyncSession,
    *,
    employee_profile_id: UUID,
) -> int | None:
    return cast(
        int | None,
        await db.scalar(
            select(AttemptResult.score_basis_points)
            .join(AssessmentAttempt, AssessmentAttempt.id == AttemptResult.attempt_id)
            .join(
                AssessmentVersion, AssessmentVersion.id == AssessmentAttempt.assessment_version_id
            )
            .join(Assessment, Assessment.id == AssessmentVersion.assessment_id)
            .where(
                AssessmentAttempt.employee_profile_id == employee_profile_id,
                Assessment.assessment_type == "whole_menu_knowledge_check",
            )
            .order_by(AttemptResult.completed_at.desc(), AttemptResult.id.desc())
            .limit(1)
        ),
    )


async def _employee_row(
    db: AsyncSession,
    *,
    profile: EmployeeProfile,
    history: FinalExamHistoryResponse,
) -> AdminEmployeeResultRow:
    current_training_status = await db.scalar(
        select(TrainingAssignment.status)
        .where(
            TrainingAssignment.employee_profile_id == profile.id,
            TrainingAssignment.status != "revoked",
        )
        .order_by(TrainingAssignment.assigned_at.desc())
        .limit(1)
    )
    return AdminEmployeeResultRow(
        employee_id=profile.id,
        first_name=profile.first_name,
        last_name=profile.last_name,
        location_id=profile.location_id,
        current_training_status=current_training_status,
        latest_practice_score_basis_points=await _practice_score(
            db, employee_profile_id=profile.id
        ),
        certification=history.certification,
        latest_final_exam=history.latest,
        critical_error_count=(
            history.latest.critical_error_count if history.latest is not None else 0
        ),
    )


async def get_admin_results_overview(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None = None,
) -> AdminResultsOverviewResponse:
    query = select(EmployeeProfile).where(EmployeeProfile.organization_id == organization_id)
    if location_id is not None:
        query = query.where(EmployeeProfile.location_id == location_id)
    profiles = list(
        await db.scalars(
            query.order_by(
                EmployeeProfile.last_name, EmployeeProfile.first_name, EmployeeProfile.id
            )
        )
    )
    items: list[AdminEmployeeResultRow] = []
    for profile in profiles:
        history = (
            await get_final_exam_history(
                db,
                organization_id=organization_id,
                location_id=profile.location_id,
                employee_profile_id=profile.id,
            )
            if profile.location_id is not None
            else FinalExamHistoryResponse(certification=None, latest=None, best=None, history=[])
        )
        items.append(await _employee_row(db, profile=profile, history=history))
    return AdminResultsOverviewResponse(items=items, total=len(items))


async def get_admin_employee_results(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_profile_id: UUID,
) -> AdminEmployeeResultsDetailResponse:
    profile = await db.scalar(
        select(EmployeeProfile).where(
            EmployeeProfile.id == employee_profile_id,
            EmployeeProfile.organization_id == organization_id,
        )
    )
    if profile is None or profile.location_id is None:
        raise _not_found()
    history = await get_final_exam_history(
        db,
        organization_id=organization_id,
        location_id=profile.location_id,
        employee_profile_id=profile.id,
    )
    return AdminEmployeeResultsDetailResponse(
        employee=await _employee_row(db, profile=profile, history=history),
        final_exam=history,
    )


async def get_admin_final_exam_result(
    db: AsyncSession,
    *,
    organization_id: UUID,
    attempt_id: UUID,
) -> FinalExamFinishResponse:
    row = (
        await db.execute(
            select(AssessmentAttempt, AttemptResult)
            .join(AttemptResult, AttemptResult.attempt_id == AssessmentAttempt.id)
            .join(
                AssessmentVersion, AssessmentVersion.id == AssessmentAttempt.assessment_version_id
            )
            .join(Assessment, Assessment.id == AssessmentVersion.assessment_id)
            .where(
                AssessmentAttempt.id == attempt_id,
                AssessmentAttempt.organization_id == organization_id,
                Assessment.assessment_type == "menu_final_exam",
            )
        )
    ).first()
    if row is None:
        raise _not_found()
    attempt, result = row._tuple()
    return await _finish_response(
        db,
        attempt=attempt,
        result=result,
        newly_certified=False,
        replayed=True,
    )
