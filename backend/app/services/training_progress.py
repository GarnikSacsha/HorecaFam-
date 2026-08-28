from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LessonCompletion, LessonVersion, TrainingAssignment, TrainingModuleVersion
from app.schemas.training import TrainingProgressResponse


async def derive_training_progress(
    db: AsyncSession,
    *,
    assignment: TrainingAssignment,
) -> TrainingProgressResponse:
    required_lesson_ids = (
        select(LessonVersion.lesson_id)
        .join(
            TrainingModuleVersion,
            TrainingModuleVersion.id == LessonVersion.training_module_version_id,
        )
        .where(
            TrainingModuleVersion.training_version_id == assignment.training_version_id,
            LessonVersion.required.is_(True),
        )
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
