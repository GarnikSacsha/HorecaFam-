from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, Menu, Organization, User
from tests.factories import (
    make_allergen,
    make_category_translation,
    make_component_translation,
    make_component_version,
    make_item_allergen,
    make_item_component,
    make_item_delta,
    make_item_translation,
    make_item_version,
    make_location,
    make_menu,
    make_menu_category,
    make_menu_component,
    make_menu_item,
    make_menu_section,
    make_menu_version,
    make_organization,
    make_section_translation,
    make_user,
    make_version_category,
    make_version_section,
)


async def assert_integrity_error(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


async def menu_root(
    db_session: AsyncSession,
) -> tuple[Organization, Location, User, Menu]:
    organization = make_organization()
    location = make_location(organization)
    user = make_user()
    db_session.add_all([organization, location, user])
    await db_session.flush()
    menu = make_menu(organization.id, location.id)
    db_session.add(menu)
    await db_session.flush()
    return organization, location, user, menu


@pytest.mark.integration
async def test_complete_menu_persistence_graph_is_owned_by_one_version(
    db_session: AsyncSession,
) -> None:
    _organization, _location, user, menu = await menu_root(db_session)
    section = make_menu_section(menu)
    category = make_menu_category(menu)
    item = make_menu_item(menu)
    component = make_menu_component(menu)
    version = make_menu_version(menu, user.id)
    db_session.add_all([section, category, item, component, version])
    await db_session.flush()

    version_section = make_version_section(version, section)
    db_session.add(version_section)
    await db_session.flush()
    version_category = make_version_category(version, category, version_section)
    component_version = make_component_version(version, component)
    db_session.add_all([version_category, component_version])
    await db_session.flush()

    item_version = make_item_version(
        version,
        item,
        version_category,
        price_minor=32500,
        component_data_status="confirmed_present",
        allergen_data_status="confirmed_present",
        verified_by_user_id=user.id,
        verified_at=datetime.now(UTC),
    )
    allergen = make_allergen()
    db_session.add_all([item_version, allergen])
    await db_session.flush()

    delta = make_item_delta(version, item)
    records = [
        make_section_translation(version, version_section),
        make_category_translation(version, version_category),
        make_item_translation(version, item_version),
        make_component_translation(version, component_version),
        make_item_component(
            version,
            item_version,
            component_version,
            verified_by_user_id=user.id,
        ),
        make_item_allergen(
            version,
            item_version,
            allergen,
            verified_by_user_id=user.id,
        ),
        delta,
    ]
    db_session.add_all(records)
    await db_session.commit()

    assert version.status == "draft"
    assert version.revision == 0
    assert item_version.currency == "UAH"
    assert delta.changed_field_codes == ["composition"]


@pytest.mark.integration
async def test_location_has_only_one_menu(db_session: AsyncSession) -> None:
    organization, location, _user, menu = await menu_root(db_session)
    db_session.add(menu)
    await db_session.commit()

    db_session.add(make_menu(organization.id, location.id))
    await assert_integrity_error(db_session)


@pytest.mark.integration
async def test_menu_rejects_cross_organization_location(db_session: AsyncSession) -> None:
    organization_a = make_organization(name="A")
    organization_b = make_organization(name="B")
    location_a = make_location(organization_a)
    db_session.add_all([organization_a, organization_b, location_a])
    await db_session.flush()

    db_session.add(make_menu(organization_b.id, location_a.id))
    await assert_integrity_error(db_session)


@pytest.mark.integration
@pytest.mark.parametrize("status", ["draft", "published"])
async def test_menu_has_at_most_one_current_version_per_status(
    db_session: AsyncSession,
    status: str,
) -> None:
    _organization, _location, user, menu = await menu_root(db_session)
    state = {}
    if status == "published":
        state = {
            "published_by_user_id": user.id,
            "published_at": datetime.now(UTC),
        }
    first = make_menu_version(menu, user.id, status=status, **state)
    db_session.add(first)
    await db_session.commit()

    db_session.add(make_menu_version(menu, user.id, version_number=2, status=status, **state))
    await assert_integrity_error(db_session)


@pytest.mark.integration
async def test_stable_code_is_normalized_and_unique_per_menu(
    db_session: AsyncSession,
) -> None:
    _organization, _location, _user, menu = await menu_root(db_session)
    db_session.add(make_menu_item(menu, stable_code="Borshch"))
    await assert_integrity_error(db_session)

    _organization, _location, _user, menu = await menu_root(db_session)
    db_session.add_all(
        [
            make_menu_item(menu, stable_code="borshch"),
            make_menu_item(menu, stable_code="borshch"),
        ]
    )
    await assert_integrity_error(db_session)


@pytest.mark.integration
async def test_category_rejects_section_from_another_version(
    db_session: AsyncSession,
) -> None:
    _organization, _location, user, menu = await menu_root(db_session)
    section = make_menu_section(menu)
    category = make_menu_category(menu)
    version_one = make_menu_version(menu, user.id)
    version_two = make_menu_version(
        menu,
        user.id,
        version_number=2,
        status="archived",
        published_by_user_id=user.id,
        published_at=datetime.now(UTC),
        archived_at=datetime.now(UTC),
    )
    db_session.add_all([section, category, version_one, version_two])
    await db_session.flush()
    version_section = make_version_section(version_one, section)
    db_session.add(version_section)
    await db_session.flush()

    db_session.add(make_version_category(version_two, category, version_section))
    await assert_integrity_error(db_session)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("position", -1),
        ("price_minor", -1),
        ("currency", "uah"),
        ("availability", "hidden"),
        ("component_data_status", "empty"),
        ("allergen_data_status", "empty"),
        ("source_kind", "csv"),
    ],
)
async def test_item_version_rejects_noncanonical_values(
    db_session: AsyncSession,
    field: str,
    value: object,
) -> None:
    _organization, _location, user, menu = await menu_root(db_session)
    section = make_menu_section(menu)
    category = make_menu_category(menu)
    item = make_menu_item(menu)
    version = make_menu_version(menu, user.id)
    db_session.add_all([section, category, item, version])
    await db_session.flush()
    version_section = make_version_section(version, section)
    db_session.add(version_section)
    await db_session.flush()
    version_category = make_version_category(version, category, version_section)
    db_session.add(version_category)
    await db_session.flush()

    db_session.add(make_item_version(version, item, version_category, **{field: value}))
    await assert_integrity_error(db_session)


@pytest.mark.integration
async def test_component_link_rejects_component_from_another_version(
    db_session: AsyncSession,
) -> None:
    _organization, _location, user, menu = await menu_root(db_session)
    section = make_menu_section(menu)
    category = make_menu_category(menu)
    item = make_menu_item(menu)
    component = make_menu_component(menu)
    draft = make_menu_version(menu, user.id)
    archived = make_menu_version(
        menu,
        user.id,
        version_number=2,
        status="archived",
        published_by_user_id=user.id,
        published_at=datetime.now(UTC),
        archived_at=datetime.now(UTC),
    )
    db_session.add_all([section, category, item, component, draft, archived])
    await db_session.flush()
    version_section = make_version_section(draft, section)
    db_session.add(version_section)
    await db_session.flush()
    version_category = make_version_category(draft, category, version_section)
    component_version = make_component_version(archived, component)
    db_session.add_all([version_category, component_version])
    await db_session.flush()
    item_version = make_item_version(draft, item, version_category)
    db_session.add(item_version)
    await db_session.flush()

    db_session.add(make_item_component(draft, item_version, component_version))
    await assert_integrity_error(db_session)
