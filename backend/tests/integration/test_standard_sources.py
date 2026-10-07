from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssessmentVersion,
    QuestionCandidate,
    QuestionSourceLink,
    StandardRule,
    StandardRuleVersion,
    StandardSet,
    StandardSetVersion,
    TrainingModule,
    TrainingModuleStandardDependency,
    TrainingModuleVersion,
    TrainingVersion,
)
from app.services.question_review import approve_question_candidate
from app.services.standard_questions import generate_standard_candidates
from app.services.training_drafts import create_training_draft
from tests.integration.test_assessment_persistence import _make_context


@pytest.mark.parametrize(
    "table",
    [
        "standard_sets",
        "standard_set_versions",
        "standard_rules",
        "standard_rule_versions",
        "training_module_standard_dependencies",
    ],
)
async def test_standard_source_version_chain_exists(
    db_session: AsyncSession,
    table: str,
) -> None:
    assert await db_session.scalar(text("SELECT to_regclass(:table)"), {"table": table}) is not None


async def _source(db: AsyncSession) -> tuple[StandardSetVersion, StandardRuleVersion]:
    context = await _make_context(db)
    scope = dict(
        organization_id=context.training.organization_id, location_id=context.training.location_id
    )
    source = StandardSet(**scope, code="service", domain_type="service")
    db.add(source)
    await db.flush()
    version = StandardSetVersion(
        **scope, standard_set_id=source.id, version_number=1, title_uk="Сервіс"
    )
    rule = StandardRule(standard_set_id=source.id, code="greeting")
    db.add_all([version, rule])
    await db.flush()
    fact = StandardRuleVersion(
        **scope,
        standard_set_id=source.id,
        standard_set_version_id=version.id,
        standard_rule_id=rule.id,
        position=0,
        scenario_uk="Гість увійшов.",
        allowed_action_uk="Привітатися.",
        prohibited_actions_uk=["Ігнорувати.", "Перебити гостя."],
        explanation_uk="Ввічливе привітання починає контакт.",
        verified=True,
        provenance={"source": "approved generic educational material"},
    )
    db.add(fact)
    await db.flush()
    version.status = "published"
    version.published_at = datetime.now(UTC)
    version.published_by_user_id = context.actor.id
    await db.flush()
    return version, fact


@pytest.mark.parametrize("operation", ["update", "delete", "insert", "reopen"])
async def test_published_standard_source_is_immutable(
    db_session: AsyncSession,
    operation: str,
) -> None:
    version, fact = await _source(db_session)
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            if operation == "update":
                fact.allowed_action_uk = "Інша дія."
            elif operation == "delete":
                await db_session.delete(fact)
            elif operation == "reopen":
                version.status = "draft"
                version.published_at = None
                version.published_by_user_id = None
            else:
                rule = StandardRule(standard_set_id=fact.standard_set_id, code="late")
                db_session.add(rule)
                await db_session.flush()
                db_session.add(
                    StandardRuleVersion(
                        organization_id=fact.organization_id,
                        location_id=fact.location_id,
                        standard_set_id=fact.standard_set_id,
                        standard_set_version_id=version.id,
                        standard_rule_id=rule.id,
                        position=1,
                    )
                )
            await db_session.flush()


async def test_standard_candidates_require_review_and_keep_menu_assessment_separate(
    db_session: AsyncSession,
) -> None:
    source, fact = await _source(db_session)
    training = await db_session.scalar(
        select(TrainingVersion).where(
            TrainingVersion.organization_id == source.organization_id,
        )
    )
    assert training is not None
    module_version = await db_session.scalar(
        select(TrainingModuleVersion).where(
            TrainingModuleVersion.training_version_id == training.id,
        )
    )
    assert module_version is not None
    module = await db_session.get(TrainingModule, module_version.training_module_id)
    assert module is not None
    module.domain_type = "service"
    db_session.add(
        TrainingModuleStandardDependency(
            organization_id=source.organization_id,
            location_id=source.location_id,
            training_version_id=training.id,
            training_module_version_id=module_version.id,
            standard_set_version_id=source.id,
        )
    )
    await db_session.flush()
    scope = dict(
        organization_id=source.organization_id,
        location_id=source.location_id,
        training_version_id=training.id,
        module_version_id=module_version.id,
    )
    assert await generate_standard_candidates(db_session, **scope) == (1, 0)
    assert await generate_standard_candidates(db_session, **scope) == (0, 1)
    candidate = await db_session.scalar(
        select(QuestionCandidate)
        .join(
            QuestionSourceLink,
            QuestionSourceLink.question_candidate_id == QuestionCandidate.id,
        )
        .where(QuestionSourceLink.standard_rule_version_id == fact.id)
        .limit(1)
    )
    assert candidate is not None
    assert candidate.status == "needs_review"
    assert (
        await db_session.scalar(
            select(AssessmentVersion.id).where(
                AssessmentVersion.assessment_type == "course_knowledge_check",
            )
        )
        is None
    )
    assert source.published_by_user_id is not None
    approval = await approve_question_candidate(
        db_session,
        organization_id=source.organization_id,
        location_id=source.location_id,
        candidate_id=candidate.id,
        expected_revision=candidate.revision,
        edited_payload=None,
        actor_user_id=source.published_by_user_id,
        request_id=uuid4(),
        now=datetime.now(UTC),
    )
    course = await db_session.get(AssessmentVersion, approval.readiness.assessment_version_id)
    assert course is not None
    assert course.assessment_type == "course_knowledge_check"
    assert course.feedback_policy == "after_final_submission"
    assert course.threshold_percent is None
    assert approval.readiness.required_count == 1
    assert approval.readiness.can_start
    assert (
        await db_session.scalar(
            select(QuestionSourceLink.id)
            .where(
                QuestionSourceLink.question_version_id == approval.question_version_id,
                QuestionSourceLink.standard_rule_version_id == fact.id,
            )
            .limit(1)
        )
        is not None
    )
    menu = await db_session.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.assessment_type == "interactive_training",
        )
    )
    assert menu is not None and menu.question_count == 5


async def test_new_training_draft_keeps_pinned_standard_version(db_session: AsyncSession) -> None:
    source, _fact = await _source(db_session)
    training = await db_session.scalar(
        select(TrainingVersion).where(
            TrainingVersion.organization_id == source.organization_id,
        )
    )
    assert training is not None and source.published_by_user_id is not None
    module = await db_session.scalar(
        select(TrainingModuleVersion).where(
            TrainingModuleVersion.training_version_id == training.id,
        )
    )
    assert module is not None
    stable_module = TrainingModule(training_id=training.training_id, domain_type="service")
    db_session.add(stable_module)
    await db_session.flush()
    module = TrainingModuleVersion(
        training_id=training.training_id,
        training_version_id=training.id,
        training_module_id=stable_module.id,
        position=1,
        required=True,
    )
    db_session.add(module)
    await db_session.flush()
    db_session.add(
        TrainingModuleStandardDependency(
            organization_id=source.organization_id,
            location_id=source.location_id,
            training_version_id=training.id,
            training_module_version_id=module.id,
            standard_set_version_id=source.id,
        )
    )
    await db_session.flush()
    draft = await create_training_draft(
        db_session,
        organization_id=source.organization_id,
        location_id=source.location_id,
        actor_user_id=source.published_by_user_id,
        request_id=uuid4(),
        base_version_id=training.id,
    )
    pinned = await db_session.scalar(
        select(TrainingModuleStandardDependency).where(
            TrainingModuleStandardDependency.training_version_id == draft.id,
        )
    )
    assert pinned is not None
    assert pinned.standard_set_version_id == source.id
    assert pinned.training_module_version_id != module.id
