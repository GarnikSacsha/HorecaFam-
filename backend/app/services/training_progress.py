from uuid import UUID

from sqlalchemy import Select, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LessonCompletion, LessonVersion, TrainingAssignment, TrainingModuleVersion
from app.schemas.training import TrainingProgressResponse
from app.services.module_audiences import module_visible_to


def position_lesson_ids(
    *,
    training_version_id: UUID,
    employee_profile_id: UUID,
    required_only: bool = True,
) -> Select[tuple[UUID]]:
    query = (
        select(LessonVersion.lesson_id)
        .join(
            TrainingModuleVersion,
            TrainingModuleVersion.id == LessonVersion.training_module_version_id,
        )
        .where(
            TrainingModuleVersion.training_version_id == training_version_id,
            module_visible_to(employee_profile_id),
        )
    )
    if required_only:
        query = query.where(
            TrainingModuleVersion.required.is_(True),
            LessonVersion.required.is_(True),
        )
    return query


async def derive_training_progress(
    db: AsyncSession,
    *,
    assignment: TrainingAssignment,
) -> TrainingProgressResponse:
    required_lesson_ids = position_lesson_ids(
        training_version_id=assignment.training_version_id,
        employee_profile_id=assignment.employee_profile_id,
    )
    required_count = int(
        await db.scalar(select(func.count()).select_from(required_lesson_ids.subquery())) or 0
    )
    completed_count = int(
        await db.scalar(
            select(func.count(distinct(LessonCompletion.lesson_id))).where(
                LessonCompletion.assignment_id == assignment.id,
                LessonCompletion.lesson_id.in_(required_lesson_ids),
            )
        )
        or 0
    )
    percentage = completed_count * 100 // required_count if required_count else 0
    return TrainingProgressResponse(
        required_lesson_count=required_count,
        completed_required_lesson_count=completed_count,
        percentage=percentage,
        is_complete=required_count > 0 and completed_count == required_count,
    )
