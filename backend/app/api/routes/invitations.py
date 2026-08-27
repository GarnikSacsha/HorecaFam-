from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import AuthorizationContext, require_organization_admin
from app.api.dependencies.session import AuthenticatedSession, get_csrf_protected_session
from app.core.clock import Clock
from app.core.config import Settings
from app.core.request_id import get_request_id
from app.db.dependencies import get_db
from app.schemas.invitations import (
    InvitationCreateRequest,
    InvitationResponse,
    InvitationValidateRequest,
    InvitationValidationResponse,
)
from app.services.invitations import (
    create_invitation,
    invitation_response,
    validate_invitation,
)

router = APIRouter(tags=["invitations"])


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
