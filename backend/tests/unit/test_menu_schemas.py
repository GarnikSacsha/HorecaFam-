from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.menu import MenuComponentInput, MenuItemPatch, MenuItemWrite


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
