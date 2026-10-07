from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import (
    AuthorizationContext,
    require_current_active_employee,
    require_organization_admin,
)
from app.api.dependencies.session import AuthenticatedSession, get_csrf_protected_session
from app.core.clock import Clock
from app.core.request_id import get_request_id
from app.db.dependencies import get_db
from app.models import AuditEvent
from app.schemas.assessment import (
    PracticeAnswerRequest,
    PracticeFinishRequest,
    QuestionCandidateGenerateResponse,
)
from app.schemas.course_assessment import CourseAttemptResponse
from app.services.course_assessments import (
    CourseActor,
    finish_course_attempt,
    get_course_attempt,
    save_course_answer,
    start_course_attempt,
    takeover_course_attempt,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.standard_questions import generate_training_standard_candidates

router = APIRouter(tags=["course-assessments"])
Employee = Annotated[AuthorizationContext, Depends(require_current_active_employee)]
Database = Annotated[AsyncSession, Depends(get_db)]
Csrf = Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
]


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/training-versions/{training_version_id}/standard-question-candidates/generate",
    response_model=QuestionCandidateGenerateResponse,
)
async def generate_standards_route(
    organization_id: UUID,
    location_id: UUID,
    training_version_id: UUID,
    request: Request,
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Database,
    _csrf: Csrf,
    idempotency_key: IdempotencyKey,
) -> QuestionCandidateGenerateResponse:
    now = cast(Clock, request.app.state.clock)()
    fingerprint = request_fingerprint(
        {"location_id": str(location_id), "training_version_id": str(training_version_id)}
    )
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=authorization.user.id,
        action="standard_candidates_generate",
        key=idempotency_key.strip(),
        fingerprint=fingerprint,
        now=now,
    )
    created, existing = await generate_training_standard_candidates(
        db,
        organization_id=organization_id,
        location_id=location_id,
        training_version_id=training_version_id,
    )
    if replay is None:
        await reserve_idempotency(
            db,
            organization_id=organization_id,
            actor_user_id=authorization.user.id,
            action="standard_candidates_generate",
            key=idempotency_key.strip(),
            fingerprint=fingerprint,
            resource_type="training_version",
            resource_id=training_version_id,
            response_status=200,
            now=now,
        )
        db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=authorization.user.id,
                actor_type="user",
                action="standard_candidates_generated",
                target_type="training_version",
                target_id=training_version_id,
                old_values=None,
                new_values={"created_count": created},
                request_id=UUID(get_request_id()),
                outcome="success",
            )
        )
    await db.commit()
    return QuestionCandidateGenerateResponse(
        created_count=created,
        existing_count=existing,
        stale_candidate_count=0,
        stale_question_count=0,
        replayed=replay is not None,
    )


def _actor(authorization: AuthorizationContext) -> CourseActor:
    if (
        authorization.organization_id is None
        or authorization.location_id is None
        or authorization.employee_profile_id is None
    ):
        raise RuntimeError("Active Employee authorization has no complete scope")
    return CourseActor(
        organization_id=authorization.organization_id,
        location_id=authorization.location_id,
        employee_profile_id=authorization.employee_profile_id,
        user_id=authorization.user.id,
        session_id=authorization.session.id,
    )


@router.post(
    "/me/training/modules/{module_version_id}/course/attempts", response_model=CourseAttemptResponse
)
async def start_course_route(
    module_version_id: UUID,
    request: Request,
    authorization: Employee,
    db: Database,
    _csrf: Csrf,
    idempotency_key: IdempotencyKey,
    locale: Literal["uk", "en"] | None = None,
) -> CourseAttemptResponse:
    return await start_course_attempt(
        db,
        _actor(authorization),
        module_version_id,
        locale=locale or ("en" if authorization.user.preferred_locale == "en" else "uk"),
        idempotency_key=idempotency_key.strip(),
        request_id=UUID(get_request_id()),
        now=cast(Clock, request.app.state.clock)(),
    )


@router.get("/me/training/course/attempts/{attempt_id}", response_model=CourseAttemptResponse)
async def get_course_route(
    attempt_id: UUID,
    authorization: Employee,
    db: Database,
) -> CourseAttemptResponse:
    return await get_course_attempt(db, _actor(authorization), attempt_id)


@router.post(
    "/me/training/course/attempts/{attempt_id}/answer", response_model=CourseAttemptResponse
)
async def answer_course_route(
    attempt_id: UUID,
    payload: PracticeAnswerRequest,
    request: Request,
    authorization: Employee,
    db: Database,
    _csrf: Csrf,
    idempotency_key: IdempotencyKey,
) -> CourseAttemptResponse:
    return await save_course_answer(
        db,
        _actor(authorization),
        attempt_id,
        question_id=payload.attempt_question_id,
        answer_payload=payload.answer_payload,
        lease_generation=payload.lease_generation,
        idempotency_key=idempotency_key.strip(),
        request_id=UUID(get_request_id()),
        now=cast(Clock, request.app.state.clock)(),
    )


@router.post(
    "/me/training/course/attempts/{attempt_id}/finish", response_model=CourseAttemptResponse
)
async def finish_course_route(
    attempt_id: UUID,
    payload: PracticeFinishRequest,
    request: Request,
    authorization: Employee,
    db: Database,
    _csrf: Csrf,
    idempotency_key: IdempotencyKey,
) -> CourseAttemptResponse:
    return await finish_course_attempt(
        db,
        _actor(authorization),
        attempt_id,
        lease_generation=payload.lease_generation,
        idempotency_key=idempotency_key.strip(),
        request_id=UUID(get_request_id()),
        now=cast(Clock, request.app.state.clock)(),
    )


@router.post(
    "/me/training/course/attempts/{attempt_id}/takeover", response_model=CourseAttemptResponse
)
async def takeover_course_route(
    attempt_id: UUID,
    request: Request,
    authorization: Employee,
    db: Database,
    _csrf: Csrf,
    idempotency_key: IdempotencyKey,
) -> CourseAttemptResponse:
    return await takeover_course_attempt(
        db,
        _actor(authorization),
        attempt_id,
        idempotency_key=idempotency_key.strip(),
        request_id=UUID(get_request_id()),
        now=cast(Clock, request.app.state.clock)(),
    )
