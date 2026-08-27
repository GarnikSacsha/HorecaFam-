from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.models import (
    Allergen,
    Menu,
    MenuCategory,
    MenuComponent,
    MenuComponentVersion,
    MenuComponentVersionTranslation,
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


def make_menu(organization_id: UUID, location_id: UUID, **overrides: Any) -> Menu:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": organization_id,
        "location_id": location_id,
    }
    values.update(overrides)
    return Menu(**values)


def _stable_values(menu: Menu, stable_code: str | None) -> dict[str, Any]:
    return {
        "id": uuid4(),
        "organization_id": menu.organization_id,
        "location_id": menu.location_id,
        "menu_id": menu.id,
        "stable_code": stable_code,
    }


def make_menu_section(menu: Menu, **overrides: Any) -> MenuSection:
    values = _stable_values(menu, "main")
    values.update(overrides)
    return MenuSection(**values)


def make_menu_category(menu: Menu, **overrides: Any) -> MenuCategory:
    values = _stable_values(menu, "starters")
    values.update(overrides)
    return MenuCategory(**values)


def make_menu_item(menu: Menu, **overrides: Any) -> MenuItem:
    values = _stable_values(menu, "borshch")
    values.update(overrides)
    return MenuItem(**values)


def make_menu_component(menu: Menu, **overrides: Any) -> MenuComponent:
    values = _stable_values(menu, "beetroot")
    values.update(overrides)
    return MenuComponent(**values)


def make_menu_version(menu: Menu, created_by_user_id: UUID, **overrides: Any) -> MenuVersion:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": menu.organization_id,
        "location_id": menu.location_id,
        "menu_id": menu.id,
        "version_number": 1,
        "status": "draft",
        "revision": 0,
        "created_by_user_id": created_by_user_id,
    }
    values.update(overrides)
    return MenuVersion(**values)


def make_version_section(
    version: MenuVersion,
    section: MenuSection,
    **overrides: Any,
) -> MenuVersionSection:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": version.organization_id,
        "location_id": version.location_id,
        "menu_id": version.menu_id,
        "menu_version_id": version.id,
        "menu_section_id": section.id,
        "position": 0,
    }
    values.update(overrides)
    return MenuVersionSection(**values)


def make_version_category(
    version: MenuVersion,
    category: MenuCategory,
    version_section: MenuVersionSection,
    **overrides: Any,
) -> MenuVersionCategory:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": version.organization_id,
        "location_id": version.location_id,
        "menu_id": version.menu_id,
        "menu_version_id": version.id,
        "menu_category_id": category.id,
        "menu_version_section_id": version_section.id,
        "position": 0,
    }
    values.update(overrides)
    return MenuVersionCategory(**values)


def make_item_version(
    version: MenuVersion,
    item: MenuItem,
    version_category: MenuVersionCategory,
    **overrides: Any,
) -> MenuItemVersion:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": version.organization_id,
        "location_id": version.location_id,
        "menu_id": version.menu_id,
        "menu_version_id": version.id,
        "menu_item_id": item.id,
        "menu_version_category_id": version_category.id,
        "position": 0,
        "availability": "available",
        "currency": "UAH",
        "component_data_status": "unknown",
        "allergen_data_status": "unknown",
        "source_kind": "manual",
    }
    values.update(overrides)
    return MenuItemVersion(**values)


def make_component_version(
    version: MenuVersion,
    component: MenuComponent,
    **overrides: Any,
) -> MenuComponentVersion:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": version.organization_id,
        "location_id": version.location_id,
        "menu_id": version.menu_id,
        "menu_version_id": version.id,
        "menu_component_id": component.id,
    }
    values.update(overrides)
    return MenuComponentVersion(**values)


def make_section_translation(
    version: MenuVersion,
    version_section: MenuVersionSection,
    **overrides: Any,
) -> MenuVersionSectionTranslation:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": version.organization_id,
        "location_id": version.location_id,
        "menu_id": version.menu_id,
        "menu_version_id": version.id,
        "menu_version_section_id": version_section.id,
        "locale": "uk",
        "status": "ready",
        "name": "Основне меню",
    }
    values.update(overrides)
    return MenuVersionSectionTranslation(**values)


def make_category_translation(
    version: MenuVersion,
    version_category: MenuVersionCategory,
    **overrides: Any,
) -> MenuVersionCategoryTranslation:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": version.organization_id,
        "location_id": version.location_id,
        "menu_id": version.menu_id,
        "menu_version_id": version.id,
        "menu_version_category_id": version_category.id,
        "locale": "uk",
        "status": "ready",
        "name": "Перші страви",
    }
    values.update(overrides)
    return MenuVersionCategoryTranslation(**values)


def make_item_translation(
    version: MenuVersion,
    item_version: MenuItemVersion,
    **overrides: Any,
) -> MenuItemVersionTranslation:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": version.organization_id,
        "location_id": version.location_id,
        "menu_id": version.menu_id,
        "menu_version_id": version.id,
        "menu_item_version_id": item_version.id,
        "locale": "uk",
        "status": "ready",
        "name": "Борщ",
        "description": "Перевірений опис страви",
    }
    values.update(overrides)
    return MenuItemVersionTranslation(**values)


def make_component_translation(
    version: MenuVersion,
    component_version: MenuComponentVersion,
    **overrides: Any,
) -> MenuComponentVersionTranslation:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": version.organization_id,
        "location_id": version.location_id,
        "menu_id": version.menu_id,
        "menu_version_id": version.id,
        "menu_component_version_id": component_version.id,
        "locale": "uk",
        "status": "ready",
        "name": "Буряк",
    }
    values.update(overrides)
    return MenuComponentVersionTranslation(**values)


def make_item_component(
    version: MenuVersion,
    item_version: MenuItemVersion,
    component_version: MenuComponentVersion,
    **overrides: Any,
) -> MenuItemVersionComponent:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": version.organization_id,
        "location_id": version.location_id,
        "menu_id": version.menu_id,
        "menu_version_id": version.id,
        "menu_item_version_id": item_version.id,
        "menu_component_version_id": component_version.id,
        "position": 0,
        "optional": False,
        "source_kind": "manual",
        "verified_at": datetime.now(UTC),
    }
    values.update(overrides)
    return MenuItemVersionComponent(**values)


def make_allergen(**overrides: Any) -> Allergen:
    values: dict[str, Any] = {
        "id": uuid4(),
        "code": "gluten",
        "label_uk": "Глютен",
        "label_en": "Gluten",
        "status": "active",
    }
    values.update(overrides)
    return Allergen(**values)


def make_item_allergen(
    version: MenuVersion,
    item_version: MenuItemVersion,
    allergen: Allergen,
    **overrides: Any,
) -> MenuItemVersionAllergen:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": version.organization_id,
        "location_id": version.location_id,
        "menu_id": version.menu_id,
        "menu_version_id": version.id,
        "menu_item_version_id": item_version.id,
        "allergen_id": allergen.id,
        "source_kind": "manual",
        "verified_at": datetime.now(UTC),
    }
    values.update(overrides)
    return MenuItemVersionAllergen(**values)


def make_item_delta(
    version: MenuVersion,
    item: MenuItem,
    **overrides: Any,
) -> MenuVersionItemDelta:
    values: dict[str, Any] = {
        "id": uuid4(),
        "organization_id": version.organization_id,
        "location_id": version.location_id,
        "menu_id": version.menu_id,
        "menu_version_id": version.id,
        "menu_item_id": item.id,
        "delta_kind": "added",
        "training_impact": "review",
        "changed_field_codes": ["composition"],
    }
    values.update(overrides)
    return MenuVersionItemDelta(**values)
