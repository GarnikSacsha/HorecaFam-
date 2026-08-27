import base64
import binascii
from datetime import datetime
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    EmployeeProfile,
    Location,
    OperationalRole,
    Organization,
    OrganizationMembership,
    User,
)
from app.schemas.employees import (
    EmployeeDetail,
    EmployeeListResponse,
    EmployeeSummary,
    LocationSummary,
    OperationalRoleSummary,
    OrganizationReference,
    OrganizationSummary,
    OwnEmployeeProfile,
    OwnEmployeeProfilesResponse,
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
