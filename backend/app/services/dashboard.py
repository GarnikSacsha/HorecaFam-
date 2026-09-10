from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Assessment,
    AssessmentAttempt,
    AssessmentVersion,
    AttemptResult,
    AttentionCase,
    EmployeeProfile,
    Location,
    OrganizationMembership,
    RetakeRequirement,
    TrainingAssignment,
)
from app.schemas.dashboard import DashboardResponse


async def get_dashboard(
    db: AsyncSession, *, organization_id: UUID, location_id: UUID | None, now: datetime
) -> DashboardResponse:
    if (
        location_id is not None
        and await db.scalar(
            select(Location.id).where(
                Location.id == location_id,
                Location.organization_id == organization_id,
            )
        )
        is None
    ):
        raise APIError(status_code=404, code="RESOURCE_NOT_FOUND", message="Ресурс не знайдено.")
    profile_query = (
        select(
            EmployeeProfile.id,
            OrganizationMembership.status,
            OrganizationMembership.training_participation_status.label("participation"),
        )
        .join(OrganizationMembership, OrganizationMembership.id == EmployeeProfile.membership_id)
        .where(
            EmployeeProfile.organization_id == organization_id,
            OrganizationMembership.organization_id == organization_id,
        )
    )
    if location_id is not None:
        profile_query = profile_query.where(EmployeeProfile.location_id == location_id)
    profiles = profile_query.cte("dashboard_profiles")
    employees = (
        (
            await db.execute(
                select(
                    func.count().label("total"),
                    func.count().filter(profiles.c.status == "active").label("active"),
                    func.count().filter(profiles.c.status == "pending").label("pending"),
                    func.count()
                    .filter(
                        profiles.c.status == "active",
                        profiles.c.participation == "paused",
                    )
                    .label("paused"),
                    func.count().filter(profiles.c.status == "disabled").label("disabled"),
                ).select_from(profiles)
            )
        )
        .mappings()
        .one()
    )
    assignments = (
        select(TrainingAssignment.id, TrainingAssignment.status)
        .join(profiles, profiles.c.id == TrainingAssignment.employee_profile_id)
        .where(
            TrainingAssignment.organization_id == organization_id,
            TrainingAssignment.status != "revoked",
            profiles.c.status == "active",
        )
    ).cte("dashboard_assignments")
    training = (
        (
            await db.execute(
                select(
                    func.count().filter(assignments.c.status == "assigned").label("assigned"),
                    func.count().filter(assignments.c.status == "in_progress").label("in_progress"),
                    func.count().filter(assignments.c.status == "completed").label("completed"),
                ).select_from(assignments)
            )
        )
        .mappings()
        .one()
    )

    # Сертифікація належить стабільному Training: пізніша невдача не скасовує успіх.
    certified = (
        select(AttemptResult.id)
        .join(
            AssessmentAttempt,
            AssessmentAttempt.id == AttemptResult.attempt_id,
        )
        .join(
            AssessmentVersion,
            AssessmentVersion.id == AssessmentAttempt.assessment_version_id,
        )
        .join(Assessment, Assessment.id == AssessmentVersion.assessment_id)
        .where(
            AssessmentAttempt.organization_id == organization_id,
            AssessmentAttempt.employee_profile_id == TrainingAssignment.employee_profile_id,
            AssessmentAttempt.training_id == TrainingAssignment.training_id,
            Assessment.assessment_type == "menu_final_exam",
            AttemptResult.pass_status == "passed",
        )
        .exists()
    )
    final = (
        (
            await db.execute(
                select(
                    func.count(func.distinct(TrainingAssignment.employee_profile_id))
                    .filter(certified)
                    .label("certified"),
                    func.count(func.distinct(TrainingAssignment.employee_profile_id))
                    .filter(
                        TrainingAssignment.status == "completed",
                        ~certified,
                    )
                    .label("needs_exam"),
                )
                .select_from(TrainingAssignment)
                .join(
                    profiles,
                    profiles.c.id == TrainingAssignment.employee_profile_id,
                )
                .where(
                    TrainingAssignment.organization_id == organization_id,
                    TrainingAssignment.status != "revoked",
                    profiles.c.status == "active",
                )
            )
        )
        .mappings()
        .one()
    )
    retakes = (
        (
            await db.execute(
                select(
                    func.count(func.distinct(RetakeRequirement.employee_profile_id)).label(
                        "retake"
                    ),
                    func.count(func.distinct(RetakeRequirement.employee_profile_id))
                    .filter(
                        RetakeRequirement.clock_frozen_at.is_(None),
                        RetakeRequirement.due_at <= now,
                        profiles.c.participation == "active",
                    )
                    .label("overdue_retake"),
                )
                .select_from(RetakeRequirement)
                .join(
                    profiles,
                    profiles.c.id == RetakeRequirement.employee_profile_id,
                )
                .where(
                    RetakeRequirement.organization_id == organization_id,
                    RetakeRequirement.state == "active",
                    profiles.c.status == "active",
                )
            )
        )
        .mappings()
        .one()
    )
    attention = (
        (
            await db.execute(
                select(
                    func.count().label("unresolved"),
                    func.count()
                    .filter(AttentionCase.case_type == "critical_allergen")
                    .label("critical"),
                )
                .select_from(AttentionCase)
                .join(
                    profiles,
                    profiles.c.id == AttentionCase.employee_profile_id,
                )
                .where(
                    AttentionCase.organization_id == organization_id,
                    AttentionCase.state.in_(["open", "acknowledged"]),
                )
            )
        )
        .mappings()
        .one()
    )
    return DashboardResponse.model_validate(
        {
            "organization_id": organization_id,
            "location_id": location_id,
            "employees": dict(employees),
            "training": dict(training),
            "final_exam": {**final, **retakes},
            "attention": dict(attention),
        }
    )
