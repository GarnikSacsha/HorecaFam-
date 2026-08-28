from typing import Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Asset,
    ContentBlockType,
    LessonContentBlock,
    LessonContentBlockTranslation,
    LessonTranslation,
    LessonVersion,
    Training,
    TrainingModule,
    TrainingModuleTranslation,
    TrainingModuleVersion,
    TrainingVersion,
)
from app.schemas.training import (
    EmployeeTrainingContentBlock,
    EmployeeTrainingLessonDetail,
    EmployeeTrainingLessonSummary,
    EmployeeTrainingModuleDetail,
    EmployeeTrainingModuleSummary,
    EmployeeTrainingReferenceResponse,
    EmployeeTrainingSummary,
)
from app.services.private_storage import PrivateStorage
from app.services.training_assets import ACCESS_EXPIRES_SECONDS
from app.services.training_content import resolve_localized_payload


def _not_found() -> APIError:
    return APIError(
        status_code=404,
        code="RESOURCE_NOT_FOUND",
        message="Ресурс не знайдено.",
    )


async def _current_training_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
) -> tuple[Training, TrainingVersion] | None:
    row = (
        await db.execute(
            select(Training, TrainingVersion)
            .join(TrainingVersion, TrainingVersion.training_id == Training.id)
            .where(
                Training.organization_id == organization_id,
                Training.location_id == location_id,
                TrainingVersion.status == "published",
            )
        )
    ).one_or_none()
    if row is None:
        return None
    return row[0], row[1]


def _localized_entity(
    uk: TrainingModuleTranslation | LessonTranslation,
    en: TrainingModuleTranslation | LessonTranslation | None,
    requested_locale: Literal["uk", "en"],
) -> tuple[str, str | None, Literal["uk", "en"], bool]:
    if requested_locale == "en" and en is not None and en.status == "ready":
        return en.title, en.description, "en", False
    return uk.title, uk.description, "uk", requested_locale == "en"


async def _module_summaries(
    db: AsyncSession,
    *,
    version: TrainingVersion,
    requested_locale: Literal["uk", "en"],
) -> list[EmployeeTrainingModuleSummary]:
    rows = (
        await db.execute(
            select(TrainingModuleVersion, TrainingModule)
            .join(TrainingModule, TrainingModule.id == TrainingModuleVersion.training_module_id)
            .where(TrainingModuleVersion.training_version_id == version.id)
            .order_by(TrainingModuleVersion.position, TrainingModuleVersion.id)
        )
    ).all()
    summaries: list[EmployeeTrainingModuleSummary] = []
    for module_version, module in rows:
        translations = list(
            (
                await db.scalars(
                    select(TrainingModuleTranslation).where(
                        TrainingModuleTranslation.training_module_version_id == module_version.id
                    )
                )
            ).all()
        )
        uk = next((row for row in translations if row.locale == "uk"), None)
        if uk is None:
            raise RuntimeError("Published Training Module has no UA translation")
        en = next((row for row in translations if row.locale == "en"), None)
        title, description, content_locale, fallback = _localized_entity(uk, en, requested_locale)
        lesson_count = int(
            await db.scalar(
                select(func.count(LessonVersion.id)).where(
                    LessonVersion.training_module_version_id == module_version.id
                )
            )
            or 0
        )
        summaries.append(
            EmployeeTrainingModuleSummary(
                id=module.id,
                domain_type=module.domain_type,
                title=title,
                description=description,
                position=module_version.position,
                required=module_version.required,
                lesson_count=lesson_count,
                content_locale=content_locale,
                translation_fallback=fallback,
            )
        )
    return summaries


async def list_employee_training(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    requested_locale: Literal["uk", "en"],
) -> EmployeeTrainingReferenceResponse:
    current = await _current_training_version(
        db,
        organization_id=organization_id,
        location_id=location_id,
    )
    if current is None:
        return EmployeeTrainingReferenceResponse(
            training=None,
            modules=[],
            content_locale=requested_locale,
            translation_fallback=False,
        )
    training, version = current
    if version.published_at is None:
        raise RuntimeError("Published Training Version has no publication timestamp")
    modules = await _module_summaries(
        db,
        version=version,
        requested_locale=requested_locale,
    )
    return EmployeeTrainingReferenceResponse(
        training=EmployeeTrainingSummary(
            id=training.id,
            version_number=version.version_number,
            published_at=version.published_at,
        ),
        modules=modules,
        content_locale=(
            "en"
            if requested_locale == "en" and all(module.content_locale == "en" for module in modules)
            else "uk"
        ),
        translation_fallback=(
            requested_locale == "en" and any(module.translation_fallback for module in modules)
        ),
    )


async def _lesson_summaries(
    db: AsyncSession,
    *,
    module_version_id: UUID,
    requested_locale: Literal["uk", "en"],
) -> list[EmployeeTrainingLessonSummary]:
    lessons = list(
        (
            await db.scalars(
                select(LessonVersion)
                .where(LessonVersion.training_module_version_id == module_version_id)
                .order_by(LessonVersion.position, LessonVersion.id)
            )
        ).all()
    )
    summaries: list[EmployeeTrainingLessonSummary] = []
    for lesson in lessons:
        translations = list(
            (
                await db.scalars(
                    select(LessonTranslation).where(
                        LessonTranslation.lesson_version_id == lesson.id
                    )
                )
            ).all()
        )
        uk = next((row for row in translations if row.locale == "uk"), None)
        if uk is None:
            raise RuntimeError("Published Lesson has no UA translation")
        en = next((row for row in translations if row.locale == "en"), None)
        title, description, content_locale, fallback = _localized_entity(uk, en, requested_locale)
        summaries.append(
            EmployeeTrainingLessonSummary(
                id=lesson.lesson_id,
                title=title,
                description=description,
                position=lesson.position,
                required=lesson.required,
                estimated_minutes=lesson.estimated_minutes,
                content_locale=content_locale,
                translation_fallback=fallback,
            )
        )
    return summaries


async def get_employee_training_module(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    module_id: UUID,
    requested_locale: Literal["uk", "en"],
) -> EmployeeTrainingModuleDetail:
    current = await _current_training_version(
        db,
        organization_id=organization_id,
        location_id=location_id,
    )
    if current is None:
        raise _not_found()
    _training, version = current
    module_version = await db.scalar(
        select(TrainingModuleVersion).where(
            TrainingModuleVersion.training_version_id == version.id,
            TrainingModuleVersion.training_module_id == module_id,
        )
    )
    if module_version is None:
        raise _not_found()
    summaries = await _module_summaries(
        db,
        version=version,
        requested_locale=requested_locale,
    )
    summary = next((item for item in summaries if item.id == module_id), None)
    if summary is None:
        raise _not_found()
    return EmployeeTrainingModuleDetail(
        **summary.model_dump(),
        lessons=await _lesson_summaries(
            db,
            module_version_id=module_version.id,
            requested_locale=requested_locale,
        ),
    )


async def get_employee_training_lesson(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    lesson_id: UUID,
    requested_locale: Literal["uk", "en"],
) -> EmployeeTrainingLessonDetail:
    current = await _current_training_version(
        db,
        organization_id=organization_id,
        location_id=location_id,
    )
    if current is None:
        raise _not_found()
    _training, version = current
    lesson = await db.scalar(
        select(LessonVersion)
        .join(TrainingModuleVersion)
        .where(
            TrainingModuleVersion.training_version_id == version.id,
            LessonVersion.lesson_id == lesson_id,
        )
    )
    if lesson is None:
        raise _not_found()
    summaries = await _lesson_summaries(
        db,
        module_version_id=lesson.training_module_version_id,
        requested_locale=requested_locale,
    )
    summary = next((item for item in summaries if item.id == lesson_id), None)
    if summary is None:
        raise _not_found()
    blocks = list(
        (
            await db.scalars(
                select(LessonContentBlock)
                .where(LessonContentBlock.lesson_version_id == lesson.id)
                .order_by(LessonContentBlock.position, LessonContentBlock.id)
            )
        ).all()
    )
    block_responses: list[EmployeeTrainingContentBlock] = []
    for block in blocks:
        translation = await db.scalar(
            select(LessonContentBlockTranslation).where(
                LessonContentBlockTranslation.lesson_content_block_id == block.id,
                LessonContentBlockTranslation.locale == "en",
            )
        )
        localized = resolve_localized_payload(
            block,
            translation,
            requested_locale=requested_locale,
        )
        payload = dict(localized.payload)
        if block.type == ContentBlockType.MENU_ITEM_CARD.value:
            payload["menu_item_id"] = block.menu_item_id
        elif block.type == ContentBlockType.IMAGE.value:
            payload["asset_id"] = block.asset_id
        block_responses.append(
            EmployeeTrainingContentBlock(
                id=block.id,
                type=block.type,
                position=block.position,
                payload=payload,
                content_locale=localized.content_locale,
                translation_fallback=localized.translation_fallback,
            )
        )
    return EmployeeTrainingLessonDetail(
        **summary.model_dump(),
        content_blocks=block_responses,
    )


async def get_employee_training_asset_access(
    db: AsyncSession,
    *,
    storage: PrivateStorage,
    organization_id: UUID,
    location_id: UUID,
    asset_id: UUID,
) -> str:
    asset = await db.scalar(
        select(Asset)
        .join(LessonContentBlock, LessonContentBlock.asset_id == Asset.id)
        .join(LessonVersion, LessonVersion.id == LessonContentBlock.lesson_version_id)
        .join(
            TrainingModuleVersion,
            TrainingModuleVersion.id == LessonVersion.training_module_version_id,
        )
        .join(TrainingVersion, TrainingVersion.id == TrainingModuleVersion.training_version_id)
        .where(
            Asset.id == asset_id,
            Asset.organization_id == organization_id,
            Asset.location_id == location_id,
            Asset.status == "ready",
            TrainingVersion.organization_id == organization_id,
            TrainingVersion.location_id == location_id,
            TrainingVersion.status == "published",
        )
    )
    if asset is None:
        raise _not_found()
    return await storage.create_download_url(
        object_key=asset.object_key,
        expires_seconds=ACCESS_EXPIRES_SECONDS,
    )
