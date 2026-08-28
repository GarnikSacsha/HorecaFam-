from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Asset,
    AuditEvent,
    ContentBlockType,
    EmployeeProfile,
    LessonContentBlock,
    LessonContentBlockTranslation,
    LessonTranslation,
    LessonVersion,
    MenuItemVersion,
    MenuVersion,
    OrganizationMembership,
    Training,
    TrainingModule,
    TrainingModuleTranslation,
    TrainingModuleVersion,
    TrainingVersion,
    TrainingVersionAudience,
    TrainingVersionMenuDependency,
)
from app.schemas.training import (
    YOUTUBE_VIDEO_ID,
    TrainingPublishResponse,
    TrainingReadinessCounts,
    TrainingReadinessIssue,
    TrainingReadinessResponse,
    validate_content_payload,
)
from app.services.applicability import evaluate_activation_applicability
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.training_queries import training_version_summary
from app.services.training_rollouts import prepare_replacement_rollout


def _not_found() -> APIError:
    return APIError(
        status_code=404,
        code="RESOURCE_NOT_FOUND",
        message="Ресурс не знайдено.",
    )


def _revision_conflict() -> APIError:
    return APIError(
        status_code=409,
        code="REVISION_CONFLICT",
        message="Чернетку вже змінено. Оновіть дані та повторіть дію.",
    )


def _issue(
    code: str,
    message: str,
    entity_type: str,
    entity_id: UUID | None,
) -> TrainingReadinessIssue:
    return TrainingReadinessIssue(
        code=code,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
    )


async def _scoped_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    lock: bool = False,
) -> TrainingVersion:
    query = select(TrainingVersion).where(
        TrainingVersion.id == version_id,
        TrainingVersion.organization_id == organization_id,
        TrainingVersion.location_id == location_id,
    )
    if lock:
        query = query.with_for_update()
    version = await db.scalar(query)
    if version is None:
        raise _not_found()
    return version


def _stored_payload_is_valid(block: LessonContentBlock) -> bool:
    try:
        block_type = ContentBlockType(block.type)
        if block_type == ContentBlockType.EXTERNAL_VIDEO:
            provider = block.payload.get("provider")
            video_id = block.payload.get("video_id")
            title = block.payload.get("title_uk")
            summary = block.payload.get("summary_uk")
            return (
                provider == "youtube"
                and isinstance(video_id, str)
                and YOUTUBE_VIDEO_ID.fullmatch(video_id) is not None
                and isinstance(title, str)
                and 1 <= len(title.strip()) <= 200
                and isinstance(summary, str)
                and 1 <= len(summary.strip()) <= 2000
            )
        candidate = dict(block.payload)
        if block_type == ContentBlockType.MENU_ITEM_CARD:
            candidate["menu_item_id"] = block.menu_item_id
        elif block_type == ContentBlockType.IMAGE:
            candidate["asset_id"] = block.asset_id
        validate_content_payload(block_type, candidate)
        return True
    except (TypeError, ValueError):
        return False


async def _readiness_for_version(
    db: AsyncSession,
    version: TrainingVersion,
    *,
    lock_menu_dependency: bool = False,
) -> TrainingReadinessResponse:
    blockers: list[TrainingReadinessIssue] = []
    warnings: list[TrainingReadinessIssue] = []
    if version.status != "draft":
        blockers.append(
            _issue(
                "VERSION_IMMUTABLE",
                "Лише чернетку навчання можна опублікувати.",
                "training_version",
                version.id,
            )
        )

    audience_count = len(
        list(
            (
                await db.scalars(
                    select(TrainingVersionAudience.id).where(
                        TrainingVersionAudience.training_version_id == version.id
                    )
                )
            ).all()
        )
    )
    if audience_count == 0:
        blockers.append(
            _issue(
                "TRAINING_AUDIENCE_REQUIRED",
                "Оберіть щонайменше одну активну операційну роль.",
                "training_version",
                version.id,
            )
        )

    current_training = await db.scalar(
        select(TrainingVersion).where(
            TrainingVersion.training_id == version.training_id,
            TrainingVersion.status == "published",
        )
    )
    current_training_id = current_training.id if current_training is not None else None
    if version.status == "draft" and version.base_version_id != current_training_id:
        blockers.append(
            _issue(
                "STALE_DRAFT_BASE",
                "Чернетку створено не з поточної опублікованої версії навчання.",
                "training_version",
                version.id,
            )
        )

    menu_query = select(MenuVersion).where(
        MenuVersion.organization_id == version.organization_id,
        MenuVersion.location_id == version.location_id,
        MenuVersion.status == "published",
    )
    if lock_menu_dependency:
        menu_query = menu_query.with_for_update()
    current_menu = await db.scalar(menu_query)
    dependency = await db.scalar(
        select(TrainingVersionMenuDependency).where(
            TrainingVersionMenuDependency.training_version_id == version.id
        )
    )
    dependency_valid = (
        current_menu is not None
        and dependency is not None
        and dependency.menu_version_id == current_menu.id
    )
    if not dependency_valid:
        blockers.append(
            _issue(
                "MENU_DEPENDENCY_INVALID",
                "Навчання має посилатися на поточну опубліковану версію меню цієї локації.",
                "training_version",
                version.id,
            )
        )

    modules = list(
        (
            await db.scalars(
                select(TrainingModuleVersion).where(
                    TrainingModuleVersion.training_version_id == version.id
                )
            )
        ).all()
    )
    valid_modules: list[TrainingModuleVersion] = []
    for module_version in modules:
        module_identity = await db.get(TrainingModule, module_version.training_module_id)
        if module_identity is not None and module_identity.domain_type == "menu":
            valid_modules.append(module_version)
    if not valid_modules:
        blockers.append(
            _issue(
                "MENU_MODULE_MISSING",
                "Системний модуль меню відсутній.",
                "training_version",
                version.id,
            )
        )

    module_ids = [module.id for module in valid_modules]
    lessons = (
        list(
            (
                await db.scalars(
                    select(LessonVersion).where(
                        LessonVersion.training_module_version_id.in_(module_ids)
                    )
                )
            ).all()
        )
        if module_ids
        else []
    )
    required_lessons = [lesson for lesson in lessons if lesson.required]
    if not required_lessons:
        blockers.append(
            _issue(
                "REQUIRED_LESSON_MISSING",
                "Потрібен щонайменше один обов’язковий урок.",
                "training_version",
                version.id,
            )
        )

    for module_state in valid_modules:
        module_translations = list(
            (
                await db.scalars(
                    select(TrainingModuleTranslation).where(
                        TrainingModuleTranslation.training_module_version_id == module_state.id
                    )
                )
            ).all()
        )
        module_ua = next((row for row in module_translations if row.locale == "uk"), None)
        module_en = next((row for row in module_translations if row.locale == "en"), None)
        if module_ua is None or module_ua.status != "ready" or not module_ua.title.strip():
            blockers.append(
                _issue(
                    "UA_CONTENT_NOT_READY",
                    "Обов’язковий український текст модуля не готовий.",
                    "training_module",
                    module_state.id,
                )
            )
        if module_en is None or module_en.status != "ready":
            warnings.append(
                _issue(
                    "EN_TRANSLATION_PENDING",
                    "Англійський переклад модуля не готовий; буде використано український текст.",
                    "training_module",
                    module_state.id,
                )
            )

    blocks: list[LessonContentBlock] = []
    for lesson in lessons:
        lesson_translations = list(
            (
                await db.scalars(
                    select(LessonTranslation).where(
                        LessonTranslation.lesson_version_id == lesson.id
                    )
                )
            ).all()
        )
        lesson_ua = next((row for row in lesson_translations if row.locale == "uk"), None)
        lesson_en = next((row for row in lesson_translations if row.locale == "en"), None)
        if lesson_ua is None or lesson_ua.status != "ready" or not lesson_ua.title.strip():
            blockers.append(
                _issue(
                    "UA_CONTENT_NOT_READY",
                    "Обов’язковий український текст уроку не готовий.",
                    "lesson",
                    lesson.lesson_id,
                )
            )
        if lesson_en is None or lesson_en.status != "ready":
            warnings.append(
                _issue(
                    "EN_TRANSLATION_PENDING",
                    "Англійський переклад уроку не готовий; буде використано український текст.",
                    "lesson",
                    lesson.lesson_id,
                )
            )
        lesson_blocks = list(
            (
                await db.scalars(
                    select(LessonContentBlock).where(
                        LessonContentBlock.lesson_version_id == lesson.id
                    )
                )
            ).all()
        )
        blocks.extend(lesson_blocks)
        if lesson.required and not lesson_blocks:
            blockers.append(
                _issue(
                    "REQUIRED_LESSON_EMPTY",
                    "Обов’язковий урок має містити хоча б один блок.",
                    "lesson",
                    lesson.lesson_id,
                )
            )

    ready_asset_count = 0
    menu_item_link_count = 0
    for block in blocks:
        if not _stored_payload_is_valid(block):
            blockers.append(
                _issue(
                    "CONTENT_BLOCK_INVALID",
                    "Блок уроку має неправильну структуру або не має текстової альтернативи.",
                    "lesson_content_block",
                    block.id,
                )
            )
        if block.type == ContentBlockType.MENU_ITEM_CARD.value:
            menu_item_link_count += 1
            linked_item = None
            if dependency_valid and dependency is not None and block.menu_item_id is not None:
                linked_item = await db.scalar(
                    select(MenuItemVersion.id).where(
                        MenuItemVersion.menu_version_id == dependency.menu_version_id,
                        MenuItemVersion.menu_item_id == block.menu_item_id,
                    )
                )
            if linked_item is None:
                blockers.append(
                    _issue(
                        "MENU_ITEM_LINK_INVALID",
                        "Посилання веде не до поточної опублікованої версії меню.",
                        "lesson_content_block",
                        block.id,
                    )
                )
        if block.type == ContentBlockType.IMAGE.value:
            asset = await db.scalar(
                select(Asset).where(
                    Asset.id == block.asset_id,
                    Asset.organization_id == version.organization_id,
                    Asset.location_id == version.location_id,
                    Asset.status == "ready",
                )
            )
            if asset is None:
                blockers.append(
                    _issue(
                        "ASSET_NOT_READY",
                        "Зображення відсутнє або не готове.",
                        "lesson_content_block",
                        block.id,
                    )
                )
            else:
                ready_asset_count += 1
        translation = await db.scalar(
            select(LessonContentBlockTranslation).where(
                LessonContentBlockTranslation.lesson_content_block_id == block.id,
                LessonContentBlockTranslation.locale == "en",
            )
        )
        if translation is None or translation.status != "ready":
            warnings.append(
                _issue(
                    "EN_TRANSLATION_PENDING",
                    "Англійський переклад блока не готовий; буде використано український текст.",
                    "lesson_content_block",
                    block.id,
                )
            )

    blockers.sort(key=lambda item: (item.code, item.entity_type, str(item.entity_id or "")))
    warnings.sort(key=lambda item: (item.code, item.entity_type, str(item.entity_id or "")))
    return TrainingReadinessResponse(
        training_id=version.training_id,
        training_version_id=version.id,
        organization_id=version.organization_id,
        location_id=version.location_id,
        revision=version.revision,
        can_publish=not blockers,
        blocking_errors=blockers,
        warnings=warnings,
        counts=TrainingReadinessCounts(
            module_count=len(valid_modules),
            lesson_count=len(lessons),
            required_lesson_count=len(required_lessons),
            content_block_count=len(blocks),
            required_asset_count=sum(
                block.type == ContentBlockType.IMAGE.value for block in blocks
            ),
            ready_asset_count=ready_asset_count,
            menu_item_link_count=menu_item_link_count,
        ),
    )


async def get_training_readiness(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
) -> TrainingReadinessResponse:
    version = await _scoped_version(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
    )
    return await _readiness_for_version(db, version)


async def _publication_response(
    db: AsyncSession,
    version: TrainingVersion,
    *,
    assignment_count: int | None = None,
    notification_count: int | None = None,
    rollout_id: UUID | None = None,
) -> TrainingPublishResponse:
    if assignment_count is None or notification_count is None:
        audit = await db.scalar(
            select(AuditEvent)
            .where(
                AuditEvent.action == "training_published",
                AuditEvent.target_id == version.id,
            )
            .order_by(AuditEvent.created_at.desc())
        )
        values = audit.new_values if audit is not None and audit.new_values is not None else {}
        assignment_count = int(values.get("assignment_count", 0))
        notification_count = int(values.get("notification_count", 0))
        stored_rollout_id = values.get("rollout_id")
        rollout_id = UUID(stored_rollout_id) if stored_rollout_id is not None else None
    return TrainingPublishResponse(
        published=await training_version_summary(db, version),
        previous_published_version_id=version.base_version_id,
        employee_reference_switched=True,
        assignment_count=assignment_count,
        completion_count=0,
        progress_count=0,
        rollout_count=1 if rollout_id is not None else 0,
        notification_count=notification_count,
        rollout_id=rollout_id,
    )


async def publish_training_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    idempotency_key: str,
    now: datetime,
) -> TrainingPublishResponse:
    fingerprint = request_fingerprint(
        {"version_id": str(version_id), "expected_revision": expected_revision}
    )
    try:
        replay = await find_idempotency_replay(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="training_version_publish",
            key=idempotency_key,
            fingerprint=fingerprint,
            now=now,
        )
        training = await db.scalar(
            select(Training)
            .where(
                Training.organization_id == organization_id,
                Training.location_id == location_id,
            )
            .with_for_update()
        )
        if training is None:
            raise _not_found()
        version = await _scoped_version(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            lock=True,
        )
        if version.training_id != training.id:
            raise _not_found()
        if replay is not None:
            if version.status != "published":
                raise RuntimeError("Idempotent Training publication resource is unavailable")
            await db.commit()
            return await _publication_response(db, version)
        if version.status != "draft" or version.revision != expected_revision:
            raise _revision_conflict()
        readiness = await _readiness_for_version(
            db,
            version,
            lock_menu_dependency=True,
        )
        if not readiness.can_publish:
            raise APIError(
                status_code=409,
                code="TRAINING_NOT_READY",
                message="Чернетка навчання не пройшла перевірку готовності.",
            )
        previous = await db.scalar(
            select(TrainingVersion)
            .where(
                TrainingVersion.training_id == version.training_id,
                TrainingVersion.status == "published",
            )
            .with_for_update()
        )
        if (previous.id if previous is not None else None) != version.base_version_id:
            raise _revision_conflict()
        if previous is not None:
            previous.status = "archived"
            previous.archived_at = now
            await db.flush()
        version.status = "published"
        version.published_by_user_id = actor_user_id
        version.published_at = now
        await db.flush()
        employee_ids = list(
            (
                await db.scalars(
                    select(EmployeeProfile.id)
                    .join(
                        OrganizationMembership,
                        OrganizationMembership.id == EmployeeProfile.membership_id,
                    )
                    .join(
                        TrainingVersionAudience,
                        TrainingVersionAudience.operational_role_id
                        == EmployeeProfile.operational_role_id,
                    )
                    .where(
                        EmployeeProfile.organization_id == organization_id,
                        EmployeeProfile.location_id == location_id,
                        OrganizationMembership.status == "active",
                        TrainingVersionAudience.training_version_id == version.id,
                    )
                    .order_by(EmployeeProfile.id)
                )
            ).all()
        )
        assignment_count = 0
        notification_count = 0
        for employee_id in employee_ids:
            applicability = await evaluate_activation_applicability(
                db,
                organization_id=organization_id,
                employee_profile_id=employee_id,
                now=now,
            )
            assignment_count += applicability.assignment_count
            notification_count += applicability.notification_count
        rollout = None
        if previous is not None:
            rollout = await prepare_replacement_rollout(
                db,
                source=previous,
                target=version,
                actor_user_id=actor_user_id,
                request_id=request_id,
                now=now,
            )
        await reserve_idempotency(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="training_version_publish",
            key=idempotency_key,
            fingerprint=fingerprint,
            resource_type="training_version",
            resource_id=version.id,
            response_status=200,
            now=now,
        )
        db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_type="user",
                action="training_published",
                target_type="training_version",
                target_id=version.id,
                old_values=None,
                new_values={
                    "location_id": str(location_id),
                    "previous_published_version_id": (
                        str(previous.id) if previous is not None else None
                    ),
                    "employee_reference_switched": True,
                    "assignment_count": assignment_count,
                    "completion_count": 0,
                    "progress_count": 0,
                    "rollout_count": 1 if rollout is not None else 0,
                    "notification_count": notification_count,
                    "rollout_id": str(rollout.id) if rollout is not None else None,
                },
                request_id=request_id,
                outcome="success",
            )
        )
        await db.commit()
        return await _publication_response(
            db,
            version,
            assignment_count=assignment_count,
            notification_count=notification_count,
            rollout_id=rollout.id if rollout is not None else None,
        )
    except Exception:
        await db.rollback()
        raise
