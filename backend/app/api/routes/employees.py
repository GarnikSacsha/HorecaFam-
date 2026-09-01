from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import AuthorizationContext, require_organization_admin
from app.api.dependencies.session import (
    AuthenticatedSession,
    get_csrf_protected_session,
    get_current_session,
)
from app.core.clock import Clock
from app.core.request_id import get_request_id
from app.db.dependencies import get_db
from app.schemas.employees import (
    EmployeeDetail,
    EmployeeDisableRequest,
    EmployeeLifecycleActionResponse,
    EmployeeLifecycleStateResponse,
    EmployeeListResponse,
    EmployeePauseRequest,
    EmployeeUpdate,
    LocationSummary,
    OperationalRoleSummary,
    OrganizationSummary,
    OwnEmployeeProfilesResponse,
)
from app.schemas.training import (
    TrainingAssignmentCreate,
    TrainingAssignmentListResponse,
    TrainingAssignmentReassign,
    TrainingAssignmentResponse,
    TrainingAssignmentRevoke,
)
from app.services.employees import (
    activate_employee,
    disable_employee,
    get_employee_detail,
    get_organization_summary,
    get_own_employee_profiles,
    list_employees,
    list_locations,
    list_operational_roles,
    pause_employee,
    reactivate_employee,
    resume_employee,
    update_pending_employee_profile,
)
from app.services.training_assignments import (
    create_training_assignment,
    list_training_assignments,
    reassign_training_assignment,
    revoke_training_assignment,
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


@router.post(
    "/organizations/{organization_id}/employees/{employee_id}/activate",
    response_model=EmployeeLifecycleActionResponse,
)
async def employee_activate_route(
    organization_id: UUID,
    employee_id: UUID,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmployeeLifecycleActionResponse:
    clock = cast(Clock, request.app.state.clock)
    return await activate_employee(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        actor_user_id=authorization.user.id,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
        request_id=UUID(get_request_id()),
    )


@router.post(
    "/organizations/{organization_id}/employees/{employee_id}/disable",
    response_model=EmployeeLifecycleStateResponse,
)
async def employee_disable_route(
    organization_id: UUID,
    employee_id: UUID,
    payload: EmployeeDisableRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmployeeLifecycleStateResponse:
    clock = cast(Clock, request.app.state.clock)
    return await disable_employee(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        actor_user_id=authorization.user.id,
        payload=payload,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
        request_id=UUID(get_request_id()),
    )


@router.post(
    "/organizations/{organization_id}/employees/{employee_id}/reactivate",
    response_model=EmployeeLifecycleStateResponse,
)
async def employee_reactivate_route(
    organization_id: UUID,
    employee_id: UUID,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmployeeLifecycleStateResponse:
    clock = cast(Clock, request.app.state.clock)
    return await reactivate_employee(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        actor_user_id=authorization.user.id,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
        request_id=UUID(get_request_id()),
    )


@router.post(
    "/organizations/{organization_id}/employees/{employee_id}/pause",
    response_model=EmployeeLifecycleStateResponse,
)
async def employee_pause_route(
    organization_id: UUID,
    employee_id: UUID,
    payload: EmployeePauseRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmployeeLifecycleStateResponse:
    clock = cast(Clock, request.app.state.clock)
    return await pause_employee(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        actor_user_id=authorization.user.id,
        payload=payload,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
        request_id=UUID(get_request_id()),
    )


@router.post(
    "/organizations/{organization_id}/employees/{employee_id}/resume",
    response_model=EmployeeLifecycleStateResponse,
)
async def employee_resume_route(
    organization_id: UUID,
    employee_id: UUID,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> EmployeeLifecycleStateResponse:
    clock = cast(Clock, request.app.state.clock)
    return await resume_employee(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        actor_user_id=authorization.user.id,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
        request_id=UUID(get_request_id()),
    )


@router.get(
    "/organizations/{organization_id}/employees/{employee_id}/training-assignments",
    response_model=TrainingAssignmentListResponse,
)
async def training_assignments_list_route(
    organization_id: UUID,
    employee_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingAssignmentListResponse:
    return await list_training_assignments(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
    )


@router.post(
    "/organizations/{organization_id}/employees/{employee_id}/training-assignments",
    response_model=TrainingAssignmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def training_assignment_create_route(
    organization_id: UUID,
    employee_id: UUID,
    payload: TrainingAssignmentCreate,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingAssignmentResponse:
    clock = cast(Clock, request.app.state.clock)
    return await create_training_assignment(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        actor_user_id=authorization.user.id,
        payload=payload,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
        request_id=UUID(get_request_id()),
    )


@router.post(
    "/organizations/{organization_id}/employees/{employee_id}"
    "/training-assignments/{assignment_id}/revoke",
    response_model=TrainingAssignmentResponse,
)
async def training_assignment_revoke_route(
    organization_id: UUID,
    employee_id: UUID,
    assignment_id: UUID,
    payload: TrainingAssignmentRevoke,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingAssignmentResponse:
    clock = cast(Clock, request.app.state.clock)
    return await revoke_training_assignment(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        assignment_id=assignment_id,
        actor_user_id=authorization.user.id,
        payload=payload,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
        request_id=UUID(get_request_id()),
    )


@router.post(
    "/organizations/{organization_id}/employees/{employee_id}"
    "/training-assignments/{assignment_id}/reassign",
    response_model=TrainingAssignmentResponse,
)
async def training_assignment_reassign_route(
    organization_id: UUID,
    employee_id: UUID,
    assignment_id: UUID,
    payload: TrainingAssignmentReassign,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingAssignmentResponse:
    clock = cast(Clock, request.app.state.clock)
    return await reassign_training_assignment(
        db,
        organization_id=organization_id,
        employee_id=employee_id,
        assignment_id=assignment_id,
        actor_user_id=authorization.user.id,
        payload=payload,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
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
