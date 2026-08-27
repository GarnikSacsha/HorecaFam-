import base64
import binascii
import json
from typing import Any, Literal, cast
from uuid import UUID

from sqlalchemy import exists, literal, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import APIError
from app.models import (
    Allergen,
    Menu,
    MenuComponentVersion,
    MenuComponentVersionTranslation,
    MenuItemVersion,
    MenuItemVersionAllergen,
    MenuItemVersionComponent,
    MenuItemVersionTranslation,
    MenuVersion,
    MenuVersionCategory,
    MenuVersionCategoryTranslation,
    MenuVersionSection,
    MenuVersionSectionTranslation,
)
from app.schemas.menu import (
    EmployeeMenuAllergen,
    EmployeeMenuCategorySummary,
    EmployeeMenuComponent,
    EmployeeMenuItemDetail,
    EmployeeMenuItemSummary,
    EmployeeMenuResponse,
    EmployeeMenuSectionSummary,
    EmployeeMenuSummary,
)


def _not_found() -> APIError:
    return APIError(status_code=404, code="RESOURCE_NOT_FOUND", message="Ресурс не знайдено.")


def _invalid_cursor() -> APIError:
    return APIError(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Перевірте правильність заповнення полів.",
    )


def _encode_cursor(section: int, category: int, item: int, item_id: UUID) -> str:
    raw = json.dumps([section, category, item, str(item_id)], separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[int, int, int, UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded).decode())
        if not isinstance(value, list) or len(value) != 4:
            raise ValueError
        return int(value[0]), int(value[1]), int(value[2]), UUID(str(value[3]))
    except (ValueError, TypeError, binascii.Error, UnicodeDecodeError, json.JSONDecodeError):
        raise _invalid_cursor() from None


async def _current_menu_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
) -> tuple[Menu, MenuVersion] | None:
    row = (
        await db.execute(
            select(Menu, MenuVersion)
            .join(MenuVersion, MenuVersion.menu_id == Menu.id)
            .where(
                Menu.organization_id == organization_id,
                Menu.location_id == location_id,
                MenuVersion.status == "published",
            )
        )
    ).one_or_none()
    if row is None:
        return None
    return row[0], row[1]


def _localized_text(
    uk: MenuItemVersionTranslation | MenuVersionSectionTranslation | MenuVersionCategoryTranslation,
    en: MenuItemVersionTranslation
    | MenuVersionSectionTranslation
    | MenuVersionCategoryTranslation
    | None,
    preferred_locale: str,
) -> tuple[str, str | None, Literal["uk", "en"], bool]:
    if preferred_locale == "en" and en is not None and en.status == "ready":
        return en.name, getattr(en, "description", None), "en", False
    return uk.name, getattr(uk, "description", None), "uk", preferred_locale == "en"


async def _menu_summary(
    db: AsyncSession,
    *,
    menu: Menu,
    version: MenuVersion,
    preferred_locale: str,
) -> EmployeeMenuSummary:
    section_en = aliased(MenuVersionSectionTranslation)
    section_rows = (
        await db.execute(
            select(
                MenuVersionSection,
                MenuVersionSectionTranslation,
                section_en,
            )
            .join(
                MenuVersionSectionTranslation,
                (MenuVersionSectionTranslation.menu_version_section_id == MenuVersionSection.id)
                & (MenuVersionSectionTranslation.locale == "uk"),
            )
            .outerjoin(
                section_en,
                (section_en.menu_version_section_id == MenuVersionSection.id)
                & (section_en.locale == "en"),
            )
            .where(MenuVersionSection.menu_version_id == version.id)
            .order_by(MenuVersionSection.position, MenuVersionSection.id)
        )
    ).all()
    category_en = aliased(MenuVersionCategoryTranslation)
    category_rows = (
        await db.execute(
            select(
                MenuVersionCategory,
                MenuVersionCategoryTranslation,
                category_en,
            )
            .join(
                MenuVersionCategoryTranslation,
                (MenuVersionCategoryTranslation.menu_version_category_id == MenuVersionCategory.id)
                & (MenuVersionCategoryTranslation.locale == "uk"),
            )
            .outerjoin(
                category_en,
                (category_en.menu_version_category_id == MenuVersionCategory.id)
                & (category_en.locale == "en"),
            )
            .where(MenuVersionCategory.menu_version_id == version.id)
            .order_by(
                MenuVersionCategory.menu_version_section_id,
                MenuVersionCategory.position,
                MenuVersionCategory.id,
            )
        )
    ).all()
    categories_by_section: dict[UUID, list[EmployeeMenuCategorySummary]] = {}
    for category, uk, en in category_rows:
        name, _description, _locale, _fallback = _localized_text(uk, en, preferred_locale)
        categories_by_section.setdefault(category.menu_version_section_id, []).append(
            EmployeeMenuCategorySummary(
                id=category.id,
                section_id=category.menu_version_section_id,
                name=name,
                position=category.position,
            )
        )
    sections = []
    for section, uk, en in section_rows:
        name, _description, _locale, _fallback = _localized_text(uk, en, preferred_locale)
        sections.append(
            EmployeeMenuSectionSummary(
                id=section.id,
                name=name,
                position=section.position,
                categories=categories_by_section.get(section.id, []),
            )
        )
    if version.published_at is None:
        raise RuntimeError("Published Menu Version has no publication timestamp")
    return EmployeeMenuSummary(
        menu_id=menu.id,
        menu_version_id=version.id,
        location_id=menu.location_id,
        version_number=version.version_number,
        published_at=version.published_at,
        sections=sections,
    )


def _item_summary(row: Any, preferred_locale: str) -> EmployeeMenuItemSummary:
    item, identity_id, item_uk, item_en, category, category_uk, section, section_uk = row
    item_name, description, locale, fallback = _localized_text(item_uk, item_en, preferred_locale)
    category_name, _value, _locale, _fallback = _localized_text(category_uk, None, preferred_locale)
    section_name, _value, _locale, _fallback = _localized_text(section_uk, None, preferred_locale)
    excerpt = description[:180] if description else None
    return EmployeeMenuItemSummary(
        item_id=identity_id,
        name=item_name,
        description_excerpt=excerpt,
        category_id=category.id,
        category_name=category_name,
        section_id=section.id,
        section_name=section_name,
        availability=item.availability,
        price_minor=item.price_minor,
        currency=item.currency,
        content_locale=locale,
        translation_fallback=fallback,
    )


def _item_statement(version_id: UUID, preferred_locale: str) -> Any:
    item_en = aliased(MenuItemVersionTranslation)
    return (
        select(
            MenuItemVersion,
            MenuItemVersion.menu_item_id,
            MenuItemVersionTranslation,
            item_en,
            MenuVersionCategory,
            MenuVersionCategoryTranslation,
            MenuVersionSection,
            MenuVersionSectionTranslation,
        )
        .join(
            MenuItemVersionTranslation,
            (MenuItemVersionTranslation.menu_item_version_id == MenuItemVersion.id)
            & (MenuItemVersionTranslation.locale == "uk"),
        )
        .outerjoin(
            item_en,
            (item_en.menu_item_version_id == MenuItemVersion.id) & (item_en.locale == "en"),
        )
        .join(
            MenuVersionCategory,
            MenuVersionCategory.id == MenuItemVersion.menu_version_category_id,
        )
        .join(
            MenuVersionCategoryTranslation,
            (MenuVersionCategoryTranslation.menu_version_category_id == MenuVersionCategory.id)
            & (MenuVersionCategoryTranslation.locale == "uk"),
        )
        .join(
            MenuVersionSection,
            MenuVersionSection.id == MenuVersionCategory.menu_version_section_id,
        )
        .join(
            MenuVersionSectionTranslation,
            (MenuVersionSectionTranslation.menu_version_section_id == MenuVersionSection.id)
            & (MenuVersionSectionTranslation.locale == "uk"),
        )
        .where(MenuItemVersion.menu_version_id == version_id)
    )


async def list_employee_menu(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    preferred_locale: str,
    query: str | None,
    section_id: UUID | None,
    category_id: UUID | None,
    cursor: str | None,
    limit: int,
) -> EmployeeMenuResponse:
    current = await _current_menu_version(
        db,
        organization_id=organization_id,
        location_id=location_id,
    )
    if current is None:
        return EmployeeMenuResponse(menu=None, items=[], next_cursor=None)
    menu, version = current
    statement = _item_statement(version.id, preferred_locale)
    if section_id is not None:
        statement = statement.where(MenuVersionSection.id == section_id)
    if category_id is not None:
        statement = statement.where(MenuVersionCategory.id == category_id)
    if query is not None:
        normalized = query.strip()
        if not normalized:
            raise _invalid_cursor()
        escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        component_match = exists(
            select(1)
            .select_from(MenuItemVersionComponent)
            .join(
                MenuComponentVersionTranslation,
                MenuComponentVersionTranslation.menu_component_version_id
                == MenuItemVersionComponent.menu_component_version_id,
            )
            .where(
                MenuItemVersionComponent.menu_item_version_id == MenuItemVersion.id,
                MenuComponentVersionTranslation.status == "ready",
                MenuComponentVersionTranslation.name.ilike(pattern, escape="\\"),
            )
        )
        statement = statement.where(
            MenuItemVersionTranslation.name.ilike(pattern, escape="\\") | component_match
        )
    if cursor is not None:
        cursor_values = _decode_cursor(cursor)
        statement = statement.where(
            tuple_(
                MenuVersionSection.position,
                MenuVersionCategory.position,
                MenuItemVersion.position,
                MenuItemVersion.menu_item_id,
            )
            > tuple_(*(literal(value) for value in cursor_values))
        )
    statement = statement.order_by(
        MenuVersionSection.position,
        MenuVersionCategory.position,
        MenuItemVersion.position,
        MenuItemVersion.menu_item_id,
    ).limit(limit + 1)
    rows = list((await db.execute(statement)).all())
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit and page:
        item, _identity, _item_uk, _item_en, category, _cat_uk, section, _section_uk = page[-1]
        next_cursor = _encode_cursor(
            section.position,
            category.position,
            item.position,
            item.menu_item_id,
        )
    return EmployeeMenuResponse(
        menu=await _menu_summary(
            db,
            menu=menu,
            version=version,
            preferred_locale=preferred_locale,
        ),
        items=[_item_summary(row, preferred_locale) for row in page],
        next_cursor=next_cursor,
    )


async def get_employee_menu_item(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    preferred_locale: str,
    item_id: UUID,
) -> EmployeeMenuItemDetail:
    current = await _current_menu_version(
        db,
        organization_id=organization_id,
        location_id=location_id,
    )
    if current is None:
        raise _not_found()
    _menu, version = current
    row = (
        await db.execute(
            _item_statement(version.id, preferred_locale).where(
                MenuItemVersion.menu_item_id == item_id
            )
        )
    ).one_or_none()
    if row is None:
        raise _not_found()
    summary = _item_summary(row, preferred_locale)
    item = cast(MenuItemVersion, row[0])
    component_uk = aliased(MenuComponentVersionTranslation)
    component_en = aliased(MenuComponentVersionTranslation)
    component_rows = (
        await db.execute(
            select(MenuItemVersionComponent, component_uk, component_en)
            .join(
                MenuComponentVersion,
                MenuComponentVersion.id == MenuItemVersionComponent.menu_component_version_id,
            )
            .join(
                component_uk,
                (component_uk.menu_component_version_id == MenuComponentVersion.id)
                & (component_uk.locale == "uk"),
            )
            .outerjoin(
                component_en,
                (component_en.menu_component_version_id == MenuComponentVersion.id)
                & (component_en.locale == "en"),
            )
            .where(MenuItemVersionComponent.menu_item_version_id == item.id)
            .order_by(MenuItemVersionComponent.position, MenuItemVersionComponent.id)
        )
    ).all()
    components = []
    for link, uk, en in component_rows:
        name, _description, _locale, _fallback = _localized_text(uk, en, preferred_locale)
        components.append(
            EmployeeMenuComponent(name=name, optional=link.optional, position=link.position)
        )
    allergen_rows = (
        (
            await db.execute(
                select(Allergen)
                .join(MenuItemVersionAllergen, MenuItemVersionAllergen.allergen_id == Allergen.id)
                .where(MenuItemVersionAllergen.menu_item_version_id == item.id)
                .order_by(Allergen.code)
            )
        )
        .scalars()
        .all()
    )
    allergens = [
        EmployeeMenuAllergen(
            code=allergen.code,
            label=(
                allergen.label_en
                if preferred_locale == "en" and allergen.label_en
                else allergen.label_uk
            ),
        )
        for allergen in allergen_rows
    ]
    _item, _identity, item_uk, item_en, *_rest = row
    _name, description, _locale, _fallback = _localized_text(item_uk, item_en, preferred_locale)
    return EmployeeMenuItemDetail(
        **summary.model_dump(),
        description=description,
        components=components,
        allergen_data_status=item.allergen_data_status,
        allergens=allergens,
    )
