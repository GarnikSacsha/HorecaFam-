from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Asset,
    AuditEvent,
    ContentBlockType,
    LessonContentBlock,
    LessonContentBlockTranslation,
    LessonVersion,
    MenuItemVersion,
    MenuVersion,
    TrainingModuleVersion,
    TrainingVersion,
    TrainingVersionMenuDependency,
)
from app.schemas.training import validate_content_payload
from app.services.training_drafts import (
    TrainingDraftMutation,
    TrainingDraftReorder,
    _lock_draft,
)


@dataclass(frozen=True, slots=True)
class LocalizedPayload:
    payload: dict[str, object]
    content_locale: Literal["uk", "en"]
    translation_fallback: bool


def _error(status_code: int, code: str, message: str) -> APIError:
    return APIError(status_code=status_code, code=code, message=message)


def _resource_not_found() -> APIError:
    return _error(404, "RESOURCE_NOT_FOUND", "Ресурс не знайдено.")


def _validation_error() -> APIError:
    return _error(422, "CONTENT_BLOCK_INVALID", "Блок уроку має неправильний формат.")


def _menu_dependency_invalid() -> APIError:
    return _error(
        409,
        "TRAINING_MENU_DEPENDENCY_INVALID",
        "Блок має посилатися на поточну опубліковану версію меню цієї локації.",
    )


def _asset_not_ready() -> APIError:
    return _error(409, "ASSET_NOT_READY", "Зображення ще не готове до використання.")


async def _lesson_in_version(
    db: AsyncSession,
    *,
    version_id: UUID,
    lesson_id: UUID,
) -> LessonVersion:
    lesson = await db.scalar(
        select(LessonVersion)
        .join(TrainingModuleVersion)
        .where(
            LessonVersion.lesson_id == lesson_id,
            TrainingModuleVersion.training_version_id == version_id,
        )
    )
    if lesson is None:
        raise _resource_not_found()
    return lesson


async def _validate_relational_payload(
    db: AsyncSession,
    *,
    version: TrainingVersion,
    menu_item_id: UUID | None,
    asset_id: UUID | None,
) -> None:
    if menu_item_id is not None:
        dependency = await db.scalar(
            select(TrainingVersionMenuDependency).where(
                TrainingVersionMenuDependency.training_version_id == version.id
            )
        )
        if dependency is None:
            raise _menu_dependency_invalid()
        item = await db.scalar(
            select(MenuItemVersion)
            .join(MenuVersion, MenuVersion.id == MenuItemVersion.menu_version_id)
            .where(
                MenuItemVersion.menu_version_id == dependency.menu_version_id,
                MenuItemVersion.menu_item_id == menu_item_id,
                MenuVersion.status == "published",
                MenuVersion.organization_id == version.organization_id,
                MenuVersion.location_id == version.location_id,
            )
        )
        if item is None:
            raise _menu_dependency_invalid()
    if asset_id is not None:
        asset = await db.scalar(
            select(Asset).where(
                Asset.id == asset_id,
                Asset.organization_id == version.organization_id,
                Asset.location_id == version.location_id,
                Asset.status == "ready",
            )
        )
        if asset is None:
            raise _asset_not_ready()


def _audit(
    db: AsyncSession,
    *,
    version: TrainingVersion,
    actor_user_id: UUID,
    request_id: UUID,
    action: str,
    target_id: UUID,
) -> None:
    db.add(
        AuditEvent(
            organization_id=version.organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action=action,
            target_type="lesson_content_block",
            target_id=target_id,
            old_values=None,
            new_values={"training_version_id": str(version.id), "revision": version.revision},
            request_id=request_id,
            outcome="success",
        )
    )


def resolve_localized_payload(
    block: LessonContentBlock,
    translation: LessonContentBlockTranslation | None,
    *,
    requested_locale: Literal["uk", "en"],
) -> LocalizedPayload:
    if requested_locale == "en" and translation is not None and translation.status == "ready":
        return LocalizedPayload(
            payload=translation.translated_payload,
            content_locale="en",
            translation_fallback=False,
        )
    return LocalizedPayload(
        payload=block.payload,
        content_locale="uk",
        translation_fallback=requested_locale == "en",
    )


async def create_content_block(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    lesson_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    block_type: ContentBlockType,
    payload: dict[str, object],
    expected_revision: int,
) -> TrainingDraftMutation[LessonContentBlock]:
    try:
        version = await _lock_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            expected_revision=expected_revision,
        )
        lesson = await _lesson_in_version(db, version_id=version.id, lesson_id=lesson_id)
        block_kind = ContentBlockType(block_type)
        try:
            canonical, menu_item_id, asset_id = validate_content_payload(block_kind, payload)
        except ValueError as exc:
            raise _validation_error() from exc
        await _validate_relational_payload(
            db,
            version=version,
            menu_item_id=menu_item_id,
            asset_id=asset_id,
        )
        siblings = list(
            (
                await db.scalars(
                    select(LessonContentBlock).where(
                        LessonContentBlock.lesson_version_id == lesson.id
                    )
                )
            ).all()
        )
        block = LessonContentBlock(
            id=uuid4(),
            lesson_version_id=lesson.id,
            type=block_kind.value,
            position=len(siblings),
            payload=canonical,
            menu_item_id=menu_item_id,
            asset_id=asset_id,
        )
        db.add(block)
        version.revision += 1
        _audit(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            action="training_block_created",
            target_id=block.id,
        )
        await db.commit()
        return TrainingDraftMutation(entity=block, revision=version.revision)
    except Exception:
        await db.rollback()
        raise


async def update_content_block(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    block_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    payload: dict[str, object],
    expected_revision: int,
) -> TrainingDraftMutation[LessonContentBlock]:
    try:
        version = await _lock_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            expected_revision=expected_revision,
        )
        block = await db.scalar(
            select(LessonContentBlock)
            .join(LessonVersion)
            .join(TrainingModuleVersion)
            .where(
                LessonContentBlock.id == block_id,
                TrainingModuleVersion.training_version_id == version.id,
            )
        )
        if block is None:
            raise _resource_not_found()
        block_type = ContentBlockType(block.type)
        try:
            canonical, menu_item_id, asset_id = validate_content_payload(block_type, payload)
        except ValueError as exc:
            raise _validation_error() from exc
        await _validate_relational_payload(
            db,
            version=version,
            menu_item_id=menu_item_id,
            asset_id=asset_id,
        )
        block.payload = canonical
        block.menu_item_id = menu_item_id
        block.asset_id = asset_id
        translation = await db.scalar(
            select(LessonContentBlockTranslation).where(
                LessonContentBlockTranslation.lesson_content_block_id == block.id,
                LessonContentBlockTranslation.locale == "en",
            )
        )
        if translation is not None:
            translation.status = "stale"
        version.revision += 1
        _audit(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            action="training_block_updated",
            target_id=block.id,
        )
        await db.commit()
        return TrainingDraftMutation(entity=block, revision=version.revision)
    except Exception:
        await db.rollback()
        raise


async def delete_content_block(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    block_id: UUID,
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
        block = await db.scalar(
            select(LessonContentBlock)
            .join(LessonVersion)
            .join(TrainingModuleVersion)
            .where(
                LessonContentBlock.id == block_id,
                TrainingModuleVersion.training_version_id == version.id,
            )
        )
        if block is None:
            raise _resource_not_found()
        await db.execute(
            delete(LessonContentBlockTranslation).where(
                LessonContentBlockTranslation.lesson_content_block_id == block.id
            )
        )
        siblings = list(
            (
                await db.scalars(
                    select(LessonContentBlock)
                    .where(
                        LessonContentBlock.lesson_version_id == block.lesson_version_id,
                        LessonContentBlock.id != block.id,
                    )
                    .order_by(LessonContentBlock.position, LessonContentBlock.id)
                )
            ).all()
        )
        await db.delete(block)
        offset = len(siblings) + 1
        for sibling in siblings:
            sibling.position += offset
        await db.flush()
        for position, sibling in enumerate(siblings):
            sibling.position = position
        version.revision += 1
        _audit(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            action="training_block_deleted",
            target_id=block.id,
        )
        await db.commit()
        return version.revision
    except Exception:
        await db.rollback()
        raise


async def reorder_content_blocks(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    lesson_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    ordered_ids: list[UUID],
) -> TrainingDraftReorder[LessonContentBlock]:
    try:
        version = await _lock_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            expected_revision=expected_revision,
        )
        lesson = await _lesson_in_version(db, version_id=version.id, lesson_id=lesson_id)
        blocks = list(
            (
                await db.scalars(
                    select(LessonContentBlock).where(
                        LessonContentBlock.lesson_version_id == lesson.id
                    )
                )
            ).all()
        )
        by_id = {block.id: block for block in blocks}
        if len(ordered_ids) != len(set(ordered_ids)) or set(ordered_ids) != set(by_id):
            raise _validation_error()
        offset = len(blocks) + 1
        for block in blocks:
            block.position += offset
        await db.flush()
        ordered = [by_id[block_id] for block_id in ordered_ids]
        for position, block in enumerate(ordered):
            block.position = position
        version.revision += 1
        _audit(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            action="training_block_reordered",
            target_id=lesson.id,
        )
        await db.commit()
        return TrainingDraftReorder(entities=ordered, revision=version.revision)
    except Exception:
        await db.rollback()
        raise
