from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    QuestionCandidate,
    QuestionGenerationRule,
    QuestionSourceLink,
    QuestionVersion,
    TrainingVersionMenuDependency,
)
from app.schemas.assessment import QuestionCandidateBatchItem
from app.services.question_generation import generate_question_candidates
from app.services.question_review import (
    approve_question_candidate,
    approve_question_candidate_batch,
)
from tests.factories.identity import make_location, make_organization, make_user
from tests.factories.menu import (
    make_category_translation,
    make_item_translation,
    make_item_version,
    make_menu,
    make_menu_category,
    make_menu_item,
    make_menu_section,
    make_menu_version,
    make_version_category,
    make_version_section,
)
from tests.factories.training import (
    make_content_block,
    make_lesson,
    make_lesson_version,
    make_training,
    make_training_module,
    make_training_module_version,
    make_training_version,
)


@pytest.mark.integration
async def test_generation_is_provenance_bound_idempotent_and_price_independent(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    location = make_location(organization)
    actor = make_user(email_normalized="candidate-generator@example.com")
    db_session.add_all([organization, location, actor])
    await db_session.flush()

    menu = make_menu(organization.id, location.id)
    section = make_menu_section(menu)
    soup_category = make_menu_category(menu, stable_code="soups")
    salad_category = make_menu_category(menu, stable_code="salads")
    soup = make_menu_item(menu, stable_code="borshch")
    salad = make_menu_item(menu, stable_code="caesar")
    training = make_training(organization.id, location.id)
    module = make_training_module(training)
    db_session.add_all(
        [menu, section, soup_category, salad_category, soup, salad, training, module]
    )
    await db_session.flush()

    now = datetime.now(UTC)
    menu_version = make_menu_version(
        menu,
        actor.id,
        status="published",
        published_by_user_id=actor.id,
        published_at=now,
    )
    training_version = make_training_version(
        training,
        actor.id,
        status="published",
        published_by_user_id=actor.id,
        published_at=now,
    )
    db_session.add_all([menu_version, training_version])
    await db_session.flush()
    module_version = make_training_module_version(training_version, module)
    lesson = make_lesson(module)
    db_session.add_all([module_version, lesson])
    await db_session.flush()

    version_section = make_version_section(menu_version, section)
    lesson_version = make_lesson_version(module_version, lesson)
    db_session.add_all([version_section, lesson_version])
    await db_session.flush()
    soup_version_category = make_version_category(
        menu_version, soup_category, version_section, position=0
    )
    salad_version_category = make_version_category(
        menu_version, salad_category, version_section, position=1
    )
    db_session.add_all([soup_version_category, salad_version_category])
    await db_session.flush()

    soup_version = make_item_version(
        menu_version,
        soup,
        soup_version_category,
        price_minor=15000,
        verified_by_user_id=actor.id,
        verified_at=now,
    )
    salad_version = make_item_version(
        menu_version,
        salad,
        salad_version_category,
        price_minor=20000,
        verified_by_user_id=actor.id,
        verified_at=now,
    )
    soup_category_translation = make_category_translation(
        menu_version, soup_version_category, name="Супи"
    )
    salad_category_translation = make_category_translation(
        menu_version, salad_version_category, name="Салати"
    )
    db_session.add_all(
        [
            soup_version,
            salad_version,
            soup_category_translation,
            salad_category_translation,
        ]
    )
    await db_session.flush()
    db_session.add_all(
        [
            make_item_translation(menu_version, soup_version, name="Борщ"),
            make_item_translation(menu_version, salad_version, name="Цезар"),
            make_content_block(
                lesson_version,
                type="menu_item_card",
                position=0,
                payload={"menu_item_id": str(soup.id)},
                menu_item_id=soup.id,
            ),
            make_content_block(
                lesson_version,
                type="menu_item_card",
                position=1,
                payload={"menu_item_id": str(salad.id)},
                menu_item_id=salad.id,
            ),
            TrainingVersionMenuDependency(
                training_version_id=training_version.id,
                menu_version_id=menu_version.id,
            ),
            QuestionGenerationRule(
                code="menu.category",
                version=1,
                domain_type="menu",
                mechanic="single_choice",
                status="active",
                configuration={},
            ),
        ]
    )
    await db_session.flush()

    scope = {
        "organization_id": organization.id,
        "location_id": location.id,
        "menu_version_id": menu_version.id,
        "training_version_id": training_version.id,
    }
    first = await generate_question_candidates(db_session, **scope)
    await db_session.flush()
    assert first.created_count == 2
    assert await db_session.scalar(select(func.count()).select_from(QuestionSourceLink)) == 6
    published_candidate = await db_session.scalar(select(QuestionCandidate).limit(1))
    assert published_candidate is not None
    approval = await approve_question_candidate(
        db_session,
        organization_id=organization.id,
        location_id=location.id,
        candidate_id=published_candidate.id,
        expected_revision=0,
        edited_payload=None,
        actor_user_id=actor.id,
        request_id=published_candidate.id,
        now=now,
    )
    assert approval.readiness.status == "blocked"
    assert approval.readiness.eligible_count == 1
    question_version = await db_session.get(QuestionVersion, approval.question_version_id)
    assert question_version is not None

    replay = await generate_question_candidates(db_session, **scope)
    soup_version.price_minor = 99999
    price_only = await generate_question_candidates(db_session, **scope)
    assert replay.existing_count == 2
    assert price_only.existing_count == 2
    assert price_only.created_count == 0
    assert price_only.stale_candidate_count == 0

    salad_category_translation.name = "Основні страви"
    unreviewed_candidate = await db_session.scalar(
        select(QuestionCandidate).where(QuestionCandidate.status == "needs_review")
    )
    assert unreviewed_candidate is not None
    with pytest.raises(APIError) as stale_approval:
        await approve_question_candidate(
            db_session,
            organization_id=organization.id,
            location_id=location.id,
            candidate_id=unreviewed_candidate.id,
            expected_revision=unreviewed_candidate.revision,
            edited_payload=None,
            actor_user_id=actor.id,
            request_id=unreviewed_candidate.id,
            now=now,
        )
    assert stale_approval.value.code == "QUESTION_CANDIDATE_STALE"
    changed = await generate_question_candidates(db_session, **scope)
    await db_session.flush()
    assert changed.created_count == 2
    assert changed.stale_candidate_count == 2
    assert changed.stale_question_count == 1
    assert question_version.status == "stale"
    assert question_version.stale_at is not None
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(QuestionCandidate)
            .where(QuestionCandidate.status == "stale")
        )
        == 2
    )
    reviewable = list(
        await db_session.scalars(
            select(QuestionCandidate)
            .where(QuestionCandidate.status == "needs_review")
            .order_by(QuestionCandidate.id)
        )
    )
    assert len(reviewable) == 2
    reviewable[1].status = "stale"
    await db_session.flush()
    with pytest.raises(APIError) as raised:
        await approve_question_candidate_batch(
            db_session,
            organization_id=organization.id,
            location_id=location.id,
            items=[
                QuestionCandidateBatchItem(candidate_id=row.id, expected_revision=row.revision)
                for row in reviewable
            ],
            actor_user_id=actor.id,
            request_id=reviewable[0].id,
            now=now,
        )
    assert raised.value.code == "QUESTION_CANDIDATE_STALE"
    assert reviewable[0].status == "needs_review"
