from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import AuditEvent, OperationalRole, TrainingVersion, TrainingVersionAudience
from app.schemas.training import TrainingAudienceResponse


def _not_found() -> APIError:
    return APIError(status_code=404, code="RESOURCE_NOT_FOUND", message="Ресурс не знайдено.")


def _revision_conflict() -> APIError:
    return APIError(
        status_code=409,
        code="REVISION_CONFLICT",
        message="Чернетку вже змінено. Оновіть дані та повторіть дію.",
    )


async def update_training_audience(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    operational_role_ids: list[UUID],
) -> TrainingAudienceResponse:
    try:
        version = await db.scalar(
            select(TrainingVersion)
            .where(
                TrainingVersion.id == version_id,
                TrainingVersion.organization_id == organization_id,
                TrainingVersion.location_id == location_id,
            )
            .with_for_update()
        )
        if version is None:
            raise _not_found()
        if version.status != "draft":
            raise APIError(
                status_code=409,
                code="VERSION_IMMUTABLE",
                message="Опубліковану версію навчання не можна змінювати.",
            )
        if version.revision != expected_revision:
            raise _revision_conflict()
        if not operational_role_ids:
            raise APIError(
                status_code=409,
                code="TRAINING_AUDIENCE_REQUIRED",
                message="Оберіть щонайменше одну активну операційну роль.",
            )

        roles = list(
            (
                await db.scalars(
                    select(OperationalRole)
                    .where(
                        OperationalRole.id.in_(operational_role_ids),
                        OperationalRole.organization_id == organization_id,
                    )
                    .with_for_update()
                )
            ).all()
        )
        if len(roles) != len(operational_role_ids):
            raise _not_found()
        if any(role.status != "active" for role in roles):
            raise APIError(
                status_code=409,
                code="REFERENCE_INACTIVE",
                message="Обраний довідниковий запис неактивний.",
            )

        previous_ids = list(
            (
                await db.scalars(
                    select(TrainingVersionAudience.operational_role_id).where(
                        TrainingVersionAudience.training_version_id == version.id
                    )
                )
            ).all()
        )
        await db.execute(
            delete(TrainingVersionAudience).where(
                TrainingVersionAudience.training_version_id == version.id
            )
        )
        ordered_ids = sorted(operational_role_ids, key=str)
        db.add_all(
            [
                TrainingVersionAudience(
                    organization_id=organization_id,
                    location_id=location_id,
                    training_version_id=version.id,
                    operational_role_id=role_id,
                )
                for role_id in ordered_ids
            ]
        )
        version.revision += 1
        db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_type="user",
                action="training_audience_updated",
                target_type="training_version",
                target_id=version.id,
                old_values={
                    "operational_role_ids": [str(item) for item in sorted(previous_ids, key=str)]
                },
                new_values={"operational_role_ids": [str(item) for item in ordered_ids]},
                request_id=request_id,
                outcome="success",
            )
        )
        await db.commit()
        return TrainingAudienceResponse(
            training_version_id=version.id,
            revision=version.revision,
            operational_role_ids=ordered_ids,
        )
    except Exception:
        await db.rollback()
        raise
