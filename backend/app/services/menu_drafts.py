from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    AuditEvent,
    Location,
    Menu,
    MenuCategory,
    MenuComponentVersion,
    MenuComponentVersionTranslation,
    MenuItemVersion,
    MenuItemVersionAllergen,
    MenuItemVersionComponent,
    MenuItemVersionTranslation,
    MenuSection,
    MenuVersion,
    MenuVersionCategory,
    MenuVersionCategoryTranslation,
    MenuVersionSection,
    MenuVersionSectionTranslation,
)


@dataclass(frozen=True, slots=True)
class DraftMutationResult[EntityT]:
    entity: EntityT
    revision: int


@dataclass(frozen=True, slots=True)
class DraftReorderResult[EntityT]:
    entities: list[EntityT]
    revision: int


@dataclass(frozen=True, slots=True)
class CategoryHierarchy:
    id: UUID
    stable_code: str | None
    name_uk: str
    position: int
    item_count: int


@dataclass(frozen=True, slots=True)
class SectionHierarchy:
    id: UUID
    stable_code: str | None
    name_uk: str
    position: int
    categories: list[CategoryHierarchy]


@dataclass(frozen=True, slots=True)
class MenuVersionHierarchy:
    version: MenuVersion
    sections: list[SectionHierarchy]
    section_count: int
    category_count: int
    item_count: int


class _Unset:
    pass


UNSET = _Unset()


def _resource_not_found() -> APIError:
    return APIError(status_code=404, code="RESOURCE_NOT_FOUND", message="Ресурс не знайдено.")


def _draft_exists() -> APIError:
    return APIError(
        status_code=409,
        code="MENU_DRAFT_EXISTS",
        message="Для цього закладу вже існує чернетка меню.",
    )


def _immutable() -> APIError:
    return APIError(
        status_code=409,
        code="VERSION_IMMUTABLE",
        message="Опубліковану або архівну версію меню не можна змінювати.",
    )


def _revision_conflict() -> APIError:
    return APIError(
        status_code=409,
        code="REVISION_CONFLICT",
        message="Чернетку меню вже змінено. Оновіть дані та повторіть дію.",
    )


def _validation_error() -> APIError:
    return APIError(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Перевірте правильність заповнення полів.",
    )


def _normalize_stable_code(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized or len(normalized) > 100:
        raise _validation_error()
    return normalized


def _validate_name(name: str) -> str:
    normalized = name.strip()
    if not normalized or len(normalized) > 200:
        raise _validation_error()
    return normalized


async def _lock_draft(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    expected_revision: int,
) -> MenuVersion:
    version = await db.scalar(
        select(MenuVersion)
        .where(
            MenuVersion.id == version_id,
            MenuVersion.organization_id == organization_id,
            MenuVersion.location_id == location_id,
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


def _audit_mutation(
    db: AsyncSession,
    *,
    version: MenuVersion,
    actor_user_id: UUID,
    request_id: UUID,
    entity_type: str,
    entity_id: UUID,
) -> None:
    db.add(
        AuditEvent(
            organization_id=version.organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="menu_draft_mutated",
            target_type=entity_type,
            target_id=entity_id,
            old_values=None,
            new_values={"menu_version_id": str(version.id), "revision": version.revision},
            request_id=request_id,
            outcome="success",
        )
    )


async def _copy_version_graph(
    db: AsyncSession,
    *,
    source: MenuVersion,
    target: MenuVersion,
) -> None:
    section_map: dict[UUID, MenuVersionSection] = {}
    source_sections = list(
        (
            await db.scalars(
                select(MenuVersionSection)
                .where(MenuVersionSection.menu_version_id == source.id)
                .order_by(MenuVersionSection.position, MenuVersionSection.id)
            )
        ).all()
    )
    for old in source_sections:
        copied = MenuVersionSection(
            id=uuid4(),
            organization_id=target.organization_id,
            location_id=target.location_id,
            menu_id=target.menu_id,
            menu_version_id=target.id,
            menu_section_id=old.menu_section_id,
            position=old.position,
        )
        section_map[old.id] = copied
        db.add(copied)
    await db.flush()

    section_translations = list(
        (
            await db.scalars(
                select(MenuVersionSectionTranslation).where(
                    MenuVersionSectionTranslation.menu_version_id == source.id
                )
            )
        ).all()
    )
    db.add_all(
        [
            MenuVersionSectionTranslation(
                id=uuid4(),
                organization_id=target.organization_id,
                location_id=target.location_id,
                menu_id=target.menu_id,
                menu_version_id=target.id,
                menu_version_section_id=section_map[old.menu_version_section_id].id,
                locale=old.locale,
                status=old.status,
                name=old.name,
            )
            for old in section_translations
        ]
    )

    category_map: dict[UUID, MenuVersionCategory] = {}
    source_categories = list(
        (
            await db.scalars(
                select(MenuVersionCategory)
                .where(MenuVersionCategory.menu_version_id == source.id)
                .order_by(MenuVersionCategory.position, MenuVersionCategory.id)
            )
        ).all()
    )
    for old_category in source_categories:
        copied_category = MenuVersionCategory(
            id=uuid4(),
            organization_id=target.organization_id,
            location_id=target.location_id,
            menu_id=target.menu_id,
            menu_version_id=target.id,
            menu_category_id=old_category.menu_category_id,
            menu_version_section_id=section_map[old_category.menu_version_section_id].id,
            position=old_category.position,
        )
        category_map[old_category.id] = copied_category
        db.add(copied_category)
    await db.flush()

    category_translations = list(
        (
            await db.scalars(
                select(MenuVersionCategoryTranslation).where(
                    MenuVersionCategoryTranslation.menu_version_id == source.id
                )
            )
        ).all()
    )
    db.add_all(
        [
            MenuVersionCategoryTranslation(
                id=uuid4(),
                organization_id=target.organization_id,
                location_id=target.location_id,
                menu_id=target.menu_id,
                menu_version_id=target.id,
                menu_version_category_id=category_map[old.menu_version_category_id].id,
                locale=old.locale,
                status=old.status,
                name=old.name,
            )
            for old in category_translations
        ]
    )

    component_map: dict[UUID, MenuComponentVersion] = {}
    source_components = list(
        (
            await db.scalars(
                select(MenuComponentVersion).where(
                    MenuComponentVersion.menu_version_id == source.id
                )
            )
        ).all()
    )
    for old_component in source_components:
        copied_component = MenuComponentVersion(
            id=uuid4(),
            organization_id=target.organization_id,
            location_id=target.location_id,
            menu_id=target.menu_id,
            menu_version_id=target.id,
            menu_component_id=old_component.menu_component_id,
        )
        component_map[old_component.id] = copied_component
        db.add(copied_component)
    await db.flush()

    component_translations = list(
        (
            await db.scalars(
                select(MenuComponentVersionTranslation).where(
                    MenuComponentVersionTranslation.menu_version_id == source.id
                )
            )
        ).all()
    )
    db.add_all(
        [
            MenuComponentVersionTranslation(
                id=uuid4(),
                organization_id=target.organization_id,
                location_id=target.location_id,
                menu_id=target.menu_id,
                menu_version_id=target.id,
                menu_component_version_id=component_map[old.menu_component_version_id].id,
                locale=old.locale,
                status=old.status,
                name=old.name,
            )
            for old in component_translations
        ]
    )

    item_map: dict[UUID, MenuItemVersion] = {}
    source_items = list(
        (
            await db.scalars(
                select(MenuItemVersion)
                .where(MenuItemVersion.menu_version_id == source.id)
                .order_by(MenuItemVersion.position, MenuItemVersion.id)
            )
        ).all()
    )
    for old_item in source_items:
        copied_item = MenuItemVersion(
            id=uuid4(),
            organization_id=target.organization_id,
            location_id=target.location_id,
            menu_id=target.menu_id,
            menu_version_id=target.id,
            menu_item_id=old_item.menu_item_id,
            menu_version_category_id=category_map[old_item.menu_version_category_id].id,
            position=old_item.position,
            availability=old_item.availability,
            price_minor=old_item.price_minor,
            currency=old_item.currency,
            component_data_status=old_item.component_data_status,
            allergen_data_status=old_item.allergen_data_status,
            source_kind=old_item.source_kind,
            source_reference=old_item.source_reference,
            source_item_key=old_item.source_item_key,
            verified_by_user_id=old_item.verified_by_user_id,
            verified_at=old_item.verified_at,
        )
        item_map[old_item.id] = copied_item
        db.add(copied_item)
    await db.flush()

    item_translations = list(
        (
            await db.scalars(
                select(MenuItemVersionTranslation).where(
                    MenuItemVersionTranslation.menu_version_id == source.id
                )
            )
        ).all()
    )
    db.add_all(
        [
            MenuItemVersionTranslation(
                id=uuid4(),
                organization_id=target.organization_id,
                location_id=target.location_id,
                menu_id=target.menu_id,
                menu_version_id=target.id,
                menu_item_version_id=item_map[old.menu_item_version_id].id,
                locale=old.locale,
                status=old.status,
                name=old.name,
                description=old.description,
            )
            for old in item_translations
        ]
    )

    source_component_links = list(
        (
            await db.scalars(
                select(MenuItemVersionComponent).where(
                    MenuItemVersionComponent.menu_version_id == source.id
                )
            )
        ).all()
    )
    db.add_all(
        [
            MenuItemVersionComponent(
                id=uuid4(),
                organization_id=target.organization_id,
                location_id=target.location_id,
                menu_id=target.menu_id,
                menu_version_id=target.id,
                menu_item_version_id=item_map[old.menu_item_version_id].id,
                menu_component_version_id=component_map[old.menu_component_version_id].id,
                position=old.position,
                optional=old.optional,
                source_kind=old.source_kind,
                source_reference=old.source_reference,
                source_item_key=old.source_item_key,
                verified_by_user_id=old.verified_by_user_id,
                verified_at=old.verified_at,
            )
            for old in source_component_links
        ]
    )

    source_allergen_links = list(
        (
            await db.scalars(
                select(MenuItemVersionAllergen).where(
                    MenuItemVersionAllergen.menu_version_id == source.id
                )
            )
        ).all()
    )
    db.add_all(
        [
            MenuItemVersionAllergen(
                id=uuid4(),
                organization_id=target.organization_id,
                location_id=target.location_id,
                menu_id=target.menu_id,
                menu_version_id=target.id,
                menu_item_version_id=item_map[old.menu_item_version_id].id,
                allergen_id=old.allergen_id,
                source_kind=old.source_kind,
                source_reference=old.source_reference,
                source_item_key=old.source_item_key,
                verified_by_user_id=old.verified_by_user_id,
                verified_at=old.verified_at,
            )
            for old in source_allergen_links
        ]
    )


async def _create_menu_draft(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    copy_from_version_id: UUID | None,
) -> MenuVersion:
    location = await db.scalar(
        select(Location)
        .where(Location.id == location_id, Location.organization_id == organization_id)
        .with_for_update()
    )
    if location is None:
        raise _resource_not_found()

    menu = await db.scalar(
        select(Menu).where(
            Menu.location_id == location_id,
            Menu.organization_id == organization_id,
        )
    )
    if menu is None:
        menu = Menu(organization_id=organization_id, location_id=location_id)
        db.add(menu)
        await db.flush()

    existing_draft = await db.scalar(
        select(MenuVersion.id).where(
            MenuVersion.menu_id == menu.id,
            MenuVersion.status == "draft",
        )
    )
    if existing_draft is not None:
        raise _draft_exists()

    if copy_from_version_id is None:
        base = await db.scalar(
            select(MenuVersion).where(
                MenuVersion.menu_id == menu.id,
                MenuVersion.status == "published",
            )
        )
    else:
        base = await db.scalar(
            select(MenuVersion).where(
                MenuVersion.id == copy_from_version_id,
                MenuVersion.menu_id == menu.id,
                MenuVersion.status.in_(("published", "archived")),
            )
        )
        if base is None:
            raise _resource_not_found()

    highest_version = await db.scalar(
        select(func.max(MenuVersion.version_number)).where(MenuVersion.menu_id == menu.id)
    )
    draft = MenuVersion(
        organization_id=organization_id,
        location_id=location_id,
        menu_id=menu.id,
        version_number=(highest_version or 0) + 1,
        status="draft",
        base_version_id=base.id if base is not None else None,
        revision=0,
        created_by_user_id=actor_user_id,
    )
    db.add(draft)
    await db.flush()
    if base is not None:
        await _copy_version_graph(db, source=base, target=draft)

    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="menu_draft_created",
            target_type="menu_version",
            target_id=draft.id,
            old_values=None,
            new_values={
                "location_id": str(location_id),
                "base_version_id": str(base.id) if base is not None else None,
            },
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return draft


async def create_menu_draft(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    copy_from_version_id: UUID | None = None,
) -> MenuVersion:
    try:
        return await _create_menu_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            actor_user_id=actor_user_id,
            request_id=request_id,
            copy_from_version_id=copy_from_version_id,
        )
    except Exception:
        await db.rollback()
        raise


async def get_menu_version_hierarchy(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
) -> MenuVersionHierarchy:
    version = await db.scalar(
        select(MenuVersion).where(
            MenuVersion.id == version_id,
            MenuVersion.organization_id == organization_id,
            MenuVersion.location_id == location_id,
        )
    )
    if version is None:
        raise _resource_not_found()

    sections = list(
        (
            await db.scalars(
                select(MenuVersionSection)
                .where(MenuVersionSection.menu_version_id == version.id)
                .order_by(MenuVersionSection.position, MenuVersionSection.id)
            )
        ).all()
    )
    section_names = {
        row.menu_version_section_id: row.name
        for row in (
            await db.scalars(
                select(MenuVersionSectionTranslation).where(
                    MenuVersionSectionTranslation.menu_version_id == version.id,
                    MenuVersionSectionTranslation.locale == "uk",
                )
            )
        ).all()
    }
    categories = list(
        (
            await db.scalars(
                select(MenuVersionCategory)
                .where(MenuVersionCategory.menu_version_id == version.id)
                .order_by(MenuVersionCategory.position, MenuVersionCategory.id)
            )
        ).all()
    )
    category_names = {
        row.menu_version_category_id: row.name
        for row in (
            await db.scalars(
                select(MenuVersionCategoryTranslation).where(
                    MenuVersionCategoryTranslation.menu_version_id == version.id,
                    MenuVersionCategoryTranslation.locale == "uk",
                )
            )
        ).all()
    }
    item_count_rows = (
        await db.execute(
            select(
                MenuItemVersion.menu_version_category_id,
                func.count(MenuItemVersion.id),
            )
            .where(MenuItemVersion.menu_version_id == version.id)
            .group_by(MenuItemVersion.menu_version_category_id)
        )
    ).all()
    item_counts: dict[UUID, int] = {row[0]: row[1] for row in item_count_rows}

    section_codes_by_identity = {
        row.id: row.stable_code
        for row in (
            await db.scalars(select(MenuSection).where(MenuSection.menu_id == version.menu_id))
        ).all()
    }
    category_codes_by_identity = {
        row.id: row.stable_code
        for row in (
            await db.scalars(select(MenuCategory).where(MenuCategory.menu_id == version.menu_id))
        ).all()
    }

    hierarchy_sections = []
    for section in sections:
        nested = [
            CategoryHierarchy(
                id=category.id,
                stable_code=category_codes_by_identity.get(category.menu_category_id),
                name_uk=category_names.get(category.id, ""),
                position=category.position,
                item_count=item_counts.get(category.id, 0),
            )
            for category in categories
            if category.menu_version_section_id == section.id
        ]
        hierarchy_sections.append(
            SectionHierarchy(
                id=section.id,
                stable_code=section_codes_by_identity.get(section.menu_section_id),
                name_uk=section_names.get(section.id, ""),
                position=section.position,
                categories=nested,
            )
        )

    return MenuVersionHierarchy(
        version=version,
        sections=hierarchy_sections,
        section_count=len(sections),
        category_count=len(categories),
        item_count=sum(item_counts.values()),
    )


async def _set_positions(
    db: AsyncSession,
    entities: Sequence[MenuVersionSection | MenuVersionCategory],
) -> None:
    temporary_offset = max((entity.position for entity in entities), default=-1) + len(entities) + 1
    for index, entity in enumerate(entities):
        entity.position = temporary_offset + index
    await db.flush()
    for index, entity in enumerate(entities):
        entity.position = index


async def _create_section(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    name_uk: str,
    stable_code: str | None,
    position: int,
) -> DraftMutationResult[MenuVersionSection]:
    version = await _lock_draft(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        expected_revision=expected_revision,
    )
    existing = list(
        (
            await db.scalars(
                select(MenuVersionSection)
                .where(MenuVersionSection.menu_version_id == version.id)
                .order_by(MenuVersionSection.position)
            )
        ).all()
    )
    if position < 0 or position > len(existing):
        raise _validation_error()

    identity = MenuSection(
        organization_id=organization_id,
        location_id=location_id,
        menu_id=version.menu_id,
        stable_code=_normalize_stable_code(stable_code),
    )
    db.add(identity)
    await db.flush()
    section = MenuVersionSection(
        organization_id=organization_id,
        location_id=location_id,
        menu_id=version.menu_id,
        menu_version_id=version.id,
        menu_section_id=identity.id,
        position=len(existing),
    )
    db.add(section)
    await db.flush()
    ordered = [*existing]
    ordered.insert(position, section)
    await _set_positions(db, ordered)
    db.add(
        MenuVersionSectionTranslation(
            organization_id=organization_id,
            location_id=location_id,
            menu_id=version.menu_id,
            menu_version_id=version.id,
            menu_version_section_id=section.id,
            locale="uk",
            status="ready",
            name=_validate_name(name_uk),
        )
    )
    version.revision += 1
    _audit_mutation(
        db,
        version=version,
        actor_user_id=actor_user_id,
        request_id=request_id,
        entity_type="menu_section",
        entity_id=section.id,
    )
    await db.commit()
    return DraftMutationResult(entity=section, revision=version.revision)


async def create_section(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    name_uk: str,
    stable_code: str | None,
    position: int,
) -> DraftMutationResult[MenuVersionSection]:
    try:
        return await _create_section(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            actor_user_id=actor_user_id,
            request_id=request_id,
            expected_revision=expected_revision,
            name_uk=name_uk,
            stable_code=stable_code,
            position=position,
        )
    except Exception:
        await db.rollback()
        raise


async def update_section(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    section_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    name_uk: str | None = None,
    stable_code: str | None | _Unset = UNSET,
    position: int | None = None,
) -> DraftMutationResult[MenuVersionSection]:
    try:
        version = await _lock_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            expected_revision=expected_revision,
        )
        section = await db.scalar(
            select(MenuVersionSection).where(
                MenuVersionSection.id == section_id,
                MenuVersionSection.menu_version_id == version.id,
            )
        )
        if section is None:
            raise _resource_not_found()
        if name_uk is not None:
            translation = await db.scalar(
                select(MenuVersionSectionTranslation).where(
                    MenuVersionSectionTranslation.menu_version_section_id == section.id,
                    MenuVersionSectionTranslation.locale == "uk",
                )
            )
            if translation is None:
                raise _resource_not_found()
            translation.name = _validate_name(name_uk)
        if not isinstance(stable_code, _Unset):
            identity = await db.get(MenuSection, section.menu_section_id)
            if identity is None:
                raise _resource_not_found()
            identity.stable_code = _normalize_stable_code(stable_code)
        if position is not None:
            ordered = list(
                (
                    await db.scalars(
                        select(MenuVersionSection)
                        .where(MenuVersionSection.menu_version_id == version.id)
                        .order_by(MenuVersionSection.position)
                    )
                ).all()
            )
            if position < 0 or position >= len(ordered):
                raise _validation_error()
            ordered.remove(section)
            ordered.insert(position, section)
            await _set_positions(db, ordered)
        version.revision += 1
        _audit_mutation(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            entity_type="menu_section",
            entity_id=section.id,
        )
        await db.commit()
        return DraftMutationResult(entity=section, revision=version.revision)
    except Exception:
        await db.rollback()
        raise


async def delete_section(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    section_id: UUID,
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
        section = await db.scalar(
            select(MenuVersionSection).where(
                MenuVersionSection.id == section_id,
                MenuVersionSection.menu_version_id == version.id,
            )
        )
        if section is None:
            raise _resource_not_found()
        category_count = await db.scalar(
            select(func.count(MenuVersionCategory.id)).where(
                MenuVersionCategory.menu_version_section_id == section.id
            )
        )
        if category_count:
            raise APIError(
                status_code=409,
                code="SECTION_NOT_EMPTY",
                message="Спочатку видаліть або перемістіть категорії розділу.",
            )
        await db.execute(
            delete(MenuVersionSectionTranslation).where(
                MenuVersionSectionTranslation.menu_version_section_id == section.id
            )
        )
        await db.delete(section)
        await db.flush()
        remaining = list(
            (
                await db.scalars(
                    select(MenuVersionSection)
                    .where(MenuVersionSection.menu_version_id == version.id)
                    .order_by(MenuVersionSection.position)
                )
            ).all()
        )
        await _set_positions(db, remaining)
        version.revision += 1
        _audit_mutation(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            entity_type="menu_section",
            entity_id=section_id,
        )
        await db.commit()
        return version.revision
    except Exception:
        await db.rollback()
        raise


async def reorder_sections(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    ordered_ids: list[UUID],
) -> DraftReorderResult[MenuVersionSection]:
    try:
        version = await _lock_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            expected_revision=expected_revision,
        )
        sections = list(
            (
                await db.scalars(
                    select(MenuVersionSection).where(
                        MenuVersionSection.menu_version_id == version.id
                    )
                )
            ).all()
        )
        by_id = {section.id: section for section in sections}
        if len(ordered_ids) != len(set(ordered_ids)) or set(ordered_ids) != set(by_id):
            raise _validation_error()
        ordered = [by_id[entity_id] for entity_id in ordered_ids]
        await _set_positions(db, ordered)
        version.revision += 1
        _audit_mutation(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            entity_type="menu_version",
            entity_id=version.id,
        )
        await db.commit()
        return DraftReorderResult(entities=ordered, revision=version.revision)
    except Exception:
        await db.rollback()
        raise


async def create_category(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    section_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    name_uk: str,
    stable_code: str | None,
    position: int,
) -> DraftMutationResult[MenuVersionCategory]:
    try:
        version = await _lock_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            expected_revision=expected_revision,
        )
        section = await db.scalar(
            select(MenuVersionSection).where(
                MenuVersionSection.id == section_id,
                MenuVersionSection.menu_version_id == version.id,
            )
        )
        if section is None:
            raise _resource_not_found()
        existing = list(
            (
                await db.scalars(
                    select(MenuVersionCategory)
                    .where(MenuVersionCategory.menu_version_section_id == section.id)
                    .order_by(MenuVersionCategory.position)
                )
            ).all()
        )
        if position < 0 or position > len(existing):
            raise _validation_error()
        identity = MenuCategory(
            organization_id=organization_id,
            location_id=location_id,
            menu_id=version.menu_id,
            stable_code=_normalize_stable_code(stable_code),
        )
        db.add(identity)
        await db.flush()
        category = MenuVersionCategory(
            organization_id=organization_id,
            location_id=location_id,
            menu_id=version.menu_id,
            menu_version_id=version.id,
            menu_category_id=identity.id,
            menu_version_section_id=section.id,
            position=len(existing),
        )
        db.add(category)
        await db.flush()
        ordered = [*existing]
        ordered.insert(position, category)
        await _set_positions(db, ordered)
        db.add(
            MenuVersionCategoryTranslation(
                organization_id=organization_id,
                location_id=location_id,
                menu_id=version.menu_id,
                menu_version_id=version.id,
                menu_version_category_id=category.id,
                locale="uk",
                status="ready",
                name=_validate_name(name_uk),
            )
        )
        version.revision += 1
        _audit_mutation(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            entity_type="menu_category",
            entity_id=category.id,
        )
        await db.commit()
        return DraftMutationResult(entity=category, revision=version.revision)
    except Exception:
        await db.rollback()
        raise


async def reorder_categories(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    section_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    ordered_ids: list[UUID],
) -> DraftReorderResult[MenuVersionCategory]:
    try:
        version = await _lock_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            expected_revision=expected_revision,
        )
        section = await db.scalar(
            select(MenuVersionSection).where(
                MenuVersionSection.id == section_id,
                MenuVersionSection.menu_version_id == version.id,
            )
        )
        if section is None:
            raise _resource_not_found()
        categories = list(
            (
                await db.scalars(
                    select(MenuVersionCategory).where(
                        MenuVersionCategory.menu_version_section_id == section.id
                    )
                )
            ).all()
        )
        by_id = {category.id: category for category in categories}
        if len(ordered_ids) != len(set(ordered_ids)) or set(ordered_ids) != set(by_id):
            raise _validation_error()
        ordered = [by_id[entity_id] for entity_id in ordered_ids]
        await _set_positions(db, ordered)
        version.revision += 1
        _audit_mutation(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            entity_type="menu_version_section",
            entity_id=section.id,
        )
        await db.commit()
        return DraftReorderResult(entities=ordered, revision=version.revision)
    except Exception:
        await db.rollback()
        raise


async def update_category(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    category_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    section_id: UUID | None = None,
    name_uk: str | None = None,
    stable_code: str | None | _Unset = UNSET,
    position: int | None = None,
) -> DraftMutationResult[MenuVersionCategory]:
    try:
        version = await _lock_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            expected_revision=expected_revision,
        )
        category = await db.scalar(
            select(MenuVersionCategory).where(
                MenuVersionCategory.id == category_id,
                MenuVersionCategory.menu_version_id == version.id,
            )
        )
        if category is None:
            raise _resource_not_found()

        target_section_id = section_id or category.menu_version_section_id
        target_section = await db.scalar(
            select(MenuVersionSection).where(
                MenuVersionSection.id == target_section_id,
                MenuVersionSection.menu_version_id == version.id,
            )
        )
        if target_section is None:
            raise _resource_not_found()

        if name_uk is not None:
            translation = await db.scalar(
                select(MenuVersionCategoryTranslation).where(
                    MenuVersionCategoryTranslation.menu_version_category_id == category.id,
                    MenuVersionCategoryTranslation.locale == "uk",
                )
            )
            if translation is None:
                raise _resource_not_found()
            translation.name = _validate_name(name_uk)
        if not isinstance(stable_code, _Unset):
            identity = await db.get(MenuCategory, category.menu_category_id)
            if identity is None:
                raise _resource_not_found()
            identity.stable_code = _normalize_stable_code(stable_code)

        moved = target_section_id != category.menu_version_section_id
        if moved or position is not None:
            old_section_id = category.menu_version_section_id
            old_order = list(
                (
                    await db.scalars(
                        select(MenuVersionCategory)
                        .where(MenuVersionCategory.menu_version_section_id == old_section_id)
                        .order_by(MenuVersionCategory.position)
                    )
                ).all()
            )
            old_order.remove(category)
            if moved:
                target_order = list(
                    (
                        await db.scalars(
                            select(MenuVersionCategory)
                            .where(MenuVersionCategory.menu_version_section_id == target_section_id)
                            .order_by(MenuVersionCategory.position)
                        )
                    ).all()
                )
                target_position = len(target_order) if position is None else position
                if target_position < 0 or target_position > len(target_order):
                    raise _validation_error()
                category.menu_version_section_id = target_section_id
                category.position = len(target_order)
                await db.flush()
                await _set_positions(db, old_order)
                target_order.insert(target_position, category)
                await _set_positions(db, target_order)
            else:
                if position is None or position < 0 or position >= len(old_order) + 1:
                    raise _validation_error()
                old_order.insert(position, category)
                await _set_positions(db, old_order)

        version.revision += 1
        _audit_mutation(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            entity_type="menu_category",
            entity_id=category.id,
        )
        await db.commit()
        return DraftMutationResult(entity=category, revision=version.revision)
    except Exception:
        await db.rollback()
        raise


async def delete_category(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    category_id: UUID,
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
        category = await db.scalar(
            select(MenuVersionCategory).where(
                MenuVersionCategory.id == category_id,
                MenuVersionCategory.menu_version_id == version.id,
            )
        )
        if category is None:
            raise _resource_not_found()
        item_count = await db.scalar(
            select(func.count(MenuItemVersion.id)).where(
                MenuItemVersion.menu_version_category_id == category.id
            )
        )
        if item_count:
            raise APIError(
                status_code=409,
                code="CATEGORY_NOT_EMPTY",
                message="Спочатку видаліть або перемістіть позиції категорії.",
            )
        section_id = category.menu_version_section_id
        await db.execute(
            delete(MenuVersionCategoryTranslation).where(
                MenuVersionCategoryTranslation.menu_version_category_id == category.id
            )
        )
        await db.delete(category)
        await db.flush()
        remaining = list(
            (
                await db.scalars(
                    select(MenuVersionCategory)
                    .where(MenuVersionCategory.menu_version_section_id == section_id)
                    .order_by(MenuVersionCategory.position)
                )
            ).all()
        )
        await _set_positions(db, remaining)
        version.revision += 1
        _audit_mutation(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            entity_type="menu_category",
            entity_id=category_id,
        )
        await db.commit()
        return version.revision
    except Exception:
        await db.rollback()
        raise
