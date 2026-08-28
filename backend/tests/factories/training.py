from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.models import (
    Asset,
    EmployeeProfile,
    Lesson,
    LessonCompletion,
    LessonContentBlock,
    LessonTranslation,
    LessonVersion,
    OperationalRole,
    RolloutEmployeeImpact,
    RolloutLessonRuleRecord,
    Training,
    TrainingAssignment,
    TrainingModule,
    TrainingModuleTranslation,
    TrainingModuleVersion,
    TrainingRollout,
    TrainingVersion,
    TrainingVersionAudience,
)


def make_training(organization_id: UUID, location_id: UUID, **overrides: Any) -> Training:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": organization_id,
        "location_id": location_id,
    }
    values.update(overrides)
    return Training(**values)


def make_training_version(
    training: Training,
    user_id: UUID,
    **overrides: Any,
) -> TrainingVersion:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": training.organization_id,
        "location_id": training.location_id,
        "training_id": training.id,
        "version_number": 1,
        "status": "draft",
        "revision": 0,
        "created_by_user_id": user_id,
    }
    values.update(overrides)
    return TrainingVersion(**values)


def make_training_module(training: Training, **overrides: Any) -> TrainingModule:
    values: dict[str, Any] = {
        "id": uuid4(),
        "training_id": training.id,
        "domain_type": "menu",
    }
    values.update(overrides)
    return TrainingModule(**values)


def make_training_module_version(
    version: TrainingVersion,
    module: TrainingModule,
    **overrides: Any,
) -> TrainingModuleVersion:
    values: dict[str, Any] = {
        "id": uuid4(),
        "training_id": version.training_id,
        "training_version_id": version.id,
        "training_module_id": module.id,
        "position": 0,
        "required": True,
    }
    values.update(overrides)
    return TrainingModuleVersion(**values)


def make_training_module_translation(
    module_version: TrainingModuleVersion,
    **overrides: Any,
) -> TrainingModuleTranslation:
    values: dict[str, Any] = {
        "id": uuid4(),
        "training_module_version_id": module_version.id,
        "locale": "uk",
        "status": "ready",
        "title": "Меню",
        "description": None,
        "source_revision": 0,
    }
    values.update(overrides)
    return TrainingModuleTranslation(**values)


def make_lesson(module: TrainingModule, **overrides: Any) -> Lesson:
    values: dict[str, Any] = {"id": uuid4(), "training_module_id": module.id}
    values.update(overrides)
    return Lesson(**values)


def make_lesson_version(
    module_version: TrainingModuleVersion,
    lesson: Lesson,
    **overrides: Any,
) -> LessonVersion:
    values: dict[str, Any] = {
        "id": uuid4(),
        "training_module_version_id": module_version.id,
        "lesson_id": lesson.id,
        "position": 0,
        "required": True,
        "estimated_minutes": 5,
    }
    values.update(overrides)
    return LessonVersion(**values)


def make_lesson_translation(
    lesson_version: LessonVersion,
    **overrides: Any,
) -> LessonTranslation:
    values: dict[str, Any] = {
        "id": uuid4(),
        "lesson_version_id": lesson_version.id,
        "locale": "uk",
        "status": "ready",
        "title": "Основи меню",
        "description": None,
        "source_revision": 0,
    }
    values.update(overrides)
    return LessonTranslation(**values)


def make_asset(
    organization_id: UUID,
    location_id: UUID,
    user_id: UUID,
    **overrides: Any,
) -> Asset:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": organization_id,
        "location_id": location_id,
        "status": "ready",
        "object_key": f"training/{organization_id}/{location_id}/{uuid4()}",
        "original_filename": "dish.webp",
        "mime_type": "image/webp",
        "size_bytes": 1024,
        "sha256": "a" * 64,
        "created_by_user_id": user_id,
        "upload_expires_at": datetime.now(UTC) + timedelta(minutes=15),
        "ready_at": datetime.now(UTC),
    }
    values.update(overrides)
    return Asset(**values)


def make_content_block(
    lesson_version: LessonVersion,
    **overrides: Any,
) -> LessonContentBlock:
    values: dict[str, Any] = {
        "id": uuid4(),
        "lesson_version_id": lesson_version.id,
        "type": "text",
        "position": 0,
        "payload": {"text_uk": "Подавайте страву теплою."},
    }
    values.update(overrides)
    return LessonContentBlock(**values)


def make_training_version_audience(
    version: TrainingVersion,
    role: OperationalRole,
    **overrides: Any,
) -> TrainingVersionAudience:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": version.organization_id,
        "location_id": version.location_id,
        "training_version_id": version.id,
        "operational_role_id": role.id,
    }
    values.update(overrides)
    return TrainingVersionAudience(**values)


def make_training_rollout(
    training: Training,
    from_version: TrainingVersion,
    to_version: TrainingVersion,
    user_id: UUID,
    **overrides: Any,
) -> TrainingRollout:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": training.organization_id,
        "location_id": training.location_id,
        "training_id": training.id,
        "from_version_id": from_version.id,
        "to_version_id": to_version.id,
        "status": "draft",
        "revision": 0,
        "from_version_revision": from_version.revision,
        "to_version_revision": to_version.revision,
        "created_by_user_id": user_id,
    }
    values.update(overrides)
    return TrainingRollout(**values)


def make_training_assignment(
    employee: EmployeeProfile,
    training: Training,
    version: TrainingVersion,
    **overrides: Any,
) -> TrainingAssignment:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": training.organization_id,
        "location_id": training.location_id,
        "training_id": training.id,
        "employee_profile_id": employee.id,
        "training_version_id": version.id,
        "status": "assigned",
        "source": "automatic",
    }
    values.update(overrides)
    return TrainingAssignment(**values)


def make_lesson_completion(
    assignment: TrainingAssignment,
    lesson_version: LessonVersion,
    user_id: UUID,
    **overrides: Any,
) -> LessonCompletion:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": assignment.organization_id,
        "location_id": assignment.location_id,
        "training_id": assignment.training_id,
        "assignment_id": assignment.id,
        "lesson_id": lesson_version.lesson_id,
        "lesson_version_id": lesson_version.id,
        "completion_source": "employee",
        "completed_by_user_id": user_id,
        "completed_at": datetime.now(UTC),
    }
    values.update(overrides)
    return LessonCompletion(**values)


def make_rollout_lesson_rule(
    rollout: TrainingRollout,
    from_lesson_version: LessonVersion,
    to_lesson_version: LessonVersion,
    **overrides: Any,
) -> RolloutLessonRuleRecord:
    values: dict[str, Any] = {
        "id": uuid4(),
        "rollout_id": rollout.id,
        "lesson_id": from_lesson_version.lesson_id,
        "from_lesson_version_id": from_lesson_version.id,
        "to_lesson_version_id": to_lesson_version.id,
        "rule": "preserve_completion",
        "requires_admin_decision": False,
    }
    values.update(overrides)
    return RolloutLessonRuleRecord(**values)


def make_rollout_employee_impact(
    rollout: TrainingRollout,
    employee: EmployeeProfile,
    source_assignment: TrainingAssignment,
    **overrides: Any,
) -> RolloutEmployeeImpact:
    values: dict[str, Any] = {
        "id": uuid4(),
        "rollout_id": rollout.id,
        "employee_profile_id": employee.id,
        "source_assignment_id": source_assignment.id,
        "current_required_count": 1,
        "current_completed_count": 1,
        "current_progress_percentage": 100,
        "projected_required_count": 1,
        "projected_completed_count": 1,
        "projected_progress_percentage": 100,
        "lesson_impact": {"preserved": [], "repeat": [], "new": [], "removed": []},
        "validation_codes": [],
        "warning_codes": [],
        "preview_fingerprint": "a" * 64,
        "previewed_at": datetime.now(UTC),
    }
    values.update(overrides)
    return RolloutEmployeeImpact(**values)
