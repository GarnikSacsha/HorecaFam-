from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Location,
    Menu,
    MenuItemVersion,
    MenuVersion,
    MenuVersionSectionTranslation,
    Organization,
    User,
)
from app.services.menu_drafts import (
    create_category,
    create_menu_draft,
    create_section,
    delete_category,
    delete_section,
    get_menu_version_hierarchy,
    reorder_categories,
    reorder_sections,
    update_category,
    update_section,
)
from tests.factories import (
    make_category_translation,
    make_item_translation,
    make_item_version,
    make_location,
    make_menu,
    make_menu_category,
    make_menu_item,
    make_menu_section,
    make_menu_version,
    make_organization,
    make_section_translation,
    make_user,
    make_version_category,
    make_version_section,
)


async def seed_identity(
    db_session: AsyncSession,
) -> tuple[Organization, Location, User]:
    organization = make_organization()
    location = make_location(organization)
    user = make_user()
    db_session.add_all([organization, location, user])
    await db_session.commit()
    return organization, location, user


async def assert_api_error(code: str, awaitable: Awaitable[Any]) -> APIError:
    with pytest.raises(APIError) as caught:
        await awaitable
    assert caught.value.code == code
    return caught.value


@pytest.mark.integration
async def test_first_draft_creates_location_menu_and_empty_version(
    db_session: AsyncSession,
) -> None:
    organization, location, user = await seed_identity(db_session)

    draft = await create_menu_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
    )

    menu = await db_session.scalar(select(Menu).where(Menu.location_id == location.id))
    assert menu is not None
    assert draft.menu_id == menu.id
    assert draft.version_number == 1
    assert draft.status == "draft"
    assert draft.base_version_id is None
    assert draft.revision == 0


@pytest.mark.integration
async def test_draft_copies_published_hierarchy_and_item_state(
    db_session: AsyncSession,
) -> None:
    organization, location, user = await seed_identity(db_session)
    menu = make_menu(organization.id, location.id)
    published = make_menu_version(
        menu,
        user.id,
        status="published",
        published_by_user_id=user.id,
        published_at=datetime.now(UTC),
    )
    section = make_menu_section(menu)
    category = make_menu_category(menu)
    item = make_menu_item(menu)
    db_session.add_all([menu, published, section, category, item])
    await db_session.flush()
    version_section = make_version_section(published, section)
    db_session.add(version_section)
    await db_session.flush()
    version_category = make_version_category(published, category, version_section)
    db_session.add(version_category)
    await db_session.flush()
    item_version = make_item_version(published, item, version_category, price_minor=32500)
    db_session.add(item_version)
    await db_session.flush()
    db_session.add_all(
        [
            make_section_translation(published, version_section, name="Основне"),
            make_category_translation(published, version_category, name="Супи"),
            make_item_translation(published, item_version, name="Борщ"),
        ]
    )
    await db_session.commit()

    draft = await create_menu_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
    )
    hierarchy = await get_menu_version_hierarchy(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
    )

    assert draft.base_version_id == published.id
    assert draft.version_number == 2
    assert [entry.name_uk for entry in hierarchy.sections] == ["Основне"]
    assert [entry.name_uk for entry in hierarchy.sections[0].categories] == ["Супи"]
    copied_item = await db_session.scalar(
        select(MenuItemVersion).where(MenuItemVersion.menu_version_id == draft.id)
    )
    assert copied_item is not None
    assert copied_item.menu_item_id == item.id
    assert copied_item.price_minor == 32500


@pytest.mark.integration
async def test_only_one_draft_can_exist_per_location(db_session: AsyncSession) -> None:
    organization, location, user = await seed_identity(db_session)
    first = await create_menu_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
    )
    first_id = first.id

    await assert_api_error(
        "MENU_DRAFT_EXISTS",
        create_menu_draft(
            db_session,
            organization_id=organization.id,
            location_id=location.id,
            actor_user_id=user.id,
            request_id=uuid4(),
        ),
    )
    assert await db_session.get(MenuVersion, first_id) is not None


@pytest.mark.integration
async def test_section_mutation_is_revision_guarded_and_atomic(
    db_session: AsyncSession,
) -> None:
    organization, location, user = await seed_identity(db_session)
    draft = await create_menu_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
    )
    mutation = await create_section(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=0,
        name_uk="Основне",
        stable_code="main",
        position=0,
    )
    assert mutation.revision == 1
    organization_id = organization.id
    location_id = location.id
    user_id = user.id
    draft_id = draft.id
    section_id = mutation.entity.id

    await assert_api_error(
        "REVISION_CONFLICT",
        update_section(
            db_session,
            organization_id=organization_id,
            location_id=location_id,
            version_id=draft_id,
            section_id=section_id,
            actor_user_id=user_id,
            request_id=uuid4(),
            expected_revision=0,
            name_uk="Застаріла зміна",
        ),
    )
    translation = await db_session.scalar(
        select(MenuVersionSectionTranslation).where(
            MenuVersionSectionTranslation.menu_version_section_id == section_id,
            MenuVersionSectionTranslation.locale == "uk",
        )
    )
    assert translation is not None
    assert translation.name == "Основне"


@pytest.mark.integration
async def test_published_version_rejects_mutation(db_session: AsyncSession) -> None:
    organization, location, user = await seed_identity(db_session)
    menu = make_menu(organization.id, location.id)
    published = make_menu_version(
        menu,
        user.id,
        status="published",
        published_by_user_id=user.id,
        published_at=datetime.now(UTC),
    )
    db_session.add_all([menu, published])
    await db_session.commit()

    await assert_api_error(
        "VERSION_IMMUTABLE",
        create_section(
            db_session,
            organization_id=organization.id,
            location_id=location.id,
            version_id=published.id,
            actor_user_id=user.id,
            request_id=uuid4(),
            expected_revision=0,
            name_uk="Не можна",
            stable_code=None,
            position=0,
        ),
    )


@pytest.mark.integration
async def test_reorder_requires_exact_complete_set(db_session: AsyncSession) -> None:
    organization, location, user = await seed_identity(db_session)
    draft = await create_menu_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
    )
    first = await create_section(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=0,
        name_uk="Перша",
        stable_code="first",
        position=0,
    )
    second = await create_section(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=1,
        name_uk="Друга",
        stable_code="second",
        position=1,
    )
    organization_id = organization.id
    location_id = location.id
    user_id = user.id
    draft_id = draft.id
    first_id = first.entity.id
    second_id = second.entity.id

    await assert_api_error(
        "VALIDATION_ERROR",
        reorder_sections(
            db_session,
            organization_id=organization_id,
            location_id=location_id,
            version_id=draft_id,
            actor_user_id=user_id,
            request_id=uuid4(),
            expected_revision=2,
            ordered_ids=[second_id],
        ),
    )
    result = await reorder_sections(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        version_id=draft_id,
        actor_user_id=user_id,
        request_id=uuid4(),
        expected_revision=2,
        ordered_ids=[second_id, first_id],
    )
    assert result.revision == 3
    assert [entry.id for entry in result.entities] == [second_id, first_id]


@pytest.mark.integration
async def test_nonempty_hierarchy_cannot_be_deleted_and_categories_reorder_per_section(
    db_session: AsyncSession,
) -> None:
    organization, location, user = await seed_identity(db_session)
    draft = await create_menu_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
    )
    section = await create_section(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=0,
        name_uk="Основне",
        stable_code=None,
        position=0,
    )
    first = await create_category(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        section_id=section.entity.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=1,
        name_uk="Супи",
        stable_code="soups",
        position=0,
    )
    second = await create_category(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        section_id=section.entity.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=2,
        name_uk="Салати",
        stable_code="salads",
        position=1,
    )
    organization_id = organization.id
    location_id = location.id
    user_id = user.id
    draft_id = draft.id
    section_id = section.entity.id
    first_id = first.entity.id
    second_id = second.entity.id

    await assert_api_error(
        "SECTION_NOT_EMPTY",
        delete_section(
            db_session,
            organization_id=organization_id,
            location_id=location_id,
            version_id=draft_id,
            section_id=section_id,
            actor_user_id=user_id,
            request_id=uuid4(),
            expected_revision=3,
        ),
    )
    reordered = await reorder_categories(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        version_id=draft_id,
        section_id=section_id,
        actor_user_id=user_id,
        request_id=uuid4(),
        expected_revision=3,
        ordered_ids=[second_id, first_id],
    )
    assert reordered.revision == 4

    item_count = await db_session.scalar(
        select(func.count(MenuItemVersion.id)).where(
            MenuItemVersion.menu_version_category_id == first_id
        )
    )
    assert item_count == 0
    deleted_revision = await delete_category(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        version_id=draft_id,
        category_id=first_id,
        actor_user_id=user_id,
        request_id=uuid4(),
        expected_revision=4,
    )
    assert deleted_revision == 5


@pytest.mark.integration
async def test_hierarchy_read_is_tenant_and_location_scoped(
    db_session: AsyncSession,
) -> None:
    organization, location, user = await seed_identity(db_session)
    draft = await create_menu_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
    )

    await assert_api_error(
        "RESOURCE_NOT_FOUND",
        get_menu_version_hierarchy(
            db_session,
            organization_id=uuid4(),
            location_id=location.id,
            version_id=draft.id,
        ),
    )


@pytest.mark.integration
async def test_category_can_move_only_within_same_draft(db_session: AsyncSession) -> None:
    organization, location, user = await seed_identity(db_session)
    draft = await create_menu_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
    )
    first_section = await create_section(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=0,
        name_uk="Кухня",
        stable_code=None,
        position=0,
    )
    second_section = await create_section(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=1,
        name_uk="Бар",
        stable_code=None,
        position=1,
    )
    category = await create_category(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        section_id=first_section.entity.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=2,
        name_uk="Напої",
        stable_code=None,
        position=0,
    )

    moved = await update_category(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        category_id=category.entity.id,
        section_id=second_section.entity.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=3,
        name_uk="Барні напої",
        position=0,
    )
    hierarchy = await get_menu_version_hierarchy(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
    )

    assert moved.revision == 4
    assert hierarchy.sections[0].categories == []
    assert [entry.name_uk for entry in hierarchy.sections[1].categories] == ["Барні напої"]
