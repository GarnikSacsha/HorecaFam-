from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    EmployeeProfile,
    LessonContentBlock,
    LessonVersion,
    OperationalRole,
    Organization,
    RolloutEmployeeImpact,
    Training,
    TrainingAssignment,
    TrainingModuleAudience,
    TrainingModuleVersion,
    TrainingVersion,
    TrainingVersionAudience,
)
from app.schemas.employees import EmployeeUpdate
from app.services.applicability import evaluate_activation_applicability
from app.services.employee_training import (
    get_employee_training_asset_access,
    get_employee_training_lesson,
    get_employee_training_module,
    list_employee_training,
)
from app.services.employees import update_pending_employee_profile
from app.services.interactive_attempts import _assignment_lesson, _owned_attempt
from app.services.interactive_history import _current_scope
from app.services.training_completion import complete_employee_training_lesson
from app.services.training_drafts import create_training_draft
from app.services.training_progress import derive_training_progress
from app.services.training_publication import get_training_readiness
from app.services.training_rollouts import confirm_training_rollout, prepare_replacement_rollout
from tests.api.test_training_admin_api import FakePrivateStorage
from tests.factories.assessments import (
    make_assessment,
    make_assessment_attempt,
    make_assessment_version,
)
from tests.factories.identity import (
    make_employee_profile,
    make_location,
    make_membership,
    make_organization,
    make_role,
    make_user,
)
from tests.factories.training import (
    make_asset,
    make_content_block,
    make_lesson,
    make_lesson_completion,
    make_lesson_translation,
    make_lesson_version,
    make_training,
    make_training_assignment,
    make_training_module,
    make_training_module_translation,
    make_training_module_version,
    make_training_version,
    make_training_version_audience,
)


@dataclass(frozen=True)
class PositionGraph:
    organization_id: UUID
    location_id: UUID
    employee_profile_id: UUID
    user_id: UUID
    assignment_id: UUID
    modules: dict[str, tuple[UUID, UUID, UUID]]


async def position_graph(db: AsyncSession, position: str) -> PositionGraph:
    organization = make_organization()
    location = make_location(organization)
    user = make_user()
    membership = make_membership(organization, user)
    roles = {
        code: make_role(organization, code=code)
        for code in ("waiter", "runner", "bartender", "barista")
    }
    db.add_all([organization, location, user, membership, *roles.values()])
    await db.flush()
    employee = make_employee_profile(
        membership, organization.id, location_id=location.id, operational_role_id=roles[position].id
    )
    training = make_training(organization.id, location.id)
    db.add_all([employee, training])
    await db.flush()
    version = make_training_version(
        training,
        user.id,
        status="published",
        published_by_user_id=user.id,
        published_at=datetime.now(UTC),
    )
    db.add(version)
    await db.flush()
    db.add_all([make_training_version_audience(version, role) for role in roles.values()])
    assignment = make_training_assignment(employee, training, version)
    db.add(assignment)
    modules = {}
    for order, code in enumerate(("waiter", "runner", "bartender", "shared", "optional")):
        module = make_training_module(
            training, domain_type="menu" if code == "waiter" else "service"
        )
        db.add(module)
        await db.flush()
        module_version = make_training_module_version(
            version,
            module,
            position=order,
            all_positions=code in {"shared", "optional"},
            required=code != "optional",
        )
        lesson = make_lesson(module)
        asset = make_asset(organization.id, location.id, user.id)
        db.add_all([module_version, lesson, asset])
        await db.flush()
        if code in roles:
            db.add(
                TrainingModuleAudience(
                    organization_id=organization.id,
                    location_id=location.id,
                    training_version_id=version.id,
                    training_module_version_id=module_version.id,
                    operational_role_id=roles[code].id,
                )
            )
        lesson_version = make_lesson_version(module_version, lesson)
        db.add(lesson_version)
        await db.flush()
        db.add_all(
            [
                make_training_module_translation(module_version, title=code),
                make_lesson_translation(lesson_version, title=code),
                make_content_block(
                    lesson_version,
                    type="image",
                    asset_id=asset.id,
                    payload={"alt_uk": "Навчальний приклад", "caption_uk": None},
                ),
            ]
        )
        modules[code] = (module.id, lesson.id, asset.id)
    await db.commit()
    return PositionGraph(organization.id, location.id, employee.id, user.id, assignment.id, modules)


@pytest.mark.parametrize("position", ["waiter", "runner", "bartender", "barista"])
async def test_position_controls_discovery_and_required_progress(
    db_session: AsyncSession, position: str
) -> None:
    graph = await position_graph(db_session, position)
    response = await list_employee_training(
        db_session,
        organization_id=graph.organization_id,
        location_id=graph.location_id,
        employee_profile_id=graph.employee_profile_id,
        requested_locale="uk",
    )
    expected = {"shared", "optional"} | ({position} if position != "barista" else set())
    assert {module.title for module in response.modules} == expected
    assignment = await db_session.get_one(TrainingAssignment, graph.assignment_id)
    progress = await derive_training_progress(db_session, assignment=assignment)
    assert progress.required_lesson_count == (1 if position == "barista" else 2)


@pytest.mark.parametrize(
    "boundary", ["module", "lesson", "asset", "completion", "interactive", "history"]
)
async def test_other_position_content_is_hidden_on_direct_access(
    db_session: AsyncSession, boundary: str
) -> None:
    graph = await position_graph(db_session, "runner")
    module_id, lesson_id, asset_id = graph.modules["bartender"]
    scope = dict(
        organization_id=graph.organization_id,
        location_id=graph.location_id,
        employee_profile_id=graph.employee_profile_id,
    )
    with pytest.raises(APIError) as caught:
        if boundary == "module":
            await get_employee_training_module(
                db_session, **scope, module_id=module_id, requested_locale="uk"
            )
        elif boundary == "lesson":
            await get_employee_training_lesson(
                db_session, **scope, lesson_id=lesson_id, requested_locale="uk"
            )
        elif boundary == "asset":
            await get_employee_training_asset_access(
                db_session, **scope, asset_id=asset_id, storage=FakePrivateStorage()
            )
        elif boundary == "completion":
            await complete_employee_training_lesson(
                db_session,
                **scope,
                actor_user_id=graph.user_id,
                lesson_id=lesson_id,
                idempotency_key="forbidden-position",
                request_id=uuid4(),
                now=datetime.now(UTC),
            )
        elif boundary == "interactive":
            await _assignment_lesson(db_session, **scope, lesson_id=lesson_id)
        else:
            await _current_scope(db_session, **scope, lesson_id=lesson_id)
    assert caught.value.status_code == 404


async def test_stored_attempt_cannot_bypass_current_module_audience(
    db_session: AsyncSession,
) -> None:
    graph = await position_graph(db_session, "runner")
    assignment = await db_session.get_one(TrainingAssignment, graph.assignment_id)
    training = await db_session.get_one(Training, assignment.training_id)
    version = await db_session.get_one(TrainingVersion, assignment.training_version_id)
    employee = await db_session.get_one(EmployeeProfile, graph.employee_profile_id)
    lesson = await db_session.scalar(
        select(LessonVersion).where(LessonVersion.lesson_id == graph.modules["bartender"][1])
    )
    assert lesson is not None
    assessment = make_assessment(training, lesson)
    db_session.add(assessment)
    await db_session.flush()
    assessment_version = make_assessment_version(assessment, version, lesson)
    db_session.add(assessment_version)
    await db_session.flush()
    attempt = make_assessment_attempt(employee, assignment, assessment_version)
    db_session.add(attempt)
    await db_session.commit()
    with pytest.raises(APIError) as caught:
        await _owned_attempt(
            db_session,
            organization_id=graph.organization_id,
            location_id=graph.location_id,
            employee_profile_id=graph.employee_profile_id,
            attempt_id=attempt.id,
        )
    assert caught.value.status_code == 404


async def test_new_draft_preserves_every_module_and_its_position_audience(
    db_session: AsyncSession,
) -> None:
    graph = await position_graph(db_session, "waiter")
    assignment = await db_session.get_one(TrainingAssignment, graph.assignment_id)
    source_id = assignment.training_version_id
    source = list(
        (
            await db_session.scalars(
                select(TrainingModuleVersion)
                .where(TrainingModuleVersion.training_version_id == source_id)
                .order_by(TrainingModuleVersion.position)
            )
        ).all()
    )
    draft = await create_training_draft(
        db_session,
        organization_id=graph.organization_id,
        location_id=graph.location_id,
        actor_user_id=graph.user_id,
        request_id=uuid4(),
        base_version_id=source_id,
    )
    target = list(
        (
            await db_session.scalars(
                select(TrainingModuleVersion)
                .where(TrainingModuleVersion.training_version_id == draft.id)
                .order_by(TrainingModuleVersion.position)
            )
        ).all()
    )
    assert len(target) == len(source) == 5
    for old, new in zip(source, target, strict=True):
        assert new.id != old.id
        assert (new.training_module_id, new.position, new.required, new.all_positions) == (
            old.training_module_id,
            old.position,
            old.required,
            old.all_positions,
        )
        for model, column in [
            (TrainingModuleAudience, TrainingModuleAudience.operational_role_id),
        ]:
            old_roles = set(
                (
                    await db_session.scalars(
                        select(column).where(model.training_module_version_id == old.id)
                    )
                ).all()
            )
            new_roles = set(
                (
                    await db_session.scalars(
                        select(column).where(model.training_module_version_id == new.id)
                    )
                ).all()
            )
            assert old_roles == new_roles
        assert set(
            (
                await db_session.scalars(
                    select(LessonVersion.lesson_id).where(
                        LessonVersion.training_module_version_id == old.id
                    )
                )
            ).all()
        ) == set(
            (
                await db_session.scalars(
                    select(LessonVersion.lesson_id).where(
                        LessonVersion.training_module_version_id == new.id
                    )
                )
            ).all()
        )
    assert (await db_session.get_one(TrainingVersion, source_id)).status == "published"


async def test_publication_checks_required_lessons_in_every_position_module(
    db_session: AsyncSession,
) -> None:
    graph = await position_graph(db_session, "runner")
    assignment = await db_session.get_one(TrainingAssignment, graph.assignment_id)
    draft = await create_training_draft(
        db_session,
        organization_id=graph.organization_id,
        location_id=graph.location_id,
        actor_user_id=graph.user_id,
        request_id=uuid4(),
        base_version_id=assignment.training_version_id,
    )
    runner_lesson = await db_session.scalar(
        select(LessonVersion)
        .join(
            TrainingModuleVersion,
            TrainingModuleVersion.id == LessonVersion.training_module_version_id,
        )
        .where(
            TrainingModuleVersion.training_version_id == draft.id,
            LessonVersion.lesson_id == graph.modules["runner"][1],
        )
    )
    assert runner_lesson is not None
    await db_session.execute(
        delete(LessonContentBlock).where(
            LessonContentBlock.lesson_version_id == runner_lesson.id,
        )
    )
    await db_session.commit()
    readiness = await get_training_readiness(
        db_session,
        organization_id=graph.organization_id,
        location_id=graph.location_id,
        version_id=draft.id,
    )
    assert any(
        issue.code == "REQUIRED_LESSON_EMPTY" and issue.entity_id == runner_lesson.lesson_id
        for issue in readiness.blocking_errors
    )
    assert readiness.counts.module_count == 5
    assert readiness.counts.required_lesson_count == 4


@pytest.mark.parametrize("all_positions", [False, True])
async def test_future_position_assignment_respects_explicit_all_positions_choice(
    db_session: AsyncSession,
    all_positions: bool,
) -> None:
    graph = await position_graph(db_session, "waiter")
    old_assignment = await db_session.get_one(TrainingAssignment, graph.assignment_id)
    version = await db_session.get_one(TrainingVersion, old_assignment.training_version_id)
    version.all_positions = all_positions
    if all_positions:
        await db_session.execute(
            delete(TrainingVersionAudience).where(
                TrainingVersionAudience.training_version_id == version.id,
            )
        )
    organization = await db_session.get_one(Organization, graph.organization_id)
    role = make_role(organization, code="future-host")
    user = make_user(email_normalized="future-host@example.com")
    membership = make_membership(organization, user)
    db_session.add_all([role, user, membership])
    await db_session.flush()
    employee = make_employee_profile(
        membership,
        organization.id,
        location_id=graph.location_id,
        operational_role_id=role.id,
    )
    db_session.add(employee)
    await db_session.flush()
    result = await evaluate_activation_applicability(
        db_session,
        organization_id=organization.id,
        employee_profile_id=employee.id,
    )
    assert result.assignment_count == int(all_positions)
    assert result.notification_count == int(all_positions)
    if all_positions:
        retained = await evaluate_activation_applicability(
            db_session,
            organization_id=organization.id,
            employee_profile_id=employee.id,
        )
        assert retained.effects == ("retained",)
        home = await list_employee_training(
            db_session,
            organization_id=organization.id,
            location_id=graph.location_id,
            employee_profile_id=employee.id,
            requested_locale="uk",
        )
        assert {module.title for module in home.modules} == {"shared", "optional"}
        draft = await create_training_draft(
            db_session,
            organization_id=organization.id,
            location_id=graph.location_id,
            actor_user_id=graph.user_id,
            request_id=uuid4(),
            base_version_id=version.id,
        )
        assert draft.all_positions is True


@pytest.mark.parametrize("position_scoped", [False, True])
async def test_role_change_preserves_history_and_renews_only_position_scoped_assignments(
    db_session: AsyncSession,
    position_scoped: bool,
) -> None:
    graph = await position_graph(db_session, "waiter")
    assignment = await db_session.get_one(TrainingAssignment, graph.assignment_id)
    completed_at = datetime.now(UTC)
    assignment.status = "completed"
    assignment.started_at = completed_at
    assignment.completed_at = completed_at
    if not position_scoped:
        for module in (await db_session.scalars(select(TrainingModuleVersion))).all():
            module.all_positions = True
        await db_session.execute(delete(TrainingModuleAudience))
    runner = await db_session.scalar(
        select(OperationalRole).where(
            OperationalRole.organization_id == graph.organization_id,
            OperationalRole.code == "runner",
        )
    )
    assert runner is not None
    await db_session.commit()
    await update_pending_employee_profile(
        db_session,
        organization_id=graph.organization_id,
        employee_id=graph.employee_profile_id,
        actor_user_id=graph.user_id,
        request_id=uuid4(),
        payload=EmployeeUpdate(operational_role_id=runner.id),
    )
    await db_session.refresh(assignment)
    assert assignment.completed_at == completed_at
    assert assignment.status == ("revoked" if position_scoped else "completed")
    current = await db_session.scalar(
        select(TrainingAssignment).where(
            TrainingAssignment.employee_profile_id == graph.employee_profile_id,
            TrainingAssignment.status != "revoked",
        )
    )
    assert current is not None
    if position_scoped:
        assert current.id != assignment.id
        assert current.previous_assignment_id == assignment.id
        assert current.status == "assigned"
        assert assignment.revoke_reason == "role_changed"
    else:
        assert current.id == assignment.id


@pytest.mark.parametrize("role_changed", [False, True])
async def test_rollout_preserves_position_specific_completion_and_progress(
    db_session: AsyncSession,
    role_changed: bool,
) -> None:
    graph = await position_graph(db_session, "runner")
    assignment = await db_session.get_one(TrainingAssignment, graph.assignment_id)
    source = await db_session.get_one(TrainingVersion, assignment.training_version_id)
    for code in ("runner", "shared"):
        lesson = await db_session.scalar(
            select(LessonVersion).where(
                LessonVersion.lesson_id == graph.modules[code][1],
            )
        )
        assert lesson is not None
        db_session.add(make_lesson_completion(assignment, lesson, graph.user_id))
    await db_session.commit()
    target = await create_training_draft(
        db_session,
        organization_id=graph.organization_id,
        location_id=graph.location_id,
        actor_user_id=graph.user_id,
        request_id=uuid4(),
        base_version_id=source.id,
    )
    if role_changed:
        for module in (
            await db_session.scalars(
                select(TrainingModuleVersion).where(
                    TrainingModuleVersion.training_version_id == source.id,
                )
            )
        ).all():
            module.all_positions = True
    now = datetime.now(UTC)
    source.status = "archived"
    source.archived_at = now
    await db_session.flush()
    target.status = "published"
    target.published_at = now
    target.published_by_user_id = graph.user_id
    await db_session.flush()
    rollout = await prepare_replacement_rollout(
        db_session,
        source=source,
        target=target,
        actor_user_id=graph.user_id,
        request_id=uuid4(),
        now=now,
    )
    await db_session.commit()
    impact = await db_session.scalar(
        select(RolloutEmployeeImpact).where(
            RolloutEmployeeImpact.rollout_id == rollout.id,
        )
    )
    assert impact is not None
    if role_changed:
        role = await db_session.scalar(
            select(OperationalRole).where(
                OperationalRole.organization_id == graph.organization_id,
                OperationalRole.code == "bartender",
            )
        )
        assert role is not None
        await update_pending_employee_profile(
            db_session,
            organization_id=graph.organization_id,
            employee_id=graph.employee_profile_id,
            actor_user_id=graph.user_id,
            request_id=uuid4(),
            payload=EmployeeUpdate(operational_role_id=role.id),
        )
        with pytest.raises(APIError) as caught:
            await confirm_training_rollout(
                db_session,
                organization_id=graph.organization_id,
                location_id=graph.location_id,
                rollout_id=rollout.id,
                actor_user_id=graph.user_id,
                request_id=uuid4(),
                expected_revision=rollout.revision,
                idempotency_key="stale-position-rollout",
                now=now,
            )
        assert caught.value.code == "TRAINING_ROLLOUT_STALE"
        return
    assert impact.current_required_count == impact.projected_required_count == 2
    assert impact.current_progress_percentage == impact.projected_progress_percentage == 100
    await confirm_training_rollout(
        db_session,
        organization_id=graph.organization_id,
        location_id=graph.location_id,
        rollout_id=rollout.id,
        actor_user_id=graph.user_id,
        request_id=uuid4(),
        expected_revision=rollout.revision,
        idempotency_key="position-rollout",
        now=now,
    )
    current = await db_session.scalar(
        select(TrainingAssignment).where(
            TrainingAssignment.employee_profile_id == graph.employee_profile_id,
            TrainingAssignment.status != "revoked",
        )
    )
    assert current is not None
    assert current.status == "completed"
    assert (await derive_training_progress(db_session, assignment=current)).percentage == 100
