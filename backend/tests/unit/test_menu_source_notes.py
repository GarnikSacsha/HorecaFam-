import pytest

from app.services.menu_source_notes import _catalog, menu_source_note

REFERENCE = "snapshot-sha256:4e6e6d6cd5b3557b654ffeae7106ddf2428d5e0827519bacc352f1cb3a693e51"


def arguments() -> dict[str, str | None]:
    return dict(
        source_kind="json_import",
        source_reference=REFERENCE,
        source_item_key="dish-1854644",
        name='Морозиво Maropu "Пломбір"',
        description="Ніжний вершковий пломбір із насиченим молочним смаком.",
        locale="uk",
    )


def test_source_annotation_preserves_unknown_recipe_and_unverified_allergen() -> None:
    note = menu_source_note(**arguments())  # type: ignore[arg-type]
    assert note is not None
    assert note.allergen_labels == ["Молоко"]
    assert note.composition is None
    assert note.verification_status == "unverified"
    assert "можу запропонувати" in note.guest_description


@pytest.mark.parametrize(
    "key,value",
    [
        ("source_kind", "manual"),
        ("source_reference", None),
        ("source_reference", "other"),
        ("source_item_key", "dish-other"),
        ("name", "Changed"),
        ("description", "Changed"),
        ("locale", "en"),
    ],
)
def test_mismatched_source_has_no_annotation(key: str, value: str | None) -> None:
    values = arguments()
    values[key] = value
    assert menu_source_note(**values) is None  # type: ignore[arg-type]


def test_every_packaged_item_matches_without_promoting_source_facts() -> None:
    catalog = _catalog()
    assert len(catalog.items) == 308
    assert sum(bool(item.note.allergen_labels) for item in catalog.items.values()) == 108
    assert sum(item.note.composition is not None for item in catalog.items.values()) == 21
    for key, item in catalog.items.items():
        note = menu_source_note(
            source_kind="json_import",
            source_reference=REFERENCE,
            source_item_key=key,
            name=item.name,
            description=item.description,
            locale="uk",
        )
        assert note == item.note
        assert note is not None and note.verification_status == "unverified"
        note.allergen_labels.append("test-only")
        assert "test-only" not in item.note.allergen_labels
