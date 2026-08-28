from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Asset,
    LessonContentBlock,
    LessonTranslation,
    LessonVersion,
    Location,
    TrainingModule,
    TrainingModuleTranslation,
    TrainingModuleVersion,
    TrainingVersion,
    TrainingVersionMenuDependency,
)
from app.schemas.training import (
    TrainingAssetResponse,
    TrainingContentBlockResponse,
    TrainingLessonResponse,
    TrainingModuleResponse,
    TrainingVersionCollection,
    TrainingVersionDetail,
    TrainingVersionSummary,
)


def _resource_not_found() -> APIError:
    return APIError(
        status_code=404,
        code="RESOURCE_NOT_FOUND",
        message="Ресурс не знайдено.",
    )


def training_asset_response(asset: Asset) -> TrainingAssetResponse:
    return TrainingAssetResponse(
        id=asset.id,
        original_filename=asset.original_filename,
        mime_type=asset.mime_type,
        size_bytes=asset.size_bytes,
        status=asset.status,
        ready_at=asset.ready_at,
        created_at=asset.created_at,
    )


async def _summary(db: AsyncSession, version: TrainingVersion) -> TrainingVersionSummary:
    module_count = int(
        await db.scalar(
            select(func.count(TrainingModuleVersion.id)).where(
                TrainingModuleVersion.training_version_id == version.id
            )
        )
        or 0
    )
    lesson_count = int(
        await db.scalar(
            select(func.count(LessonVersion.id))
            .join(TrainingModuleVersion)
            .where(TrainingModuleVersion.training_version_id == version.id)
        )
        or 0
    )
    return TrainingVersionSummary(
        id=version.id,
        training_id=version.training_id,
        location_id=version.location_id,
        version_number=version.version_number,
        status=version.status,
        revision=version.revision,
        base_version_id=version.base_version_id,
        module_count=module_count,
        lesson_count=lesson_count,
        created_at=version.created_at,
        published_at=version.published_at,
        archived_at=version.archived_at,
    )


async def list_training_versions(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
) -> TrainingVersionCollection:
    location_exists = await db.scalar(
        select(Location.id).where(
            Location.id == location_id,
            Location.organization_id == organization_id,
        )
    )
    if location_exists is None:
        raise _resource_not_found()
    versions = list(
        (
            await db.scalars(
                select(TrainingVersion)
                .where(
                    TrainingVersion.organization_id == organization_id,
                    TrainingVersion.location_id == location_id,
                )
                .order_by(TrainingVersion.version_number.desc())
            )
        ).all()
    )
    summaries = [await _summary(db, version) for version in versions]
    return TrainingVersionCollection(
        published=next((item for item in summaries if item.status == "published"), None),
        draft=next((item for item in summaries if item.status == "draft"), None),
        archived=[item for item in summaries if item.status == "archived"],
    )


async def get_training_version_detail(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
) -> TrainingVersionDetail:
    version = await db.scalar(
        select(TrainingVersion).where(
            TrainingVersion.id == version_id,
            TrainingVersion.organization_id == organization_id,
            TrainingVersion.location_id == location_id,
        )
    )
    if version is None:
        raise _resource_not_found()

    modules = list(
        (
            await db.scalars(
                select(TrainingModuleVersion)
                .where(TrainingModuleVersion.training_version_id == version.id)
                .order_by(TrainingModuleVersion.position, TrainingModuleVersion.id)
            )
        ).all()
    )
    module_responses: list[TrainingModuleResponse] = []
    for module_version in modules:
        module = await db.get(TrainingModule, module_version.training_module_id)
        if module is None:
            raise RuntimeError("Training Module identity invariant is broken")
        translations = list(
            (
                await db.scalars(
                    select(TrainingModuleTranslation).where(
                        TrainingModuleTranslation.training_module_version_id == module_version.id
                    )
                )
            ).all()
        )
        uk_module = next((row for row in translations if row.locale == "uk"), None)
        if uk_module is None:
            raise RuntimeError("Training Module UA translation invariant is broken")
        en_module = next((row for row in translations if row.locale == "en"), None)
        lessons = list(
            (
                await db.scalars(
                    select(LessonVersion)
                    .where(LessonVersion.training_module_version_id == module_version.id)
                    .order_by(LessonVersion.position, LessonVersion.id)
                )
            ).all()
        )
        lesson_responses: list[TrainingLessonResponse] = []
        for lesson_version in lessons:
            lesson_translations = list(
                (
                    await db.scalars(
                        select(LessonTranslation).where(
                            LessonTranslation.lesson_version_id == lesson_version.id
                        )
                    )
                ).all()
            )
            uk_lesson = next((row for row in lesson_translations if row.locale == "uk"), None)
            if uk_lesson is None:
                raise RuntimeError("Lesson UA translation invariant is broken")
            en_lesson = next((row for row in lesson_translations if row.locale == "en"), None)
            blocks = list(
                (
                    await db.scalars(
                        select(LessonContentBlock)
                        .where(LessonContentBlock.lesson_version_id == lesson_version.id)
                        .order_by(LessonContentBlock.position, LessonContentBlock.id)
                    )
                ).all()
            )
            block_responses: list[TrainingContentBlockResponse] = []
            for block in blocks:
                asset = await db.get(Asset, block.asset_id) if block.asset_id is not None else None
                block_responses.append(
                    TrainingContentBlockResponse(
                        id=block.id,
                        type=block.type,
                        position=block.position,
                        payload=block.payload,
                        menu_item_id=block.menu_item_id,
                        asset=training_asset_response(asset) if asset is not None else None,
                    )
                )
            lesson_responses.append(
                TrainingLessonResponse(
                    id=lesson_version.lesson_id,
                    position=lesson_version.position,
                    title_uk=uk_lesson.title,
                    description_uk=uk_lesson.description,
                    required=lesson_version.required,
                    estimated_minutes=lesson_version.estimated_minutes,
                    translation_status_en=en_lesson.status if en_lesson is not None else None,
                    content_blocks=block_responses,
                )
            )
        module_responses.append(
            TrainingModuleResponse(
                id=module_version.id,
                domain_type=module.domain_type,
                position=module_version.position,
                title_uk=uk_module.title,
                description_uk=uk_module.description,
                required=module_version.required,
                translation_status_en=en_module.status if en_module is not None else None,
                lessons=lesson_responses,
            )
        )

    summary = await _summary(db, version)
    dependency = await db.scalar(
        select(TrainingVersionMenuDependency).where(
            TrainingVersionMenuDependency.training_version_id == version.id
        )
    )
    return TrainingVersionDetail(
        **summary.model_dump(),
        modules=module_responses,
        menu_version_id=dependency.menu_version_id if dependency is not None else None,
    )
