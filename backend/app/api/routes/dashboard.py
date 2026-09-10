from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import AuthorizationContext, require_organization_admin
from app.core.clock import Clock
from app.db.dependencies import get_db
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard import get_dashboard

router = APIRouter(tags=["dashboard"])


@router.get("/organizations/{organization_id}/dashboard", response_model=DashboardResponse)
async def dashboard_route(
    organization_id: UUID,
    request: Request,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    location_id: UUID | None = None,
) -> DashboardResponse:
    clock = cast(Clock, request.app.state.clock)
    return await get_dashboard(
        db, organization_id=organization_id, location_id=location_id, now=clock()
    )
