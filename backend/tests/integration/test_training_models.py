from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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


async def assert_integrity_error(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.integration
async def test_complete_training_content_graph_is_version_owned(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    location = make_location(organization)
    user = make_user()
    db_session.add_all([organization, location, user])
    await db_session.flush()

    training = make_training(organization.id, location.id)
    version = make_training_version(training, user.id)
    module = make_training_module(training)
    db_session.add_all([training, version, module])
    await db_session.flush()

    module_version = make_training_module_version(version, module)
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
    await db_session.commit()

    assert version.status == "draft"
    assert version.revision == 0
    assert module.domain_type == "menu"
    assert block.payload == {"text_uk": "Подавайте страву теплою."}


@pytest.mark.integration
async def test_training_has_one_root_and_one_current_version_per_location(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    location = make_location(organization)
    user = make_user()
    db_session.add_all([organization, location, user])
    await db_session.flush()
    training = make_training(organization.id, location.id)
    training_id = training.id
    organization_id = organization.id
    location_id = location.id
    user_id = user.id
    db_session.add(training)
    await db_session.flush()
    db_session.add(make_training_version(training, user.id))
    await db_session.commit()

    db_session.add(make_training(organization_id, location_id))
    await assert_integrity_error(db_session)

    replacement = make_training(organization_id, location_id, id=training_id)
    db_session.add(make_training_version(replacement, user_id, version_number=2))
    await assert_integrity_error(db_session)


@pytest.mark.integration
async def test_training_version_requires_matching_lifecycle_fields(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    location = make_location(organization)
    user = make_user()
    db_session.add_all([organization, location, user])
    await db_session.flush()
    training = make_training(organization.id, location.id)
    db_session.add(training)
    await db_session.flush()

    db_session.add(
        make_training_version(
            training,
            user.id,
            status="published",
            published_at=datetime.now(UTC),
            published_by_user_id=None,
        )
    )
    await assert_integrity_error(db_session)
