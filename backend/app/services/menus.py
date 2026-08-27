from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Allergen,
    Location,
    Menu,
    MenuComponent,
    MenuComponentVersion,
    MenuComponentVersionTranslation,
    MenuItem,
    MenuItemVersion,
    MenuItemVersionAllergen,
    MenuItemVersionComponent,
    MenuItemVersionTranslation,
    MenuVersion,
    MenuVersionCategory,
    MenuVersionItemDelta,
    MenuVersionSection,
)
from app.schemas.menu import (
    MenuComponentInput,
    MenuComponentResponse,
    MenuItemListResponse,
    MenuItemPatch,
    MenuItemResponse,
    MenuItemWrite,
    MenuVersionCollection,
    MenuVersionDetail,
    MenuVersionSummary,
)
from app.services.menu_drafts import (
    _audit_mutation,
    _lock_draft,
    _normalize_stable_code,
    _resource_not_found,
    _set_positions,
    _validation_error,
    get_menu_version_hierarchy,
)


@dataclass(frozen=True, slots=True)
class MenuItemMutationResult:
    item_version: MenuItemVersion
    delta: MenuVersionItemDelta
    revision: int


@dataclass(frozen=True, slots=True)
class MenuItemDeleteResult:
    delta: MenuVersionItemDelta | None
    revision: int


@dataclass(frozen=True, slots=True)
class _ItemSnapshot:
    category_identity_id: UUID
    name_uk: str
    description_uk: str | None
    price_minor: int | None
    currency: str
    availability: str
    position: int
    component_data_status: str
    components: tuple[tuple[UUID, bool | None, int], ...]
    allergen_data_status: str
    allergens: tuple[UUID, ...]


async def _version_category(
    db: AsyncSession,
    *,
    version: MenuVersion,
    category_id: UUID,
) -> MenuVersionCategory:
    category = await db.scalar(
        select(MenuVersionCategory).where(
            MenuVersionCategory.id == category_id,
            MenuVersionCategory.menu_version_id == version.id,
        )
    )
    if category is None:
        raise _resource_not_found()
    return category


async def _category_items(
    db: AsyncSession,
    *,
    category_id: UUID,
) -> list[MenuItemVersion]:
    return list(
        (
            await db.scalars(
                select(MenuItemVersion)
                .where(MenuItemVersion.menu_version_category_id == category_id)
                .order_by(MenuItemVersion.position, MenuItemVersion.id)
            )
        ).all()
    )


async def _component_version(
    db: AsyncSession,
    *,
    version: MenuVersion,
    component: MenuComponentInput,
) -> MenuComponentVersion:
    identity: MenuComponent | None
    if component.id is not None:
        identity = await db.scalar(
            select(MenuComponent).where(
                MenuComponent.id == component.id,
                MenuComponent.menu_id == version.menu_id,
                MenuComponent.retired_at.is_(None),
            )
        )
        if identity is None:
            raise _resource_not_found()
    elif component.stable_code is not None:
        identity = await db.scalar(
            select(MenuComponent).where(
                MenuComponent.menu_id == version.menu_id,
                MenuComponent.stable_code == component.stable_code,
                MenuComponent.retired_at.is_(None),
            )
        )
    else:
        identity = None

    if identity is None:
        identity = MenuComponent(
            organization_id=version.organization_id,
            location_id=version.location_id,
            menu_id=version.menu_id,
            stable_code=_normalize_stable_code(component.stable_code),
        )
        db.add(identity)
        await db.flush()

    state = await db.scalar(
        select(MenuComponentVersion).where(
            MenuComponentVersion.menu_version_id == version.id,
            MenuComponentVersion.menu_component_id == identity.id,
        )
    )
    if state is None:
        state = MenuComponentVersion(
            organization_id=version.organization_id,
            location_id=version.location_id,
            menu_id=version.menu_id,
            menu_version_id=version.id,
            menu_component_id=identity.id,
        )
        db.add(state)
        await db.flush()

    translation = await db.scalar(
        select(MenuComponentVersionTranslation).where(
            MenuComponentVersionTranslation.menu_component_version_id == state.id,
            MenuComponentVersionTranslation.locale == "uk",
        )
    )
    if translation is None:
        db.add(
            MenuComponentVersionTranslation(
                organization_id=version.organization_id,
                location_id=version.location_id,
                menu_id=version.menu_id,
                menu_version_id=version.id,
                menu_component_version_id=state.id,
                locale="uk",
                status="ready",
                name=component.name_uk,
            )
        )
    else:
        translation.name = component.name_uk
        translation.status = "ready"
    return state


async def _validate_allergens(
    db: AsyncSession,
    *,
    codes: list[str],
) -> list[Allergen]:
    if not codes:
        return []
    allergens = list(
        (
            await db.scalars(
                select(Allergen).where(Allergen.code.in_(codes), Allergen.status == "active")
            )
        ).all()
    )
    by_code = {allergen.code: allergen for allergen in allergens}
    if set(by_code) != set(codes):
        raise _validation_error()
    return [by_code[code] for code in codes]


async def _replace_facts(
    db: AsyncSession,
    *,
    version: MenuVersion,
    item_version: MenuItemVersion,
    payload: MenuItemWrite,
    actor_user_id: UUID,
    now: datetime,
) -> None:
    await db.execute(
        delete(MenuItemVersionComponent).where(
            MenuItemVersionComponent.menu_item_version_id == item_version.id
        )
    )
    await db.execute(
        delete(MenuItemVersionAllergen).where(
            MenuItemVersionAllergen.menu_item_version_id == item_version.id
        )
    )

    component_states = [
        await _component_version(db, version=version, component=component)
        for component in payload.components
    ]
    for component, state in zip(payload.components, component_states, strict=True):
        db.add(
            MenuItemVersionComponent(
                organization_id=version.organization_id,
                location_id=version.location_id,
                menu_id=version.menu_id,
                menu_version_id=version.id,
                menu_item_version_id=item_version.id,
                menu_component_version_id=state.id,
                position=component.position,
                optional=component.optional,
                source_kind=payload.source_kind,
                source_reference=payload.source_reference,
                source_item_key=payload.source_item_key,
                verified_by_user_id=actor_user_id,
                verified_at=now,
            )
        )

    for allergen in await _validate_allergens(db, codes=payload.allergen_codes):
        db.add(
            MenuItemVersionAllergen(
                organization_id=version.organization_id,
                location_id=version.location_id,
                menu_id=version.menu_id,
                menu_version_id=version.id,
                menu_item_version_id=item_version.id,
                allergen_id=allergen.id,
                source_kind=payload.source_kind,
                source_reference=payload.source_reference,
                source_item_key=payload.source_item_key,
                verified_by_user_id=actor_user_id,
                verified_at=now,
            )
        )


async def _item_snapshot(
    db: AsyncSession,
    *,
    item_version: MenuItemVersion,
) -> _ItemSnapshot:
    category_identity_id = await db.scalar(
        select(MenuVersionCategory.menu_category_id).where(
            MenuVersionCategory.id == item_version.menu_version_category_id
        )
    )
    translation = await db.scalar(
        select(MenuItemVersionTranslation).where(
            MenuItemVersionTranslation.menu_item_version_id == item_version.id,
            MenuItemVersionTranslation.locale == "uk",
        )
    )
    if category_identity_id is None or translation is None:
        raise _resource_not_found()
    component_rows = (
        await db.execute(
            select(
                MenuComponentVersion.menu_component_id,
                MenuItemVersionComponent.optional,
                MenuItemVersionComponent.position,
            )
            .join(
                MenuItemVersionComponent,
                MenuItemVersionComponent.menu_component_version_id == MenuComponentVersion.id,
            )
            .where(MenuItemVersionComponent.menu_item_version_id == item_version.id)
            .order_by(MenuItemVersionComponent.position, MenuComponentVersion.menu_component_id)
        )
    ).all()
    allergen_ids = tuple(
        (
            await db.scalars(
                select(MenuItemVersionAllergen.allergen_id)
                .where(MenuItemVersionAllergen.menu_item_version_id == item_version.id)
                .order_by(MenuItemVersionAllergen.allergen_id)
            )
        ).all()
    )
    return _ItemSnapshot(
        category_identity_id=category_identity_id,
        name_uk=translation.name,
        description_uk=translation.description,
        price_minor=item_version.price_minor,
        currency=item_version.currency,
        availability=item_version.availability,
        position=item_version.position,
        component_data_status=item_version.component_data_status,
        components=tuple((row[0], row[1], row[2]) for row in component_rows),
        allergen_data_status=item_version.allergen_data_status,
        allergens=allergen_ids,
    )


def _classify_delta(
    base: _ItemSnapshot | None,
    current: _ItemSnapshot | None,
) -> tuple[str, str, list[str]]:
    if base is None and current is not None:
        return "added", "required", ["item"]
    if base is not None and current is None:
        return "removed", "required", ["item"]
    if base is None or current is None:
        raise RuntimeError("A delta requires at least one item state")

    fields = (
        "category_identity_id",
        "name_uk",
        "description_uk",
        "price_minor",
        "currency",
        "availability",
        "position",
        "component_data_status",
        "components",
        "allergen_data_status",
        "allergens",
    )
    changed = [field for field in fields if getattr(base, field) != getattr(current, field)]
    if not changed:
        return "unchanged", "none", []
    required = {
        "component_data_status",
        "components",
        "allergen_data_status",
        "allergens",
    }
    review = {"category_identity_id", "name_uk", "description_uk", "availability"}
    if required.intersection(changed):
        impact = "required"
    elif review.intersection(changed):
        impact = "review"
    else:
        impact = "none"
    public_names = {
        "category_identity_id": "category",
        "component_data_status": "component_data_status",
        "allergen_data_status": "allergen_data_status",
        "allergens": "allergens",
    }
    return "changed", impact, [public_names.get(field, field) for field in changed]


async def _replace_delta(
    db: AsyncSession,
    *,
    version: MenuVersion,
    menu_item_id: UUID,
    current: MenuItemVersion | None,
) -> MenuVersionItemDelta | None:
    base_item = None
    if version.base_version_id is not None:
        base_item = await db.scalar(
            select(MenuItemVersion).where(
                MenuItemVersion.menu_version_id == version.base_version_id,
                MenuItemVersion.menu_item_id == menu_item_id,
            )
        )
    base_snapshot = (
        await _item_snapshot(db, item_version=base_item) if base_item is not None else None
    )
    current_snapshot = (
        await _item_snapshot(db, item_version=current) if current is not None else None
    )
    await db.execute(
        delete(MenuVersionItemDelta).where(
            MenuVersionItemDelta.menu_version_id == version.id,
            MenuVersionItemDelta.menu_item_id == menu_item_id,
        )
    )
    if base_snapshot is None and current_snapshot is None:
        return None
    delta_kind, training_impact, changed_fields = _classify_delta(
        base_snapshot,
        current_snapshot,
    )
    delta = MenuVersionItemDelta(
        organization_id=version.organization_id,
        location_id=version.location_id,
        menu_id=version.menu_id,
        menu_version_id=version.id,
        base_version_id=version.base_version_id,
        menu_item_id=menu_item_id,
        delta_kind=delta_kind,
        training_impact=training_impact,
        changed_field_codes=changed_fields,
    )
    db.add(delta)
    await db.flush()
    return delta


async def _create_menu_item(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    payload: MenuItemWrite,
    now: datetime,
) -> MenuItemMutationResult:
    version = await _lock_draft(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        expected_revision=expected_revision,
    )
    category = await _version_category(db, version=version, category_id=payload.category_id)
    existing = await _category_items(db, category_id=category.id)
    if payload.position > len(existing):
        raise _validation_error()

    identity = MenuItem(
        organization_id=version.organization_id,
        location_id=version.location_id,
        menu_id=version.menu_id,
        stable_code=_normalize_stable_code(payload.stable_code),
    )
    db.add(identity)
    await db.flush()
    item_version = MenuItemVersion(
        organization_id=version.organization_id,
        location_id=version.location_id,
        menu_id=version.menu_id,
        menu_version_id=version.id,
        menu_item_id=identity.id,
        menu_version_category_id=category.id,
        position=len(existing),
        availability=payload.availability,
        price_minor=payload.price_minor,
        currency=payload.currency,
        component_data_status=payload.component_data_status,
        allergen_data_status=payload.allergen_data_status,
        source_kind=payload.source_kind,
        source_reference=payload.source_reference,
        source_item_key=payload.source_item_key,
        verified_by_user_id=actor_user_id,
        verified_at=now,
    )
    db.add(item_version)
    await db.flush()
    ordered = [*existing]
    ordered.insert(payload.position, item_version)
    await _set_positions(db, ordered)
    db.add(
        MenuItemVersionTranslation(
            organization_id=version.organization_id,
            location_id=version.location_id,
            menu_id=version.menu_id,
            menu_version_id=version.id,
            menu_item_version_id=item_version.id,
            locale="uk",
            status="ready",
            name=payload.name_uk,
            description=payload.description_uk,
        )
    )
    await _replace_facts(
        db,
        version=version,
        item_version=item_version,
        payload=payload,
        actor_user_id=actor_user_id,
        now=now,
    )
    await db.flush()
    delta = await _replace_delta(
        db,
        version=version,
        menu_item_id=identity.id,
        current=item_version,
    )
    if delta is None:
        raise RuntimeError("A created Menu Item must produce a delta")
    version.revision += 1
    _audit_mutation(
        db,
        version=version,
        actor_user_id=actor_user_id,
        request_id=request_id,
        entity_type="menu_item",
        entity_id=identity.id,
    )
    await db.commit()
    return MenuItemMutationResult(
        item_version=item_version,
        delta=delta,
        revision=version.revision,
    )


async def create_menu_item(
    db: AsyncSession,
    **kwargs: object,
) -> MenuItemMutationResult:
    try:
        return await _create_menu_item(db, **kwargs)  # type: ignore[arg-type]
    except Exception:
        await db.rollback()
        raise


async def _current_payload(
    db: AsyncSession,
    *,
    item_version: MenuItemVersion,
) -> MenuItemWrite:
    translation = await db.scalar(
        select(MenuItemVersionTranslation).where(
            MenuItemVersionTranslation.menu_item_version_id == item_version.id,
            MenuItemVersionTranslation.locale == "uk",
        )
    )
    if translation is None:
        raise _resource_not_found()
    component_rows = (
        await db.execute(
            select(
                MenuComponent,
                MenuComponentVersionTranslation,
                MenuItemVersionComponent,
            )
            .join(
                MenuComponentVersion,
                MenuComponentVersion.menu_component_id == MenuComponent.id,
            )
            .join(
                MenuItemVersionComponent,
                MenuItemVersionComponent.menu_component_version_id == MenuComponentVersion.id,
            )
            .join(
                MenuComponentVersionTranslation,
                MenuComponentVersionTranslation.menu_component_version_id
                == MenuComponentVersion.id,
            )
            .where(
                MenuItemVersionComponent.menu_item_version_id == item_version.id,
                MenuComponentVersionTranslation.locale == "uk",
            )
            .order_by(MenuItemVersionComponent.position)
        )
    ).all()
    allergen_codes = list(
        (
            await db.scalars(
                select(Allergen.code)
                .join(
                    MenuItemVersionAllergen,
                    MenuItemVersionAllergen.allergen_id == Allergen.id,
                )
                .where(MenuItemVersionAllergen.menu_item_version_id == item_version.id)
                .order_by(Allergen.code)
            )
        ).all()
    )
    identity = await db.get(MenuItem, item_version.menu_item_id)
    if identity is None:
        raise _resource_not_found()
    return MenuItemWrite(
        category_id=item_version.menu_version_category_id,
        stable_code=identity.stable_code,
        name_uk=translation.name,
        description_uk=translation.description,
        price_minor=item_version.price_minor,
        currency=item_version.currency,
        availability=item_version.availability,
        position=item_version.position,
        component_data_status=item_version.component_data_status,
        components=[
            MenuComponentInput(
                id=component.id,
                stable_code=component.stable_code,
                name_uk=component_translation.name,
                optional=link.optional,
                position=link.position,
            )
            for component, component_translation, link in component_rows
        ],
        allergen_data_status=item_version.allergen_data_status,
        allergen_codes=allergen_codes,
        source_kind=item_version.source_kind,
        source_reference=item_version.source_reference,
        source_item_key=item_version.source_item_key,
    )


async def _update_menu_item(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    item_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    payload: MenuItemPatch,
    now: datetime,
) -> MenuItemMutationResult:
    version = await _lock_draft(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        expected_revision=payload.expected_revision,
    )
    item_version = await db.scalar(
        select(MenuItemVersion).where(
            MenuItemVersion.menu_version_id == version.id,
            MenuItemVersion.menu_item_id == item_id,
        )
    )
    if item_version is None:
        raise _resource_not_found()
    current = await _current_payload(db, item_version=item_version)
    values = current.model_dump()
    for field in payload.model_fields_set - {"expected_revision"}:
        values[field] = getattr(payload, field)
    merged = MenuItemWrite.model_validate(values)
    target_category = await _version_category(
        db,
        version=version,
        category_id=merged.category_id,
    )

    old_category_id = item_version.menu_version_category_id
    moved = target_category.id != old_category_id
    old_order = await _category_items(db, category_id=old_category_id)
    old_order.remove(item_version)
    if moved:
        target_order = await _category_items(db, category_id=target_category.id)
        if merged.position > len(target_order):
            raise _validation_error()
        item_version.menu_version_category_id = target_category.id
        item_version.position = len(target_order)
        await db.flush()
        await _set_positions(db, old_order)
        target_order.insert(merged.position, item_version)
        await _set_positions(db, target_order)
    else:
        if merged.position > len(old_order):
            raise _validation_error()
        old_order.insert(merged.position, item_version)
        await _set_positions(db, old_order)

    identity = await db.get(MenuItem, item_version.menu_item_id)
    translation = await db.scalar(
        select(MenuItemVersionTranslation).where(
            MenuItemVersionTranslation.menu_item_version_id == item_version.id,
            MenuItemVersionTranslation.locale == "uk",
        )
    )
    if identity is None or translation is None:
        raise _resource_not_found()
    identity.stable_code = _normalize_stable_code(merged.stable_code)
    translation.name = merged.name_uk
    translation.description = merged.description_uk
    translation.status = "ready"
    item_version.availability = merged.availability
    item_version.price_minor = merged.price_minor
    item_version.currency = merged.currency
    item_version.component_data_status = merged.component_data_status
    item_version.allergen_data_status = merged.allergen_data_status
    item_version.source_kind = merged.source_kind
    item_version.source_reference = merged.source_reference
    item_version.source_item_key = merged.source_item_key
    item_version.verified_by_user_id = actor_user_id
    item_version.verified_at = now
    await _replace_facts(
        db,
        version=version,
        item_version=item_version,
        payload=merged,
        actor_user_id=actor_user_id,
        now=now,
    )
    await db.flush()
    delta = await _replace_delta(
        db,
        version=version,
        menu_item_id=item_version.menu_item_id,
        current=item_version,
    )
    if delta is None:
        raise RuntimeError("An updated Menu Item must produce a delta")
    version.revision += 1
    _audit_mutation(
        db,
        version=version,
        actor_user_id=actor_user_id,
        request_id=request_id,
        entity_type="menu_item",
        entity_id=item_id,
    )
    await db.commit()
    return MenuItemMutationResult(
        item_version=item_version,
        delta=delta,
        revision=version.revision,
    )


async def update_menu_item(
    db: AsyncSession,
    **kwargs: object,
) -> MenuItemMutationResult:
    try:
        return await _update_menu_item(db, **kwargs)  # type: ignore[arg-type]
    except Exception:
        await db.rollback()
        raise


async def delete_menu_item(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    item_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
) -> MenuItemDeleteResult:
    try:
        version = await _lock_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            expected_revision=expected_revision,
        )
        item_version = await db.scalar(
            select(MenuItemVersion).where(
                MenuItemVersion.menu_version_id == version.id,
                MenuItemVersion.menu_item_id == item_id,
            )
        )
        if item_version is None:
            raise _resource_not_found()
        category_id = item_version.menu_version_category_id
        await db.execute(
            delete(MenuItemVersionComponent).where(
                MenuItemVersionComponent.menu_item_version_id == item_version.id
            )
        )
        await db.execute(
            delete(MenuItemVersionAllergen).where(
                MenuItemVersionAllergen.menu_item_version_id == item_version.id
            )
        )
        await db.execute(
            delete(MenuItemVersionTranslation).where(
                MenuItemVersionTranslation.menu_item_version_id == item_version.id
            )
        )
        await db.delete(item_version)
        await db.flush()
        await _set_positions(db, await _category_items(db, category_id=category_id))
        delta = await _replace_delta(
            db,
            version=version,
            menu_item_id=item_id,
            current=None,
        )
        if delta is None:
            identity = await db.get(MenuItem, item_id)
            if identity is not None:
                identity.retired_at = datetime.now(tz=version.created_at.tzinfo)
        version.revision += 1
        _audit_mutation(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            entity_type="menu_item",
            entity_id=item_id,
        )
        await db.commit()
        return MenuItemDeleteResult(delta=delta, revision=version.revision)
    except Exception:
        await db.rollback()
        raise


async def _version_summary(
    db: AsyncSession,
    *,
    version: MenuVersion,
) -> MenuVersionSummary:
    section_count = await db.scalar(
        select(func.count(MenuVersionSection.id)).where(
            MenuVersionSection.menu_version_id == version.id
        )
    )
    category_count = await db.scalar(
        select(func.count(MenuVersionCategory.id)).where(
            MenuVersionCategory.menu_version_id == version.id
        )
    )
    item_count = await db.scalar(
        select(func.count(MenuItemVersion.id)).where(MenuItemVersion.menu_version_id == version.id)
    )
    return MenuVersionSummary(
        id=version.id,
        menu_id=version.menu_id,
        organization_id=version.organization_id,
        location_id=version.location_id,
        version_number=version.version_number,
        status=version.status,
        base_version_id=version.base_version_id,
        revision=version.revision,
        section_count=section_count or 0,
        category_count=category_count or 0,
        item_count=item_count or 0,
        created_at=version.created_at,
        published_at=version.published_at,
        archived_at=version.archived_at,
    )


async def list_menu_versions(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
) -> MenuVersionCollection:
    location = await db.scalar(
        select(Location.id).where(
            Location.id == location_id,
            Location.organization_id == organization_id,
        )
    )
    if location is None:
        raise _resource_not_found()
    menu = await db.scalar(
        select(Menu).where(
            Menu.organization_id == organization_id,
            Menu.location_id == location_id,
        )
    )
    if menu is None:
        return MenuVersionCollection(
            menu_id=None,
            organization_id=organization_id,
            location_id=location_id,
            current_published=None,
            draft=None,
            archived=[],
        )
    versions = list(
        (
            await db.scalars(
                select(MenuVersion)
                .where(MenuVersion.menu_id == menu.id)
                .order_by(MenuVersion.version_number.desc())
            )
        ).all()
    )
    summaries = {version.id: await _version_summary(db, version=version) for version in versions}
    published = next((summaries[row.id] for row in versions if row.status == "published"), None)
    draft = next((summaries[row.id] for row in versions if row.status == "draft"), None)
    archived = [summaries[row.id] for row in versions if row.status == "archived"]
    return MenuVersionCollection(
        menu_id=menu.id,
        organization_id=organization_id,
        location_id=location_id,
        current_published=published,
        draft=draft,
        archived=archived,
    )


async def get_menu_version_detail(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
) -> MenuVersionDetail:
    hierarchy = await get_menu_version_hierarchy(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
    )
    summary = await _version_summary(db, version=hierarchy.version)
    return MenuVersionDetail(
        **summary.model_dump(),
        sections=[
            {
                "id": section.id,
                "stable_code": section.stable_code,
                "name_uk": section.name_uk,
                "position": section.position,
                "category_count": len(section.categories),
                "categories": [
                    {
                        "id": category.id,
                        "section_id": section.id,
                        "stable_code": category.stable_code,
                        "name_uk": category.name_uk,
                        "position": category.position,
                        "item_count": category.item_count,
                    }
                    for category in section.categories
                ],
            }
            for section in hierarchy.sections
        ],
    )


async def _admin_item_response(
    db: AsyncSession,
    *,
    item_version: MenuItemVersion,
) -> MenuItemResponse:
    identity = await db.get(MenuItem, item_version.menu_item_id)
    translation = await db.scalar(
        select(MenuItemVersionTranslation).where(
            MenuItemVersionTranslation.menu_item_version_id == item_version.id,
            MenuItemVersionTranslation.locale == "uk",
        )
    )
    if identity is None or translation is None:
        raise _resource_not_found()
    component_rows = (
        await db.execute(
            select(
                MenuComponent,
                MenuComponentVersionTranslation,
                MenuItemVersionComponent,
            )
            .join(
                MenuComponentVersion,
                MenuComponentVersion.menu_component_id == MenuComponent.id,
            )
            .join(
                MenuItemVersionComponent,
                MenuItemVersionComponent.menu_component_version_id == MenuComponentVersion.id,
            )
            .join(
                MenuComponentVersionTranslation,
                MenuComponentVersionTranslation.menu_component_version_id
                == MenuComponentVersion.id,
            )
            .where(
                MenuItemVersionComponent.menu_item_version_id == item_version.id,
                MenuComponentVersionTranslation.locale == "uk",
            )
            .order_by(MenuItemVersionComponent.position)
        )
    ).all()
    allergen_codes = list(
        (
            await db.scalars(
                select(Allergen.code)
                .join(
                    MenuItemVersionAllergen,
                    MenuItemVersionAllergen.allergen_id == Allergen.id,
                )
                .where(MenuItemVersionAllergen.menu_item_version_id == item_version.id)
                .order_by(Allergen.code)
            )
        ).all()
    )
    delta = await db.scalar(
        select(MenuVersionItemDelta).where(
            MenuVersionItemDelta.menu_version_id == item_version.menu_version_id,
            MenuVersionItemDelta.menu_item_id == item_version.menu_item_id,
        )
    )
    return MenuItemResponse(
        item_id=item_version.menu_item_id,
        item_version_id=item_version.id,
        version_id=item_version.menu_version_id,
        category_id=item_version.menu_version_category_id,
        stable_code=identity.stable_code,
        name_uk=translation.name,
        description_uk=translation.description,
        price_minor=item_version.price_minor,
        currency=item_version.currency,
        availability=item_version.availability,
        position=item_version.position,
        component_data_status=item_version.component_data_status,
        components=[
            MenuComponentResponse(
                id=component.id,
                stable_code=component.stable_code,
                name_uk=component_translation.name,
                optional=link.optional,
                position=link.position,
                source_kind=link.source_kind,
                source_reference=link.source_reference,
                verified_at=link.verified_at,
            )
            for component, component_translation, link in component_rows
        ],
        allergen_data_status=item_version.allergen_data_status,
        allergen_codes=allergen_codes,
        source_kind=item_version.source_kind,
        source_reference=item_version.source_reference,
        source_item_key=item_version.source_item_key,
        verified_at=item_version.verified_at,
        delta_kind=delta.delta_kind if delta is not None else "unchanged",
        training_impact=delta.training_impact if delta is not None else "none",
        changed_field_codes=delta.changed_field_codes if delta is not None else [],
        created_at=item_version.created_at,
        updated_at=item_version.updated_at,
    )


async def get_admin_menu_item(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    item_id: UUID,
) -> MenuItemResponse:
    item_version = await db.scalar(
        select(MenuItemVersion).where(
            MenuItemVersion.menu_version_id == version_id,
            MenuItemVersion.menu_item_id == item_id,
            MenuItemVersion.organization_id == organization_id,
            MenuItemVersion.location_id == location_id,
        )
    )
    if item_version is None:
        raise _resource_not_found()
    return await _admin_item_response(db, item_version=item_version)


async def list_admin_menu_items(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    query: str | None,
    section_id: UUID | None,
    category_id: UUID | None,
    cursor: str | None,
    limit: int,
) -> MenuItemListResponse:
    version = await db.scalar(
        select(MenuVersion).where(
            MenuVersion.id == version_id,
            MenuVersion.organization_id == organization_id,
            MenuVersion.location_id == location_id,
        )
    )
    if version is None:
        raise _resource_not_found()
    statement = (
        select(MenuItemVersion)
        .join(
            MenuItemVersionTranslation,
            MenuItemVersionTranslation.menu_item_version_id == MenuItemVersion.id,
        )
        .join(
            MenuVersionCategory,
            MenuVersionCategory.id == MenuItemVersion.menu_version_category_id,
        )
        .where(
            MenuItemVersion.menu_version_id == version.id,
            MenuItemVersionTranslation.locale == "uk",
        )
    )
    if query is not None:
        pattern = f"%{query.strip().replace('%', r'\%').replace('_', r'\_')}%"
        component_match = (
            select(MenuItemVersionComponent.menu_item_version_id)
            .join(
                MenuComponentVersionTranslation,
                MenuComponentVersionTranslation.menu_component_version_id
                == MenuItemVersionComponent.menu_component_version_id,
            )
            .where(
                MenuComponentVersionTranslation.locale == "uk",
                MenuComponentVersionTranslation.name.ilike(pattern, escape="\\"),
            )
        )
        statement = statement.where(
            or_(
                MenuItemVersionTranslation.name.ilike(pattern, escape="\\"),
                MenuItemVersion.id.in_(component_match),
            )
        )
    if section_id is not None:
        statement = statement.where(MenuVersionCategory.menu_version_section_id == section_id)
    if category_id is not None:
        statement = statement.where(MenuVersionCategory.id == category_id)
    if cursor is not None:
        try:
            cursor_id = UUID(cursor)
        except ValueError as exc:
            raise _validation_error() from exc
        statement = statement.where(MenuItemVersion.id > cursor_id)
    rows = list((await db.scalars(statement.order_by(MenuItemVersion.id).limit(limit + 1))).all())
    page = rows[:limit]
    next_cursor = str(page[-1].id) if len(rows) > limit and page else None
    return MenuItemListResponse(
        items=[await _admin_item_response(db, item_version=item) for item in page],
        next_cursor=next_cursor,
        revision=version.revision,
    )
