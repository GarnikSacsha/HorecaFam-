from uuid import UUID, uuid4

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models import (
    EmployeeProfile,
    OperationalRole,
    TrainingModule,
    TrainingModuleAudience,
    TrainingModuleTranslation,
    TrainingModuleVersion,
    TrainingVersion,
)
from app.schemas.training import ModuleAudienceWrite
from app.services.training_drafts import (
    TrainingDraftMutation,
    _audit,
    _bounded_text,
    _lock_draft,
    _optional_text,
    _resource_not_found,
    _validation_error,
)


def module_visible_to(employee_profile_id: UUID) -> ColumnElement[bool]:
    role = (
        select(EmployeeProfile.operational_role_id)
        .where(EmployeeProfile.id == employee_profile_id)
        .scalar_subquery()
    )
    return or_(
        TrainingModuleVersion.all_positions.is_(True),
        select(TrainingModuleAudience.id)
        .where(
            TrainingModuleAudience.training_module_version_id == TrainingModuleVersion.id,
            TrainingModuleAudience.operational_role_id == role,
        )
        .exists(),
    )


async def set_module_audience(
    db: AsyncSession,
    *,
    version: TrainingVersion,
    module: TrainingModuleVersion,
    all_positions: bool,
    operational_role_ids: list[UUID],
) -> None:
    ModuleAudienceWrite(all_positions=all_positions, operational_role_ids=operational_role_ids)
    roles = list(
        (
            await db.scalars(
                select(OperationalRole)
                .where(
                    OperationalRole.organization_id == version.organization_id,
                    OperationalRole.id.in_(operational_role_ids),
                    OperationalRole.status == "active",
                )
                .with_for_update()
            )
        ).all()
    )
    if len(roles) != len(operational_role_ids):
        raise _resource_not_found()
    await db.execute(
        delete(TrainingModuleAudience).where(
            TrainingModuleAudience.training_module_version_id == module.id
        )
    )
    module.all_positions = all_positions
    db.add_all(
        [
            TrainingModuleAudience(
                organization_id=version.organization_id,
                location_id=version.location_id,
                training_version_id=version.id,
                training_module_version_id=module.id,
                operational_role_id=role.id,
            )
            for role in roles
        ]
    )


async def create_position_module(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    domain_type: str,
    title_uk: str,
    description_uk: str | None,
    required: bool,
    all_positions: bool,
    operational_role_ids: list[UUID],
) -> TrainingDraftMutation[TrainingModuleVersion]:
    try:
        version = await _lock_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            expected_revision=expected_revision,
        )
        if domain_type not in {"service", "sales", "venue_standards"}:
            raise _validation_error()
        highest = await db.scalar(
            select(func.max(TrainingModuleVersion.position)).where(
                TrainingModuleVersion.training_version_id == version.id
            )
        )
        identity = TrainingModule(
            id=uuid4(), training_id=version.training_id, domain_type=domain_type
        )
        db.add(identity)
        await db.flush()
        module = TrainingModuleVersion(
            id=uuid4(),
            training_id=version.training_id,
            training_version_id=version.id,
            training_module_id=identity.id,
            position=(highest + 1 if highest is not None else 0),
            required=required,
            all_positions=all_positions,
        )
        db.add(module)
        await db.flush()
        await set_module_audience(
            db,
            version=version,
            module=module,
            all_positions=all_positions,
            operational_role_ids=operational_role_ids,
        )
        db.add(
            TrainingModuleTranslation(
                training_module_version_id=module.id,
                locale="uk",
                status="ready",
                title=_bounded_text(title_uk, maximum=200),
                description=_optional_text(description_uk, maximum=2000),
                source_revision=0,
            )
        )
        version.revision += 1
        _audit(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            action="training_module_created",
            target_type="training_module_version",
            target_id=module.id,
        )
        await db.commit()
        return TrainingDraftMutation(entity=module, revision=version.revision)
    except Exception:
        await db.rollback()
        raise


async def update_module_audience(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    module_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    all_positions: bool,
    operational_role_ids: list[UUID],
) -> TrainingDraftMutation[TrainingModuleVersion]:
    try:
        version = await _lock_draft(
            db,
            organization_id=organization_id,
            location_id=location_id,
            version_id=version_id,
            expected_revision=expected_revision,
        )
        module = await db.scalar(
            select(TrainingModuleVersion).where(
                TrainingModuleVersion.id == module_id,
                TrainingModuleVersion.training_version_id == version.id,
            )
        )
        if module is None:
            raise _resource_not_found()
        await set_module_audience(
            db,
            version=version,
            module=module,
            all_positions=all_positions,
            operational_role_ids=operational_role_ids,
        )
        version.revision += 1
        _audit(
            db,
            version=version,
            actor_user_id=actor_user_id,
            request_id=request_id,
            action="training_module_audience_updated",
            target_type="training_module_version",
            target_id=module.id,
        )
        await db.commit()
        return TrainingDraftMutation(entity=module, revision=version.revision)
    except Exception:
        await db.rollback()
        raise
