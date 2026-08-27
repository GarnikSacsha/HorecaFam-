from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    AuditEvent,
    MenuImport,
    MenuImportFinding,
    MenuItemVersion,
    MenuItemVersionTranslation,
    MenuVersion,
    MenuVersionCategory,
    MenuVersionCategoryTranslation,
    MenuVersionItemDelta,
    MenuVersionSection,
    MenuVersionSectionTranslation,
)
from app.schemas.menu import (
    MenuApplicabilityCounts,
    MenuDiffCounts,
    MenuPublishResponse,
    MenuReadinessIssue,
    MenuReadinessResponse,
    MenuTrainingImpactCounts,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.menus import _replace_delta, _version_summary


def _not_found() -> APIError:
    return APIError(status_code=404, code="RESOURCE_NOT_FOUND", message="Ресурс не знайдено.")


def _revision_conflict() -> APIError:
    return APIError(
        status_code=409,
        code="REVISION_CONFLICT",
        message="Чернетку меню вже змінено. Оновіть дані та повторіть дію.",
    )


def _issue(
    code: str,
    message: str,
    entity_type: str,
    entity_id: UUID | None,
) -> MenuReadinessIssue:
    return MenuReadinessIssue(
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
) -> MenuVersion:
    query = select(MenuVersion).where(
        MenuVersion.id == version_id,
        MenuVersion.organization_id == organization_id,
        MenuVersion.location_id == location_id,
    )
    if lock:
        query = query.with_for_update()
    version = await db.scalar(query)
    if version is None:
        raise _not_found()
    return version


async def _readiness_for_version(
    db: AsyncSession,
    version: MenuVersion,
) -> MenuReadinessResponse:
    blockers: list[MenuReadinessIssue] = []
    warnings: list[MenuReadinessIssue] = []
    if version.status != "draft":
        blockers.append(
            _issue(
                "VERSION_IMMUTABLE",
                "Лише чернетку меню можна опублікувати.",
                "menu_version",
                version.id,
            )
        )

    current = await db.scalar(
        select(MenuVersion).where(
            MenuVersion.menu_id == version.menu_id,
            MenuVersion.status == "published",
        )
    )
    current_id = current.id if current is not None else None
    if version.status == "draft" and version.base_version_id != current_id:
        blockers.append(
            _issue(
                "STALE_DRAFT_BASE",
                "Чернетка створена не з поточної опублікованої версії.",
                "menu_version",
                version.id,
            )
        )

    sections = list(
        (
            await db.scalars(
                select(MenuVersionSection).where(MenuVersionSection.menu_version_id == version.id)
            )
        ).all()
    )
    categories = list(
        (
            await db.scalars(
                select(MenuVersionCategory).where(MenuVersionCategory.menu_version_id == version.id)
            )
        ).all()
    )
    items = list(
        (
            await db.scalars(
                select(MenuItemVersion).where(MenuItemVersion.menu_version_id == version.id)
            )
        ).all()
    )
    if not sections or not categories or not items:
        blockers.append(
            _issue(
                "MENU_EMPTY",
                "Меню має містити щонайменше один розділ, категорію та позицію.",
                "menu_version",
                version.id,
            )
        )

    section_translation_ids = set(
        (
            await db.scalars(
                select(MenuVersionSectionTranslation.menu_version_section_id).where(
                    MenuVersionSectionTranslation.menu_version_id == version.id,
                    MenuVersionSectionTranslation.locale == "uk",
                    MenuVersionSectionTranslation.status == "ready",
                )
            )
        ).all()
    )
    category_translation_ids = set(
        (
            await db.scalars(
                select(MenuVersionCategoryTranslation.menu_version_category_id).where(
                    MenuVersionCategoryTranslation.menu_version_id == version.id,
                    MenuVersionCategoryTranslation.locale == "uk",
                    MenuVersionCategoryTranslation.status == "ready",
                )
            )
        ).all()
    )
    item_translation_ids = set(
        (
            await db.scalars(
                select(MenuItemVersionTranslation.menu_item_version_id).where(
                    MenuItemVersionTranslation.menu_version_id == version.id,
                    MenuItemVersionTranslation.locale == "uk",
                    MenuItemVersionTranslation.status == "ready",
                )
            )
        ).all()
    )
    english_item_translation_ids = set(
        (
            await db.scalars(
                select(MenuItemVersionTranslation.menu_item_version_id).where(
                    MenuItemVersionTranslation.menu_version_id == version.id,
                    MenuItemVersionTranslation.locale == "en",
                    MenuItemVersionTranslation.status == "ready",
                )
            )
        ).all()
    )
    for entity_type, rows, translated_ids in (
        ("menu_section", sections, section_translation_ids),
        ("menu_category", categories, category_translation_ids),
        ("menu_item", items, item_translation_ids),
    ):
        for row in rows:
            if row.id not in translated_ids:
                blockers.append(
                    _issue(
                        "UA_CONTENT_NOT_READY",
                        "Обов’язковий український текст не готовий.",
                        entity_type,
                        row.id,
                    )
                )

    for item in items:
        if item.id not in english_item_translation_ids:
            warnings.append(
                _issue(
                    "EN_TRANSLATION_PENDING",
                    "Англійський переклад ще не готовий; український текст буде основним.",
                    "menu_item",
                    item.menu_item_id,
                )
            )
        if item.component_data_status == "unknown" or item.allergen_data_status == "unknown":
            blockers.append(
                _issue(
                    "FACTS_UNCONFIRMED",
                    "Склад і алергени позиції мають бути підтверджені.",
                    "menu_item",
                    item.menu_item_id,
                )
            )

    confirmed_import = await db.scalar(
        select(MenuImport).where(MenuImport.confirmed_menu_version_id == version.id)
    )
    if confirmed_import is not None:
        invalid_findings = list(
            (
                await db.scalars(
                    select(MenuImportFinding).where(
                        MenuImportFinding.menu_import_id == confirmed_import.id,
                        (
                            (MenuImportFinding.severity == "blocker")
                            | (
                                (MenuImportFinding.severity == "requires_review")
                                & (MenuImportFinding.resolution_status != "resolved")
                            )
                        ),
                    )
                )
            ).all()
        )
        for finding in invalid_findings:
            blockers.append(
                _issue(
                    "IMPORT_FINDING_UNRESOLVED",
                    "Імпорт містить невирішену знахідку.",
                    finding.entity_type,
                    None,
                )
            )

    return MenuReadinessResponse(
        menu_id=version.menu_id,
        menu_version_id=version.id,
        organization_id=version.organization_id,
        location_id=version.location_id,
        revision=version.revision,
        can_publish=not blockers,
        blocking_errors=sorted(
            blockers,
            key=lambda value: (value.code, value.entity_type, str(value.entity_id or "")),
        ),
        warnings=warnings,
        required_training_asset_count=0,
        ready_training_asset_count=0,
        applicable_training_content_count=0,
    )


async def get_menu_readiness(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
) -> MenuReadinessResponse:
    version = await _scoped_version(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
    )
    return await _readiness_for_version(db, version)


async def _persist_complete_diff(db: AsyncSession, version: MenuVersion) -> None:
    current_items = list(
        (
            await db.scalars(
                select(MenuItemVersion).where(MenuItemVersion.menu_version_id == version.id)
            )
        ).all()
    )
    current_ids = {item.menu_item_id for item in current_items}
    for item in current_items:
        await _replace_delta(
            db,
            version=version,
            menu_item_id=item.menu_item_id,
            current=item,
        )
    if version.base_version_id is not None:
        base_ids = set(
            (
                await db.scalars(
                    select(MenuItemVersion.menu_item_id).where(
                        MenuItemVersion.menu_version_id == version.base_version_id
                    )
                )
            ).all()
        )
        for removed_id in base_ids - current_ids:
            await _replace_delta(
                db,
                version=version,
                menu_item_id=removed_id,
                current=None,
            )


async def _publication_response(
    db: AsyncSession,
    version: MenuVersion,
) -> MenuPublishResponse:
    diff_rows = (
        await db.execute(
            select(MenuVersionItemDelta.delta_kind, func.count())
            .where(MenuVersionItemDelta.menu_version_id == version.id)
            .group_by(MenuVersionItemDelta.delta_kind)
        )
    ).all()
    impact_rows = (
        await db.execute(
            select(MenuVersionItemDelta.training_impact, func.count())
            .where(MenuVersionItemDelta.menu_version_id == version.id)
            .group_by(MenuVersionItemDelta.training_impact)
        )
    ).all()
    diffs = {kind: count for kind, count in diff_rows}
    impacts = {kind: count for kind, count in impact_rows}
    return MenuPublishResponse(
        published=await _version_summary(db, version=version),
        previous_published_version_id=version.base_version_id,
        diff_counts=MenuDiffCounts(
            added=diffs.get("added", 0),
            changed=diffs.get("changed", 0),
            removed=diffs.get("removed", 0),
            unchanged=diffs.get("unchanged", 0),
        ),
        training_impact_counts=MenuTrainingImpactCounts(
            none=impacts.get("none", 0),
            review=impacts.get("review", 0),
            required=impacts.get("required", 0),
        ),
        applicability=MenuApplicabilityCounts(
            published_content_count=0,
            assignment_count=0,
            notification_count=0,
        ),
    )


async def publish_menu_version(
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
) -> MenuPublishResponse:
    fingerprint = request_fingerprint(
        {"version_id": str(version_id), "expected_revision": expected_revision}
    )
    try:
        replay = await find_idempotency_replay(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="menu_version_publish",
            key=idempotency_key,
            fingerprint=fingerprint,
            now=now,
        )
        version = await _scoped_version(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            lock=True,
        )
        if replay is not None:
            if version.status != "published":
                raise RuntimeError("Idempotent publication resource is unavailable")
            await db.commit()
            return await _publication_response(db, version)
        if version.status != "draft" or version.revision != expected_revision:
            raise _revision_conflict()
        readiness = await _readiness_for_version(db, version)
        if not readiness.can_publish:
            raise APIError(
                status_code=409,
                code="MENU_NOT_READY",
                message="Чернетка меню не пройшла перевірку готовності.",
            )
        previous = await db.scalar(
            select(MenuVersion)
            .where(MenuVersion.menu_id == version.menu_id, MenuVersion.status == "published")
            .with_for_update()
        )
        if (previous.id if previous is not None else None) != version.base_version_id:
            raise _revision_conflict()
        await _persist_complete_diff(db, version)
        if previous is not None:
            previous.status = "archived"
            previous.archived_at = now
            await db.flush()
        version.status = "published"
        version.published_by_user_id = actor_user_id
        version.published_at = now
        await db.flush()
        await reserve_idempotency(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="menu_version_publish",
            key=idempotency_key,
            fingerprint=fingerprint,
            resource_type="menu_version",
            resource_id=version.id,
            response_status=200,
            now=now,
        )
        db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_type="user",
                action="menu_version_published",
                target_type="menu_version",
                target_id=version.id,
                old_values=None,
                new_values={
                    "location_id": str(location_id),
                    "previous_published_version_id": (
                        str(previous.id) if previous is not None else None
                    ),
                    "applicable_training_content_count": 0,
                    "assignment_count": 0,
                    "notification_count": 0,
                },
                request_id=request_id,
                outcome="success",
            )
        )
        await db.commit()
        return await _publication_response(db, version)
    except Exception:
        await db.rollback()
        raise
