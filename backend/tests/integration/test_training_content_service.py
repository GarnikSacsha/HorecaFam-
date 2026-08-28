from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    ContentBlockType,
    LessonContentBlockTranslation,
    MenuItem,
    MenuVersion,
    TrainingModuleVersion,
    TrainingVersionMenuDependency,
)
from app.schemas.training import ContentBlockWrite
from app.services.training_content import (
    create_content_block,
    reorder_content_blocks,
    resolve_localized_payload,
    update_content_block,
)
from app.services.training_drafts import create_lesson, create_training_draft
from tests.factories.identity import make_location, make_organization, make_user
from tests.factories.menu import (
    make_item_version,
    make_menu,
    make_menu_category,
    make_menu_item,
    make_menu_section,
    make_menu_version,
    make_version_category,
    make_version_section,
)


async def published_menu(
    db: AsyncSession,
    organization_id: UUID,
    location_id: UUID,
    user_id: UUID,
) -> tuple[MenuVersion, MenuItem]:
    menu = make_menu(organization_id, location_id)
    section = make_menu_section(menu)
    category = make_menu_category(menu)
    item = make_menu_item(menu)
    version = make_menu_version(
        menu,
        user_id,
        status="published",
        published_by_user_id=user_id,
        published_at=datetime.now(UTC),
    )
    db.add_all([menu, section, category, item, version])
    await db.flush()
    version_section = make_version_section(version, section)
    db.add(version_section)
    await db.flush()
    version_category = make_version_category(version, category, version_section)
    db.add(version_category)
    await db.flush()
    db.add(make_item_version(version, item, version_category))
    await db.commit()
    return version, item


@pytest.mark.integration
async def test_draft_binds_current_published_menu_and_validates_item_cards(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    location = make_location(organization)
    user = make_user()
    db_session.add_all([organization, location, user])
    await db_session.commit()
    menu_version, item = await published_menu(db_session, organization.id, location.id, user.id)
    draft = await create_training_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        base_version_id=None,
    )
    dependency = await db_session.scalar(
        select(TrainingVersionMenuDependency).where(
            TrainingVersionMenuDependency.training_version_id == draft.id
        )
    )
    module = await db_session.scalar(
        select(TrainingModuleVersion).where(TrainingModuleVersion.training_version_id == draft.id)
    )
    assert dependency is not None and dependency.menu_version_id == menu_version.id
    assert module is not None
    lesson = await create_lesson(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        module_id=module.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=0,
        title_uk="Борщ",
        description_uk=None,
        required=True,
        estimated_minutes=5,
    )
    card_request = ContentBlockWrite(
        type="menu_item_card",
        payload={"menu_item_id": item.id, "note_uk": "Опишіть склад."},
        expected_revision=lesson.revision,
    )
    card = await create_content_block(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        lesson_id=lesson.entity.lesson_id,
        actor_user_id=user.id,
        request_id=uuid4(),
        block_type=card_request.type,
        payload=card_request.payload,
        expected_revision=card_request.expected_revision,
    )

    assert card.entity.menu_item_id == item.id
    assert card.revision == 2


@pytest.mark.integration
async def test_content_block_crud_reorder_and_translation_fallback(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    location = make_location(organization)
    user = make_user()
    db_session.add_all([organization, location, user])
    await db_session.commit()
    draft = await create_training_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        base_version_id=None,
    )
    module = await db_session.scalar(
        select(TrainingModuleVersion).where(TrainingModuleVersion.training_version_id == draft.id)
    )
    assert module is not None
    lesson = await create_lesson(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        module_id=module.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=0,
        title_uk="Подача",
        description_uk=None,
        required=True,
        estimated_minutes=4,
    )
    first = await create_content_block(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        lesson_id=lesson.entity.lesson_id,
        actor_user_id=user.id,
        request_id=uuid4(),
        block_type=ContentBlockType.TEXT,
        payload={"text_uk": "Подавайте теплою."},
        expected_revision=lesson.revision,
    )
    second = await create_content_block(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        lesson_id=lesson.entity.lesson_id,
        actor_user_id=user.id,
        request_id=uuid4(),
        block_type=ContentBlockType.HEADING,
        payload={"level": 2, "text_uk": "Температура"},
        expected_revision=first.revision,
    )
    updated = await update_content_block(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        block_id=first.entity.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        payload={"text_uk": "Подавайте одразу після кухні."},
        expected_revision=second.revision,
    )
    reordered = await reorder_content_blocks(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        lesson_id=lesson.entity.lesson_id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=updated.revision,
        ordered_ids=[second.entity.id, first.entity.id],
    )
    translation = LessonContentBlockTranslation(
        lesson_content_block_id=first.entity.id,
        locale="en",
        status="ready",
        translated_payload={"text_uk": "Serve immediately from the kitchen."},
        source_revision=1,
    )
    db_session.add(translation)
    await db_session.commit()

    localized = resolve_localized_payload(first.entity, translation, requested_locale="en")
    stale = resolve_localized_payload(first.entity, translation, requested_locale="uk")

    assert reordered.revision == 5
    assert [block.id for block in reordered.entities] == [second.entity.id, first.entity.id]
    assert localized.content_locale == "en" and localized.translation_fallback is False
    assert stale.content_locale == "uk" and stale.translation_fallback is False


@pytest.mark.integration
async def test_menu_item_outside_exact_dependency_is_rejected(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    location = make_location(organization)
    user = make_user()
    db_session.add_all([organization, location, user])
    await db_session.commit()
    _menu_version, _item = await published_menu(db_session, organization.id, location.id, user.id)
    foreign_item = uuid4()
    draft = await create_training_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        base_version_id=None,
    )
    module = await db_session.scalar(
        select(TrainingModuleVersion).where(TrainingModuleVersion.training_version_id == draft.id)
    )
    assert module is not None
    lesson = await create_lesson(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        module_id=module.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=0,
        title_uk="Урок",
        description_uk=None,
        required=True,
        estimated_minutes=3,
    )

    with pytest.raises(APIError) as invalid:
        await create_content_block(
            db_session,
            organization_id=organization.id,
            location_id=location.id,
            version_id=draft.id,
            lesson_id=lesson.entity.lesson_id,
            actor_user_id=user.id,
            request_id=uuid4(),
            block_type=ContentBlockType.MENU_ITEM_CARD,
            payload={"menu_item_id": foreign_item, "note_uk": None},
            expected_revision=lesson.revision,
        )

    assert invalid.value.code == "TRAINING_MENU_DEPENDENCY_INVALID"
