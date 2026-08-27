import hashlib
import json
from collections import Counter
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Allergen,
    AuditEvent,
    Location,
    Menu,
    MenuCategory,
    MenuComponent,
    MenuComponentVersion,
    MenuComponentVersionTranslation,
    MenuImport,
    MenuImportFinding,
    MenuItem,
    MenuItemVersion,
    MenuItemVersionAllergen,
    MenuItemVersionComponent,
    MenuItemVersionTranslation,
    MenuSection,
    MenuVersion,
    MenuVersionCategory,
    MenuVersionCategoryTranslation,
    MenuVersionItemDelta,
    MenuVersionSection,
    MenuVersionSectionTranslation,
)
from app.schemas.menu import (
    MenuFindingResolveRequest,
    MenuFindingResolveResponse,
    MenuImportConfirmResponse,
    MenuImportCreate,
    MenuImportDetail,
    MenuImportFindingResponse,
    MenuItemWrite,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.menus import _replace_delta, _replace_facts, get_menu_version_detail

MAX_CANONICAL_BYTES = 2 * 1024 * 1024
MAX_ITEMS = 1000


def _error(status_code: int, code: str, message: str) -> APIError:
    return APIError(status_code=status_code, code=code, message=message)


def _not_found() -> APIError:
    return _error(404, "RESOURCE_NOT_FOUND", "Ресурс не знайдено.")


def _revision_conflict() -> APIError:
    return _error(
        409,
        "REVISION_CONFLICT",
        "Перевірку імпорту вже змінено. Оновіть дані та повторіть дію.",
    )


def _canonical_payload(payload: MenuImportCreate) -> tuple[dict[str, object], str]:
    value = payload.model_dump(mode="json")
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > MAX_CANONICAL_BYTES:
        raise _error(413, "MENU_IMPORT_TOO_LARGE", "JSON-імпорт перевищує ліміт 2 МіБ.")
    item_count = sum(
        len(category.items) for section in payload.sections for category in section.categories
    )
    if item_count > MAX_ITEMS:
        raise _error(422, "MENU_IMPORT_ITEM_LIMIT", "JSON-імпорт містить понад 1000 позицій.")
    return value, hashlib.sha256(encoded).hexdigest()


def _finding_message(finding: MenuImportFinding) -> str:
    messages = {
        "UNKNOWN_ALLERGEN_CODE": "Код алергену відсутній у контрольованому довіднику.",
        "ITEM_REMOVAL": "Опублікована позиція відсутня в імпорті та потребує підтвердження.",
        "CRITICAL_FACT_CHANGE": "Критичні факти позиції змінено та потрібно підтвердити.",
        "DUPLICATE_ITEM_NAME": "Імпорт містить повторювану назву позиції.",
    }
    return messages.get(finding.message_code, "Знахідка імпорту потребує перевірки.")


def _finding_response(finding: MenuImportFinding) -> MenuImportFindingResponse:
    return MenuImportFindingResponse(
        id=finding.id,
        severity=finding.severity,
        code=finding.code,
        entity_type=finding.entity_type,
        source_key=finding.source_key,
        message=_finding_message(finding),
        resolution_status=finding.resolution_status,
        allowed_actions=finding.allowed_actions,
        resolution_action=finding.resolution_action,
        target_entity_id=finding.target_entity_id,
        resolution_comment=finding.resolution_comment,
        resolved_at=finding.resolved_at,
    )


async def _import_detail(db: AsyncSession, menu_import: MenuImport) -> MenuImportDetail:
    findings = list(
        (
            await db.scalars(
                select(MenuImportFinding)
                .where(MenuImportFinding.menu_import_id == menu_import.id)
                .order_by(
                    MenuImportFinding.severity,
                    MenuImportFinding.code,
                    MenuImportFinding.id,
                )
            )
        ).all()
    )
    return MenuImportDetail(
        id=menu_import.id,
        organization_id=menu_import.organization_id,
        location_id=menu_import.location_id,
        menu_id=menu_import.menu_id,
        base_menu_version_id=menu_import.base_menu_version_id,
        status=menu_import.status,
        review_revision=menu_import.review_revision,
        source_filename=menu_import.source_filename,
        source_reference=menu_import.source_reference,
        source_checksum=menu_import.source_checksum,
        section_count=menu_import.section_count,
        category_count=menu_import.category_count,
        item_count=menu_import.item_count,
        added_count=menu_import.added_count,
        changed_count=menu_import.changed_count,
        removed_count=menu_import.removed_count,
        unchanged_count=menu_import.unchanged_count,
        blocker_count=menu_import.blocker_count,
        review_count=menu_import.review_count,
        warning_count=menu_import.warning_count,
        findings=[_finding_response(finding) for finding in findings],
        created_at=menu_import.created_at,
        confirmed_at=menu_import.confirmed_at,
        failure_code=menu_import.failure_code,
    )


async def _scoped_import(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    import_id: UUID,
    lock: bool = False,
) -> MenuImport:
    query = select(MenuImport).where(
        MenuImport.id == import_id,
        MenuImport.organization_id == organization_id,
        MenuImport.location_id == location_id,
    )
    if lock:
        query = query.with_for_update()
    menu_import = await db.scalar(query)
    if menu_import is None:
        raise _not_found()
    return menu_import


async def get_menu_import(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    import_id: UUID,
) -> MenuImportDetail:
    return await _import_detail(
        db,
        await _scoped_import(
            db,
            organization_id=organization_id,
            location_id=location_id,
            import_id=import_id,
        ),
    )


async def _base_item_facts(
    db: AsyncSession, base_version_id: UUID | None
) -> dict[str, tuple[MenuItem, tuple[str, ...], tuple[str, ...]]]:
    if base_version_id is None:
        return {}
    rows = (
        await db.execute(
            select(MenuItem, MenuItemVersion)
            .join(MenuItemVersion, MenuItemVersion.menu_item_id == MenuItem.id)
            .where(
                MenuItemVersion.menu_version_id == base_version_id,
                MenuItem.stable_code.is_not(None),
            )
        )
    ).all()
    result: dict[str, tuple[MenuItem, tuple[str, ...], tuple[str, ...]]] = {}
    for identity, item_version in rows:
        components = tuple(
            (
                await db.scalars(
                    select(MenuComponent.stable_code)
                    .join(
                        MenuComponentVersion,
                        MenuComponentVersion.menu_component_id == MenuComponent.id,
                    )
                    .join(
                        MenuItemVersionComponent,
                        MenuItemVersionComponent.menu_component_version_id
                        == MenuComponentVersion.id,
                    )
                    .where(MenuItemVersionComponent.menu_item_version_id == item_version.id)
                    .order_by(MenuComponent.stable_code)
                )
            ).all()
        )
        allergens = tuple(
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
        result[identity.stable_code or ""] = (
            cast(MenuItem, identity),
            tuple(value for value in components if value is not None),
            allergens,
        )
    return result


async def create_menu_import(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    payload: MenuImportCreate,
    idempotency_key: str,
    now: datetime,
) -> MenuImportDetail:
    canonical, checksum = _canonical_payload(payload)
    fingerprint = request_fingerprint(canonical)
    try:
        replay = await find_idempotency_replay(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="menu_import_create",
            key=idempotency_key,
            fingerprint=fingerprint,
            now=now,
        )
        if replay is not None:
            existing = await _scoped_import(
                db,
                organization_id=organization_id,
                location_id=location_id,
                import_id=replay.resource_id,
            )
            await db.commit()
            return await _import_detail(db, existing)

        location = await db.scalar(
            select(Location)
            .where(Location.id == location_id, Location.organization_id == organization_id)
            .with_for_update()
        )
        if location is None:
            raise _not_found()
        menu = await db.scalar(
            select(Menu).where(
                Menu.organization_id == organization_id,
                Menu.location_id == location_id,
            )
        )
        if menu is None:
            menu = Menu(organization_id=organization_id, location_id=location_id)
            db.add(menu)
            await db.flush()
        base = await db.scalar(
            select(MenuVersion).where(
                MenuVersion.menu_id == menu.id,
                MenuVersion.status == "published",
            )
        )
        checksum_query = select(MenuImport).where(
            MenuImport.menu_id == menu.id,
            MenuImport.source_checksum == checksum,
        )
        checksum_query = (
            checksum_query.where(MenuImport.base_menu_version_id == base.id)
            if base is not None
            else checksum_query.where(MenuImport.base_menu_version_id.is_(None))
        )
        duplicate = await db.scalar(checksum_query)
        if duplicate is not None:
            await reserve_idempotency(
                db,
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="menu_import_create",
                key=idempotency_key,
                fingerprint=fingerprint,
                resource_type="menu_import",
                resource_id=duplicate.id,
                response_status=201,
                now=now,
            )
            await db.commit()
            return await _import_detail(db, duplicate)

        categories = [category for section in payload.sections for category in section.categories]
        items = [item for category in categories for item in category.items]
        base_facts = await _base_item_facts(db, base.id if base is not None else None)
        source_codes = {item.stable_code for item in items if item.stable_code is not None}
        active_allergens = set(
            (await db.scalars(select(Allergen.code).where(Allergen.status == "active"))).all()
        )
        findings: list[MenuImportFinding] = []
        for item in items:
            for code in item.allergen_codes:
                if code not in active_allergens:
                    findings.append(
                        MenuImportFinding(
                            organization_id=organization_id,
                            location_id=location_id,
                            menu_id=menu.id,
                            severity="blocker",
                            code="UNKNOWN_ALLERGEN_CODE",
                            entity_type="menu_item",
                            source_key=item.source_key,
                            message_code="UNKNOWN_ALLERGEN_CODE",
                            message_parameters={"allergen_code": code},
                            allowed_actions=[],
                        )
                    )
            if item.stable_code is not None and item.stable_code in base_facts:
                _, base_components, base_allergens = base_facts[item.stable_code]
                component_codes = tuple(
                    sorted(
                        component.stable_code
                        for component in item.components
                        if component.stable_code is not None
                    )
                )
                if (
                    component_codes != tuple(str(value) for value in base_components)
                    or tuple(sorted(item.allergen_codes)) != base_allergens
                ):
                    findings.append(
                        MenuImportFinding(
                            organization_id=organization_id,
                            location_id=location_id,
                            menu_id=menu.id,
                            severity="requires_review",
                            code="CRITICAL_FACT_CHANGE",
                            entity_type="menu_item",
                            source_key=item.source_key,
                            message_code="CRITICAL_FACT_CHANGE",
                            message_parameters={},
                            allowed_actions=["confirm_critical_change"],
                        )
                    )
        for code, (identity, _, _) in base_facts.items():
            if code not in source_codes:
                findings.append(
                    MenuImportFinding(
                        organization_id=organization_id,
                        location_id=location_id,
                        menu_id=menu.id,
                        severity="requires_review",
                        code="ITEM_REMOVAL",
                        entity_type="menu_item",
                        source_key=code,
                        message_code="ITEM_REMOVAL",
                        message_parameters={"menu_item_id": str(identity.id)},
                        allowed_actions=["confirm_removal"],
                    )
                )
        duplicate_names = {
            name
            for name, count in Counter(item.name_uk.casefold() for item in items).items()
            if count > 1
        }
        for item in items:
            if item.name_uk.casefold() in duplicate_names:
                findings.append(
                    MenuImportFinding(
                        organization_id=organization_id,
                        location_id=location_id,
                        menu_id=menu.id,
                        severity="warning",
                        code="DUPLICATE_ITEM_NAME",
                        entity_type="menu_item",
                        source_key=item.source_key,
                        message_code="DUPLICATE_ITEM_NAME",
                        message_parameters={},
                        allowed_actions=[],
                    )
                )

        matched = len(source_codes.intersection(base_facts))
        changed_codes = {
            finding.source_key for finding in findings if finding.code == "CRITICAL_FACT_CHANGE"
        }
        menu_import = MenuImport(
            organization_id=organization_id,
            location_id=location_id,
            menu_id=menu.id,
            base_menu_version_id=base.id if base is not None else None,
            status="ready_for_review",
            review_revision=0,
            source_filename=payload.source_filename,
            source_reference=payload.source_reference,
            source_checksum=checksum,
            source_payload=canonical,
            section_count=len(payload.sections),
            category_count=len(categories),
            item_count=len(items),
            added_count=len(items) - matched,
            changed_count=len(changed_codes),
            removed_count=len(base_facts) - matched,
            unchanged_count=matched - len(changed_codes),
            blocker_count=sum(finding.severity == "blocker" for finding in findings),
            review_count=sum(finding.severity == "requires_review" for finding in findings),
            warning_count=sum(finding.severity == "warning" for finding in findings),
            created_by_user_id=actor_user_id,
            completed_at=now,
        )
        db.add(menu_import)
        await db.flush()
        for finding in findings:
            finding.menu_import_id = menu_import.id
        db.add_all(findings)
        await reserve_idempotency(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="menu_import_create",
            key=idempotency_key,
            fingerprint=fingerprint,
            resource_type="menu_import",
            resource_id=menu_import.id,
            response_status=201,
            now=now,
        )
        db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_type="user",
                action="menu_import_review_created",
                target_type="menu_import",
                target_id=menu_import.id,
                old_values=None,
                new_values={
                    "location_id": str(location_id),
                    "checksum": checksum,
                    "item_count": len(items),
                },
                request_id=request_id,
                outcome="success",
            )
        )
        await db.commit()
        return await _import_detail(db, menu_import)
    except Exception:
        await db.rollback()
        raise


async def resolve_menu_import_finding(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    import_id: UUID,
    finding_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    payload: MenuFindingResolveRequest,
    idempotency_key: str,
    now: datetime,
) -> MenuFindingResolveResponse:
    fingerprint = request_fingerprint(payload.model_dump(mode="json"))
    try:
        replay = await find_idempotency_replay(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="menu_import_finding_resolve",
            key=idempotency_key,
            fingerprint=fingerprint,
            now=now,
        )
        menu_import = await _scoped_import(
            db,
            organization_id=organization_id,
            location_id=location_id,
            import_id=import_id,
            lock=True,
        )
        finding = await db.scalar(
            select(MenuImportFinding)
            .where(
                MenuImportFinding.id == finding_id,
                MenuImportFinding.menu_import_id == menu_import.id,
            )
            .with_for_update()
        )
        if finding is None:
            raise _not_found()
        if replay is not None:
            await db.commit()
            return MenuFindingResolveResponse(
                finding=_finding_response(finding),
                review_revision=menu_import.review_revision,
            )
        if menu_import.status != "ready_for_review":
            raise _error(409, "MENU_IMPORT_NOT_REVIEWABLE", "Імпорт уже не можна редагувати.")
        if menu_import.review_revision != payload.expected_revision:
            raise _revision_conflict()
        if finding.severity == "blocker" or payload.action not in finding.allowed_actions:
            raise _error(422, "FINDING_ACTION_NOT_ALLOWED", "Цю знахідку не можна вирішити так.")
        finding.resolution_status = "resolved"
        finding.resolution_action = payload.action
        finding.target_entity_id = payload.target_entity_id
        finding.resolution_comment = payload.comment.strip() if payload.comment else None
        finding.resolved_by_user_id = actor_user_id
        finding.resolved_at = now
        menu_import.review_revision += 1
        await reserve_idempotency(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="menu_import_finding_resolve",
            key=idempotency_key,
            fingerprint=fingerprint,
            resource_type="menu_import_finding",
            resource_id=finding.id,
            response_status=200,
            now=now,
        )
        db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_type="user",
                action="menu_import_finding_resolved",
                target_type="menu_import_finding",
                target_id=finding.id,
                old_values=None,
                new_values={"action": payload.action, "revision": menu_import.review_revision},
                request_id=request_id,
                outcome="success",
            )
        )
        await db.commit()
        return MenuFindingResolveResponse(
            finding=_finding_response(finding),
            review_revision=menu_import.review_revision,
        )
    except Exception:
        await db.rollback()
        raise


async def _identity[IdentityT: MenuSection | MenuCategory | MenuItem](
    db: AsyncSession,
    model: type[IdentityT],
    *,
    menu_import: MenuImport,
    stable_code: str | None,
) -> IdentityT:
    identity = None
    if stable_code is not None:
        identity = cast(
            IdentityT | None,
            await db.scalar(
                select(model).where(
                    model.menu_id == menu_import.menu_id,
                    model.stable_code == stable_code,
                )
            ),
        )
    if identity is None:
        identity = cast(
            IdentityT,
            model(
                organization_id=menu_import.organization_id,
                location_id=menu_import.location_id,
                menu_id=menu_import.menu_id,
                stable_code=stable_code,
            ),
        )
        db.add(identity)
        await db.flush()
    return identity


async def _clear_draft_graph(db: AsyncSession, version_id: UUID) -> None:
    tables = (
        MenuVersionItemDelta,
        MenuItemVersionAllergen,
        MenuItemVersionComponent,
        MenuItemVersionTranslation,
        MenuItemVersion,
        MenuComponentVersionTranslation,
        MenuComponentVersion,
        MenuVersionCategoryTranslation,
        MenuVersionCategory,
        MenuVersionSectionTranslation,
        MenuVersionSection,
    )
    for model in tables:
        await db.execute(delete(model).where(model.menu_version_id == version_id))


async def _materialize_draft(
    db: AsyncSession,
    *,
    menu_import: MenuImport,
    actor_user_id: UUID,
    now: datetime,
) -> MenuVersion:
    draft = await db.scalar(
        select(MenuVersion)
        .where(MenuVersion.menu_id == menu_import.menu_id, MenuVersion.status == "draft")
        .with_for_update()
    )
    if draft is None:
        highest = await db.scalar(
            select(func.max(MenuVersion.version_number)).where(
                MenuVersion.menu_id == menu_import.menu_id
            )
        )
        draft = MenuVersion(
            organization_id=menu_import.organization_id,
            location_id=menu_import.location_id,
            menu_id=menu_import.menu_id,
            version_number=(highest or 0) + 1,
            status="draft",
            base_version_id=menu_import.base_menu_version_id,
            revision=0,
            created_by_user_id=actor_user_id,
        )
        db.add(draft)
        await db.flush()
    else:
        await _clear_draft_graph(db, draft.id)
        draft.base_version_id = menu_import.base_menu_version_id

    payload = MenuImportCreate.model_validate(menu_import.source_payload)
    imported_item_ids: set[UUID] = set()
    for section_input in payload.sections:
        section_identity = await _identity(
            db,
            MenuSection,
            menu_import=menu_import,
            stable_code=section_input.stable_code,
        )
        section = MenuVersionSection(
            organization_id=menu_import.organization_id,
            location_id=menu_import.location_id,
            menu_id=menu_import.menu_id,
            menu_version_id=draft.id,
            menu_section_id=section_identity.id,
            position=section_input.position,
        )
        db.add(section)
        await db.flush()
        db.add(
            MenuVersionSectionTranslation(
                organization_id=menu_import.organization_id,
                location_id=menu_import.location_id,
                menu_id=menu_import.menu_id,
                menu_version_id=draft.id,
                menu_version_section_id=section.id,
                locale="uk",
                status="ready",
                name=section_input.name_uk,
            )
        )
        for category_input in section_input.categories:
            category_identity = await _identity(
                db,
                MenuCategory,
                menu_import=menu_import,
                stable_code=category_input.stable_code,
            )
            category = MenuVersionCategory(
                organization_id=menu_import.organization_id,
                location_id=menu_import.location_id,
                menu_id=menu_import.menu_id,
                menu_version_id=draft.id,
                menu_category_id=category_identity.id,
                menu_version_section_id=section.id,
                position=category_input.position,
            )
            db.add(category)
            await db.flush()
            db.add(
                MenuVersionCategoryTranslation(
                    organization_id=menu_import.organization_id,
                    location_id=menu_import.location_id,
                    menu_id=menu_import.menu_id,
                    menu_version_id=draft.id,
                    menu_version_category_id=category.id,
                    locale="uk",
                    status="ready",
                    name=category_input.name_uk,
                )
            )
            for item_input in category_input.items:
                item_identity = await _identity(
                    db,
                    MenuItem,
                    menu_import=menu_import,
                    stable_code=item_input.stable_code,
                )
                imported_item_ids.add(item_identity.id)
                item_version = MenuItemVersion(
                    organization_id=menu_import.organization_id,
                    location_id=menu_import.location_id,
                    menu_id=menu_import.menu_id,
                    menu_version_id=draft.id,
                    menu_item_id=item_identity.id,
                    menu_version_category_id=category.id,
                    position=item_input.position,
                    availability=item_input.availability,
                    price_minor=item_input.price_minor,
                    currency=item_input.currency,
                    component_data_status=item_input.component_data_status,
                    allergen_data_status=item_input.allergen_data_status,
                    source_kind="json_import",
                    source_reference=item_input.source_reference or payload.source_reference,
                    source_item_key=item_input.source_item_key or item_input.source_key,
                    verified_by_user_id=actor_user_id,
                    verified_at=now,
                )
                db.add(item_version)
                await db.flush()
                db.add(
                    MenuItemVersionTranslation(
                        organization_id=menu_import.organization_id,
                        location_id=menu_import.location_id,
                        menu_id=menu_import.menu_id,
                        menu_version_id=draft.id,
                        menu_item_version_id=item_version.id,
                        locale="uk",
                        status="ready",
                        name=item_input.name_uk,
                        description=item_input.description_uk,
                    )
                )
                item_payload = MenuItemWrite.model_validate(
                    {
                        **item_input.model_dump(exclude={"source_key", "components"}),
                        "category_id": category.id,
                        "components": [
                            component.model_dump(exclude={"source_key"})
                            for component in item_input.components
                        ],
                        "source_kind": "json_import",
                        "source_reference": item_input.source_reference or payload.source_reference,
                        "source_item_key": item_input.source_item_key or item_input.source_key,
                    }
                )
                await _replace_facts(
                    db,
                    version=draft,
                    item_version=item_version,
                    payload=item_payload,
                    actor_user_id=actor_user_id,
                    now=now,
                )
                await db.flush()
                await _replace_delta(
                    db,
                    version=draft,
                    menu_item_id=item_identity.id,
                    current=item_version,
                )
    if draft.base_version_id is not None:
        base_item_ids = set(
            (
                await db.scalars(
                    select(MenuItemVersion.menu_item_id).where(
                        MenuItemVersion.menu_version_id == draft.base_version_id
                    )
                )
            ).all()
        )
        for removed_id in base_item_ids - imported_item_ids:
            await _replace_delta(
                db,
                version=draft,
                menu_item_id=removed_id,
                current=None,
            )
    draft.revision += 1
    await db.flush()
    return draft


async def confirm_menu_import(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    import_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    acknowledge_warnings: bool,
    idempotency_key: str,
    now: datetime,
) -> MenuImportConfirmResponse:
    fingerprint = request_fingerprint(
        {
            "import_id": str(import_id),
            "expected_revision": expected_revision,
            "acknowledge_warnings": acknowledge_warnings,
        }
    )
    try:
        replay = await find_idempotency_replay(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="menu_import_confirm",
            key=idempotency_key,
            fingerprint=fingerprint,
            now=now,
        )
        menu_import = await _scoped_import(
            db,
            organization_id=organization_id,
            location_id=location_id,
            import_id=import_id,
            lock=True,
        )
        if replay is not None:
            if menu_import.confirmed_menu_version_id is None:
                raise RuntimeError("Confirmed import has no Draft resource")
            detail = await get_menu_version_detail(
                db,
                organization_id=organization_id,
                location_id=location_id,
                version_id=menu_import.confirmed_menu_version_id,
            )
            await db.commit()
            return MenuImportConfirmResponse(
                import_=await _import_detail(db, menu_import), draft=detail
            )
        if menu_import.status != "ready_for_review":
            raise _error(409, "MENU_IMPORT_NOT_REVIEWABLE", "Імпорт уже не можна підтвердити.")
        if menu_import.review_revision != expected_revision:
            raise _revision_conflict()
        findings = list(
            (
                await db.scalars(
                    select(MenuImportFinding).where(
                        MenuImportFinding.menu_import_id == menu_import.id
                    )
                )
            ).all()
        )
        if any(finding.severity == "blocker" for finding in findings):
            raise _error(409, "MENU_IMPORT_BLOCKED", "Імпорт містить блокувальні знахідки.")
        if any(
            finding.severity == "requires_review" and finding.resolution_status != "resolved"
            for finding in findings
        ):
            raise _error(409, "MENU_IMPORT_REVIEW_REQUIRED", "Спершу вирішіть усі знахідки.")
        if menu_import.warning_count and not acknowledge_warnings:
            raise _error(409, "MENU_IMPORT_WARNING_ACK_REQUIRED", "Підтвердьте попередження.")
        current_base = await db.scalar(
            select(MenuVersion)
            .where(MenuVersion.menu_id == menu_import.menu_id, MenuVersion.status == "published")
            .with_for_update()
        )
        current_base_id = current_base.id if current_base is not None else None
        if current_base_id != menu_import.base_menu_version_id:
            menu_import.status = "stale"
            menu_import.completed_at = now
            await db.commit()
            raise _error(409, "MENU_IMPORT_STALE", "Опубліковане меню змінилося; повторіть імпорт.")
        draft = await _materialize_draft(
            db,
            menu_import=menu_import,
            actor_user_id=actor_user_id,
            now=now,
        )
        menu_import.status = "confirmed"
        menu_import.confirmed_menu_version_id = draft.id
        menu_import.confirmed_by_user_id = actor_user_id
        menu_import.confirmed_at = now
        menu_import.completed_at = now
        await reserve_idempotency(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="menu_import_confirm",
            key=idempotency_key,
            fingerprint=fingerprint,
            resource_type="menu_version",
            resource_id=draft.id,
            response_status=200,
            now=now,
        )
        db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_type="user",
                action="menu_import_confirmed",
                target_type="menu_import",
                target_id=menu_import.id,
                old_values=None,
                new_values={"draft_menu_version_id": str(draft.id)},
                request_id=request_id,
                outcome="success",
            )
        )
        await db.commit()
        return MenuImportConfirmResponse(
            import_=await _import_detail(db, menu_import),
            draft=await get_menu_version_detail(
                db,
                organization_id=organization_id,
                location_id=location_id,
                version_id=draft.id,
            ),
        )
    except APIError as exc:
        if exc.code != "MENU_IMPORT_STALE":
            await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise
