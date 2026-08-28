from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    AuditEvent,
    Lesson,
    LessonContentBlock,
    LessonContentBlockTranslation,
    LessonTranslation,
    LessonVersion,
    Location,
    Menu,
    MenuVersion,
    Training,
    TrainingModule,
    TrainingModuleTranslation,
    TrainingModuleVersion,
    TrainingVersion,
    TrainingVersionMenuDependency,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)


@dataclass(frozen=True, slots=True)
class TrainingDraftMutation[EntityT]:
    entity: EntityT
    revision: int


@dataclass(frozen=True, slots=True)
class TrainingDraftReorder[EntityT]:
    entities: list[EntityT]
    revision: int


def _error(status_code: int, code: str, message: str) -> APIError:
    return APIError(status_code=status_code, code=code, message=message)


def _resource_not_found() -> APIError:
    return _error(404, "RESOURCE_NOT_FOUND", "Ресурс не знайдено.")


def _revision_conflict() -> APIError:
    return _error(409, "REVISION_CONFLICT", "Чернетку вже змінено. Оновіть дані.")


def _immutable() -> APIError:
    return _error(
        409,
        "TRAINING_VERSION_IMMUTABLE",
        "Опубліковану або архівну версію навчання не можна змінювати.",
    )


def _draft_exists() -> APIError:
    return _error(409, "TRAINING_DRAFT_EXISTS", "Для цієї локації вже існує чернетка.")


def _validation_error() -> APIError:
    return _error(422, "VALIDATION_ERROR", "Перевірте правильність заповнення полів.")


def _lesson_not_empty() -> APIError:
    return _error(409, "LESSON_NOT_EMPTY", "Спочатку видаліть блоки уроку.")


def _bounded_text(value: str, *, maximum: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise _validation_error()
    return normalized


def _optional_text(value: str | None, *, maximum: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > maximum:
        raise _validation_error()
    return normalized


def _validate_minutes(value: int | None) -> int | None:
    if value is not None and not 1 <= value <= 240:
        raise _validation_error()
    return value


async def _lock_draft(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    expected_revision: int,
) -> TrainingVersion:
    version = await db.scalar(
        select(TrainingVersion)
        .where(
            TrainingVersion.id == version_id,
            TrainingVersion.organization_id == organization_id,
            TrainingVersion.location_id == location_id,
        )
        .with_for_update()
    )
    if version is None:
        raise _resource_not_found()
    if version.status != "draft":
        raise _immutable()
    if version.revision != expected_revision:
        raise _revision_conflict()
    return version


def _audit(
    db: AsyncSession,
    *,
    version: TrainingVersion,
    actor_user_id: UUID,
    request_id: UUID,
    action: str,
    target_type: str,
    target_id: UUID,
) -> None:
    db.add(
        AuditEvent(
            organization_id=version.organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action=action,
            target_type=target_type,
            target_id=target_id,
            old_values=None,
            new_values={"training_version_id": str(version.id), "revision": version.revision},
            request_id=request_id,
            outcome="success",
        )
    )


async def _copy_version_graph(
    db: AsyncSession,
    *,
    source: TrainingVersion,
    target: TrainingVersion,
) -> None:
    source_module = await db.scalar(
        select(TrainingModuleVersion).where(TrainingModuleVersion.training_version_id == source.id)
    )
    if source_module is None:
        raise _resource_not_found()
    target_module = TrainingModuleVersion(
        id=uuid4(),
        training_id=target.training_id,
        training_version_id=target.id,
        training_module_id=source_module.training_module_id,
        position=source_module.position,
        required=source_module.required,
    )
    db.add(target_module)
    await db.flush()

    source_module_translations = list(
        (
            await db.scalars(
                select(TrainingModuleTranslation).where(
                    TrainingModuleTranslation.training_module_version_id == source_module.id
                )
            )
        ).all()
    )
    db.add_all(
        [
            TrainingModuleTranslation(
                id=uuid4(),
                training_module_version_id=target_module.id,
                locale=row.locale,
                status=row.status,
                title=row.title,
                description=row.description,
                source_revision=row.source_revision,
            )
            for row in source_module_translations
        ]
    )

    source_lessons = list(
        (
            await db.scalars(
                select(LessonVersion)
                .where(LessonVersion.training_module_version_id == source_module.id)
                .order_by(LessonVersion.position, LessonVersion.id)
            )
        ).all()
    )
    lesson_version_map: dict[UUID, LessonVersion] = {}
    for row in source_lessons:
        copied = LessonVersion(
            id=uuid4(),
            training_module_version_id=target_module.id,
            lesson_id=row.lesson_id,
            position=row.position,
            required=row.required,
            estimated_minutes=row.estimated_minutes,
        )
        lesson_version_map[row.id] = copied
        db.add(copied)
    await db.flush()

    source_translations = list(
        (
            await db.scalars(
                select(LessonTranslation).where(
                    LessonTranslation.lesson_version_id.in_(lesson_version_map)
                )
            )
        ).all()
    )
    db.add_all(
        [
            LessonTranslation(
                id=uuid4(),
                lesson_version_id=lesson_version_map[row.lesson_version_id].id,
                locale=row.locale,
                status=row.status,
                title=row.title,
                description=row.description,
                source_revision=row.source_revision,
            )
            for row in source_translations
        ]
    )

    source_blocks = list(
        (
            await db.scalars(
                select(LessonContentBlock)
                .where(LessonContentBlock.lesson_version_id.in_(lesson_version_map))
                .order_by(LessonContentBlock.position, LessonContentBlock.id)
            )
        ).all()
    )
    block_map: dict[UUID, LessonContentBlock] = {}
    for block_row in source_blocks:
        copied_block = LessonContentBlock(
            id=uuid4(),
            lesson_version_id=lesson_version_map[block_row.lesson_version_id].id,
            type=block_row.type,
            position=block_row.position,
            payload=block_row.payload,
            menu_item_id=block_row.menu_item_id,
            asset_id=block_row.asset_id,
        )
        block_map[block_row.id] = copied_block
        db.add(copied_block)
    await db.flush()
    if block_map:
        source_block_translations = list(
            (
                await db.scalars(
                    select(LessonContentBlockTranslation).where(
                        LessonContentBlockTranslation.lesson_content_block_id.in_(block_map)
                    )
                )
            ).all()
        )
        db.add_all(
            [
                LessonContentBlockTranslation(
                    id=uuid4(),
                    lesson_content_block_id=block_map[row.lesson_content_block_id].id,
                    locale=row.locale,
                    status=row.status,
                    translated_payload=row.translated_payload,
                    source_revision=row.source_revision,
                )
                for row in source_block_translations
            ]
        )


async def create_training_draft(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    base_version_id: UUID | None,
    _commit: bool = True,
) -> TrainingVersion:
    try:
        location = await db.scalar(
            select(Location)
            .where(Location.id == location_id, Location.organization_id == organization_id)
            .with_for_update()
        )
        if location is None:
            raise _resource_not_found()

        training = await db.scalar(
            select(Training).where(
                Training.organization_id == organization_id,
                Training.location_id == location_id,
            )
        )
        if training is None:
            training = Training(
                id=uuid4(), organization_id=organization_id, location_id=location_id
            )
            db.add(training)
            await db.flush()
            module = TrainingModule(id=uuid4(), training_id=training.id, domain_type="menu")
            db.add(module)
            await db.flush()
        else:
            existing_module = await db.scalar(
                select(TrainingModule).where(
                    TrainingModule.training_id == training.id,
                    TrainingModule.domain_type == "menu",
                )
            )
            if existing_module is None:
                raise RuntimeError("Training Menu Module invariant is broken")
            module = existing_module

        if await db.scalar(
            select(TrainingVersion.id).where(
                TrainingVersion.training_id == training.id,
                TrainingVersion.status == "draft",
            )
        ):
            raise _draft_exists()

        published = await db.scalar(
            select(TrainingVersion).where(
                TrainingVersion.training_id == training.id,
                TrainingVersion.status == "published",
            )
        )
        if (published is None and base_version_id is not None) or (
            published is not None and base_version_id != published.id
        ):
            raise _resource_not_found()

        highest = await db.scalar(
            select(func.max(TrainingVersion.version_number)).where(
                TrainingVersion.training_id == training.id
            )
        )
        draft = TrainingVersion(
            id=uuid4(),
            organization_id=organization_id,
            location_id=location_id,
            training_id=training.id,
            version_number=(highest or 0) + 1,
            status="draft",
            base_version_id=published.id if published is not None else None,
            revision=0,
            created_by_user_id=actor_user_id,
        )
        db.add(draft)
        await db.flush()
        if published is None:
            module_version = TrainingModuleVersion(
                id=uuid4(),
                training_id=training.id,
                training_version_id=draft.id,
                training_module_id=module.id,
                position=0,
                required=True,
            )
            db.add(module_version)
            await db.flush()
            db.add(
                TrainingModuleTranslation(
                    id=uuid4(),
                    training_module_version_id=module_version.id,
                    locale="uk",
                    status="ready",
                    title="Меню",
                    description=None,
                    source_revision=0,
                )
            )
        else:
            await _copy_version_graph(db, source=published, target=draft)

        current_menu_version = await db.scalar(
            select(MenuVersion)
            .join(Menu, Menu.id == MenuVersion.menu_id)
            .where(
                Menu.organization_id == organization_id,
                Menu.location_id == location_id,
                MenuVersion.status == "published",
            )
        )
        if current_menu_version is not None:
            db.add(
                TrainingVersionMenuDependency(
                    id=uuid4(),
                    training_version_id=draft.id,
                    menu_version_id=current_menu_version.id,
                )
            )

        _audit(
            db,
            version=draft,
            actor_user_id=actor_user_id,
            request_id=request_id,
            action="training_draft_created",
            target_type="training_version",
            target_id=draft.id,
        )
        if _commit:
            await db.commit()
        else:
            await db.flush()
        return draft
    except Exception:
        await db.rollback()
        raise


async def create_training_draft_idempotent(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    base_version_id: UUID | None,
    idempotency_key: str,
    now: datetime,
) -> TrainingVersion:
    fingerprint = request_fingerprint(
        {
            "location_id": str(location_id),
            "base_version_id": str(base_version_id) if base_version_id is not None else None,
        }
    )
    try:
        replay = await find_idempotency_replay(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="training_draft_create",
            key=idempotency_key,
            fingerprint=fingerprint,
            now=now,
        )
        if replay is not None:
            version = await db.scalar(
                select(TrainingVersion).where(
                    TrainingVersion.id == replay.resource_id,
                    TrainingVersion.organization_id == organization_id,
                    TrainingVersion.location_id == location_id,
                )
            )
            if version is None:
                raise RuntimeError("Idempotent Training Version resource is unavailable")
            await db.commit()
            return version

        try:
            draft = await create_training_draft(
                db,
                organization_id=organization_id,
                location_id=location_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                base_version_id=base_version_id,
                _commit=False,
            )
        except APIError as exc:
            if exc.code != "TRAINING_DRAFT_EXISTS":
                raise
            await db.rollback()
            replay = await find_idempotency_replay(
                db,
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="training_draft_create",
                key=idempotency_key,
                fingerprint=fingerprint,
                now=now,
            )
            if replay is None:
                raise
            version = await db.scalar(
                select(TrainingVersion).where(
                    TrainingVersion.id == replay.resource_id,
                    TrainingVersion.organization_id == organization_id,
                    TrainingVersion.location_id == location_id,
                )
            )
            if version is None:
                raise RuntimeError("Idempotent Training Version resource is unavailable") from exc
            await db.commit()
            return cast(TrainingVersion, version)

        decision = await reserve_idempotency(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="training_draft_create",
            key=idempotency_key,
            fingerprint=fingerprint,
            resource_type="training_version",
            resource_id=draft.id,
            response_status=201,
            now=now,
        )
        if decision.replayed and decision.record.resource_id != draft.id:
            raise RuntimeError("Concurrent Training Draft replay selected another resource")
        await db.commit()
        return draft
    except Exception:
        await db.rollback()
        raise


async def update_module(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    module_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    title_uk: str,
    description_uk: str | None,
    required: bool,
) -> TrainingDraftMutation[TrainingModuleVersion]:
    try:
        version = await _lock_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            expected_revision=expected_revision,
        )
        module = await db.scalar(
            select(TrainingModuleVersion).where(
                TrainingModuleVersion.id == module_id,
                TrainingModuleVersion.training_version_id == version.id,
            )
        )
        if module is None:
            raise _resource_not_found()
        translation = await db.scalar(
            select(TrainingModuleTranslation).where(
                TrainingModuleTranslation.training_module_version_id == module.id,
                TrainingModuleTranslation.locale == "uk",
            )
        )
        if translation is None:
            raise RuntimeError("Training Module UA translation invariant is broken")
        translation.title = _bounded_text(title_uk, maximum=200)
        translation.description = _optional_text(description_uk, maximum=2000)
        translation.source_revision += 1
        module.required = required
        en_translation = await db.scalar(
            select(TrainingModuleTranslation).where(
                TrainingModuleTranslation.training_module_version_id == module.id,
                TrainingModuleTranslation.locale == "en",
            )
        )
        if en_translation is not None:
            en_translation.status = "stale"
        version.revision += 1
        _audit(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            action="training_module_updated",
            target_type="training_module_version",
            target_id=module.id,
        )
        await db.commit()
        return TrainingDraftMutation(entity=module, revision=version.revision)
    except Exception:
        await db.rollback()
        raise


async def create_lesson(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    module_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    title_uk: str,
    description_uk: str | None,
    required: bool,
    estimated_minutes: int | None,
) -> TrainingDraftMutation[LessonVersion]:
    try:
        version = await _lock_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            expected_revision=expected_revision,
        )
        module = await db.scalar(
            select(TrainingModuleVersion).where(
                TrainingModuleVersion.id == module_id,
                TrainingModuleVersion.training_version_id == version.id,
            )
        )
        if module is None:
            raise _resource_not_found()
        position = await db.scalar(
            select(func.count(LessonVersion.id)).where(
                LessonVersion.training_module_version_id == module.id
            )
        )
        lesson = Lesson(id=uuid4(), training_module_id=module.training_module_id)
        lesson_version = LessonVersion(
            id=uuid4(),
            training_module_version_id=module.id,
            lesson_id=lesson.id,
            position=position or 0,
            required=required,
            estimated_minutes=_validate_minutes(estimated_minutes),
        )
        db.add_all([lesson, lesson_version])
        await db.flush()
        db.add(
            LessonTranslation(
                id=uuid4(),
                lesson_version_id=lesson_version.id,
                locale="uk",
                status="ready",
                title=_bounded_text(title_uk, maximum=200),
                description=_optional_text(description_uk, maximum=2000),
                source_revision=0,
            )
        )
        version.revision += 1
        _audit(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            action="training_lesson_created",
            target_type="lesson_version",
            target_id=lesson_version.id,
        )
        await db.commit()
        return TrainingDraftMutation(entity=lesson_version, revision=version.revision)
    except Exception:
        await db.rollback()
        raise


async def update_lesson(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    lesson_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    title_uk: str,
    description_uk: str | None,
    required: bool,
    estimated_minutes: int | None,
) -> TrainingDraftMutation[LessonVersion]:
    try:
        version = await _lock_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            expected_revision=expected_revision,
        )
        lesson = await db.scalar(
            select(LessonVersion)
            .join(TrainingModuleVersion)
            .where(
                LessonVersion.lesson_id == lesson_id,
                TrainingModuleVersion.training_version_id == version.id,
            )
        )
        if lesson is None:
            raise _resource_not_found()
        translation = await db.scalar(
            select(LessonTranslation).where(
                LessonTranslation.lesson_version_id == lesson.id,
                LessonTranslation.locale == "uk",
            )
        )
        if translation is None:
            raise RuntimeError("Lesson UA translation invariant is broken")
        translation.title = _bounded_text(title_uk, maximum=200)
        translation.description = _optional_text(description_uk, maximum=2000)
        translation.source_revision += 1
        lesson.required = required
        lesson.estimated_minutes = _validate_minutes(estimated_minutes)
        en_translation = await db.scalar(
            select(LessonTranslation).where(
                LessonTranslation.lesson_version_id == lesson.id,
                LessonTranslation.locale == "en",
            )
        )
        if en_translation is not None:
            en_translation.status = "stale"
        version.revision += 1
        _audit(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            action="training_lesson_updated",
            target_type="lesson_version",
            target_id=lesson.id,
        )
        await db.commit()
        return TrainingDraftMutation(entity=lesson, revision=version.revision)
    except Exception:
        await db.rollback()
        raise


async def delete_lesson(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    lesson_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
) -> int:
    try:
        version = await _lock_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            expected_revision=expected_revision,
        )
        lesson = await db.scalar(
            select(LessonVersion)
            .join(TrainingModuleVersion)
            .where(
                LessonVersion.lesson_id == lesson_id,
                TrainingModuleVersion.training_version_id == version.id,
            )
        )
        if lesson is None:
            raise _resource_not_found()
        if await db.scalar(
            select(LessonContentBlock.id).where(LessonContentBlock.lesson_version_id == lesson.id)
        ):
            raise _lesson_not_empty()
        await db.execute(
            delete(LessonTranslation).where(LessonTranslation.lesson_version_id == lesson.id)
        )
        await db.delete(lesson)
        siblings = list(
            (
                await db.scalars(
                    select(LessonVersion)
                    .where(
                        LessonVersion.training_module_version_id
                        == lesson.training_module_version_id,
                        LessonVersion.id != lesson.id,
                    )
                    .order_by(LessonVersion.position, LessonVersion.id)
                )
            ).all()
        )
        for position, sibling in enumerate(siblings):
            sibling.position = position
        version.revision += 1
        _audit(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            action="training_lesson_deleted",
            target_type="lesson_version",
            target_id=lesson.id,
        )
        await db.commit()
        return version.revision
    except Exception:
        await db.rollback()
        raise


async def reorder_lessons(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    module_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    ordered_ids: list[UUID],
) -> TrainingDraftReorder[LessonVersion]:
    try:
        version = await _lock_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            expected_revision=expected_revision,
        )
        module = await db.scalar(
            select(TrainingModuleVersion).where(
                TrainingModuleVersion.id == module_id,
                TrainingModuleVersion.training_version_id == version.id,
            )
        )
        if module is None:
            raise _resource_not_found()
        lessons = list(
            (
                await db.scalars(
                    select(LessonVersion).where(
                        LessonVersion.training_module_version_id == module.id
                    )
                )
            ).all()
        )
        by_id = {lesson.lesson_id: lesson for lesson in lessons}
        if len(ordered_ids) != len(set(ordered_ids)) or set(ordered_ids) != set(by_id):
            raise _validation_error()
        offset = len(lessons) + 1
        for lesson in lessons:
            lesson.position += offset
        await db.flush()
        ordered = [by_id[lesson_id] for lesson_id in ordered_ids]
        for position, lesson in enumerate(ordered):
            lesson.position = position
        version.revision += 1
        _audit(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            action="training_lesson_reordered",
            target_type="training_module_version",
            target_id=module.id,
        )
        await db.commit()
        return TrainingDraftReorder(entities=ordered, revision=version.revision)
    except Exception:
        await db.rollback()
        raise
