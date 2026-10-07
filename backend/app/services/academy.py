from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Select, delete, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import AuthorizationContext
from app.core.errors import APIError
from app.models import (
    AcademyArticle,
    AcademyArticleAudience,
    Asset,
    AuditEvent,
    EmployeeProfile,
    Location,
    OperationalRole,
)
from app.schemas.academy import (
    AcademyArticleResponse,
    AcademyCollection,
    AcademySeedRequest,
    AcademyWrite,
)
from app.services.academy_catalog import ARTICLES
from app.services.idempotency import request_fingerprint, reserve_idempotency


def not_found() -> APIError:
    return APIError(status_code=404, code="RESOURCE_NOT_FOUND", message="Ресурс не знайдено.")


@asynccontextmanager
async def transaction(db: AsyncSession) -> AsyncIterator[None]:
    try:
        yield
        await db.commit()
    except Exception:
        await db.rollback()
        raise


async def location_scope(db: AsyncSession, org: UUID, loc: UUID, *, lock: bool = False) -> None:
    statement = select(Location).where(Location.id == loc, Location.organization_id == org)
    if lock:
        statement = statement.with_for_update()
    if await db.scalar(statement) is None:
        raise not_found()


async def validate_write(db: AsyncSession, org: UUID, loc: UUID, payload: AcademyWrite) -> None:
    roles = set(
        await db.scalars(
            select(OperationalRole.id).where(
                OperationalRole.organization_id == org,
                OperationalRole.status == "active",
                OperationalRole.id.in_(payload.operational_role_ids),
            )
        )
    )
    if roles != set(payload.operational_role_ids):
        raise not_found()
    if payload.cover_asset_id is not None:
        # Блокування узгоджує прив’язування обкладинки з архівацією файлу.
        asset = await db.scalar(
            select(Asset)
            .where(
                Asset.id == payload.cover_asset_id,
                Asset.organization_id == org,
                Asset.location_id == loc,
                Asset.status == "ready",
            )
            .with_for_update()
        )
        if asset is None:
            raise not_found()


async def response(db: AsyncSession, article: AcademyArticle) -> AcademyArticleResponse:
    roles = list(
        await db.scalars(
            select(AcademyArticleAudience.operational_role_id)
            .where(
                AcademyArticleAudience.article_id == article.id,
            )
            .order_by(AcademyArticleAudience.operational_role_id)
        )
    )
    return AcademyArticleResponse(
        id=article.id,
        revision=article.revision,
        created_at=article.created_at,
        updated_at=article.updated_at,
        slug=article.slug,
        title_uk=article.title_uk,
        summary_uk=article.summary_uk,
        body_uk=article.body_uk,
        category=article.category,
        status=article.status,
        position=article.position,
        all_positions=article.all_positions,
        operational_role_ids=roles,
        cover_asset_id=article.cover_asset_id,
    )


async def write_article(
    db: AsyncSession,
    *,
    org: UUID,
    loc: UUID,
    actor: UUID,
    request_id: UUID,
    payload: AcademyWrite,
    now: datetime,
    article_id: UUID | None = None,
    expected_revision: int | None = None,
    key: str | None = None,
) -> AcademyArticleResponse:
    await location_scope(db, org, loc, lock=True)
    if article_id is None:
        if key is None:
            raise RuntimeError("Article creation requires idempotency")
        decision = await reserve_idempotency(
            db,
            organization_id=org,
            actor_user_id=actor,
            action="academy_create",
            key=key,
            fingerprint=request_fingerprint(
                {"location_id": str(loc), **payload.model_dump(mode="json")}
            ),
            resource_type="academy_article",
            resource_id=uuid4(),
            response_status=201,
            now=now,
        )
        article_id = decision.record.resource_id
        if decision.replayed:
            article = await db.get(AcademyArticle, article_id)
            if article is None or article.organization_id != org or article.location_id != loc:
                raise not_found()
            return await response(db, article)
        article = AcademyArticle(id=article_id, organization_id=org, location_id=loc)
        old_values = None
    else:
        existing = await db.scalar(
            select(AcademyArticle)
            .where(
                AcademyArticle.id == article_id,
                AcademyArticle.organization_id == org,
                AcademyArticle.location_id == loc,
            )
            .with_for_update()
        )
        if existing is None:
            raise not_found()
        article = existing
        if article.revision != expected_revision:
            raise APIError(
                status_code=409,
                code="REVISION_CONFLICT",
                message="Статтю вже змінено. Оновіть сторінку.",
            )
        old_values = {"revision": article.revision, "status": article.status}
    await validate_write(db, org, loc, payload)
    duplicate = await db.scalar(
        select(AcademyArticle.id).where(
            AcademyArticle.location_id == loc,
            AcademyArticle.slug == payload.slug,
            AcademyArticle.id != article_id,
        )
    )
    if duplicate is not None:
        raise APIError(
            status_code=409, code="ARTICLE_SLUG_EXISTS", message="Така адреса статті вже існує."
        )
    for field in (
        "slug",
        "title_uk",
        "summary_uk",
        "body_uk",
        "category",
        "status",
        "position",
        "all_positions",
        "cover_asset_id",
    ):
        setattr(article, field, getattr(payload, field))
    article.revision = (article.revision + 1) if old_values is not None else 0
    article.updated_at = now
    if old_values is None:
        article.created_at = now
    db.add(article)
    await db.flush()
    await db.execute(
        delete(AcademyArticleAudience).where(AcademyArticleAudience.article_id == article.id)
    )
    db.add_all(
        [
            AcademyArticleAudience(
                article_id=article.id,
                organization_id=org,
                location_id=loc,
                operational_role_id=role,
            )
            for role in payload.operational_role_ids
        ]
    )
    db.add(
        AuditEvent(
            organization_id=org,
            actor_user_id=actor,
            actor_type="user",
            action="academy_article_saved",
            target_type="academy_article",
            target_id=article.id,
            old_values=old_values,
            new_values={"revision": article.revision, "status": article.status},
            request_id=request_id,
            outcome="success",
        )
    )
    await db.flush()
    await db.refresh(article)
    return await response(db, article)


async def collection(
    db: AsyncSession, statement: Select[tuple[AcademyArticle]], offset: int, limit: int
) -> AcademyCollection:
    articles = list(
        await db.scalars(
            statement.order_by(AcademyArticle.position, AcademyArticle.id)
            .offset(offset)
            .limit(limit + 1)
        )
    )
    return AcademyCollection(
        items=[await response(db, article) for article in articles[:limit]],
        next_offset=offset + limit if len(articles) > limit else None,
    )


async def employee_statement(
    db: AsyncSession, auth: AuthorizationContext
) -> Select[tuple[AcademyArticle]]:
    profile = await db.scalar(
        select(EmployeeProfile).where(
            EmployeeProfile.id == auth.employee_profile_id,
            EmployeeProfile.organization_id == auth.organization_id,
            EmployeeProfile.location_id == auth.location_id,
        )
    )
    if profile is None:
        raise not_found()
    allowed = exists(
        select(AcademyArticleAudience.id).where(
            AcademyArticleAudience.article_id == AcademyArticle.id,
            AcademyArticleAudience.operational_role_id == profile.operational_role_id,
        )
    )
    return select(AcademyArticle).where(
        AcademyArticle.organization_id == auth.organization_id,
        AcademyArticle.location_id == auth.location_id,
        AcademyArticle.status == "published",
        or_(AcademyArticle.all_positions.is_(True), allowed),
    )


async def seed_articles(
    db: AsyncSession,
    *,
    org: UUID,
    loc: UUID,
    actor: UUID,
    request_id: UUID,
    payload: AcademySeedRequest,
    now: datetime,
) -> int:
    await location_scope(db, org, loc, lock=True)
    roles = {
        "waiter": payload.waiter_role_id,
        "runner": payload.runner_role_id,
        "bartender": payload.bartender_role_id,
    }
    active = set(
        await db.scalars(
            select(OperationalRole.id).where(
                OperationalRole.organization_id == org,
                OperationalRole.status == "active",
                OperationalRole.id.in_(roles.values()),
            )
        )
    )
    if active != set(roles.values()):
        raise not_found()
    existing = set(
        await db.scalars(select(AcademyArticle.slug).where(AcademyArticle.location_id == loc))
    )
    count = 0
    for position, source in enumerate(ARTICLES):
        if source.slug in existing:
            continue
        await write_article(
            db,
            org=org,
            loc=loc,
            actor=actor,
            request_id=request_id,
            now=now,
            key=f"academy-catalog-v1-{loc}-{source.slug}",
            payload=AcademyWrite(
                slug=source.slug,
                title_uk=source.title,
                summary_uk=source.summary,
                body_uk=source.body,
                category=source.category,
                position=position,
                all_positions=source.position is None,
                operational_role_ids=[roles[source.position]] if source.position else [],
            ),
        )
        count += 1
    return count
