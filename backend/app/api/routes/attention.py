from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    AuthorizationContext,
    require_current_active_employee,
    require_organization_admin,
)
from app.api.dependencies.session import AuthenticatedSession, get_csrf_protected_session
from app.core.clock import Clock
from app.db.dependencies import get_db
from app.models import AttentionCase, RetakeRequirement
from app.schemas.attention import (
    AttentionAcknowledgeRequest,
    AttentionCaseCollection,
    AttentionCaseResponse,
    AttentionResolveRequest,
    EmployeeRetakeRequirementCollection,
    RetakeRequirementCancelRequest,
    RetakeRequirementCollection,
    RetakeRequirementConfirmRequest,
    RetakeRequirementCreateRequest,
    RetakeRequirementResponse,
    RetakeRequirementUpdateRequest,
)
from app.services.admin_follow_up import (
    acknowledge_case,
    attention_response,
    cancel_requirement,
    confirm_requirement,
    create_proposed_requirement,
    get_attention_case,
    get_requirement,
    list_attention,
    list_requirements,
    requirement_response,
    resolve_case,
    update_proposed_due_at,
)
from app.services.employee_follow_up import list_employee_requirements
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)

router = APIRouter(tags=["attention"])

IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
]


def _now(request: Request) -> datetime:
    return cast(Clock, request.app.state.clock)()


def _employee_scope(authorization: AuthorizationContext) -> tuple[UUID, UUID, UUID]:
    if (
        authorization.organization_id is None
        or authorization.location_id is None
        or authorization.employee_profile_id is None
    ):
        raise RuntimeError("Active Employee authorization has no complete scope")
    return (
        authorization.organization_id,
        authorization.location_id,
        authorization.employee_profile_id,
    )


@router.get(
    "/me/training/retake-requirements",
    response_model=EmployeeRetakeRequirementCollection,
)
async def list_own_requirements_route(
    request: Request,
    authorization: Annotated[
        AuthorizationContext,
        Depends(require_current_active_employee),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> EmployeeRetakeRequirementCollection:
    organization_id, location_id, employee_profile_id = _employee_scope(authorization)
    return await list_employee_requirements(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        now=_now(request),
        cursor=cursor,
        limit=limit,
    )


async def _replay_resource_id(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    action: str,
    key: str,
    fingerprint: str,
    now: datetime,
) -> UUID | None:
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        key=key,
        fingerprint=fingerprint,
        now=now,
    )
    return replay.resource_id if replay is not None else None


async def _reserve(
    db: AsyncSession,
    *,
    organization_id: UUID,
    actor_user_id: UUID,
    action: str,
    key: str,
    fingerprint: str,
    resource_type: str,
    resource_id: UUID,
    response_status: int,
    now: datetime,
) -> None:
    await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        key=key,
        fingerprint=fingerprint,
        resource_type=resource_type,
        resource_id=resource_id,
        response_status=response_status,
        now=now,
    )


@router.get(
    "/organizations/{organization_id}/retake-requirements",
    response_model=RetakeRequirementCollection,
)
async def list_requirements_route(
    organization_id: UUID,
    request: Request,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    state_filter: Annotated[
        Literal["proposed", "active", "completed", "cancelled"] | None,
        Query(alias="state"),
    ] = None,
    timing_state: Literal["scheduled", "approaching", "overdue", "frozen"] | None = None,
    reason: Literal[
        "failed_exam",
        "critical_error",
        "management_follow_up",
        "material_content_change",
    ]
    | None = None,
    location_id: UUID | None = None,
    employee_query: Annotated[str | None, Query(alias="q", max_length=200)] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> RetakeRequirementCollection:
    return await list_requirements(
        db,
        organization_id=organization_id,
        now=_now(request),
        state=state_filter,
        timing_state=timing_state,
        reason=reason,
        location_id=location_id,
        employee_query=employee_query,
        cursor=cursor,
        limit=limit,
    )


@router.get(
    "/organizations/{organization_id}/retake-requirements/{requirement_id}",
    response_model=RetakeRequirementResponse,
)
async def get_requirement_route(
    organization_id: UUID,
    requirement_id: UUID,
    request: Request,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetakeRequirementResponse:
    requirement = await get_requirement(
        db,
        organization_id=organization_id,
        requirement_id=requirement_id,
    )
    return await requirement_response(requirement, now=_now(request))


@router.post(
    "/organizations/{organization_id}/employees/{employee_id}/retake-requirements",
    response_model=RetakeRequirementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_requirement_route(
    organization_id: UUID,
    employee_id: UUID,
    payload: RetakeRequirementCreateRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetakeRequirementResponse:
    now = _now(request)
    fingerprint = request_fingerprint(payload.model_dump(mode="json"))
    key = idempotency_key.strip()
    replay_id = await _replay_resource_id(
        db,
        organization_id=organization_id,
        actor_user_id=authorization.user.id,
        action="retake_requirement_create",
        key=key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay_id is not None:
        requirement = await get_requirement(
            db, organization_id=organization_id, requirement_id=replay_id
        )
        return await requirement_response(requirement, now=now)
    requirement = await create_proposed_requirement(
        db,
        organization_id=organization_id,
        employee_profile_id=employee_id,
        actor_user_id=authorization.user.id,
        reason=payload.reason,
        target_assessment_id=payload.target_assessment_id,
        source_attention_case_id=payload.source_attention_case_id,
        management_source_key=payload.management_source_key,
        target_policy=payload.target_policy,
        due_at=payload.due_at,
        now=now,
    )
    await _reserve(
        db,
        organization_id=organization_id,
        actor_user_id=authorization.user.id,
        action="retake_requirement_create",
        key=key,
        fingerprint=fingerprint,
        resource_type="retake_requirement",
        resource_id=requirement.id,
        response_status=201,
        now=now,
    )
    await db.commit()
    return await requirement_response(requirement, now=now)


async def _requirement_mutation(
    *,
    db: AsyncSession,
    organization_id: UUID,
    actor_user_id: UUID,
    requirement_id: UUID,
    action: str,
    key: str,
    fingerprint: str,
    now: datetime,
    operation: Callable[[], Awaitable[object]],
) -> RetakeRequirementResponse:
    replay_id = await _replay_resource_id(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        key=key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay_id is not None:
        requirement = await get_requirement(
            db, organization_id=organization_id, requirement_id=replay_id
        )
        return await requirement_response(requirement, now=now)
    requirement = cast(RetakeRequirement, await operation())
    await _reserve(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        key=key,
        fingerprint=fingerprint,
        resource_type="retake_requirement",
        resource_id=requirement.id,
        response_status=200,
        now=now,
    )
    await db.commit()
    return await requirement_response(requirement, now=now)


@router.patch(
    "/organizations/{organization_id}/retake-requirements/{requirement_id}",
    response_model=RetakeRequirementResponse,
)
async def update_requirement_route(
    organization_id: UUID,
    requirement_id: UUID,
    payload: RetakeRequirementUpdateRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetakeRequirementResponse:
    now = _now(request)
    return await _requirement_mutation(
        db=db,
        organization_id=organization_id,
        actor_user_id=authorization.user.id,
        requirement_id=requirement_id,
        action="retake_requirement_update",
        key=idempotency_key.strip(),
        fingerprint=request_fingerprint(payload.model_dump(mode="json")),
        now=now,
        operation=lambda: update_proposed_due_at(
            db,
            organization_id=organization_id,
            requirement_id=requirement_id,
            actor_user_id=authorization.user.id,
            due_at=payload.due_at,
            expected_revision=payload.expected_revision,
            now=now,
        ),
    )


@router.post(
    "/organizations/{organization_id}/retake-requirements/{requirement_id}/confirm",
    response_model=RetakeRequirementResponse,
)
async def confirm_requirement_route(
    organization_id: UUID,
    requirement_id: UUID,
    payload: RetakeRequirementConfirmRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetakeRequirementResponse:
    now = _now(request)
    return await _requirement_mutation(
        db=db,
        organization_id=organization_id,
        actor_user_id=authorization.user.id,
        requirement_id=requirement_id,
        action="retake_requirement_confirm",
        key=idempotency_key.strip(),
        fingerprint=request_fingerprint(payload.model_dump(mode="json")),
        now=now,
        operation=lambda: confirm_requirement(
            db,
            organization_id=organization_id,
            requirement_id=requirement_id,
            actor_user_id=authorization.user.id,
            expected_revision=payload.expected_revision,
            now=now,
        ),
    )


@router.post(
    "/organizations/{organization_id}/retake-requirements/{requirement_id}/cancel",
    response_model=RetakeRequirementResponse,
)
async def cancel_requirement_route(
    organization_id: UUID,
    requirement_id: UUID,
    payload: RetakeRequirementCancelRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RetakeRequirementResponse:
    now = _now(request)
    return await _requirement_mutation(
        db=db,
        organization_id=organization_id,
        actor_user_id=authorization.user.id,
        requirement_id=requirement_id,
        action="retake_requirement_cancel",
        key=idempotency_key.strip(),
        fingerprint=request_fingerprint(payload.model_dump(mode="json")),
        now=now,
        operation=lambda: cancel_requirement(
            db,
            organization_id=organization_id,
            requirement_id=requirement_id,
            actor_user_id=authorization.user.id,
            expected_revision=payload.expected_revision,
            comment=payload.comment,
            now=now,
        ),
    )


@router.get(
    "/organizations/{organization_id}/attention",
    response_model=AttentionCaseCollection,
)
async def list_attention_route(
    organization_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    state_filter: Annotated[
        Literal["open", "acknowledged", "resolved"] | None,
        Query(alias="state"),
    ] = None,
    case_type: Annotated[
        Literal["critical_allergen", "retake_overdue"] | None,
        Query(alias="type"),
    ] = None,
    severity: Literal["critical", "overdue"] | None = None,
    location_id: UUID | None = None,
    employee_query: Annotated[str | None, Query(alias="q", max_length=200)] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> AttentionCaseCollection:
    return await list_attention(
        db,
        organization_id=organization_id,
        employee_profile_id=None,
        state=state_filter,
        case_type=case_type,
        severity=severity,
        location_id=location_id,
        employee_query=employee_query,
        cursor=cursor,
        limit=limit,
    )


@router.get(
    "/organizations/{organization_id}/employees/{employee_id}/attention",
    response_model=AttentionCaseCollection,
)
async def list_employee_attention_route(
    organization_id: UUID,
    employee_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> AttentionCaseCollection:
    return await list_attention(
        db,
        organization_id=organization_id,
        employee_profile_id=employee_id,
        state=None,
        case_type=None,
        severity=None,
        location_id=None,
        employee_query=None,
        cursor=cursor,
        limit=limit,
    )


@router.get(
    "/organizations/{organization_id}/attention/{attention_id}",
    response_model=AttentionCaseResponse,
)
async def get_attention_route(
    organization_id: UUID,
    attention_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AttentionCaseResponse:
    case = await get_attention_case(
        db,
        organization_id=organization_id,
        attention_id=attention_id,
    )
    return await attention_response(db, case)


async def _attention_mutation(
    *,
    db: AsyncSession,
    organization_id: UUID,
    actor_user_id: UUID,
    attention_id: UUID,
    action: str,
    key: str,
    fingerprint: str,
    now: datetime,
    operation: Callable[[], Awaitable[object]],
) -> AttentionCaseResponse:
    replay_id = await _replay_resource_id(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        key=key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay_id is not None:
        case = await get_attention_case(db, organization_id=organization_id, attention_id=replay_id)
        return await attention_response(db, case)
    case = cast(AttentionCase, await operation())
    await _reserve(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action=action,
        key=key,
        fingerprint=fingerprint,
        resource_type="attention_case",
        resource_id=case.id,
        response_status=200,
        now=now,
    )
    await db.commit()
    await db.refresh(case)
    return await attention_response(db, case)


@router.post(
    "/organizations/{organization_id}/attention/{attention_id}/acknowledge",
    response_model=AttentionCaseResponse,
)
async def acknowledge_attention_route(
    organization_id: UUID,
    attention_id: UUID,
    payload: AttentionAcknowledgeRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AttentionCaseResponse:
    now = _now(request)
    return await _attention_mutation(
        db=db,
        organization_id=organization_id,
        actor_user_id=authorization.user.id,
        attention_id=attention_id,
        action="attention_acknowledge",
        key=idempotency_key.strip(),
        fingerprint=request_fingerprint(payload.model_dump(mode="json")),
        now=now,
        operation=lambda: acknowledge_case(
            db,
            organization_id=organization_id,
            attention_id=attention_id,
            actor_user_id=authorization.user.id,
            expected_revision=payload.expected_revision,
            now=now,
        ),
    )


@router.post(
    "/organizations/{organization_id}/attention/{attention_id}/resolve",
    response_model=AttentionCaseResponse,
)
async def resolve_attention_route(
    organization_id: UUID,
    attention_id: UUID,
    payload: AttentionResolveRequest,
    request: Request,
    idempotency_key: IdempotencyKey,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AttentionCaseResponse:
    now = _now(request)
    return await _attention_mutation(
        db=db,
        organization_id=organization_id,
        actor_user_id=authorization.user.id,
        attention_id=attention_id,
        action="attention_resolve",
        key=idempotency_key.strip(),
        fingerprint=request_fingerprint(payload.model_dump(mode="json")),
        now=now,
        operation=lambda: resolve_case(
            db,
            organization_id=organization_id,
            attention_id=attention_id,
            actor_user_id=authorization.user.id,
            expected_revision=payload.expected_revision,
            resolution_type=payload.resolution_type,
            comment=payload.comment,
            evidence_attempt_id=payload.evidence_attempt_id,
            now=now,
        ),
    )
