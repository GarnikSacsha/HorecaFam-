from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import AuthorizationContext, require_organization_admin
from app.api.dependencies.session import AuthenticatedSession, get_csrf_protected_session
from app.core.clock import Clock
from app.core.request_id import get_request_id
from app.db.dependencies import get_db
from app.schemas.menu import (
    MenuCategoryCreate,
    MenuCategoryMutationResponse,
    MenuCategoryPatch,
    MenuCategoryReorderRequest,
    MenuCategoryResponse,
    MenuFindingResolveRequest,
    MenuFindingResolveResponse,
    MenuImportConfirmRequest,
    MenuImportConfirmResponse,
    MenuImportCreate,
    MenuImportDetail,
    MenuItemCreate,
    MenuItemListResponse,
    MenuItemMutationResponse,
    MenuItemPatch,
    MenuItemResponse,
    MenuItemWrite,
    MenuPublishRequest,
    MenuPublishResponse,
    MenuReadinessResponse,
    MenuReorderRequest,
    MenuReorderResponse,
    MenuRevisionResponse,
    MenuSectionCreate,
    MenuSectionMutationResponse,
    MenuSectionPatch,
    MenuSectionResponse,
    MenuVersionCollection,
    MenuVersionCreate,
    MenuVersionDetail,
)
from app.services.menu_drafts import (
    UNSET,
    create_category,
    create_menu_draft_idempotent,
    create_section,
    delete_category,
    delete_section,
    reorder_categories,
    reorder_sections,
    update_category,
    update_section,
)
from app.services.menu_imports import (
    confirm_menu_import,
    create_menu_import,
    get_menu_import,
    resolve_menu_import_finding,
)
from app.services.menu_publication import get_menu_readiness, publish_menu_version
from app.services.menus import (
    create_menu_item,
    delete_menu_item,
    get_admin_menu_item,
    get_menu_version_detail,
    list_admin_menu_items,
    list_menu_versions,
    update_menu_item,
)

router = APIRouter(tags=["menus"])


@router.get(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}/readiness",
    response_model=MenuReadinessResponse,
)
async def menu_version_readiness_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuReadinessResponse:
    return await get_menu_readiness(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}/publish",
    response_model=MenuPublishResponse,
)
async def menu_version_publish_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    payload: MenuPublishRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuPublishResponse:
    clock = cast(Clock, request.app.state.clock)
    return await publish_menu_version(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/menu-imports",
    response_model=MenuImportDetail,
    status_code=status.HTTP_201_CREATED,
)
async def menu_import_create_route(
    organization_id: UUID,
    location_id: UUID,
    payload: MenuImportCreate,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuImportDetail:
    clock = cast(Clock, request.app.state.clock)
    return await create_menu_import(
        db,
        organization_id=organization_id,
        location_id=location_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        payload=payload,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
    )


@router.get(
    "/organizations/{organization_id}/locations/{location_id}/menu-imports/{import_id}",
    response_model=MenuImportDetail,
)
async def menu_import_detail_route(
    organization_id: UUID,
    location_id: UUID,
    import_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuImportDetail:
    return await get_menu_import(
        db,
        organization_id=organization_id,
        location_id=location_id,
        import_id=import_id,
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/menu-imports/"
    "{import_id}/findings/{finding_id}/resolve",
    response_model=MenuFindingResolveResponse,
)
async def menu_import_finding_resolve_route(
    organization_id: UUID,
    location_id: UUID,
    import_id: UUID,
    finding_id: UUID,
    payload: MenuFindingResolveRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuFindingResolveResponse:
    clock = cast(Clock, request.app.state.clock)
    return await resolve_menu_import_finding(
        db,
        organization_id=organization_id,
        location_id=location_id,
        import_id=import_id,
        finding_id=finding_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        payload=payload,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/menu-imports/{import_id}/confirm",
    response_model=MenuImportConfirmResponse,
)
async def menu_import_confirm_route(
    organization_id: UUID,
    location_id: UUID,
    import_id: UUID,
    payload: MenuImportConfirmRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuImportConfirmResponse:
    clock = cast(Clock, request.app.state.clock)
    return await confirm_menu_import(
        db,
        organization_id=organization_id,
        location_id=location_id,
        import_id=import_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        acknowledge_warnings=payload.acknowledge_warnings,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
    )


def _section_response(detail: MenuVersionDetail, section_id: UUID) -> MenuSectionResponse:
    for section in detail.sections:
        if section.id == section_id:
            return section
    raise RuntimeError("Mutated Menu Section is missing from the version detail")


def _category_response(detail: MenuVersionDetail, category_id: UUID) -> MenuCategoryResponse:
    for section in detail.sections:
        for category in section.categories:
            if category.id == category_id:
                return category
    raise RuntimeError("Mutated Menu Category is missing from the version detail")


@router.get(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions",
    response_model=MenuVersionCollection,
)
async def menu_versions_route(
    organization_id: UUID,
    location_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuVersionCollection:
    return await list_menu_versions(
        db,
        organization_id=organization_id,
        location_id=location_id,
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions",
    response_model=MenuVersionDetail,
    status_code=status.HTTP_201_CREATED,
)
async def menu_version_create_route(
    organization_id: UUID,
    location_id: UUID,
    payload: MenuVersionCreate,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuVersionDetail:
    clock = cast(Clock, request.app.state.clock)
    version = await create_menu_draft_idempotent(
        db,
        organization_id=organization_id,
        location_id=location_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        copy_from_version_id=payload.copy_from_version_id,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
    )
    return await get_menu_version_detail(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version.id,
    )


@router.get(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}",
    response_model=MenuVersionDetail,
)
async def menu_version_detail_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuVersionDetail:
    return await get_menu_version_detail(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}/sections",
    response_model=MenuSectionMutationResponse,
)
async def menu_section_create_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    payload: MenuSectionCreate,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuSectionMutationResponse:
    mutation = await create_section(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        name_uk=payload.name_uk,
        stable_code=payload.stable_code,
        position=payload.position,
    )
    detail = await get_menu_version_detail(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
    )
    return MenuSectionMutationResponse(
        section=_section_response(detail, mutation.entity.id),
        revision=mutation.revision,
    )


@router.patch(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}/sections/{section_id}",
    response_model=MenuSectionMutationResponse,
)
async def menu_section_update_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    section_id: UUID,
    payload: MenuSectionPatch,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuSectionMutationResponse:
    mutation = await update_section(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        section_id=section_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        name_uk=payload.name_uk,
        stable_code=payload.stable_code if "stable_code" in payload.model_fields_set else UNSET,
        position=payload.position,
    )
    detail = await get_menu_version_detail(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
    )
    return MenuSectionMutationResponse(
        section=_section_response(detail, mutation.entity.id),
        revision=mutation.revision,
    )


@router.delete(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}/sections/{section_id}",
    response_model=MenuRevisionResponse,
)
async def menu_section_delete_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    section_id: UUID,
    expected_revision: Annotated[int, Query(ge=0)],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuRevisionResponse:
    revision = await delete_section(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        section_id=section_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=expected_revision,
    )
    return MenuRevisionResponse(revision=revision)


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}/sections/reorder",
    response_model=MenuReorderResponse,
)
async def menu_sections_reorder_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    payload: MenuReorderRequest,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuReorderResponse:
    result = await reorder_sections(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        ordered_ids=payload.ordered_ids,
    )
    return MenuReorderResponse(
        ordered_ids=[entity.id for entity in result.entities],
        revision=result.revision,
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}/categories",
    response_model=MenuCategoryMutationResponse,
)
async def menu_category_create_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    payload: MenuCategoryCreate,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuCategoryMutationResponse:
    mutation = await create_category(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        section_id=payload.section_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        name_uk=payload.name_uk,
        stable_code=payload.stable_code,
        position=payload.position,
    )
    detail = await get_menu_version_detail(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
    )
    return MenuCategoryMutationResponse(
        category=_category_response(detail, mutation.entity.id),
        revision=mutation.revision,
    )


@router.patch(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}/categories/{category_id}",
    response_model=MenuCategoryMutationResponse,
)
async def menu_category_update_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    category_id: UUID,
    payload: MenuCategoryPatch,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuCategoryMutationResponse:
    mutation = await update_category(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        category_id=category_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        section_id=payload.section_id,
        name_uk=payload.name_uk,
        stable_code=payload.stable_code if "stable_code" in payload.model_fields_set else UNSET,
        position=payload.position,
    )
    detail = await get_menu_version_detail(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
    )
    return MenuCategoryMutationResponse(
        category=_category_response(detail, mutation.entity.id),
        revision=mutation.revision,
    )


@router.delete(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}/categories/{category_id}",
    response_model=MenuRevisionResponse,
)
async def menu_category_delete_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    category_id: UUID,
    expected_revision: Annotated[int, Query(ge=0)],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuRevisionResponse:
    revision = await delete_category(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        category_id=category_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=expected_revision,
    )
    return MenuRevisionResponse(revision=revision)


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}/categories/reorder",
    response_model=MenuReorderResponse,
)
async def menu_categories_reorder_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    payload: MenuCategoryReorderRequest,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuReorderResponse:
    result = await reorder_categories(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        section_id=payload.section_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        ordered_ids=payload.ordered_ids,
    )
    return MenuReorderResponse(
        ordered_ids=[entity.id for entity in result.entities],
        revision=result.revision,
    )


@router.get(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}/items",
    response_model=MenuItemListResponse,
)
async def menu_items_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    query: Annotated[str | None, Query(alias="q", min_length=1, max_length=200)] = None,
    section_id: UUID | None = None,
    category_id: UUID | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MenuItemListResponse:
    return await list_admin_menu_items(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        query=query,
        section_id=section_id,
        category_id=category_id,
        cursor=cursor,
        limit=limit,
    )


@router.get(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}/items/{item_id}",
    response_model=MenuItemResponse,
)
async def menu_item_detail_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    item_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuItemResponse:
    return await get_admin_menu_item(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        item_id=item_id,
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}/items",
    response_model=MenuItemMutationResponse,
)
async def menu_item_create_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    payload: MenuItemCreate,
    request: Request,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuItemMutationResponse:
    clock = cast(Clock, request.app.state.clock)
    item_payload = MenuItemWrite.model_validate(payload.model_dump(exclude={"expected_revision"}))
    result = await create_menu_item(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        payload=item_payload,
        now=clock(),
    )
    item = await get_admin_menu_item(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        item_id=result.item_version.menu_item_id,
    )
    return MenuItemMutationResponse(item=item, revision=result.revision)


@router.patch(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}/items/{item_id}",
    response_model=MenuItemMutationResponse,
)
async def menu_item_update_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    item_id: UUID,
    payload: MenuItemPatch,
    request: Request,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuItemMutationResponse:
    clock = cast(Clock, request.app.state.clock)
    result = await update_menu_item(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        item_id=item_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        payload=payload,
        now=clock(),
    )
    item = await get_admin_menu_item(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        item_id=result.item_version.menu_item_id,
    )
    return MenuItemMutationResponse(item=item, revision=result.revision)


@router.delete(
    "/organizations/{organization_id}/locations/{location_id}/menu-versions/{version_id}/items/{item_id}",
    response_model=MenuRevisionResponse,
)
async def menu_item_delete_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    item_id: UUID,
    expected_revision: Annotated[int, Query(ge=0)],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MenuRevisionResponse:
    result = await delete_menu_item(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        item_id=item_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=expected_revision,
    )
    return MenuRevisionResponse(revision=result.revision)
