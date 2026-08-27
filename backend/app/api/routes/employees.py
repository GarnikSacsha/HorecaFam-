from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import AuthorizationContext, require_organization_admin
from app.api.dependencies.session import (
    AuthenticatedSession,
    get_csrf_protected_session,
    get_current_session,
)
from app.core.request_id import get_request_id
from app.db.dependencies import get_db
from app.schemas.employees import (
    EmployeeDetail,
    EmployeeListResponse,
    EmployeeUpdate,
    LocationSummary,
    OperationalRoleSummary,
    OrganizationSummary,
    OwnEmployeeProfilesResponse,
)
from app.services.employees import (
    get_employee_detail,
    get_organization_summary,
    get_own_employee_profiles,
    list_employees,
    list_locations,
    list_operational_roles,
    update_pending_employee_profile,
)

router = APIRouter(tags=["employees"])


@router.get(
    "/organizations/{organization_id}",
    response_model=OrganizationSummary,
)
async def organization_detail_route(
    organization_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OrganizationSummary:
    return await get_organization_summary(db, organization_id=organization_id)


@router.get(
    "/organizations/{organization_id}/locations",
    response_model=list[LocationSummary],
)
async def locations_list_route(
    organization_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[LocationSummary]:
    return await list_locations(db, organization_id=organization_id)


@router.get(
    "/organizations/{organization_id}/operational-roles",
    response_model=list[OperationalRoleSummary],
)
async def operational_roles_list_route(
    organization_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[OperationalRoleSummary]:
    return await list_operational_roles(db, organization_id=organization_id)


@router.get(
    "/organizations/{organization_id}/employees",
    response_model=EmployeeListResponse,
)
async def employees_list_route(
    organization_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    membership_status: Annotated[
        Literal["pending", "active", "disabled"] | None,
        Query(alias="status"),
    ] = None,
    location_id: UUID | None = None,
    operational_role_id: UUID | None = None,
    query: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> EmployeeListResponse:
    return await list_employees(
        db,
        organization_id=organization_id,
        membership_status=membership_status,
        location_id=location_id,
        operational_role_id=operational_role_id,
        query=query,
        cursor=cursor,
        limit=limit,
    )


@router.get(
    "/organizations/{organization_id}/employees/{employee_id}",
    response_model=EmployeeDetail,
)
async def employee_detail_route(
    organization_id: UUID,
    employee_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmployeeDetail:
    return await get_employee_detail(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
    )


@router.patch(
    "/organizations/{organization_id}/employees/{employee_id}",
    response_model=EmployeeDetail,
)
async def employee_update_route(
    organization_id: UUID,
    employee_id: UUID,
    payload: EmployeeUpdate,
    request: Request,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmployeeDetail:
    return await update_pending_employee_profile(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        actor_user_id=authorization.user.id,
        payload=payload,
        request_id=UUID(get_request_id()),
    )


@router.get("/me/profile", response_model=OwnEmployeeProfilesResponse)
async def own_employee_profiles_route(
    current: Annotated[AuthenticatedSession, Depends(get_current_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OwnEmployeeProfilesResponse:
    response = await get_own_employee_profiles(db, user_id=current.user.id)
    await db.commit()
    return response
