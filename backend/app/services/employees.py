import base64
import binascii
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    AuditEvent,
    EmployeeProfile,
    Location,
    OperationalRole,
    Organization,
    OrganizationMembership,
    User,
)
from app.schemas.employees import (
    EmployeeDetail,
    EmployeeLifecycleActionResponse,
    EmployeeListResponse,
    EmployeeSummary,
    EmployeeUpdate,
    LocationSummary,
    OperationalRoleSummary,
    OrganizationReference,
    OrganizationSummary,
    OwnEmployeeProfile,
    OwnEmployeeProfilesResponse,
)
from app.services.applicability import evaluate_activation_applicability
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)

EmployeeRow = tuple[
    EmployeeProfile,
    OrganizationMembership,
    User,
    OperationalRole | None,
    Location | None,
]


def _resource_not_found() -> APIError:
    return APIError(
        status_code=404,
        code="RESOURCE_NOT_FOUND",
        message="Ресурс не знайдено.",
    )


def _invalid_cursor() -> APIError:
    return APIError(
        status_code=422,
        code="VALIDATION_ERROR",
        message="Перевірте правильність заповнення полів.",
    )


def _location_summary(location: Location | None) -> LocationSummary | None:
    if location is None:
        return None
    return LocationSummary(
        id=location.id,
        organization_id=location.organization_id,
        name=location.name,
        status=location.status,
        address=location.address,
        timezone=location.timezone,
    )


def _role_summary(role: OperationalRole | None) -> OperationalRoleSummary | None:
    if role is None:
        return None
    return OperationalRoleSummary(
        id=role.id,
        organization_id=role.organization_id,
        code=role.code,
        name_uk=role.name_uk,
        status=role.status,
    )


def _profile_complete(row: EmployeeRow) -> bool:
    profile, _membership, _user, role, location = row
    return bool(
        profile.first_name
        and profile.first_name.strip()
        and profile.last_name
        and profile.last_name.strip()
        and role is not None
        and role.organization_id == profile.organization_id
        and role.status == "active"
        and location is not None
        and location.organization_id == profile.organization_id
        and location.status == "active"
    )


def _employee_summary(row: EmployeeRow) -> EmployeeSummary:
    profile, membership, user, role, location = row
    return EmployeeSummary(
        id=profile.id,
        organization_id=profile.organization_id,
        email=user.email_normalized,
        first_name=profile.first_name,
        last_name=profile.last_name,
        membership_status=membership.status,
        operational_role=_role_summary(role),
        location=_location_summary(location),
        profile_complete=_profile_complete(row),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _employee_detail(row: EmployeeRow) -> EmployeeDetail:
    profile, membership, _user, _role, _location = row
    summary = _employee_summary(row)
    return EmployeeDetail(
        **summary.model_dump(),
        membership_created_at=membership.created_at,
        activated_at=membership.activated_at,
        disabled_at=membership.disabled_at,
    )


def _employee_statement() -> Select[
    tuple[EmployeeProfile, OrganizationMembership, User, OperationalRole, Location]
]:
    return (
        select(EmployeeProfile, OrganizationMembership, User, OperationalRole, Location)
        .join(
            OrganizationMembership,
            and_(
                OrganizationMembership.id == EmployeeProfile.membership_id,
                OrganizationMembership.organization_id == EmployeeProfile.organization_id,
            ),
        )
        .join(User, User.id == OrganizationMembership.user_id)
        .outerjoin(
            OperationalRole,
            and_(
                OperationalRole.id == EmployeeProfile.operational_role_id,
                OperationalRole.organization_id == EmployeeProfile.organization_id,
            ),
        )
        .outerjoin(
            Location,
            and_(
                Location.id == EmployeeProfile.location_id,
                Location.organization_id == EmployeeProfile.organization_id,
            ),
        )
    )


def _encode_cursor(created_at: datetime, profile_id: UUID) -> str:
    value = f"{created_at.isoformat()}|{profile_id}".encode()
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padding = "=" * (-len(cursor) % 4)
        value = base64.urlsafe_b64decode(f"{cursor}{padding}").decode()
        created_at_text, profile_id_text = value.rsplit("|", maxsplit=1)
        created_at = datetime.fromisoformat(created_at_text)
        if created_at.tzinfo is None:
            raise ValueError
        return created_at, UUID(profile_id_text)
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise _invalid_cursor() from exc


async def get_organization_summary(
    db: AsyncSession,
    *,
    organization_id: UUID,
) -> OrganizationSummary:
    organization = await db.get(Organization, organization_id)
    if organization is None:
        raise _resource_not_found()
    return OrganizationSummary(
        id=organization.id,
        name=organization.name,
        status=organization.status,
        default_locale=organization.default_locale,
        timezone=organization.timezone,
    )


async def list_locations(
    db: AsyncSession,
    *,
    organization_id: UUID,
) -> list[LocationSummary]:
    locations = list(
        (
            await db.scalars(
                select(Location)
                .where(Location.organization_id == organization_id)
                .order_by(func.lower(Location.name), Location.id)
            )
        ).all()
    )
    return [summary for item in locations if (summary := _location_summary(item)) is not None]


async def list_operational_roles(
    db: AsyncSession,
    *,
    organization_id: UUID,
) -> list[OperationalRoleSummary]:
    roles = list(
        (
            await db.scalars(
                select(OperationalRole)
                .where(OperationalRole.organization_id == organization_id)
                .order_by(func.lower(OperationalRole.name_uk), OperationalRole.id)
            )
        ).all()
    )
    return [summary for item in roles if (summary := _role_summary(item)) is not None]


async def list_employees(
    db: AsyncSession,
    *,
    organization_id: UUID,
    membership_status: str | None,
    location_id: UUID | None,
    operational_role_id: UUID | None,
    query: str | None,
    cursor: str | None,
    limit: int,
) -> EmployeeListResponse:
    statement = _employee_statement().where(EmployeeProfile.organization_id == organization_id)
    if membership_status is not None:
        statement = statement.where(OrganizationMembership.status == membership_status)
    if location_id is not None:
        statement = statement.where(EmployeeProfile.location_id == location_id)
    if operational_role_id is not None:
        statement = statement.where(EmployeeProfile.operational_role_id == operational_role_id)
    if query is not None:
        normalized_query = query.strip()
        if not normalized_query:
            raise APIError(
                status_code=422,
                code="VALIDATION_ERROR",
                message="Перевірте правильність заповнення полів.",
            )
        escaped_query = (
            normalized_query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        )
        pattern = f"%{escaped_query}%"
        statement = statement.where(
            or_(
                User.email_normalized.ilike(pattern, escape="\\"),
                EmployeeProfile.first_name.ilike(pattern, escape="\\"),
                EmployeeProfile.last_name.ilike(pattern, escape="\\"),
            )
        )
    if cursor is not None:
        cursor_created_at, cursor_id = _decode_cursor(cursor)
        statement = statement.where(
            or_(
                EmployeeProfile.created_at < cursor_created_at,
                and_(
                    EmployeeProfile.created_at == cursor_created_at,
                    EmployeeProfile.id < cursor_id,
                ),
            )
        )
    statement = statement.order_by(
        EmployeeProfile.created_at.desc(),
        EmployeeProfile.id.desc(),
    ).limit(limit + 1)
    rows = list((await db.execute(statement)).tuples().all())
    has_next = len(rows) > limit
    page_rows = rows[:limit]
    next_cursor = None
    if has_next and page_rows:
        next_cursor = _encode_cursor(page_rows[-1][0].created_at, page_rows[-1][0].id)
    return EmployeeListResponse(
        items=[_employee_summary(row) for row in page_rows],
        next_cursor=next_cursor,
    )


async def get_employee_detail(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
) -> EmployeeDetail:
    row = (
        (
            await db.execute(
                _employee_statement().where(
                    EmployeeProfile.organization_id == organization_id,
                    EmployeeProfile.id == employee_id,
                )
            )
        )
        .tuples()
        .one_or_none()
    )
    if row is None:
        raise _resource_not_found()
    return _employee_detail(row)


async def get_own_employee_profiles(
    db: AsyncSession,
    *,
    user_id: UUID,
) -> OwnEmployeeProfilesResponse:
    rows = list(
        (
            await db.execute(
                _employee_statement()
                .join(Organization, Organization.id == EmployeeProfile.organization_id)
                .where(OrganizationMembership.user_id == user_id)
                .order_by(func.lower(Organization.name), Organization.id, EmployeeProfile.id)
                .add_columns(Organization)
            )
        ).tuples()
    )
    profiles = []
    for profile, membership, user, role, location, organization in rows:
        row: EmployeeRow = (profile, membership, user, role, location)
        profiles.append(
            OwnEmployeeProfile(
                id=profile.id,
                organization=OrganizationReference(id=organization.id, name=organization.name),
                membership_status=membership.status,
                first_name=profile.first_name,
                last_name=profile.last_name,
                operational_role=_role_summary(role),
                location=_location_summary(location),
                profile_complete=_profile_complete(row),
                updated_at=profile.updated_at,
            )
        )
    return OwnEmployeeProfilesResponse(profiles=profiles)


def _profile_not_editable() -> APIError:
    return APIError(
        status_code=409,
        code="EMPLOYEE_PROFILE_NOT_EDITABLE",
        message="Профіль працівника недоступний для редагування.",
    )


def _reference_inactive() -> APIError:
    return APIError(
        status_code=409,
        code="REFERENCE_INACTIVE",
        message="Обраний довідниковий запис неактивний.",
    )


async def _validated_role(
    db: AsyncSession,
    *,
    organization_id: UUID,
    role_id: UUID,
) -> OperationalRole:
    role = await db.scalar(
        select(OperationalRole)
        .where(
            OperationalRole.id == role_id,
            OperationalRole.organization_id == organization_id,
        )
        .with_for_update()
    )
    if role is None:
        raise _resource_not_found()
    if role.status != "active":
        raise _reference_inactive()
    return role


async def _validated_location(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
) -> Location:
    location = await db.scalar(
        select(Location)
        .where(
            Location.id == location_id,
            Location.organization_id == organization_id,
        )
        .with_for_update()
    )
    if location is None:
        raise _resource_not_found()
    if location.status != "active":
        raise _reference_inactive()
    return location


async def _update_pending_employee_profile(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    actor_user_id: UUID,
    payload: EmployeeUpdate,
    request_id: UUID,
) -> EmployeeDetail:
    locked = (
        (
            await db.execute(
                select(EmployeeProfile, OrganizationMembership)
                .join(
                    OrganizationMembership,
                    and_(
                        OrganizationMembership.id == EmployeeProfile.membership_id,
                        OrganizationMembership.organization_id == EmployeeProfile.organization_id,
                    ),
                )
                .where(
                    EmployeeProfile.id == employee_id,
                    EmployeeProfile.organization_id == organization_id,
                )
                .with_for_update()
            )
        )
        .tuples()
        .one_or_none()
    )
    if locked is None:
        raise _resource_not_found()
    profile, membership = locked
    if membership.status != "pending":
        raise _profile_not_editable()

    supplied = payload.model_fields_set
    old_values: dict[str, bool | str | None] = {}
    new_values: dict[str, bool | str | None] = {}
    if "first_name" in supplied:
        old_values["first_name_changed"] = profile.first_name != payload.first_name
        new_values["first_name_changed"] = profile.first_name != payload.first_name
        profile.first_name = payload.first_name
    if "last_name" in supplied:
        old_values["last_name_changed"] = profile.last_name != payload.last_name
        new_values["last_name_changed"] = profile.last_name != payload.last_name
        profile.last_name = payload.last_name
    if "operational_role_id" in supplied:
        old_values["operational_role_id"] = (
            str(profile.operational_role_id) if profile.operational_role_id is not None else None
        )
        if payload.operational_role_id is not None:
            await _validated_role(
                db,
                organization_id=organization_id,
                role_id=payload.operational_role_id,
            )
        profile.operational_role_id = payload.operational_role_id
        new_values["operational_role_id"] = (
            str(payload.operational_role_id) if payload.operational_role_id is not None else None
        )
    if "location_id" in supplied:
        old_values["location_id"] = (
            str(profile.location_id) if profile.location_id is not None else None
        )
        if payload.location_id is not None:
            await _validated_location(
                db,
                organization_id=organization_id,
                location_id=payload.location_id,
            )
        profile.location_id = payload.location_id
        new_values["location_id"] = (
            str(payload.location_id) if payload.location_id is not None else None
        )

    await db.flush()
    detail = await get_employee_detail(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
    )
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="employee_profile_updated",
            target_type="employee_profile",
            target_id=employee_id,
            old_values=old_values,
            new_values=new_values,
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return detail


async def update_pending_employee_profile(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    actor_user_id: UUID,
    payload: EmployeeUpdate,
    request_id: UUID,
) -> EmployeeDetail:
    try:
        return await _update_pending_employee_profile(
            db,
            organization_id=organization_id,
            employee_id=employee_id,
            actor_user_id=actor_user_id,
            payload=payload,
            request_id=request_id,
        )
    except Exception:
        await db.rollback()
        raise


def _employee_profile_incomplete() -> APIError:
    return APIError(
        status_code=409,
        code="EMPLOYEE_PROFILE_INCOMPLETE",
        message="Профіль працівника потребує заповнення перед активацією.",
    )


def _employee_activation_not_allowed() -> APIError:
    return APIError(
        status_code=409,
        code="EMPLOYEE_ACTIVATION_NOT_ALLOWED",
        message="Працівника не можна активувати з поточного стану.",
    )


async def _activation_replay_response(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
) -> EmployeeLifecycleActionResponse:
    membership = await db.scalar(
        select(OrganizationMembership)
        .join(
            EmployeeProfile,
            and_(
                EmployeeProfile.membership_id == OrganizationMembership.id,
                EmployeeProfile.organization_id == OrganizationMembership.organization_id,
            ),
        )
        .where(
            EmployeeProfile.id == employee_id,
            EmployeeProfile.organization_id == organization_id,
        )
    )
    if membership is None or membership.status != "active" or membership.activated_at is None:
        raise RuntimeError("Idempotent employee activation resource is unavailable")
    await db.commit()
    return EmployeeLifecycleActionResponse(
        employee_id=employee_id,
        organization_id=organization_id,
        membership_status="active",
        training_participation_status="active",
        activated_at=membership.activated_at,
    )


async def _activate_employee(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    actor_user_id: UUID,
    idempotency_key: str,
    now: datetime,
    request_id: UUID,
) -> EmployeeLifecycleActionResponse:
    fingerprint = request_fingerprint({"employee_id": str(employee_id)})
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="employee.activate",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay is not None:
        if replay.resource_type != "employee_profile" or replay.resource_id != employee_id:
            raise RuntimeError("Idempotent employee activation target is inconsistent")
        return await _activation_replay_response(
            db,
            organization_id=organization_id,
            employee_id=employee_id,
        )

    decision = await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="employee.activate",
        key=idempotency_key,
        fingerprint=fingerprint,
        resource_type="employee_profile",
        resource_id=employee_id,
        response_status=200,
        now=now,
    )
    if decision.replayed:
        return await _activation_replay_response(
            db,
            organization_id=organization_id,
            employee_id=employee_id,
        )

    locked = (
        (
            await db.execute(
                select(EmployeeProfile, OrganizationMembership)
                .join(
                    OrganizationMembership,
                    and_(
                        OrganizationMembership.id == EmployeeProfile.membership_id,
                        OrganizationMembership.organization_id == EmployeeProfile.organization_id,
                    ),
                )
                .where(
                    EmployeeProfile.id == employee_id,
                    EmployeeProfile.organization_id == organization_id,
                )
                .with_for_update()
            )
        )
        .tuples()
        .one_or_none()
    )
    if locked is None:
        raise _resource_not_found()
    profile, membership = locked
    if membership.status != "pending":
        raise _employee_activation_not_allowed()
    if not (
        profile.first_name
        and profile.first_name.strip()
        and profile.last_name
        and profile.last_name.strip()
        and profile.operational_role_id is not None
        and profile.location_id is not None
    ):
        raise _employee_profile_incomplete()

    await _validated_role(
        db,
        organization_id=organization_id,
        role_id=profile.operational_role_id,
    )
    await _validated_location(
        db,
        organization_id=organization_id,
        location_id=profile.location_id,
    )
    await evaluate_activation_applicability(
        db,
        organization_id=organization_id,
        employee_profile_id=employee_id,
    )

    membership.status = "active"
    membership.activated_at = now
    membership.disabled_at = None
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="employee_activated",
            target_type="employee_profile",
            target_id=employee_id,
            old_values={"membership_status": "pending"},
            new_values={"membership_status": "active"},
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return EmployeeLifecycleActionResponse(
        employee_id=employee_id,
        organization_id=organization_id,
        membership_status="active",
        training_participation_status="active",
        activated_at=now,
    )


async def activate_employee(
    db: AsyncSession,
    *,
    organization_id: UUID,
    employee_id: UUID,
    actor_user_id: UUID,
    idempotency_key: str,
    now: datetime,
    request_id: UUID,
) -> EmployeeLifecycleActionResponse:
    try:
        return await _activate_employee(
            db,
            organization_id=organization_id,
            employee_id=employee_id,
            actor_user_id=actor_user_id,
            idempotency_key=idempotency_key,
            now=now,
            request_id=request_id,
        )
    except Exception:
        await db.rollback()
        raise
