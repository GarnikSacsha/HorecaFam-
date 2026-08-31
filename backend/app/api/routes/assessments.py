from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
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
    InteractiveAnswerRequest,
    InteractiveAnswerResponse,
    InteractiveAttemptResponse,
    InteractiveAttemptStartResponse,
    InteractiveAttemptTakeoverResponse,
    InteractiveTrainingReadinessResponse,
    LessonInteractiveTrainingSummaryResponse,
    PracticeAnswerRequest,
    PracticeAnswerResponse,
    PracticeAttemptResponse,
    PracticeAttemptStartResponse,
    PracticeAttemptTakeoverResponse,
    PracticeFinishRequest,
    PracticeFinishResponse,
    PracticeHistoryResponse,
    PracticeReadinessResponse,
    PracticeSummaryResponse,
    QuestionCandidateApprovalResponse,
    QuestionCandidateApproveRequest,
    QuestionCandidateBatchApprovalResponse,
    QuestionCandidateBatchApproveRequest,
    QuestionCandidateCollection,
    QuestionCandidateGenerateRequest,
    QuestionCandidateGenerateResponse,
    QuestionCandidateRejectRequest,
    QuestionCandidateResponse,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.interactive_answers import submit_interactive_answer
from app.services.interactive_attempts import (
    get_interactive_attempt,
    start_or_resume_interactive_attempt,
    takeover_interactive_attempt,
)
from app.services.interactive_history import get_lesson_interactive_training_summary
from app.services.practice_answers import save_practice_answer
from app.services.practice_attempts import (
    get_practice_attempt,
    get_practice_summary,
    start_or_resume_practice_attempt,
    takeover_practice_attempt,
)
from app.services.practice_results import finish_practice_attempt, get_practice_history
from app.services.question_generation import generate_question_candidates
from app.services.question_review import (
    approve_question_candidate,
    approve_question_candidate_batch,
    ensure_practice_readiness,
    get_interactive_training_readiness,
    get_practice_readiness,
    get_question_candidate,
    list_question_candidates,
    reject_question_candidate,
)

router = APIRouter(tags=["assessments"])


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


@router.get("/me/training/practice", response_model=PracticeSummaryResponse)
async def get_practice_summary_route(
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PracticeSummaryResponse:
    organization_id, location_id, employee_profile_id = _employee_scope(authorization)
    return await get_practice_summary(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        session_id=authorization.session.id,
    )


@router.post("/me/training/practice/attempts", response_model=PracticeAttemptStartResponse)
async def start_practice_attempt_route(
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
    locale: Literal["uk", "en"] | None = None,
) -> PracticeAttemptStartResponse:
    organization_id, location_id, employee_profile_id = _employee_scope(authorization)
    presentation_locale = locale or ("en" if authorization.user.preferred_locale == "en" else "uk")
    return await start_or_resume_practice_attempt(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        actor_user_id=authorization.user.id,
        session_id=authorization.session.id,
        presentation_locale=presentation_locale,
        idempotency_key=idempotency_key.strip(),
        request_id=UUID(get_request_id()),
        now=cast(Clock, request.app.state.clock)(),
    )


@router.get("/me/training/practice/attempts", response_model=PracticeHistoryResponse)
async def get_practice_history_route(
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PracticeHistoryResponse:
    organization_id, location_id, employee_profile_id = _employee_scope(authorization)
    return await get_practice_history(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
    )


@router.get("/me/training/practice/attempts/{attempt_id}", response_model=PracticeAttemptResponse)
async def get_practice_attempt_route(
    attempt_id: UUID,
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PracticeAttemptResponse:
    organization_id, location_id, employee_profile_id = _employee_scope(authorization)
    return await get_practice_attempt(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        attempt_id=attempt_id,
        session_id=authorization.session.id,
    )


@router.post(
    "/me/training/practice/attempts/{attempt_id}/takeover",
    response_model=PracticeAttemptTakeoverResponse,
)
async def takeover_practice_attempt_route(
    attempt_id: UUID,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PracticeAttemptTakeoverResponse:
    organization_id, location_id, employee_profile_id = _employee_scope(authorization)
    return await takeover_practice_attempt(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        actor_user_id=authorization.user.id,
        session_id=authorization.session.id,
        attempt_id=attempt_id,
        idempotency_key=idempotency_key.strip(),
        request_id=UUID(get_request_id()),
        now=cast(Clock, request.app.state.clock)(),
    )


@router.post(
    "/me/training/practice/attempts/{attempt_id}/answer",
    response_model=PracticeAnswerResponse,
)
async def save_practice_answer_route(
    attempt_id: UUID,
    payload: PracticeAnswerRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PracticeAnswerResponse:
    organization_id, location_id, employee_profile_id = _employee_scope(authorization)
    return await save_practice_answer(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        actor_user_id=authorization.user.id,
        session_id=authorization.session.id,
        attempt_id=attempt_id,
        attempt_question_id=payload.attempt_question_id,
        answer_payload=payload.answer_payload,
        lease_generation=payload.lease_generation,
        idempotency_key=idempotency_key.strip(),
        request_id=UUID(get_request_id()),
        now=cast(Clock, request.app.state.clock)(),
    )


@router.post(
    "/me/training/practice/attempts/{attempt_id}/finish",
    response_model=PracticeFinishResponse,
)
async def finish_practice_attempt_route(
    attempt_id: UUID,
    payload: PracticeFinishRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PracticeFinishResponse:
    organization_id, location_id, employee_profile_id = _employee_scope(authorization)
    return await finish_practice_attempt(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        actor_user_id=authorization.user.id,
        session_id=authorization.session.id,
        attempt_id=attempt_id,
        lease_generation=payload.lease_generation,
        idempotency_key=idempotency_key.strip(),
        request_id=UUID(get_request_id()),
        now=cast(Clock, request.app.state.clock)(),
    )


@router.get(
    "/me/training/lessons/{lesson_id}/interactive-training",
    response_model=LessonInteractiveTrainingSummaryResponse,
)
async def get_lesson_interactive_training_summary_route(
    lesson_id: UUID,
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LessonInteractiveTrainingSummaryResponse:
    organization_id, location_id, employee_profile_id = _employee_scope(authorization)
    return await get_lesson_interactive_training_summary(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        lesson_id=lesson_id,
        session_id=authorization.session.id,
    )


@router.post(
    "/me/training/lessons/{lesson_id}/interactive-training/attempts",
    response_model=InteractiveAttemptStartResponse,
)
async def start_interactive_attempt_route(
    lesson_id: UUID,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
    locale: Literal["uk", "en"] | None = None,
) -> InteractiveAttemptStartResponse:
    organization_id, location_id, employee_profile_id = _employee_scope(authorization)
    presentation_locale = locale or ("en" if authorization.user.preferred_locale == "en" else "uk")
    return await start_or_resume_interactive_attempt(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        actor_user_id=authorization.user.id,
        session_id=authorization.session.id,
        lesson_id=lesson_id,
        presentation_locale=presentation_locale,
        idempotency_key=idempotency_key.strip(),
        request_id=UUID(get_request_id()),
        now=cast(Clock, request.app.state.clock)(),
    )


@router.get(
    "/me/training/interactive-training/attempts/{attempt_id}",
    response_model=InteractiveAttemptResponse,
)
async def get_interactive_attempt_route(
    attempt_id: UUID,
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InteractiveAttemptResponse:
    organization_id, location_id, employee_profile_id = _employee_scope(authorization)
    return await get_interactive_attempt(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        attempt_id=attempt_id,
        session_id=authorization.session.id,
    )


@router.post(
    "/me/training/interactive-training/attempts/{attempt_id}/takeover",
    response_model=InteractiveAttemptTakeoverResponse,
)
async def takeover_interactive_attempt_route(
    attempt_id: UUID,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InteractiveAttemptTakeoverResponse:
    organization_id, location_id, employee_profile_id = _employee_scope(authorization)
    return await takeover_interactive_attempt(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        actor_user_id=authorization.user.id,
        session_id=authorization.session.id,
        attempt_id=attempt_id,
        idempotency_key=idempotency_key.strip(),
        request_id=UUID(get_request_id()),
        now=cast(Clock, request.app.state.clock)(),
    )


@router.post(
    "/me/training/interactive-training/attempts/{attempt_id}/answer",
    response_model=InteractiveAnswerResponse,
)
async def submit_interactive_answer_route(
    attempt_id: UUID,
    payload: InteractiveAnswerRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_current_active_employee)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InteractiveAnswerResponse:
    organization_id, location_id, employee_profile_id = _employee_scope(authorization)
    return await submit_interactive_answer(
        db,
        organization_id=organization_id,
        location_id=location_id,
        employee_profile_id=employee_profile_id,
        actor_user_id=authorization.user.id,
        session_id=authorization.session.id,
        attempt_id=attempt_id,
        attempt_question_id=payload.attempt_question_id,
        answer_payload=payload.answer_payload,
        lease_generation=payload.lease_generation,
        idempotency_key=idempotency_key.strip(),
        request_id=UUID(get_request_id()),
        now=cast(Clock, request.app.state.clock)(),
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/question-candidates/generate",
    response_model=QuestionCandidateGenerateResponse,
)
async def generate_question_candidates_route(
    organization_id: UUID,
    location_id: UUID,
    payload: QuestionCandidateGenerateRequest,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=128, pattern=r".*\S.*"),
    ],
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuestionCandidateGenerateResponse:
    now = cast(Clock, request.app.state.clock)()
    fingerprint = request_fingerprint(
        {
            "menu_version_id": str(payload.menu_version_id),
            "training_version_id": str(payload.training_version_id),
        }
    )
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=authorization.user.id,
        action="question_candidates_generate",
        key=idempotency_key.strip(),
        fingerprint=fingerprint,
        now=now,
    )
    result = await generate_question_candidates(
        db,
        organization_id=organization_id,
        location_id=location_id,
        menu_version_id=payload.menu_version_id,
        training_version_id=payload.training_version_id,
    )
    await ensure_practice_readiness(
        db,
        organization_id=organization_id,
        location_id=location_id,
        training_version_id=payload.training_version_id,
        actor_user_id=authorization.user.id,
        now=now,
    )
    if replay is None:
        await reserve_idempotency(
            db,
            organization_id=organization_id,
            actor_user_id=authorization.user.id,
            action="question_candidates_generate",
            key=idempotency_key.strip(),
            fingerprint=fingerprint,
            resource_type="training_version",
            resource_id=payload.training_version_id,
            response_status=200,
            now=now,
        )
        db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=authorization.user.id,
                actor_type="user",
                action="question_candidates_generated",
                target_type="training_version",
                target_id=payload.training_version_id,
                old_values=None,
                new_values={
                    "created_count": result.created_count,
                    "stale_candidate_count": result.stale_candidate_count,
                    "stale_question_count": result.stale_question_count,
                },
                request_id=UUID(get_request_id()),
                outcome="success",
            )
        )
    await db.commit()
    return QuestionCandidateGenerateResponse(
        created_count=result.created_count,
        existing_count=result.existing_count,
        stale_candidate_count=result.stale_candidate_count,
        stale_question_count=result.stale_question_count,
        replayed=replay is not None,
    )


@router.get(
    "/organizations/{organization_id}/locations/{location_id}/question-candidates",
    response_model=QuestionCandidateCollection,
)
async def list_question_candidates_route(
    organization_id: UUID,
    location_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    candidate_status: Annotated[
        Literal["needs_review", "approved", "rejected", "stale"] | None,
        Query(alias="status"),
    ] = None,
) -> QuestionCandidateCollection:
    return await list_question_candidates(
        db,
        organization_id=organization_id,
        location_id=location_id,
        status=candidate_status,
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/question-candidates/batch-approve",
    response_model=QuestionCandidateBatchApprovalResponse,
)
async def batch_approve_question_candidates_route(
    organization_id: UUID,
    location_id: UUID,
    payload: QuestionCandidateBatchApproveRequest,
    request: Request,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuestionCandidateBatchApprovalResponse:
    return await approve_question_candidate_batch(
        db,
        organization_id=organization_id,
        location_id=location_id,
        items=payload.items,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        now=cast(Clock, request.app.state.clock)(),
    )


@router.get(
    "/organizations/{organization_id}/locations/{location_id}/question-candidates/{candidate_id}",
    response_model=QuestionCandidateResponse,
)
async def get_question_candidate_route(
    organization_id: UUID,
    location_id: UUID,
    candidate_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuestionCandidateResponse:
    return await get_question_candidate(
        db,
        organization_id=organization_id,
        location_id=location_id,
        candidate_id=candidate_id,
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/question-candidates/"
    "{candidate_id}/approve",
    response_model=QuestionCandidateApprovalResponse,
)
async def approve_question_candidate_route(
    organization_id: UUID,
    location_id: UUID,
    candidate_id: UUID,
    payload: QuestionCandidateApproveRequest,
    request: Request,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuestionCandidateApprovalResponse:
    return await approve_question_candidate(
        db,
        organization_id=organization_id,
        location_id=location_id,
        candidate_id=candidate_id,
        expected_revision=payload.expected_revision,
        edited_payload=payload.edited_payload,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        now=cast(Clock, request.app.state.clock)(),
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/question-candidates/"
    "{candidate_id}/reject",
    response_model=QuestionCandidateResponse,
)
async def reject_question_candidate_route(
    organization_id: UUID,
    location_id: UUID,
    candidate_id: UUID,
    payload: QuestionCandidateRejectRequest,
    request: Request,
    _csrf: Annotated[AuthenticatedSession, Depends(get_csrf_protected_session)],
    authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QuestionCandidateResponse:
    return await reject_question_candidate(
        db,
        organization_id=organization_id,
        location_id=location_id,
        candidate_id=candidate_id,
        expected_revision=payload.expected_revision,
        reason_code=payload.reason_code,
        actor_user_id=authorization.user.id,
        request_id=UUID(get_request_id()),
        now=cast(Clock, request.app.state.clock)(),
    )


@router.get(
    "/organizations/{organization_id}/locations/{location_id}/training-versions/"
    "{version_id}/interactive-training/readiness",
    response_model=InteractiveTrainingReadinessResponse,
)
async def interactive_training_readiness_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> InteractiveTrainingReadinessResponse:
    return await get_interactive_training_readiness(
        db,
        organization_id=organization_id,
        location_id=location_id,
        training_version_id=version_id,
    )


@router.get(
    "/organizations/{organization_id}/locations/{location_id}/training-versions/"
    "{version_id}/practice/readiness",
    response_model=PracticeReadinessResponse,
)
async def practice_readiness_route(
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    _authorization: Annotated[AuthorizationContext, Depends(require_organization_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PracticeReadinessResponse:
    return await get_practice_readiness(
        db,
        organization_id=organization_id,
        location_id=location_id,
        training_version_id=version_id,
    )
