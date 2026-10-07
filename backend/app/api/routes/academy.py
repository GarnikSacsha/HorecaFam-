from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    AuthorizationContext,
    require_current_active_employee,
    require_organization_admin,
)
from app.api.dependencies.session import AuthenticatedSession, get_csrf_protected_session
from app.api.routes.training import get_private_storage
from app.core.clock import Clock
from app.core.request_id import get_request_id
from app.db.dependencies import get_db
from app.models import AcademyArticle, Asset
from app.schemas.academy import (
    AcademyArticleResponse,
    AcademyCollection,
    AcademySeedRequest,
    AcademyUpdate,
    AcademyWrite,
)
from app.schemas.training import AssetAccessResponse
from app.services import academy
from app.services.private_storage import PrivateStorage
from app.services.training_assets import ACCESS_EXPIRES_SECONDS

router = APIRouter(tags=["academy"])
Db = Annotated[AsyncSession, Depends(get_db)]
Admin = Annotated[AuthorizationContext, Depends(require_organization_admin)]
Employee = Annotated[AuthorizationContext, Depends(require_current_active_employee)]
Csrf = Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)]
BASE = "/organizations/{organization_id}/locations/{location_id}/academy"


@router.get(BASE)
async def list_articles(
    organization_id: UUID,
    location_id: UUID,
    db: Db,
    _auth: Admin,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> AcademyCollection:
    await academy.location_scope(db, organization_id, location_id)
    return await academy.collection(
        db,
        select(AcademyArticle).where(
            AcademyArticle.organization_id == organization_id,
            AcademyArticle.location_id == location_id,
        ),
        offset,
        limit,
    )


@router.post(BASE, status_code=201)
async def create_article(
    organization_id: UUID,
    location_id: UUID,
    payload: AcademyWrite,
    request: Request,
    db: Db,
    auth: Admin,
    _csrf: Csrf,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*")
    ],
) -> AcademyArticleResponse:
    async with academy.transaction(db):
        result = await academy.write_article(
            db,
            org=organization_id,
            loc=location_id,
            actor=auth.user.id,
            request_id=UUID(get_request_id()),
            payload=payload,
            now=cast(Clock, request.app.state.clock)(),
            key=idempotency_key.strip(),
        )
    return result


@router.post(BASE + "/seed")
async def seed_articles(
    organization_id: UUID,
    location_id: UUID,
    payload: AcademySeedRequest,
    request: Request,
    db: Db,
    auth: Admin,
    _csrf: Csrf,
) -> dict[str, int]:
    async with academy.transaction(db):
        count = await academy.seed_articles(
            db,
            org=organization_id,
            loc=location_id,
            actor=auth.user.id,
            request_id=UUID(get_request_id()),
            payload=payload,
            now=cast(Clock, request.app.state.clock)(),
        )
    return {"created_count": count}


@router.patch(BASE + "/{article_id}")
async def update_article(
    organization_id: UUID,
    location_id: UUID,
    article_id: UUID,
    payload: AcademyUpdate,
    request: Request,
    db: Db,
    auth: Admin,
    _csrf: Csrf,
) -> AcademyArticleResponse:
    async with academy.transaction(db):
        result = await academy.write_article(
            db,
            org=organization_id,
            loc=location_id,
            actor=auth.user.id,
            request_id=UUID(get_request_id()),
            payload=payload,
            article_id=article_id,
            expected_revision=payload.expected_revision,
            now=cast(Clock, request.app.state.clock)(),
        )
    return result


@router.get("/me/academy")
async def employee_articles(
    db: Db,
    auth: Employee,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> AcademyCollection:
    return await academy.collection(db, await academy.employee_statement(db, auth), offset, limit)


@router.get("/me/academy/{slug}")
async def employee_article(slug: str, db: Db, auth: Employee) -> AcademyArticleResponse:
    article = await db.scalar(
        (await academy.employee_statement(db, auth)).where(AcademyArticle.slug == slug)
    )
    if article is None:
        raise academy.not_found()
    return await academy.response(db, article)


@router.get("/me/academy/{slug}/cover")
async def employee_cover(
    slug: str,
    db: Db,
    auth: Employee,
    storage: Annotated[PrivateStorage, Depends(get_private_storage)],
) -> AssetAccessResponse:
    article = await db.scalar(
        (await academy.employee_statement(db, auth)).where(AcademyArticle.slug == slug)
    )
    if article is None or article.cover_asset_id is None:
        raise academy.not_found()
    asset = await db.scalar(
        select(Asset).where(
            Asset.id == article.cover_asset_id,
            Asset.organization_id == auth.organization_id,
            Asset.location_id == auth.location_id,
            Asset.status == "ready",
        )
    )
    if asset is None:
        raise academy.not_found()
    url = await storage.create_download_url(
        object_key=asset.object_key, expires_seconds=ACCESS_EXPIRES_SECONDS
    )
    return AssetAccessResponse(url=url)
