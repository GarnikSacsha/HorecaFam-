from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    AuthorizationContext,
    require_organization_admin,
    require_platform_operator,
)
from app.api.dependencies.session import AuthenticatedSession, get_csrf_protected_session
from app.core.clock import Clock
from app.core.request_id import get_request_id
from app.db.dependencies import get_db
from app.schemas.operations import (
    AuditEventListResponse,
    JobStatus,
    JobType,
    OperatorJobDetail,
    OperatorJobListResponse,
    OperatorJobRetryRequest,
    OperatorJobRetryResponse,
)
from app.services.audit_queries import (
    AuditActorType,
    list_operator_audit_events,
    list_organization_audit_events,
)
from app.services.operator_jobs import (
    get_operator_job,
    list_operator_jobs,
    retry_failed_job,
)

router = APIRouter(tags=["operations"])


@router.get(
    "/organizations/{organization_id}/audit-events",
    response_model=AuditEventListResponse,
)
async def organization_audit_events_route(
    organization_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    action: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    actor_type: AuditActorType | None = None,
    target_type: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    created_from: Annotated[datetime | None, Query(alias="from")] = None,
    created_to: Annotated[datetime | None, Query(alias="to")] = None,
    cursor: Annotated[str | None, Query(min_length=1, max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AuditEventListResponse:
    return await list_organization_audit_events(
        db,
        organization_id=organization_id,
        action=action,
        actor_type=actor_type,
        target_type=target_type,
        created_from=created_from,
        created_to=created_to,
        cursor=cursor,
        limit=limit,
    )


@router.get("/operator/jobs", response_model=OperatorJobListResponse)
async def operator_jobs_route(
    _authorization: Annotated[AuthorizationContext, Depends(require_platform_operator)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: JobStatus | None = None,
    job_type: JobType | None = None,
    organization_id: UUID | None = None,
    cursor: Annotated[str | None, Query(min_length=1, max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> OperatorJobListResponse:
    return await list_operator_jobs(
        db,
        status=status,
        job_type=job_type,
        organization_id=organization_id,
        cursor=cursor,
        limit=limit,
    )


@router.get("/operator/jobs/{job_id}", response_model=OperatorJobDetail)
async def operator_job_detail_route(
    job_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_platform_operator)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OperatorJobDetail:
    return await get_operator_job(db, job_id=job_id)


@router.post(
    "/operator/jobs/{job_id}/retry",
    response_model=OperatorJobRetryResponse,
)
async def operator_job_retry_route(
    job_id: UUID,
    payload: OperatorJobRetryRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_platform_operator)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OperatorJobRetryResponse:
    clock = cast(Clock, request.app.state.clock)
    return await retry_failed_job(
        db,
        source_job_id=job_id,
        actor_user_id=authorization.user.id,
        reason=payload.reason,
        idempotency_key=idempotency_key.strip(),
        request_id=UUID(get_request_id()),
        now=clock(),
    )


@router.get("/operator/audit-events", response_model=AuditEventListResponse)
async def operator_audit_events_route(
    _authorization: Annotated[AuthorizationContext, Depends(require_platform_operator)],
    db: Annotated[AsyncSession, Depends(get_db)],
    action: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    actor_type: Literal["user", "system", "worker", "cron"] | None = None,
    target_type: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    created_from: Annotated[datetime | None, Query(alias="from")] = None,
    created_to: Annotated[datetime | None, Query(alias="to")] = None,
    cursor: Annotated[str | None, Query(min_length=1, max_length=500)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> AuditEventListResponse:
    return await list_operator_audit_events(
        db,
        action=action,
        actor_type=actor_type,
        target_type=target_type,
        created_from=created_from,
        created_to=created_to,
        cursor=cursor,
        limit=limit,
    )
