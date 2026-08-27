from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Location,
    MenuItemVersionAllergen,
    MenuItemVersionComponent,
    MenuVersion,
    MenuVersionCategory,
    MenuVersionItemDelta,
    Organization,
    User,
)
from app.schemas.menu import MenuItemPatch, MenuItemWrite
from app.services.menu_drafts import create_category, create_menu_draft, create_section
from app.services.menus import create_menu_item, delete_menu_item, update_menu_item
from tests.factories import make_allergen, make_location, make_organization, make_user


async def draft_category(
    db_session: AsyncSession,
) -> tuple[Organization, Location, User, MenuVersion, MenuVersionCategory]:
    organization = make_organization()
    location = make_location(organization)
    user = make_user()
    allergen = make_allergen(code="milk", label_uk="Молоко")
    db_session.add_all([organization, location, user, allergen])
    await db_session.commit()
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
        stable_code="main",
        position=0,
    )
    category = await create_category(
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
    return organization, location, user, draft, category.entity


def item_payload(category_id: UUID, **overrides: object) -> MenuItemWrite:
    values: dict[str, object] = {
        "category_id": category_id,
        "stable_code": "borshch",
        "name_uk": "Борщ",
        "description_uk": "Перевірений опис",
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
        "allergen_data_status": "confirmed_present",
        "allergen_codes": ["milk"],
        "source_kind": "manual",
        "source_reference": "admin-entry",
        "source_item_key": None,
    }
    values.update(overrides)
    return MenuItemWrite.model_validate(values)


@pytest.mark.integration
async def test_create_item_persists_verified_facts_provenance_and_added_delta(
    db_session: AsyncSession,
) -> None:
    organization, location, user, draft, category = await draft_category(db_session)

    result = await create_menu_item(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=2,
        payload=item_payload(category.id),
        now=datetime.now(UTC),
    )

    component_link = await db_session.scalar(
        select(MenuItemVersionComponent).where(
            MenuItemVersionComponent.menu_item_version_id == result.item_version.id
        )
    )
    allergen_link = await db_session.scalar(
        select(MenuItemVersionAllergen).where(
            MenuItemVersionAllergen.menu_item_version_id == result.item_version.id
        )
    )
    delta = await db_session.scalar(
        select(MenuVersionItemDelta).where(
            MenuVersionItemDelta.menu_version_id == draft.id,
            MenuVersionItemDelta.menu_item_id == result.item_version.menu_item_id,
        )
    )
    assert result.revision == 3
    assert component_link is not None and component_link.verified_by_user_id == user.id
    assert component_link.source_reference == "admin-entry"
    assert allergen_link is not None and allergen_link.verified_at is not None
    assert delta is not None
    assert (delta.delta_kind, delta.training_impact) == ("added", "required")


@pytest.mark.integration
async def test_price_only_update_has_no_training_impact(db_session: AsyncSession) -> None:
    organization, location, user, draft, category = await draft_category(db_session)
    created = await create_menu_item(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=2,
        payload=item_payload(category.id),
        now=datetime.now(UTC),
    )
    draft.status = "published"
    draft.published_by_user_id = user.id
    draft.published_at = datetime.now(UTC)
    await db_session.commit()
    copied = await create_menu_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
    )

    updated = await update_menu_item(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=copied.id,
        item_id=created.item_version.menu_item_id,
        actor_user_id=user.id,
        request_id=uuid4(),
        payload=MenuItemPatch(expected_revision=0, price_minor=35000),
        now=datetime.now(UTC),
    )

    assert updated.delta.delta_kind == "changed"
    assert updated.delta.training_impact == "none"
    assert updated.delta.changed_field_codes == ["price_minor"]


@pytest.mark.integration
async def test_component_change_requires_training(db_session: AsyncSession) -> None:
    organization, location, user, draft, category = await draft_category(db_session)
    created = await create_menu_item(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=2,
        payload=item_payload(category.id),
        now=datetime.now(UTC),
    )
    draft.status = "published"
    draft.published_by_user_id = user.id
    draft.published_at = datetime.now(UTC)
    await db_session.commit()
    copied = await create_menu_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
    )
    changed_components = [
        {
            "stable_code": "potato",
            "name_uk": "Картопля",
            "optional": False,
            "position": 0,
        }
    ]

    updated = await update_menu_item(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=copied.id,
        item_id=created.item_version.menu_item_id,
        actor_user_id=user.id,
        request_id=uuid4(),
        payload=MenuItemPatch(expected_revision=0, components=changed_components),
        now=datetime.now(UTC),
    )

    assert updated.delta.training_impact == "required"
    assert "components" in updated.delta.changed_field_codes


@pytest.mark.integration
async def test_unknown_allergen_code_rejects_whole_item_mutation(
    db_session: AsyncSession,
) -> None:
    organization, location, user, draft, category = await draft_category(db_session)
    payload = item_payload(category.id, allergen_codes=["not-controlled"])

    with pytest.raises(APIError) as caught:
        await create_menu_item(
            db_session,
            organization_id=organization.id,
            location_id=location.id,
            version_id=draft.id,
            actor_user_id=user.id,
            request_id=uuid4(),
            expected_revision=2,
            payload=payload,
            now=datetime.now(UTC),
        )

    assert caught.value.code == "VALIDATION_ERROR"


@pytest.mark.integration
async def test_delete_base_item_persists_removed_required_delta(
    db_session: AsyncSession,
) -> None:
    organization, location, user, draft, category = await draft_category(db_session)
    created = await create_menu_item(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=2,
        payload=item_payload(category.id),
        now=datetime.now(UTC),
    )
    draft.status = "published"
    draft.published_by_user_id = user.id
    draft.published_at = datetime.now(UTC)
    await db_session.commit()
    copied = await create_menu_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
    )

    result = await delete_menu_item(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=copied.id,
        item_id=created.item_version.menu_item_id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=0,
    )

    assert result.revision == 1
    assert result.delta is not None
    assert (result.delta.delta_kind, result.delta.training_impact) == ("removed", "required")
