from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import app.models.enums as model_enums
from app.db.base import Base
from app.models import (
    BackgroundJob,
    EmployeeProfile,
    Lesson,
    LessonVersion,
    OperationalRole,
    Training,
    TrainingVersion,
    User,
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
    make_lesson,
    make_lesson_completion,
    make_lesson_version,
    make_rollout_employee_impact,
    make_rollout_lesson_rule,
    make_training,
    make_training_assignment,
    make_training_module,
    make_training_module_version,
    make_training_rollout,
    make_training_version,
    make_training_version_audience,
)

EXPECTED_ENUM_VALUES = {
    "BackgroundJobType": {
        "attempt_expiry",
        "audit_retention",
        "invitation_email",
        "password_reset_email",
        "retake_deadline_projection",
        "security_record_cleanup",
        "training_assignment_notification",
        "training_rollout_notification",
    },
    "LessonCompletionSource": {
        "employee",
        "reassignment_preserved",
        "rollout_preserved",
    },
    "RolloutLessonRule": {
        "new_incomplete",
        "needs_repeat",
        "preserve_completion",
        "removed_historical",
    },
    "TrainingAssignmentRevokeReason": {
        "admin",
        "location_changed",
        "role_changed",
        "rollout",
    },
    "TrainingAssignmentSource": {"admin", "automatic", "reassign", "rollout"},
    "TrainingAssignmentStatus": {"assigned", "completed", "in_progress", "revoked"},
    "TrainingRolloutStatus": {
        "cancelled",
        "completed",
        "confirmed",
        "draft",
        "failed",
        "preview_ready",
        "processing",
        "stale",
    },
}

EXPECTED_TABLE_COLUMNS = {
    "training_version_audiences": {
        "id",
        "organization_id",
        "location_id",
        "training_version_id",
        "operational_role_id",
        "created_at",
    },
    "training_assignments": {
        "id",
        "organization_id",
        "location_id",
        "training_id",
        "employee_profile_id",
        "training_version_id",
        "status",
        "source",
        "previous_assignment_id",
        "source_rollout_id",
        "assigned_by_user_id",
        "assigned_at",
        "started_at",
        "completed_at",
        "revoked_at",
        "revoke_reason",
        "revoke_note",
        "created_at",
        "updated_at",
    },
    "lesson_completions": {
        "id",
        "organization_id",
        "location_id",
        "training_id",
        "assignment_id",
        "lesson_id",
        "lesson_version_id",
        "completion_source",
        "source_completion_id",
        "source_rollout_id",
        "completed_by_user_id",
        "completed_at",
        "created_at",
    },
    "training_rollouts": {
        "id",
        "organization_id",
        "location_id",
        "training_id",
        "from_version_id",
        "to_version_id",
        "status",
        "revision",
        "source_assignment_set_fingerprint",
        "from_version_revision",
        "to_version_revision",
        "created_by_user_id",
        "confirmed_by_user_id",
        "previewed_at",
        "confirmed_at",
        "processing_at",
        "completed_at",
        "failure_code",
        "created_at",
        "updated_at",
    },
    "rollout_lesson_rules": {
        "id",
        "rollout_id",
        "lesson_id",
        "from_lesson_version_id",
        "to_lesson_version_id",
        "rule",
        "requires_admin_decision",
        "decided_by_user_id",
        "decided_at",
    },
    "rollout_employee_impacts": {
        "id",
        "rollout_id",
        "employee_profile_id",
        "source_assignment_id",
        "target_assignment_id",
        "current_required_count",
        "current_completed_count",
        "current_progress_percentage",
        "projected_required_count",
        "projected_completed_count",
        "projected_progress_percentage",
        "lesson_impact",
        "validation_codes",
        "warning_codes",
        "preview_fingerprint",
        "previewed_at",
    },
}


def _constraint_names(table_name: str) -> set[str]:
    return {
        str(constraint.name)
        for constraint in Base.metadata.tables[table_name].constraints
        if constraint.name is not None
    }


def _index_names(table_name: str) -> set[str]:
    return {
        str(index.name)
        for index in Base.metadata.tables[table_name].indexes
        if index.name is not None
    }


def _enum_values(enum_type: type[object]) -> Collection[str]:
    return {str(member.value) for member in enum_type}  # type: ignore[attr-defined]


def test_assignment_rollout_enums_match_the_accepted_contract() -> None:
    missing = set(EXPECTED_ENUM_VALUES) - set(vars(model_enums))
    assert not missing, f"Missing accepted Slice 4 enums: {sorted(missing)}"

    for name, expected_values in EXPECTED_ENUM_VALUES.items():
        assert set(_enum_values(getattr(model_enums, name))) == expected_values


def test_assignment_rollout_metadata_contains_only_the_accepted_columns() -> None:
    missing = set(EXPECTED_TABLE_COLUMNS) - set(Base.metadata.tables)
    assert not missing, f"Missing accepted Slice 4 tables: {sorted(missing)}"

    for table_name, expected_columns in EXPECTED_TABLE_COLUMNS.items():
        assert set(Base.metadata.tables[table_name].columns.keys()) == expected_columns


def test_assignment_rollout_metadata_declares_required_constraints_and_indexes() -> None:
    missing = set(EXPECTED_TABLE_COLUMNS) - set(Base.metadata.tables)
    assert not missing, f"Missing accepted Slice 4 tables: {sorted(missing)}"

    assert {
        "uq_training_version_audiences_version_role",
        "fk_training_version_audiences_version_scope",
        "fk_training_version_audiences_role_scope",
        "fk_training_version_audiences_location_scope",
    } <= _constraint_names("training_version_audiences")

    assert {
        "uq_training_assignments_lineage_scope",
        "fk_training_assignments_version_scope",
        "fk_training_assignments_employee_scope",
        "fk_training_assignments_previous_scope",
        "fk_training_assignments_rollout_scope",
        "ck_training_assignments_lifecycle_timestamps_match",
    } <= _constraint_names("training_assignments")
    assert {
        "uq_training_assignments_current",
        "ix_training_assignments_employee_training_status",
        "ix_training_assignments_employee_assigned_at",
    } <= _index_names("training_assignments")

    assert {
        "uq_lesson_completions_assignment_lesson",
        "fk_lesson_completions_assignment_scope",
        "fk_lesson_completions_lesson_version",
        "fk_lesson_completions_source_scope",
        "ck_lesson_completions_source_provenance_match",
    } <= _constraint_names("lesson_completions")
    assert "ix_lesson_completions_source_completion" in _index_names("lesson_completions")

    assert {
        "uq_training_rollouts_lineage_scope",
        "fk_training_rollouts_from_version_scope",
        "fk_training_rollouts_to_version_scope",
        "ck_training_rollouts_versions_differ",
        "ck_training_rollouts_lifecycle_timestamps_match",
    } <= _constraint_names("training_rollouts")
    assert {
        "uq_training_rollouts_active_pair",
        "ix_training_rollouts_training_status_versions",
    } <= _index_names("training_rollouts")

    assert {
        "uq_rollout_lesson_rules_rollout_lesson",
        "ck_rollout_lesson_rules_decision_matches",
        "ck_rollout_lesson_rules_versions_match_rule",
    } <= _constraint_names("rollout_lesson_rules")

    assert {
        "uq_rollout_employee_impacts_rollout_assignment",
        "ck_rollout_employee_impacts_counts_nonnegative",
        "ck_rollout_employee_impacts_progress_range",
        "ck_rollout_employee_impacts_payload_shapes",
    } <= _constraint_names("rollout_employee_impacts")
    assert "ix_rollout_employee_impacts_rollout_employee" in _index_names(
        "rollout_employee_impacts"
    )


@dataclass(frozen=True)
class AssignmentContext:
    actor: User
    employee: EmployeeProfile
    role: OperationalRole
    training: Training
    from_version: TrainingVersion
    to_version: TrainingVersion
    lesson: Lesson
    from_lesson_version: LessonVersion
    to_lesson_version: LessonVersion


async def _make_assignment_context(session: AsyncSession) -> AssignmentContext:
    organization = make_organization()
    location = make_location(organization)
    role = make_role(organization)
    actor = make_user(email_normalized="admin@example.com")
    employee_user = make_user(email_normalized="employee@example.com")
    session.add_all([organization, location, role, actor, employee_user])
    await session.flush()

    membership = make_membership(organization, employee_user)
    session.add(membership)
    await session.flush()
    employee = make_employee_profile(
        membership,
        organization.id,
        operational_role_id=role.id,
        location_id=location.id,
    )
    session.add(employee)
    await session.flush()

    training = make_training(organization.id, location.id)
    module = make_training_module(training)
    session.add_all([training, module])
    await session.flush()

    now = datetime.now(UTC)
    from_version = make_training_version(
        training,
        actor.id,
        status="archived",
        published_by_user_id=actor.id,
        published_at=now,
        archived_at=now,
    )
    to_version = make_training_version(
        training,
        actor.id,
        version_number=2,
        status="published",
        published_by_user_id=actor.id,
        published_at=now,
    )
    session.add_all([from_version, to_version])
    await session.flush()

    from_module_version = make_training_module_version(from_version, module)
    to_module_version = make_training_module_version(to_version, module)
    lesson = make_lesson(module)
    session.add_all([from_module_version, to_module_version, lesson])
    await session.flush()
    from_lesson_version = make_lesson_version(from_module_version, lesson)
    to_lesson_version = make_lesson_version(to_module_version, lesson)
    session.add_all([from_lesson_version, to_lesson_version])
    await session.flush()

    return AssignmentContext(
        actor=actor,
        employee=employee,
        role=role,
        training=training,
        from_version=from_version,
        to_version=to_version,
        lesson=lesson,
        from_lesson_version=from_lesson_version,
        to_lesson_version=to_lesson_version,
    )


async def _assert_integrity_error(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


@pytest.mark.integration
async def test_complete_assignment_completion_rollout_graph_persists(
    db_session: AsyncSession,
) -> None:
    context = await _make_assignment_context(db_session)
    rollout = make_training_rollout(
        context.training,
        context.from_version,
        context.to_version,
        context.actor.id,
    )
    now = datetime.now(UTC)
    assignment = make_training_assignment(
        context.employee,
        context.training,
        context.from_version,
        status="completed",
        started_at=now,
        completed_at=now,
    )
    db_session.add_all(
        [
            make_training_version_audience(context.to_version, context.role),
            rollout,
            assignment,
        ]
    )
    await db_session.flush()
    completion = make_lesson_completion(
        assignment,
        context.from_lesson_version,
        context.employee.membership.user_id,
    )
    rule = make_rollout_lesson_rule(
        rollout,
        context.from_lesson_version,
        context.to_lesson_version,
    )
    impact = make_rollout_employee_impact(rollout, context.employee, assignment)
    db_session.add_all([completion, rule, impact])
    await db_session.commit()

    assert assignment.status == "completed"
    assert completion.completion_source == "employee"
    assert rule.rule == "preserve_completion"
    assert impact.projected_progress_percentage == 100


@pytest.mark.integration
async def test_only_one_current_assignment_survives_database_enforcement(
    db_session: AsyncSession,
) -> None:
    context = await _make_assignment_context(db_session)
    db_session.add_all(
        [
            make_training_assignment(context.employee, context.training, context.from_version),
            make_training_assignment(context.employee, context.training, context.to_version),
        ]
    )

    await _assert_integrity_error(db_session)


@pytest.mark.integration
async def test_assignment_lifecycle_timestamps_are_database_enforced(
    db_session: AsyncSession,
) -> None:
    context = await _make_assignment_context(db_session)
    db_session.add(
        make_training_assignment(
            context.employee,
            context.training,
            context.from_version,
            status="completed",
        )
    )

    await _assert_integrity_error(db_session)


@pytest.mark.integration
async def test_completion_provenance_is_database_enforced(db_session: AsyncSession) -> None:
    context = await _make_assignment_context(db_session)
    assignment = make_training_assignment(context.employee, context.training, context.from_version)
    db_session.add(assignment)
    await db_session.flush()
    db_session.add(
        make_lesson_completion(
            assignment,
            context.from_lesson_version,
            context.actor.id,
            completion_source="rollout_preserved",
            completed_by_user_id=None,
        )
    )

    await _assert_integrity_error(db_session)


@pytest.mark.integration
async def test_rollout_requires_distinct_versions(db_session: AsyncSession) -> None:
    context = await _make_assignment_context(db_session)
    db_session.add(
        make_training_rollout(
            context.training,
            context.from_version,
            context.from_version,
            context.actor.id,
        )
    )

    await _assert_integrity_error(db_session)


@pytest.mark.integration
async def test_rollout_impact_counts_are_database_enforced(db_session: AsyncSession) -> None:
    context = await _make_assignment_context(db_session)
    rollout = make_training_rollout(
        context.training,
        context.from_version,
        context.to_version,
        context.actor.id,
    )
    assignment = make_training_assignment(context.employee, context.training, context.from_version)
    db_session.add_all([rollout, assignment])
    await db_session.flush()
    db_session.add(
        make_rollout_employee_impact(
            rollout,
            context.employee,
            assignment,
            current_required_count=1,
            current_completed_count=2,
        )
    )

    await _assert_integrity_error(db_session)


@pytest.mark.integration
async def test_version_audience_rejects_a_role_from_another_organization(
    db_session: AsyncSession,
) -> None:
    context = await _make_assignment_context(db_session)
    other_organization = make_organization(name="Other Organization")
    other_role = make_role(other_organization, code="runner")
    db_session.add_all([other_organization, other_role])
    await db_session.flush()
    db_session.add(make_training_version_audience(context.to_version, other_role))

    await _assert_integrity_error(db_session)


@pytest.mark.integration
async def test_training_notification_job_safe_payload_persists(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    db_session.add(organization)
    await db_session.flush()
    job = BackgroundJob(
        organization_id=organization.id,
        job_type="training_assignment_notification",
        status="pending",
        payload={
            "assignment_id": str(uuid4()),
            "template_code": "training_assigned",
            "locale": "uk",
        },
        idempotency_key=f"assignment:{uuid4()}",
    )
    db_session.add(job)
    await db_session.commit()

    assert job.job_type == "training_assignment_notification"


@pytest.mark.integration
async def test_training_notification_job_rejects_an_unbounded_payload(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    db_session.add(organization)
    await db_session.flush()
    db_session.add(
        BackgroundJob(
            organization_id=organization.id,
            job_type="training_assignment_notification",
            status="pending",
            payload={
                "assignment_id": str(uuid4()),
                "template_code": "training_assigned",
                "locale": "uk",
                "rendered_body": "must not enter the job payload",
            },
            idempotency_key=f"assignment:{uuid4()}",
        )
    )

    await _assert_integrity_error(db_session)
