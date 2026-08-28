from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    LessonContentBlock,
    LessonContentBlockTranslation,
    LessonTranslation,
    LessonVersion,
    Location,
    Organization,
    TrainingModule,
    TrainingModuleTranslation,
    TrainingModuleVersion,
    User,
)
from app.services.training_drafts import (
    create_lesson,
    create_training_draft,
    delete_lesson,
    reorder_lessons,
    update_lesson,
    update_module,
)
from tests.factories.identity import make_location, make_organization, make_user
from tests.factories.training import (
    make_content_block,
    make_lesson,
    make_lesson_translation,
    make_lesson_version,
    make_training,
    make_training_module,
    make_training_module_translation,
    make_training_module_version,
    make_training_version,
)


async def identity_root(db: AsyncSession) -> tuple[Organization, Location, User]:
    organization = make_organization()
    location = make_location(organization)
    user = make_user()
    db.add_all([organization, location, user])
    await db.commit()
    return organization, location, user


@pytest.mark.integration
async def test_first_draft_creates_fixed_menu_module(db_session: AsyncSession) -> None:
    organization, location, user = await identity_root(db_session)

    draft = await create_training_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        base_version_id=None,
    )

    module = await db_session.scalar(
        select(TrainingModule).where(TrainingModule.training_id == draft.training_id)
    )
    module_version = await db_session.scalar(
        select(TrainingModuleVersion).where(TrainingModuleVersion.training_version_id == draft.id)
    )
    assert module_version is not None
    translation = await db_session.scalar(
        select(TrainingModuleTranslation).where(
            TrainingModuleTranslation.training_module_version_id == module_version.id
        )
    )

    assert draft.status == "draft"
    assert draft.revision == 0
    assert module is not None and module.domain_type == "menu"
    assert module_version.required is True
    assert translation is not None and translation.title == "Меню"


@pytest.mark.integration
async def test_draft_module_and_lessons_use_expected_revision(
    db_session: AsyncSession,
) -> None:
    organization, location, user = await identity_root(db_session)
    draft = await create_training_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        base_version_id=None,
    )
    module_version = await db_session.scalar(
        select(TrainingModuleVersion).where(TrainingModuleVersion.training_version_id == draft.id)
    )
    assert module_version is not None

    module_result = await update_module(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        module_id=module_version.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=0,
        title_uk="Страви та подача",
        description_uk="Короткий довідник команди.",
        required=True,
    )
    first = await create_lesson(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        module_id=module_version.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=module_result.revision,
        title_uk="Борщ",
        description_uk=None,
        required=True,
        estimated_minutes=5,
    )
    second = await create_lesson(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        module_id=module_version.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=first.revision,
        title_uk="Вареники",
        description_uk=None,
        required=True,
        estimated_minutes=7,
    )
    reordered = await reorder_lessons(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        module_id=module_version.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=second.revision,
        ordered_ids=[second.entity.lesson_id, first.entity.lesson_id],
    )

    assert reordered.revision == 4
    assert [lesson.lesson_id for lesson in reordered.entities] == [
        second.entity.lesson_id,
        first.entity.lesson_id,
    ]

    with pytest.raises(APIError) as stale:
        await update_module(
            db_session,
            organization_id=organization.id,
            location_id=location.id,
            version_id=draft.id,
            module_id=module_version.id,
            actor_user_id=user.id,
            request_id=uuid4(),
            expected_revision=0,
            title_uk="Застарілий запис",
            description_uk=None,
            required=True,
        )
    assert stale.value.code == "REVISION_CONFLICT"


@pytest.mark.integration
async def test_draft_copies_published_stable_lesson_identity(
    db_session: AsyncSession,
) -> None:
    organization, location, user = await identity_root(db_session)
    training = make_training(organization.id, location.id)
    published = make_training_version(
        training,
        user.id,
        status="published",
        published_by_user_id=user.id,
        published_at=datetime.now(UTC),
    )
    module = make_training_module(training)
    db_session.add_all([training, published, module])
    await db_session.flush()
    module_version = make_training_module_version(published, module)
    lesson = make_lesson(module)
    db_session.add_all([module_version, lesson])
    await db_session.flush()
    lesson_version = make_lesson_version(module_version, lesson)
    db_session.add_all(
        [
            make_training_module_translation(module_version),
            lesson_version,
        ]
    )
    await db_session.flush()
    block = make_content_block(lesson_version)
    db_session.add_all([make_lesson_translation(lesson_version), block])
    await db_session.flush()
    db_session.add(
        LessonContentBlockTranslation(
            lesson_content_block_id=block.id,
            locale="en",
            status="ready",
            translated_payload={"text_uk": "Serve warm."},
            source_revision=0,
        )
    )
    await db_session.commit()

    draft = await create_training_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        base_version_id=published.id,
    )
    copied_lesson = await db_session.scalar(
        select(LessonVersion).where(
            LessonVersion.training_module_version_id.in_(
                select(TrainingModuleVersion.id).where(
                    TrainingModuleVersion.training_version_id == draft.id
                )
            )
        )
    )
    assert copied_lesson is not None
    copied_translation = await db_session.scalar(
        select(LessonTranslation).where(LessonTranslation.lesson_version_id == copied_lesson.id)
    )
    copied_block = await db_session.scalar(
        select(LessonContentBlock).where(LessonContentBlock.lesson_version_id == copied_lesson.id)
    )
    assert copied_block is not None
    copied_block_translation = await db_session.scalar(
        select(LessonContentBlockTranslation).where(
            LessonContentBlockTranslation.lesson_content_block_id == copied_block.id
        )
    )

    assert copied_lesson.lesson_id == lesson.id
    assert copied_lesson.id != lesson_version.id
    assert copied_translation is not None and copied_translation.title == "Основи меню"
    assert copied_block.id != block.id and copied_block.payload == block.payload
    assert copied_block_translation is not None
    assert copied_block_translation.translated_payload == {"text_uk": "Serve warm."}


@pytest.mark.integration
async def test_published_version_is_immutable(db_session: AsyncSession) -> None:
    organization, location, user = await identity_root(db_session)
    training = make_training(organization.id, location.id)
    published = make_training_version(
        training,
        user.id,
        status="published",
        published_by_user_id=user.id,
        published_at=datetime.now(UTC),
    )
    module = make_training_module(training)
    db_session.add_all([training, published, module])
    await db_session.flush()
    module_version = make_training_module_version(published, module)
    db_session.add(module_version)
    await db_session.commit()

    with pytest.raises(APIError) as immutable:
        await update_module(
            db_session,
            organization_id=organization.id,
            location_id=location.id,
            version_id=published.id,
            module_id=module_version.id,
            actor_user_id=user.id,
            request_id=uuid4(),
            expected_revision=0,
            title_uk="Не можна",
            description_uk=None,
            required=True,
        )
    assert immutable.value.code == "TRAINING_VERSION_IMMUTABLE"


@pytest.mark.integration
async def test_lesson_update_and_delete_complete_crud(db_session: AsyncSession) -> None:
    organization, location, user = await identity_root(db_session)
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
    created = await create_lesson(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        module_id=module.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=0,
        title_uk="Чернетка",
        description_uk=None,
        required=True,
        estimated_minutes=5,
    )
    updated = await update_lesson(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        lesson_id=created.entity.lesson_id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=created.revision,
        title_uk="Готовий урок",
        description_uk="Зміст перевірено.",
        required=False,
        estimated_minutes=8,
    )
    deleted_revision = await delete_lesson(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        version_id=draft.id,
        lesson_id=created.entity.lesson_id,
        actor_user_id=user.id,
        request_id=uuid4(),
        expected_revision=updated.revision,
    )

    assert updated.entity.required is False
    assert updated.entity.estimated_minutes == 8
    assert deleted_revision == 3
    assert (
        await db_session.scalar(
            select(LessonVersion.id).where(LessonVersion.id == created.entity.id)
        )
        is None
    )


@pytest.mark.integration
async def test_second_draft_is_rejected(db_session: AsyncSession) -> None:
    organization, location, user = await identity_root(db_session)
    await create_training_draft(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        base_version_id=None,
    )

    with pytest.raises(APIError) as duplicate:
        await create_training_draft(
            db_session,
            organization_id=organization.id,
            location_id=location.id,
            actor_user_id=user.id,
            request_id=uuid4(),
            base_version_id=None,
        )

    assert duplicate.value.code == "TRAINING_DRAFT_EXISTS"
