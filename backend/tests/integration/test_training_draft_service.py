from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    AuditEvent,
    LessonContentBlock,
    LessonContentBlockTranslation,
    LessonTranslation,
    LessonVersion,
    Location,
    Organization,
    TrainingModule,
    TrainingModuleTranslation,
    TrainingModuleVersion,
    TrainingVersion,
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


@pytest.mark.integration
@pytest.mark.parametrize("problem", ["title", "description", "minutes", "module", "location"])
async def test_rejected_lesson_creation_rolls_back_partial_rows(
    db_session: AsyncSession, problem: str
) -> None:
    organization, location, user = await identity_root(db_session)
    organization_id, location_id, user_id = organization.id, location.id, user.id
    draft = await create_training_draft(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        actor_user_id=user_id,
        request_id=uuid4(),
        base_version_id=None,
    )
    draft_id = draft.id
    module = await db_session.scalar(
        select(TrainingModuleVersion).where(TrainingModuleVersion.training_version_id == draft_id)
    )
    assert module is not None
    module_id = module.id
    audit_before = await db_session.scalar(select(func.count()).select_from(AuditEvent))
    with pytest.raises(APIError) as rejected:
        await create_lesson(
            db_session,
            organization_id=organization_id,
            location_id=uuid4() if problem == "location" else location_id,
            version_id=draft_id,
            module_id=uuid4() if problem == "module" else module_id,
            actor_user_id=user_id,
            request_id=uuid4(),
            expected_revision=0,
            title_uk="  " if problem == "title" else "Урок",
            description_uk="я" * 2001 if problem == "description" else None,
            required=True,
            estimated_minutes=0 if problem == "minutes" else None,
        )
    assert rejected.value.code == (
        "RESOURCE_NOT_FOUND" if problem in {"module", "location"} else "VALIDATION_ERROR"
    )
    assert (await db_session.get_one(TrainingVersion, draft_id)).revision == 0
    assert await db_session.scalar(select(func.count()).select_from(LessonVersion)) == 0
    assert await db_session.scalar(select(func.count()).select_from(LessonTranslation)) == 0
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == audit_before
    created = await create_lesson(
        db_session,
        organization_id=organization_id,
        location_id=location_id,
        version_id=draft_id,
        module_id=module_id,
        actor_user_id=user_id,
        request_id=uuid4(),
        expected_revision=0,
        title_uk=" Урок ",
        description_uk="  ",
        required=True,
        estimated_minutes=None,
    )
    assert created.revision == 1
    translation = await db_session.scalar(
        select(LessonTranslation).where(LessonTranslation.lesson_version_id == created.entity.id)
    )
    assert translation is not None
    assert translation.title == "Урок" and translation.description is None


async def test_training_structure_rejections_and_translation_staleness_are_atomic(
    db_session: AsyncSession,
) -> None:
    from typing import Any

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
    args: dict[str, Any] = dict(
        organization_id=organization.id,
        location_id=location.id,
        actor_user_id=user.id,
        request_id=uuid4(),
        version_id=draft.id,
    )
    module_id = module.id
    audit_before = await db_session.scalar(select(func.count()).select_from(AuditEvent))
    with pytest.raises(APIError, match="RESOURCE_NOT_FOUND"):
        await update_module(
            db_session,
            **args,
            expected_revision=0,
            module_id=uuid4(),
            title_uk="Menu",
            description_uk=None,
            required=True,
        )
    with pytest.raises(APIError, match="RESOURCE_NOT_FOUND"):
        await update_lesson(
            db_session,
            **args,
            expected_revision=0,
            lesson_id=uuid4(),
            title_uk="Lesson",
            description_uk=None,
            required=True,
            estimated_minutes=5,
        )
    with pytest.raises(APIError, match="RESOURCE_NOT_FOUND"):
        await delete_lesson(db_session, **args, expected_revision=0, lesson_id=uuid4())
    with pytest.raises(APIError, match="RESOURCE_NOT_FOUND"):
        await reorder_lessons(
            db_session, **args, expected_revision=0, module_id=uuid4(), ordered_ids=[]
        )
    with pytest.raises(APIError, match="VALIDATION_ERROR"):
        await reorder_lessons(
            db_session, **args, expected_revision=0, module_id=module_id, ordered_ids=[uuid4()]
        )
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == audit_before
    created = await create_lesson(
        db_session,
        **args,
        expected_revision=0,
        module_id=module_id,
        title_uk="Lesson",
        description_uk=None,
        required=True,
        estimated_minutes=5,
    )
    lesson_id, lesson_version_id = created.entity.lesson_id, created.entity.id
    module = await db_session.get_one(TrainingModuleVersion, module_id)
    module_en = make_training_module_translation(module, locale="en", title="Menu", status="ready")
    lesson_en = make_lesson_translation(created.entity, locale="en", title="Lesson", status="ready")
    block = make_content_block(created.entity)
    db_session.add_all([module_en, lesson_en, block])
    await db_session.commit()
    module_en_id, lesson_en_id = module_en.id, lesson_en.id
    audit_before = await db_session.scalar(select(func.count()).select_from(AuditEvent))
    with pytest.raises(APIError, match="LESSON_NOT_EMPTY"):
        await delete_lesson(db_session, **args, expected_revision=1, lesson_id=lesson_id)
    assert await db_session.get(LessonVersion, lesson_version_id) is not None
    assert (await db_session.get_one(TrainingVersion, args["version_id"])).revision == 1
    assert await db_session.scalar(select(func.count()).select_from(AuditEvent)) == audit_before
    await update_module(
        db_session,
        **args,
        expected_revision=1,
        module_id=module_id,
        title_uk="Revised menu",
        description_uk=None,
        required=True,
    )
    await update_lesson(
        db_session,
        **args,
        expected_revision=2,
        lesson_id=lesson_id,
        title_uk="Revised lesson",
        description_uk=None,
        required=True,
        estimated_minutes=6,
    )
    assert (await db_session.get_one(TrainingModuleTranslation, module_en_id)).status == "stale"
    assert (await db_session.get_one(LessonTranslation, lesson_en_id)).status == "stale"
    assert (await db_session.get_one(TrainingVersion, args["version_id"])).revision == 3
