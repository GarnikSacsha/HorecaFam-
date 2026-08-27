from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.session import AuthenticatedSession, get_current_session
from app.core.errors import APIError
from app.db.dependencies import get_db
from app.models import AdminAccess, EmployeeProfile, Location, OrganizationMembership, Session, User


@dataclass(frozen=True)
class AuthorizationContext:
    user: User
    session: Session
    organization_id: UUID | None = None
    employee_profile_id: UUID | None = None
    location_id: UUID | None = None


def _forbidden() -> APIError:
    return APIError(status_code=403, code="FORBIDDEN", message="Недостатньо прав доступу.")


def _resource_not_found() -> APIError:
    return APIError(
        status_code=404,
        code="RESOURCE_NOT_FOUND",
        message="Ресурс не знайдено.",
    )


def _require_mfa(current: AuthenticatedSession) -> None:
    if current.record.mfa_verified_at is None:
        raise APIError(
            status_code=403,
            code="MFA_REQUIRED",
            message="Для цієї дії потрібна MFA-перевірка.",
        )


async def require_active_employee(
    organization_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthorizationContext:
    membership_id = await db.scalar(
        select(OrganizationMembership.id)
        .join(
            EmployeeProfile,
            EmployeeProfile.membership_id == OrganizationMembership.id,
        )
        .where(
            OrganizationMembership.user_id == current.user.id,
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == "active",
        )
    )
    if membership_id is None:
        raise _forbidden()
    await db.commit()
    return AuthorizationContext(
        user=current.user,
        session=current.record,
        organization_id=organization_id,
    )


async def require_current_active_employee(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthorizationContext:
    rows = (
        (
            await db.execute(
                select(EmployeeProfile)
                .join(
                    OrganizationMembership,
                    EmployeeProfile.membership_id == OrganizationMembership.id,
                )
                .join(
                    Location,
                    (Location.id == EmployeeProfile.location_id)
                    & (Location.organization_id == EmployeeProfile.organization_id),
                )
                .where(
                    OrganizationMembership.user_id == current.user.id,
                    OrganizationMembership.status == "active",
                    Location.status == "active",
                )
            )
        )
        .scalars()
        .all()
    )
    if len(rows) != 1 or rows[0].location_id is None:
        raise _forbidden()
    profile = rows[0]
    await db.commit()
    return AuthorizationContext(
        user=current.user,
        session=current.record,
        organization_id=profile.organization_id,
        employee_profile_id=profile.id,
        location_id=profile.location_id,
    )


async def require_organization_admin(
    organization_id: UUID,
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthorizationContext:
    access_id = await db.scalar(
        select(AdminAccess.id).where(
            AdminAccess.user_id == current.user.id,
            AdminAccess.organization_id == organization_id,
            AdminAccess.scope == "organization_admin",
            AdminAccess.status == "active",
        )
    )
    if access_id is None:
        known_organization = await db.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.user_id == current.user.id,
                OrganizationMembership.organization_id == organization_id,
            )
        )
        if known_organization is None:
            raise _resource_not_found()
        raise _forbidden()
    _require_mfa(current)
    await db.commit()
    return AuthorizationContext(
        user=current.user,
        session=current.record,
        organization_id=organization_id,
    )


async def require_platform_operator(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthorizationContext:
    access_id = await db.scalar(
        select(AdminAccess.id).where(
            AdminAccess.user_id == current.user.id,
            AdminAccess.scope == "platform_operator",
            AdminAccess.status == "active",
        )
    )
    if access_id is None:
        raise _forbidden()
    _require_mfa(current)
    await db.commit()
    return AuthorizationContext(user=current.user, session=current.record)
