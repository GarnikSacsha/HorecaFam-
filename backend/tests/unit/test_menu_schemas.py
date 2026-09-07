from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.menu import (
    MenuCategoryPatch,
    MenuComponentInput,
    MenuFindingResolveRequest,
    MenuImportCreate,
    MenuItemPatch,
    MenuItemWrite,
    MenuReorderRequest,
    MenuSectionPatch,
)


def valid_item(**overrides: object) -> MenuItemWrite:
    values: dict[str, object] = {
        "category_id": uuid4(),
        "stable_code": "borshch",
        "name_uk": "Борщ",
        "description_uk": "Український борщ",
        "price_minor": 32500,
        "currency": "UAH",
        "availability": "available",
        "position": 0,
        "component_data_status": "confirmed_present",
        "components": [
            {
                "stable_code": "beetroot",
                "name_uk": "Буряк",
                "optional": False,
                "position": 0,
            }
        ],
        "allergen_data_status": "confirmed_none",
        "allergen_codes": [],
        "source_kind": "manual",
        "source_reference": None,
        "source_item_key": None,
    }
    values.update(overrides)
    return MenuItemWrite.model_validate(values)


@pytest.mark.parametrize(
    ("status", "components"),
    [
        ("unknown", [{"name_uk": "Буряк", "position": 0}]),
        ("confirmed_none", [{"name_uk": "Буряк", "position": 0}]),
        ("confirmed_present", []),
    ],
)
def test_component_completeness_rejects_contradictions(
    status: str,
    components: list[dict[str, object]],
) -> None:
    with pytest.raises(ValidationError):
        valid_item(component_data_status=status, components=components)


@pytest.mark.parametrize(
    ("status", "codes"),
    [
        ("unknown", ["milk"]),
        ("confirmed_none", ["milk"]),
        ("confirmed_present", []),
    ],
)
def test_allergen_completeness_rejects_contradictions(
    status: str,
    codes: list[str],
) -> None:
    with pytest.raises(ValidationError):
        valid_item(allergen_data_status=status, allergen_codes=codes)


def test_item_rejects_duplicate_component_identity_and_allergen_codes() -> None:
    component_id = uuid4()
    with pytest.raises(ValidationError):
        valid_item(
            components=[
                {"id": component_id, "name_uk": "Буряк", "position": 0},
                {"id": component_id, "name_uk": "Овоч", "position": 1},
            ]
        )
    with pytest.raises(ValidationError):
        valid_item(
            allergen_data_status="confirmed_present",
            allergen_codes=["milk", "milk"],
        )


def test_item_normalizes_codes_text_and_currency() -> None:
    item = valid_item(
        stable_code="  BORSHCH ",
        name_uk="  Борщ  ",
        components=[
            MenuComponentInput(
                stable_code="  BEETROOT ",
                name_uk="  Буряк ",
                position=0,
            )
        ],
    )

    assert item.stable_code == "borshch"
    assert item.name_uk == "Борщ"
    assert item.components[0].stable_code == "beetroot"


def test_item_patch_requires_at_least_one_mutable_field() -> None:
    with pytest.raises(ValidationError):
        MenuItemPatch(expected_revision=1)


@pytest.mark.parametrize(
    "field",
    [
        "stable_code",
        "name_uk",
        "description_uk",
        "source_reference",
        "source_item_key",
        "allergen_codes",
    ],
)
def test_patch_distinguishes_omission_from_explicit_null(field: str) -> None:
    patch = MenuItemPatch.model_validate({"expected_revision": 1, field: None})
    assert patch.model_dump(exclude_unset=True) == {"expected_revision": 1, field: None}


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("stable_code", " CODE ", "code"),
        ("name_uk", " Назва ", "Назва"),
        ("description_uk", "   ", None),
        ("description_uk", " Опис ", "Опис"),
        ("source_reference", " ref ", "ref"),
        ("source_item_key", " key ", "key"),
        ("allergen_codes", [" MILK "], ["milk"]),
    ],
)
def test_patch_normalizes_only_supplied_fields(field: str, value: object, expected: object) -> None:
    patch = MenuItemPatch.model_validate({"expected_revision": 1, field: value})
    assert patch.model_dump(exclude_unset=True) == {"expected_revision": 1, field: expected}


@pytest.mark.parametrize(
    "payload",
    [
        {
            "components": [
                {"name_uk": "А", "stable_code": "x", "position": 0},
                {"name_uk": "Б", "stable_code": " X ", "position": 1},
            ]
        },
        {"components": [{"name_uk": "А", "position": 1}]},
        {"allergen_codes": ["milk", " MILK "]},
        {"stable_code": "   "},
        {"name_uk": "   "},
    ],
)
def test_patch_rejects_invalid_normalized_facts(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        MenuItemPatch.model_validate({"expected_revision": 1, **payload})


def test_write_rejects_duplicate_stable_codes_and_noncontiguous_components() -> None:
    with pytest.raises(ValidationError):
        valid_item(
            components=[
                {"name_uk": "А", "stable_code": "X", "position": 0},
                {"name_uk": "Б", "stable_code": "x", "position": 1},
            ]
        )
    with pytest.raises(ValidationError):
        valid_item(components=[{"name_uk": "А", "position": 1}])
    assert (
        valid_item(
            stable_code=None, components=[{"stable_code": None, "name_uk": "А", "position": 0}]
        ).stable_code
        is None
    )


@pytest.mark.parametrize("schema", [MenuSectionPatch, MenuCategoryPatch])
def test_hierarchy_patch_normalizes_optional_fields_and_requires_mutation(
    schema: type[MenuSectionPatch] | type[MenuCategoryPatch],
) -> None:
    with pytest.raises(ValidationError):
        schema.model_validate({"expected_revision": 0})
    nulls = schema.model_validate({"expected_revision": 0, "name_uk": None, "stable_code": None})
    assert nulls.name_uk is None and nulls.stable_code is None
    values = schema.model_validate(
        {"expected_revision": 0, "name_uk": " Назва ", "stable_code": " CODE "}
    )
    assert values.name_uk == "Назва" and values.stable_code == "code"


def test_reorder_ids_and_finding_target_are_validated() -> None:
    identity = uuid4()
    assert MenuReorderRequest(ordered_ids=[], expected_revision=0).ordered_ids == []
    with pytest.raises(ValidationError):
        MenuReorderRequest(ordered_ids=[identity, identity], expected_revision=0)
    with pytest.raises(ValidationError):
        MenuFindingResolveRequest(action="map_existing", expected_revision=0)
    with pytest.raises(ValidationError):
        MenuFindingResolveRequest(
            action="confirm_removal", target_entity_id=identity, expected_revision=0
        )
    assert (
        MenuFindingResolveRequest(
            action="map_existing", target_entity_id=identity, expected_revision=0
        ).target_entity_id
        == identity
    )


@pytest.mark.parametrize("level", ["item", "category", "section"])
@pytest.mark.parametrize("damage", ["duplicate_key", "position"])
def test_import_rejects_ambiguous_hierarchy(level: str, damage: str) -> None:
    item = valid_item().model_dump(mode="json")
    item.pop("category_id")
    item["source_key"] = "item"
    category = {"source_key": "category", "name_uk": "Категорія", "position": 0, "items": [item]}
    section = {
        "source_key": "section",
        "name_uk": "Розділ",
        "position": 0,
        "categories": [category],
    }
    payload = {"source_filename": "menu.json", "sections": [section]}
    target = {"item": item, "category": category, "section": section}[level]
    if damage == "position":
        target["position"] = 1
    else:
        duplicate = dict(target)
        duplicate["position"] = 1
        if level == "item":
            category["items"] = [item, duplicate]
        elif level == "category":
            section["categories"] = [category, duplicate]
        else:
            payload["sections"] = [section, duplicate]
    with pytest.raises(ValidationError):
        MenuImportCreate.model_validate(payload)


def test_import_source_reference_is_optional_but_not_blank() -> None:
    request = MenuImportCreate(source_filename=" menu.json ", source_reference=None, sections=[])
    assert request.source_filename == "menu.json" and request.source_reference is None
    with pytest.raises(ValidationError):
        MenuImportCreate(source_filename="menu.json", source_reference="   ", sections=[])


def test_optional_import_and_hierarchy_codes_preserve_explicit_null() -> None:
    from app.schemas.menu import MenuCategoryCreate, MenuImportItem, MenuSectionCreate

    section = MenuSectionCreate(name_uk="Menu", stable_code=None, position=0, expected_revision=0)
    category = MenuCategoryCreate(
        section_id=uuid4(), name_uk="Main", stable_code=None, position=0, expected_revision=0
    )
    payload = valid_item(stable_code=None).model_dump(exclude={"category_id"})
    item = MenuImportItem.model_validate({**payload, "source_key": "source-1"})
    assert section.stable_code is category.stable_code is item.stable_code is None
