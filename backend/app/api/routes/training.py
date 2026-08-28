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
from app.core.config import Settings
from app.core.request_id import get_request_id
from app.db.dependencies import get_db
from app.schemas.training import (
    AssetAccessResponse,
    AssetUploadComplete,
    AssetUploadIntentCreate,
    AssetUploadIntentResponse,
    ContentBlockUpdate,
    ContentBlockWrite,
    EmployeeTrainingHomeResponse,
    EmployeeTrainingLessonDetail,
    EmployeeTrainingModuleDetail,
    LessonCompletionResponse,
    ReorderRequest,
    TrainingAssetResponse,
    TrainingAudienceResponse,
    TrainingAudienceUpdate,
    TrainingContentBlockMutationResponse,
    TrainingContentBlockResponse,
    TrainingLessonCreate,
    TrainingLessonMutationResponse,
    TrainingLessonPatch,
    TrainingLessonResponse,
    TrainingModuleMutationResponse,
    TrainingModulePatch,
    TrainingModuleResponse,
    TrainingPublishRequest,
    TrainingPublishResponse,
    TrainingReadinessResponse,
    TrainingReorderResponse,
    TrainingRevisionResponse,
    TrainingRolloutConfirmRequest,
    TrainingRolloutCreate,
    TrainingRolloutLessonRuleUpdate,
    TrainingRolloutPreviewRequest,
    TrainingRolloutResponse,
    TrainingVersionCollection,
    TrainingVersionCreate,
    TrainingVersionDetail,
)
from app.services.employee_training import (
    get_employee_training_asset_access,
    get_employee_training_lesson,
    get_employee_training_module,
    list_employee_training,
)
from app.services.private_storage import PrivateStorage, build_private_storage
from app.services.training_assets import (
    ACCESS_EXPIRES_SECONDS,
    archive_unlinked_asset,
    complete_asset_upload,
    get_admin_asset_access,
    prepare_asset_upload,
)
from app.services.training_audiences import update_training_audience
from app.services.training_completion import complete_employee_training_lesson
from app.services.training_content import (
    create_content_block,
    delete_content_block,
    reorder_content_blocks,
    update_content_block,
)
from app.services.training_drafts import (
    create_lesson,
    create_training_draft_idempotent,
    delete_lesson,
    reorder_lessons,
    update_lesson,
    update_module,
)
from app.services.training_publication import (
    get_training_readiness,
    publish_training_version,
)
from app.services.training_queries import (
    get_training_version_detail,
    list_training_versions,
    training_asset_response,
)
from app.services.training_rollouts import (
    confirm_training_rollout,
    create_training_rollout,
    get_training_rollout,
    preview_training_rollout,
    update_training_rollout_lesson_rule,
)

router = APIRouter(tags=["training"])


def get_private_storage(request: Request) -> PrivateStorage:
    configured = getattr(request.app.state, "private_storage", None)
    if configured is None:
        settings = cast(Settings, request.app.state.settings)
        configured = build_private_storage(settings)
        request.app.state.private_storage = configured
    return cast(PrivateStorage, configured)


def _employee_locale(
    authorization: AuthorizationContext,
    requested: Literal["uk", "en"] | None,
) -> Literal["uk", "en"]:
    if requested is not None:
        return requested
    return "en" if authorization.user.preferred_locale == "en" else "uk"


@router.get("/me/training", response_model=EmployeeTrainingHomeResponse)
async def employee_training_route(
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
    locale: Literal["uk", "en"] | None = None,
) -> EmployeeTrainingHomeResponse:
    if (
        authorization.organization_id is None
        or authorization.location_id is None
        or authorization.employee_profile_id is None
    ):
        raise RuntimeError("Active Employee authorization has no Organization or Location")
    response = await list_employee_training(
        db,
        organization_id=authorization.organization_id,
        location_id=authorization.location_id,
        employee_profile_id=authorization.employee_profile_id,
        requested_locale=_employee_locale(authorization, locale),
    )
    await db.commit()
    return response


@router.get(
    "/me/training/modules/{module_id}",
    response_model=EmployeeTrainingModuleDetail,
)
async def employee_training_module_route(
    module_id: UUID,
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
    locale: Literal["uk", "en"] | None = None,
) -> EmployeeTrainingModuleDetail:
    if (
        authorization.organization_id is None
        or authorization.location_id is None
        or authorization.employee_profile_id is None
    ):
        raise RuntimeError("Active Employee authorization has no Organization or Location")
    response = await get_employee_training_module(
        db,
        organization_id=authorization.organization_id,
        location_id=authorization.location_id,
        employee_profile_id=authorization.employee_profile_id,
        module_id=module_id,
        requested_locale=_employee_locale(authorization, locale),
    )
    await db.commit()
    return response


@router.get(
    "/me/training/lessons/{lesson_id}",
    response_model=EmployeeTrainingLessonDetail,
)
async def employee_training_lesson_route(
    lesson_id: UUID,
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
    locale: Literal["uk", "en"] | None = None,
) -> EmployeeTrainingLessonDetail:
    if (
        authorization.organization_id is None
        or authorization.location_id is None
        or authorization.employee_profile_id is None
    ):
        raise RuntimeError("Active Employee authorization has no Organization or Location")
    response = await get_employee_training_lesson(
        db,
        organization_id=authorization.organization_id,
        location_id=authorization.location_id,
        employee_profile_id=authorization.employee_profile_id,
        lesson_id=lesson_id,
        requested_locale=_employee_locale(authorization, locale),
    )
    await db.commit()
    return response


@router.post(
    "/me/training/lessons/{lesson_id}/complete",
    response_model=LessonCompletionResponse,
)
async def employee_training_lesson_complete_route(
    lesson_id: UUID,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LessonCompletionResponse:
    if (
        authorization.organization_id is None
        or authorization.location_id is None
        or authorization.employee_profile_id is None
    ):
        raise RuntimeError("Active Employee authorization has no Organization or Location")
    clock = cast(Clock, request.app.state.clock)
    return await complete_employee_training_lesson(
        db,
        organization_id=authorization.organization_id,
        location_id=authorization.location_id,
        employee_profile_id=authorization.employee_profile_id,
        actor_user_id=authorization.user.id,
        lesson_id=lesson_id,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
        request_id=UUID(get_request_id()),
    )


@router.get(
    "/me/training/assets/{asset_id}/access",
    response_model=AssetAccessResponse,
)
async def employee_training_asset_access_route(
    asset_id: UUID,
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[PrivateStorage, Depends(get_private_storage)],
) -> AssetAccessResponse:
    if (
        authorization.organization_id is None
        or authorization.location_id is None
        or authorization.employee_profile_id is None
    ):
        raise RuntimeError("Active Employee authorization has no Organization or Location")
    url = await get_employee_training_asset_access(
        db,
        storage=storage,
        organization_id=authorization.organization_id,
        location_id=authorization.location_id,
        employee_profile_id=authorization.employee_profile_id,
        asset_id=asset_id,
    )
    await db.commit()
    return AssetAccessResponse(url=url, expires_in=ACCESS_EXPIRES_SECONDS)


def _module(detail: TrainingVersionDetail, module_id: UUID) -> TrainingModuleResponse:
    for module in detail.modules:
        if module.id == module_id:
            return module
    raise RuntimeError("Mutated Training Module is missing from version detail")


def _lesson(detail: TrainingVersionDetail, lesson_id: UUID) -> TrainingLessonResponse:
    for module in detail.modules:
        for lesson in module.lessons:
            if lesson.id == lesson_id:
                return lesson
    raise RuntimeError("Mutated Lesson is missing from version detail")


def _content_block(
    detail: TrainingVersionDetail,
    block_id: UUID,
) -> TrainingContentBlockResponse:
    for module in detail.modules:
        for lesson in module.lessons:
            for block in lesson.content_blocks:
                if block.id == block_id:
                    return block
    raise RuntimeError("Mutated Content Block is missing from version detail")


@router.get(
    "/organizations/{organization_id}/locations/{location_id}/training-versions",
    response_model=TrainingVersionCollection,
)
async def training_versions_route(
    organization_id: UUID,
    location_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingVersionCollection:
    return await list_training_versions(
        db,
        organization_id=organization_id,
        location_id=location_id,
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/training-versions",
    response_model=TrainingVersionDetail,
    status_code=status.HTTP_201_CREATED,
)
async def training_version_create_route(
    organization_id: UUID,
    location_id: UUID,
    payload: TrainingVersionCreate,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingVersionDetail:
    clock = cast(Clock, request.app.state.clock)
    version = await create_training_draft_idempotent(
        db,
        organization_id=organization_id,
        location_id=location_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        base_version_id=payload.base_version_id,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
    )
    return await get_training_version_detail(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version.id,
    )


@router.get(
    "/organizations/{organization_id}/locations/{location_id}/training-versions/{version_id}",
    response_model=TrainingVersionDetail,
)
async def training_version_detail_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingVersionDetail:
    return await get_training_version_detail(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
    )


@router.put(
    "/organizations/{organization_id}/locations/{location_id}/training-versions/"
    "{version_id}/audiences",
    response_model=TrainingAudienceResponse,
)
async def training_version_audience_update_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    payload: TrainingAudienceUpdate,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingAudienceResponse:
    return await update_training_audience(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        operational_role_ids=payload.operational_role_ids,
    )


@router.get(
    "/organizations/{organization_id}/locations/{location_id}/training-versions/"
    "{version_id}/readiness",
    response_model=TrainingReadinessResponse,
)
async def training_version_readiness_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingReadinessResponse:
    return await get_training_readiness(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/training-versions/"
    "{version_id}/publish",
    response_model=TrainingPublishResponse,
)
async def training_version_publish_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    payload: TrainingPublishRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingPublishResponse:
    clock = cast(Clock, request.app.state.clock)
    return await publish_training_version(
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
    "/organizations/{organization_id}/locations/{location_id}/training-rollouts",
    response_model=TrainingRolloutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def training_rollout_create_route(
    organization_id: UUID,
    location_id: UUID,
    payload: TrainingRolloutCreate,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingRolloutResponse:
    clock = cast(Clock, request.app.state.clock)
    return await create_training_rollout(
        db,
        organization_id=organization_id,
        location_id=location_id,
        from_version_id=payload.from_version_id,
        to_version_id=payload.to_version_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        idempotency_key=idempotency_key.strip(),
        now=clock(),
    )


@router.get(
    "/organizations/{organization_id}/locations/{location_id}/training-rollouts/{rollout_id}",
    response_model=TrainingRolloutResponse,
)
async def training_rollout_detail_route(
    organization_id: UUID,
    location_id: UUID,
    rollout_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingRolloutResponse:
    return await get_training_rollout(
        db,
        organization_id=organization_id,
        location_id=location_id,
        rollout_id=rollout_id,
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/training-rollouts/"
    "{rollout_id}/preview",
    response_model=TrainingRolloutResponse,
)
async def training_rollout_preview_route(
    organization_id: UUID,
    location_id: UUID,
    rollout_id: UUID,
    payload: TrainingRolloutPreviewRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingRolloutResponse:
    clock = cast(Clock, request.app.state.clock)
    return await preview_training_rollout(
        db,
        organization_id=organization_id,
        location_id=location_id,
        rollout_id=rollout_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/training-rollouts/"
    "{rollout_id}/confirm",
    response_model=TrainingRolloutResponse,
)
async def training_rollout_confirm_route(
    organization_id: UUID,
    location_id: UUID,
    rollout_id: UUID,
    payload: TrainingRolloutConfirmRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingRolloutResponse:
    clock = cast(Clock, request.app.state.clock)
    return await confirm_training_rollout(
        db,
        organization_id=organization_id,
        location_id=location_id,
        rollout_id=rollout_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        idempotency_key=idempotency_key.strip(),
        now=clock(),
    )


@router.patch(
    "/organizations/{organization_id}/locations/{location_id}/training-rollouts/"
    "{rollout_id}/lesson-rules/{lesson_id}",
    response_model=TrainingRolloutResponse,
)
async def training_rollout_lesson_rule_update_route(
    organization_id: UUID,
    location_id: UUID,
    rollout_id: UUID,
    lesson_id: UUID,
    payload: TrainingRolloutLessonRuleUpdate,
    request: Request,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingRolloutResponse:
    clock = cast(Clock, request.app.state.clock)
    return await update_training_rollout_lesson_rule(
        db,
        organization_id=organization_id,
        location_id=location_id,
        rollout_id=rollout_id,
        lesson_id=lesson_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        rule_value=payload.rule,
        now=clock(),
    )


@router.patch(
    "/organizations/{organization_id}/locations/{location_id}/training-versions/"
    "{version_id}/modules/{module_id}",
    response_model=TrainingModuleMutationResponse,
)
async def training_module_update_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    module_id: UUID,
    payload: TrainingModulePatch,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingModuleMutationResponse:
    result = await update_module(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        module_id=module_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        title_uk=payload.title_uk,
        description_uk=payload.description_uk,
        required=payload.required,
    )
    detail = await get_training_version_detail(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
    )
    return TrainingModuleMutationResponse(
        module=_module(detail, result.entity.id),
        revision=result.revision,
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/training-versions/"
    "{version_id}/modules/{module_id}/lessons",
    response_model=TrainingLessonMutationResponse,
)
async def training_lesson_create_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    module_id: UUID,
    payload: TrainingLessonCreate,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingLessonMutationResponse:
    result = await create_lesson(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        module_id=module_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        title_uk=payload.title_uk,
        description_uk=payload.description_uk,
        required=payload.required,
        estimated_minutes=payload.estimated_minutes,
    )
    detail = await get_training_version_detail(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
    )
    return TrainingLessonMutationResponse(
        lesson=_lesson(detail, result.entity.lesson_id),
        revision=result.revision,
    )


@router.patch(
    "/organizations/{organization_id}/locations/{location_id}/training-versions/"
    "{version_id}/lessons/{lesson_id}",
    response_model=TrainingLessonMutationResponse,
)
async def training_lesson_update_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    lesson_id: UUID,
    payload: TrainingLessonPatch,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingLessonMutationResponse:
    result = await update_lesson(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        lesson_id=lesson_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        title_uk=payload.title_uk,
        description_uk=payload.description_uk,
        required=payload.required,
        estimated_minutes=payload.estimated_minutes,
    )
    detail = await get_training_version_detail(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
    )
    return TrainingLessonMutationResponse(
        lesson=_lesson(detail, result.entity.lesson_id),
        revision=result.revision,
    )


@router.delete(
    "/organizations/{organization_id}/locations/{location_id}/training-versions/"
    "{version_id}/lessons/{lesson_id}",
    response_model=TrainingRevisionResponse,
)
async def training_lesson_delete_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    lesson_id: UUID,
    expected_revision: Annotated[int, Query(ge=0)],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingRevisionResponse:
    revision = await delete_lesson(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        lesson_id=lesson_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=expected_revision,
    )
    return TrainingRevisionResponse(revision=revision)


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/training-versions/"
    "{version_id}/modules/{module_id}/lessons/reorder",
    response_model=TrainingReorderResponse,
)
async def training_lessons_reorder_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    module_id: UUID,
    payload: ReorderRequest,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingReorderResponse:
    result = await reorder_lessons(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        module_id=module_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        ordered_ids=payload.ordered_ids,
    )
    return TrainingReorderResponse(
        ordered_ids=[entity.lesson_id for entity in result.entities],
        revision=result.revision,
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/training-versions/"
    "{version_id}/lessons/{lesson_id}/content-blocks",
    response_model=TrainingContentBlockMutationResponse,
)
async def training_content_block_create_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    lesson_id: UUID,
    payload: ContentBlockWrite,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingContentBlockMutationResponse:
    result = await create_content_block(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        lesson_id=lesson_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        block_type=payload.type,
        payload=payload.payload,
        expected_revision=payload.expected_revision,
    )
    detail = await get_training_version_detail(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
    )
    return TrainingContentBlockMutationResponse(
        content_block=_content_block(detail, result.entity.id),
        revision=result.revision,
    )


@router.patch(
    "/organizations/{organization_id}/locations/{location_id}/training-versions/"
    "{version_id}/content-blocks/{block_id}",
    response_model=TrainingContentBlockMutationResponse,
)
async def training_content_block_update_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    block_id: UUID,
    payload: ContentBlockUpdate,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingContentBlockMutationResponse:
    result = await update_content_block(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        block_id=block_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        payload=payload.payload,
        expected_revision=payload.expected_revision,
    )
    detail = await get_training_version_detail(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
    )
    return TrainingContentBlockMutationResponse(
        content_block=_content_block(detail, result.entity.id),
        revision=result.revision,
    )


@router.delete(
    "/organizations/{organization_id}/locations/{location_id}/training-versions/"
    "{version_id}/content-blocks/{block_id}",
    response_model=TrainingRevisionResponse,
)
async def training_content_block_delete_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    block_id: UUID,
    expected_revision: Annotated[int, Query(ge=0)],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingRevisionResponse:
    revision = await delete_content_block(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        block_id=block_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=expected_revision,
    )
    return TrainingRevisionResponse(revision=revision)


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/training-versions/"
    "{version_id}/lessons/{lesson_id}/content-blocks/reorder",
    response_model=TrainingReorderResponse,
)
async def training_content_blocks_reorder_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    lesson_id: UUID,
    payload: ReorderRequest,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingReorderResponse:
    result = await reorder_content_blocks(
        db,
        organization_id=organization_id,
        location_id=location_id,
        version_id=version_id,
        lesson_id=lesson_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        expected_revision=payload.expected_revision,
        ordered_ids=payload.ordered_ids,
    )
    return TrainingReorderResponse(
        ordered_ids=[entity.id for entity in result.entities],
        revision=result.revision,
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/assets/upload-intents",
    response_model=AssetUploadIntentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def training_asset_upload_intent_route(
    organization_id: UUID,
    location_id: UUID,
    payload: AssetUploadIntentCreate,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[PrivateStorage, Depends(get_private_storage)],
) -> AssetUploadIntentResponse:
    clock = cast(Clock, request.app.state.clock)
    intent = await prepare_asset_upload(
        db,
        storage=storage,
        organization_id=organization_id,
        location_id=location_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        idempotency_key=idempotency_key.strip(),
        file_name=payload.file_name,
        mime_type=payload.mime_type,
        size_bytes=payload.size_bytes,
        sha256=payload.sha256,
        now=clock(),
    )
    return AssetUploadIntentResponse(
        asset_id=intent.asset.id,
        upload_url=intent.upload_url,
        upload_fields=intent.upload_fields,
        expires_at=intent.expires_at,
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/assets/{asset_id}/complete",
    response_model=TrainingAssetResponse,
)
async def training_asset_complete_route(
    organization_id: UUID,
    location_id: UUID,
    asset_id: UUID,
    payload: AssetUploadComplete,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[PrivateStorage, Depends(get_private_storage)],
) -> TrainingAssetResponse:
    clock = cast(Clock, request.app.state.clock)
    asset = await complete_asset_upload(
        db,
        storage=storage,
        organization_id=organization_id,
        location_id=location_id,
        asset_id=asset_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        idempotency_key=idempotency_key.strip(),
        sha256=payload.sha256,
        now=clock(),
    )
    return training_asset_response(asset)


@router.delete(
    "/organizations/{organization_id}/locations/{location_id}/assets/{asset_id}",
    response_model=TrainingAssetResponse,
)
async def training_asset_archive_route(
    organization_id: UUID,
    location_id: UUID,
    asset_id: UUID,
    request: Request,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TrainingAssetResponse:
    clock = cast(Clock, request.app.state.clock)
    asset = await archive_unlinked_asset(
        db,
        organization_id=organization_id,
        location_id=location_id,
        asset_id=asset_id,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        now=clock(),
    )
    return training_asset_response(asset)


@router.get(
    "/organizations/{organization_id}/locations/{location_id}/assets/{asset_id}/access",
    response_model=AssetAccessResponse,
)
async def training_asset_access_route(
    organization_id: UUID,
    location_id: UUID,
    asset_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[PrivateStorage, Depends(get_private_storage)],
) -> AssetAccessResponse:
    url = await get_admin_asset_access(
        db,
        storage=storage,
        organization_id=organization_id,
        location_id=location_id,
        asset_id=asset_id,
    )
    await db.commit()
    return AssetAccessResponse(url=url, expires_in=ACCESS_EXPIRES_SECONDS)
