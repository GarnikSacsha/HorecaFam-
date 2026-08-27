from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import AuthorizationContext, require_organization_admin
from app.api.dependencies.session import AuthenticatedSession, get_csrf_protected_session
from app.core.clock import Clock
from app.core.config import Settings
from app.core.cookies import set_session_cookie
from app.core.request_id import get_request_id
from app.db.dependencies import get_db
from app.schemas.invitations import (
    InvitationAcceptanceRequest,
    InvitationAcceptanceResponse,
    InvitationCreateRequest,
    InvitationResponse,
    InvitationValidateRequest,
    InvitationValidationResponse,
    PendingMembershipResponse,
)
from app.security.passwords import PasswordManager
from app.services.invitation_acceptance import accept_invitation
from app.services.invitations import (
    create_invitation,
    invitation_response,
    resend_invitation,
    revoke_invitation,
    validate_invitation,
)
from app.services.sessions import build_session_response

router = APIRouter(tags=["invitations"])


@router.post(
    "/invitations/accept",
    response_model=InvitationAcceptanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def accept_invitation_route(
    payload: InvitationAcceptanceRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvitationAcceptanceResponse:
    settings = cast(Settings, request.app.state.settings)
    clock = cast(Clock, request.app.state.clock)
    passwords = cast(PasswordManager, request.app.state.password_manager)
    now = clock()
    outcome = await accept_invitation(
        db,
        raw_token=payload.token.get_secret_value(),
        acceptance_mode=payload.acceptance_mode,
        password=payload.password.get_secret_value(),
        settings=settings,
        passwords=passwords,
        now=now,
        request_id=UUID(get_request_id()),
        user_agent=request.headers.get("user-agent"),
    )
    hmac_key = settings.auth_throttle_hmac_key
    if hmac_key is None:
        raise RuntimeError("Auth security settings were not validated")
    session_response = await build_session_response(
        db,
        issued_session=outcome.session.record,
        user=outcome.user,
        raw_token=outcome.session.raw_token,
        hmac_key=hmac_key,
    )
    set_session_cookie(
        response,
        settings,
        outcome.session.raw_token,
        outcome.session.record.absolute_expires_at,
        now,
    )
    return InvitationAcceptanceResponse(
        **session_response.model_dump(),
        acceptance_mode=outcome.acceptance_mode,
        membership=PendingMembershipResponse(
            id=outcome.membership.id,
            organization_id=outcome.membership.organization_id,
            employee_profile_id=outcome.profile.id,
        ),
    )


@router.post(
    "/organizations/{organization_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation_route(
    organization_id: UUID,
    payload: InvitationCreateRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvitationResponse:
    settings = cast(Settings, request.app.state.settings)
    clock = cast(Clock, request.app.state.clock)
    now = clock()
    invitation = await create_invitation(
        db,
        organization_id=organization_id,
        actor_user_id=authorization.user.id,
        email=str(payload.email),
        idempotency_key=idempotency_key,
        settings=settings,
        now=now,
        request_id=UUID(get_request_id()),
    )
    return invitation_response(invitation, now=now)


@router.post(
    "/organizations/{organization_id}/invitations/{invitation_id}/resend",
    response_model=InvitationResponse,
)
async def resend_invitation_route(
    organization_id: UUID,
    invitation_id: UUID,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvitationResponse:
    settings = cast(Settings, request.app.state.settings)
    clock = cast(Clock, request.app.state.clock)
    now = clock()
    invitation = await resend_invitation(
        db,
        organization_id=organization_id,
        invitation_id=invitation_id,
        actor_user_id=authorization.user.id,
        idempotency_key=idempotency_key,
        settings=settings,
        now=now,
        request_id=UUID(get_request_id()),
    )
    return invitation_response(invitation, now=now)


@router.post(
    "/organizations/{organization_id}/invitations/{invitation_id}/revoke",
    response_model=InvitationResponse,
)
async def revoke_invitation_route(
    organization_id: UUID,
    invitation_id: UUID,
    request: Request,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvitationResponse:
    clock = cast(Clock, request.app.state.clock)
    now = clock()
    invitation = await revoke_invitation(
        db,
        organization_id=organization_id,
        invitation_id=invitation_id,
        actor_user_id=authorization.user.id,
        now=now,
        request_id=UUID(get_request_id()),
    )
    return invitation_response(invitation, now=now)


@router.post(
    "/invitations/validate",
    response_model=InvitationValidationResponse,
)
async def validate_invitation_route(
    payload: InvitationValidateRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InvitationValidationResponse:
    clock = cast(Clock, request.app.state.clock)
    return await validate_invitation(
        db,
        raw_token=payload.token.get_secret_value(),
        now=clock(),
    )
