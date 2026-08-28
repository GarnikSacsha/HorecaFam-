from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    AuditEvent,
    BackgroundJob,
    EmployeeProfile,
    OrganizationMembership,
    Training,
    TrainingAssignment,
    TrainingVersion,
    User,
)
from app.schemas.training import (
    TrainingAssignmentCreate,
    TrainingAssignmentListResponse,
    TrainingAssignmentReassign,
    TrainingAssignmentResponse,
    TrainingAssignmentRevoke,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)


def _not_found() -> APIError:
    return APIError(
        status_code=404,
        code="RESOURCE_NOT_FOUND",
        message="Ресурс не знайдено.",
    )


def _assignment_exists() -> APIError:
    return APIError(
        status_code=409,
        code="TRAINING_ASSIGNMENT_EXISTS",
        message="Працівник уже має поточне призначення навчання.",
    )


def _assignment_revoked() -> APIError:
    return APIError(
        status_code=409,
        code="TRAINING_ASSIGNMENT_REVOKED",
        message="Призначення навчання вже відкликано.",
    )


def _version_invalid() -> APIError:
    return APIError(
        status_code=409,
        code="TRAINING_ASSIGNMENT_VERSION_INVALID",
        message="Версія навчання недоступна для цього працівника.",
    )


def _response(assignment: TrainingAssignment) -> TrainingAssignmentResponse:
    return TrainingAssignmentResponse(
        id=assignment.id,
        organization_id=assignment.organization_id,
        location_id=assignment.location_id,
        training_id=assignment.training_id,
        employee_profile_id=assignment.employee_profile_id,
        training_version_id=assignment.training_version_id,
        status=assignment.status,
        source=assignment.source,
        previous_assignment_id=assignment.previous_assignment_id,
        source_rollout_id=assignment.source_rollout_id,
        assigned_at=assignment.assigned_at,
        started_at=assignment.started_at,
        completed_at=assignment.completed_at,
        revoked_at=assignment.revoked_at,
        revoke_reason=assignment.revoke_reason,
        revoke_note=assignment.revoke_note,
    )


async def _employee_context(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    lock: bool,
) -> tuple[EmployeeProfile, OrganizationMembership, User]:
    query = (
        select(EmployeeProfile, OrganizationMembership, User)
        .join(
            OrganizationMembership,
            and_(
                OrganizationMembership.id == EmployeeProfile.membership_id,
                OrganizationMembership.organization_id == EmployeeProfile.organization_id,
            ),
        )
        .join(User, User.id == OrganizationMembership.user_id)
        .where(
            EmployeeProfile.id == employee_id,
            EmployeeProfile.organization_id == organization_id,
        )
    )
    if lock:
        query = query.with_for_update()
    row = (await db.execute(query)).tuples().one_or_none()
    if row is None:
        raise _not_found()
    return row


async def _target_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    profile: EmployeeProfile,
    version_id: UUID | None,
    allow_retained: bool,
) -> tuple[Training, TrainingVersion]:
    if profile.location_id is None:
        raise _version_invalid()
    query = (
        select(Training, TrainingVersion)
        .join(
            TrainingVersion,
            and_(
                TrainingVersion.training_id == Training.id,
                TrainingVersion.organization_id == Training.organization_id,
                TrainingVersion.location_id == Training.location_id,
            ),
        )
        .where(
            Training.organization_id == organization_id,
            Training.location_id == profile.location_id,
        )
    )
    if version_id is None:
        query = query.where(TrainingVersion.status == "published")
    else:
        query = query.where(TrainingVersion.id == version_id)
    target = (await db.execute(query.with_for_update())).tuples().one_or_none()
    if target is None:
        if version_id is not None:
            raise _not_found()
        raise _version_invalid()
    if version_id is not None:
        allowed_statuses = ("published", "archived") if allow_retained else ("published",)
        if target[1].status not in allowed_statuses:
            raise _version_invalid()
    return target


async def _current_assignment(
    db: AsyncSession,
    *,
    employee_id: UUID,
) -> TrainingAssignment | None:
    return cast(
        TrainingAssignment | None,
        await db.scalar(
            select(TrainingAssignment)
            .where(
                TrainingAssignment.employee_profile_id == employee_id,
                TrainingAssignment.status != "revoked",
            )
            .order_by(TrainingAssignment.assigned_at.desc(), TrainingAssignment.id.desc())
            .limit(1)
            .with_for_update()
        ),
    )


async def _scoped_assignment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    assignment_id: UUID,
) -> TrainingAssignment:
    assignment = await db.scalar(
        select(TrainingAssignment)
        .where(
            TrainingAssignment.id == assignment_id,
            TrainingAssignment.organization_id == organization_id,
            TrainingAssignment.employee_profile_id == employee_id,
        )
        .with_for_update()
    )
    if assignment is None:
        raise _not_found()
    return assignment


def _notification_job(
    *,
    organization_id: UUID,
    assignment_id: UUID,
    template_code: str,
    locale: str,
    effect: str,
) -> BackgroundJob:
    return BackgroundJob(
        organization_id=organization_id,
        job_type="training_assignment_notification",
        status="pending",
        payload={
            "assignment_id": str(assignment_id),
            "template_code": template_code,
            "locale": "en" if locale == "en" else "uk",
        },
        idempotency_key=f"assignment:{assignment_id}:{effect}",
    )


async def list_training_assignments(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
) -> TrainingAssignmentListResponse:
    await _employee_context(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        lock=False,
    )
    assignments = list(
        (
            await db.scalars(
                select(TrainingAssignment)
                .where(
                    TrainingAssignment.organization_id == organization_id,
                    TrainingAssignment.employee_profile_id == employee_id,
                )
                .order_by(TrainingAssignment.assigned_at.desc(), TrainingAssignment.id.desc())
            )
        ).all()
    )
    current = next((row for row in assignments if row.status != "revoked"), None)
    history = [row for row in assignments if row.status == "revoked"]
    return TrainingAssignmentListResponse(
        current=_response(current) if current is not None else None,
        history=[_response(row) for row in history],
        progress=None,
    )


async def _assignment_replay(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    assignment_id: UUID,
) -> TrainingAssignmentResponse:
    assignment = await db.scalar(
        select(TrainingAssignment).where(
            TrainingAssignment.id == assignment_id,
            TrainingAssignment.organization_id == organization_id,
            TrainingAssignment.employee_profile_id == employee_id,
        )
    )
    if assignment is None:
        raise RuntimeError("Idempotent Training Assignment resource is unavailable")
    await db.commit()
    return _response(assignment)


async def _create_training_assignment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    actor_user_id: UUID,
    payload: TrainingAssignmentCreate,
    idempotency_key: str,
    now: datetime,
    request_id: UUID,
) -> TrainingAssignmentResponse:
    fingerprint = request_fingerprint(
        {
            "employee_id": str(employee_id),
            "training_version_id": (
                str(payload.training_version_id)
                if payload.training_version_id is not None
                else None
            ),
            "reason": payload.reason,
        }
    )
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="training_assignment.create",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay is not None:
        if replay.resource_type != "training_assignment":
            raise RuntimeError("Idempotent Training Assignment target is inconsistent")
        return await _assignment_replay(
            db,
            organization_id=organization_id,
            employee_id=employee_id,
            assignment_id=replay.resource_id,
        )

    assignment_id = uuid4()
    decision = await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="training_assignment.create",
        key=idempotency_key,
        fingerprint=fingerprint,
        resource_type="training_assignment",
        resource_id=assignment_id,
        response_status=201,
        now=now,
    )
    if decision.replayed:
        return await _assignment_replay(
            db,
            organization_id=organization_id,
            employee_id=employee_id,
            assignment_id=decision.record.resource_id,
        )

    profile, membership, user = await _employee_context(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        lock=True,
    )
    training, version = await _target_version(
        db,
        organization_id=organization_id,
        profile=profile,
        version_id=payload.training_version_id,
        allow_retained=False,
    )
    if (
        membership.status != "active"
        or await _current_assignment(db, employee_id=employee_id) is not None
    ):
        if membership.status == "active":
            raise _assignment_exists()
        raise _version_invalid()
    assignment = TrainingAssignment(
        id=assignment_id,
        organization_id=organization_id,
        location_id=training.location_id,
        training_id=training.id,
        employee_profile_id=employee_id,
        training_version_id=version.id,
        status="assigned",
        source="admin",
        assigned_by_user_id=actor_user_id,
        assigned_at=now,
    )
    db.add(assignment)
    db.add(
        _notification_job(
            organization_id=organization_id,
            assignment_id=assignment.id,
            template_code="training_assigned",
            locale=user.preferred_locale,
            effect="created",
        )
    )
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="training_assignment_created",
            target_type="training_assignment",
            target_id=assignment.id,
            old_values=None,
            new_values={
                "employee_profile_id": str(employee_id),
                "training_id": str(training.id),
                "training_version_id": str(version.id),
                "source": "admin",
                "reason": payload.reason,
            },
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return _response(assignment)


async def create_training_assignment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    actor_user_id: UUID,
    payload: TrainingAssignmentCreate,
    idempotency_key: str,
    now: datetime,
    request_id: UUID,
) -> TrainingAssignmentResponse:
    try:
        return await _create_training_assignment(
            db,
            organization_id=organization_id,
            employee_id=employee_id,
            actor_user_id=actor_user_id,
            payload=payload,
            idempotency_key=idempotency_key,
            now=now,
            request_id=request_id,
        )
    except Exception:
        await db.rollback()
        raise


async def _revoke_training_assignment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    assignment_id: UUID,
    actor_user_id: UUID,
    payload: TrainingAssignmentRevoke,
    idempotency_key: str,
    now: datetime,
    request_id: UUID,
) -> TrainingAssignmentResponse:
    fingerprint = request_fingerprint(
        {
            "employee_id": str(employee_id),
            "assignment_id": str(assignment_id),
            "reason": payload.reason,
        }
    )
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="training_assignment.revoke",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay is not None:
        return await _assignment_replay(
            db,
            organization_id=organization_id,
            employee_id=employee_id,
            assignment_id=replay.resource_id,
        )
    decision = await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="training_assignment.revoke",
        key=idempotency_key,
        fingerprint=fingerprint,
        resource_type="training_assignment",
        resource_id=assignment_id,
        response_status=200,
        now=now,
    )
    if decision.replayed:
        return await _assignment_replay(
            db,
            organization_id=organization_id,
            employee_id=employee_id,
            assignment_id=decision.record.resource_id,
        )
    _profile, _membership, user = await _employee_context(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        lock=True,
    )
    assignment = await _scoped_assignment(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        assignment_id=assignment_id,
    )
    if assignment.status == "revoked":
        raise _assignment_revoked()
    old_status = assignment.status
    assignment.status = "revoked"
    assignment.revoked_at = now
    assignment.revoke_reason = "admin"
    assignment.revoke_note = payload.reason
    db.add(
        _notification_job(
            organization_id=organization_id,
            assignment_id=assignment.id,
            template_code="training_revoked",
            locale=user.preferred_locale,
            effect="revoked",
        )
    )
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="training_assignment_revoked",
            target_type="training_assignment",
            target_id=assignment.id,
            old_values={"status": old_status},
            new_values={"status": "revoked", "revoke_reason": "admin", "reason": payload.reason},
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return _response(assignment)


async def revoke_training_assignment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    assignment_id: UUID,
    actor_user_id: UUID,
    payload: TrainingAssignmentRevoke,
    idempotency_key: str,
    now: datetime,
    request_id: UUID,
) -> TrainingAssignmentResponse:
    try:
        return await _revoke_training_assignment(
            db,
            organization_id=organization_id,
            employee_id=employee_id,
            assignment_id=assignment_id,
            actor_user_id=actor_user_id,
            payload=payload,
            idempotency_key=idempotency_key,
            now=now,
            request_id=request_id,
        )
    except Exception:
        await db.rollback()
        raise


async def _reassign_training_assignment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    assignment_id: UUID,
    actor_user_id: UUID,
    payload: TrainingAssignmentReassign,
    idempotency_key: str,
    now: datetime,
    request_id: UUID,
) -> TrainingAssignmentResponse:
    fingerprint = request_fingerprint(
        {
            "employee_id": str(employee_id),
            "assignment_id": str(assignment_id),
            "training_version_id": (
                str(payload.training_version_id)
                if payload.training_version_id is not None
                else None
            ),
            "reason": payload.reason,
        }
    )
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="training_assignment.reassign",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay is not None:
        return await _assignment_replay(
            db,
            organization_id=organization_id,
            employee_id=employee_id,
            assignment_id=replay.resource_id,
        )
    target_assignment_id = uuid4()
    decision = await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="training_assignment.reassign",
        key=idempotency_key,
        fingerprint=fingerprint,
        resource_type="training_assignment",
        resource_id=target_assignment_id,
        response_status=200,
        now=now,
    )
    if decision.replayed:
        return await _assignment_replay(
            db,
            organization_id=organization_id,
            employee_id=employee_id,
            assignment_id=decision.record.resource_id,
        )
    profile, membership, user = await _employee_context(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        lock=True,
    )
    source = await _scoped_assignment(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        assignment_id=assignment_id,
    )
    training, version = await _target_version(
        db,
        organization_id=organization_id,
        profile=profile,
        version_id=payload.training_version_id,
        allow_retained=True,
    )
    if membership.status != "active":
        raise _version_invalid()
    if source.status == "revoked":
        raise _assignment_revoked()
    if training.id != source.training_id:
        raise _version_invalid()
    source_status = source.status
    source.status = "revoked"
    source.revoked_at = now
    source.revoke_reason = "admin"
    source.revoke_note = payload.reason or None
    target = TrainingAssignment(
        id=target_assignment_id,
        organization_id=organization_id,
        location_id=training.location_id,
        training_id=training.id,
        employee_profile_id=employee_id,
        training_version_id=version.id,
        status="assigned",
        source="reassign",
        previous_assignment_id=source.id,
        assigned_by_user_id=actor_user_id,
        assigned_at=now,
    )
    db.add(target)
    await db.flush()
    db.add(
        _notification_job(
            organization_id=organization_id,
            assignment_id=target.id,
            template_code="training_assigned",
            locale=user.preferred_locale,
            effect="created",
        )
    )
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="training_assignment_reassigned",
            target_type="training_assignment",
            target_id=target.id,
            old_values={
                "assignment_id": str(source.id),
                "status": source_status,
                "training_version_id": str(source.training_version_id),
            },
            new_values={
                "assignment_id": str(target.id),
                "status": "assigned",
                "training_version_id": str(target.training_version_id),
                "previous_assignment_id": str(source.id),
                "reason": payload.reason,
            },
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return _response(target)


async def reassign_training_assignment(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    assignment_id: UUID,
    actor_user_id: UUID,
    payload: TrainingAssignmentReassign,
    idempotency_key: str,
    now: datetime,
    request_id: UUID,
) -> TrainingAssignmentResponse:
    try:
        return await _reassign_training_assignment(
            db,
            organization_id=organization_id,
            employee_id=employee_id,
            assignment_id=assignment_id,
            actor_user_id=actor_user_id,
            payload=payload,
            idempotency_key=idempotency_key,
            now=now,
            request_id=request_id,
        )
    except Exception:
        await db.rollback()
        raise
