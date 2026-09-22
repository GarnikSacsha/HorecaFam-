"""Новий банк створює окрему версію, не змінюючи знімки старих спроб."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Assessment,
    AssessmentVersion,
    AuditEvent,
    MenuItemVersion,
    MenuVersionCategory,
    QuestionCandidate,
    QuestionGenerationRule,
    QuestionSourceLink,
    QuestionVersion,
    TrainingVersion,
    TrainingVersionMenuDependency,
)
from app.schemas.assessment import FinalExamReadinessResponse, FinalExamVersionRequest
from app.services.final_exam_readiness import (
    SUPPORTED_FINAL_EXAM_FAMILIES,
    FinalExamPoolCandidate,
    ensure_final_exam_readiness,
    get_final_exam_readiness,
    quota_readiness,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.question_generation import candidate_source_fingerprint_is_current


async def create_final_exam_version(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    training_version_id: UUID,
    payload: FinalExamVersionRequest,
    actor_user_id: UUID,
    idempotency_key: str,
    request_id: UUID,
    now: datetime,
) -> FinalExamReadinessResponse:
    scope = dict(
        organization_id=organization_id,
        location_id=location_id,
        training_version_id=training_version_id,
    )
    training = await db.scalar(
        select(TrainingVersion)
        .where(
            TrainingVersion.id == training_version_id,
            TrainingVersion.organization_id == organization_id,
            TrainingVersion.location_id == location_id,
            TrainingVersion.status == "published",
        )
        .with_for_update()
    )
    if training is None:
        raise APIError(status_code=404, code="RESOURCE_NOT_FOUND", message="Ресурс не знайдено.")
    fingerprint = request_fingerprint(
        {
            "scope": {key: str(value) for key, value in scope.items()},
            "payload": payload.model_dump(mode="json"),
        }
    )
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="final_exam_version_create",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay is not None:
        return await get_final_exam_readiness(db, **scope, assessment_version_id=replay.resource_id)
    current = await db.scalar(
        select(AssessmentVersion)
        .join(
            Assessment,
            Assessment.id == AssessmentVersion.assessment_id,
        )
        .where(
            Assessment.training_id == training.training_id,
            Assessment.assessment_type == "menu_final_exam",
            AssessmentVersion.training_version_id == training_version_id,
            AssessmentVersion.status == "published",
        )
        .order_by(AssessmentVersion.version_number.desc())
        .limit(1)
        .with_for_update(of=Assessment)
    )
    if current is None or current.id != payload.expected_assessment_version_id:
        raise APIError(
            status_code=409, code="REVISION_CONFLICT", message="Поточна версія іспиту змінилася."
        )
    rows = (
        await db.execute(
            select(QuestionVersion, QuestionCandidate, MenuItemVersion, QuestionGenerationRule.code)
            .join(QuestionCandidate, QuestionCandidate.id == QuestionVersion.candidate_id)
            .join(
                QuestionGenerationRule,
                QuestionGenerationRule.id == QuestionCandidate.generation_rule_id,
            )
            .join(
                QuestionSourceLink,
                (QuestionSourceLink.question_version_id == QuestionVersion.id)
                & (QuestionSourceLink.source_role == "explanation_source"),
            )
            .join(MenuItemVersion, MenuItemVersion.id == QuestionSourceLink.menu_item_version_id)
            .where(
                QuestionVersion.id.in_(payload.policy.question_version_ids),
                QuestionVersion.organization_id == organization_id,
                QuestionVersion.location_id == location_id,
                QuestionVersion.status == "published",
                QuestionCandidate.training_version_id == training_version_id,
                QuestionCandidate.status == "approved",
                QuestionGenerationRule.code.in_(SUPPORTED_FINAL_EXAM_FAMILIES),
            )
        )
    ).all()
    categories = {value for bucket in payload.policy.buckets for value in bucket.category_ids}
    bound_categories = set(
        await db.scalars(
            select(MenuVersionCategory.id)
            .join(
                TrainingVersionMenuDependency,
                TrainingVersionMenuDependency.menu_version_id
                == MenuVersionCategory.menu_version_id,
            )
            .where(
                TrainingVersionMenuDependency.training_version_id == training_version_id,
                MenuVersionCategory.id.in_(categories),
            )
        )
    )
    if (
        categories != bound_categories
        or len(rows) != len(payload.policy.question_version_ids)
        or any(item.menu_version_category_id not in categories for _, _, item, _ in rows)
    ):
        raise APIError(
            status_code=422,
            code="QUESTION_PROVENANCE_INVALID",
            message="Банк містить недоступні питання або невідомі категорії.",
        )
    for _, candidate, _, _ in rows:
        if not await candidate_source_fingerprint_is_current(db, candidate):
            raise APIError(
                status_code=409,
                code="QUESTION_CANDIDATE_STALE",
                message="Джерело питання змінилося.",
            )
    candidates = [
        FinalExamPoolCandidate(
            question.id,
            str(item.menu_item_id),
            str(item.menu_version_category_id),
            family,
            question.mechanic,
            question.is_critical,
        )
        for question, _, item, family in rows
    ]
    if quota_readiness(candidates, payload.policy)[0] == "blocked":
        raise APIError(
            status_code=409,
            code="INSUFFICIENT_BUCKET_POOL",
            message="Недостатньо питань для одного з розділів.",
        )
    number = (
        await db.scalar(
            select(func.max(AssessmentVersion.version_number)).where(
                AssessmentVersion.assessment_id == current.assessment_id
            )
        )
        or 0
    ) + 1
    version = AssessmentVersion(
        organization_id=organization_id,
        location_id=location_id,
        assessment_id=current.assessment_id,
        training_version_id=training_version_id,
        version_number=number,
        status="published",
        question_count=20,
        threshold_percent=70,
        feedback_policy="after_final_submission",
        sampling_configuration=payload.policy.model_dump(mode="json"),
        published_by_user_id=actor_user_id,
        published_at=now,
    )
    db.add(version)
    await db.flush()
    await ensure_final_exam_readiness(db, **scope, actor_user_id=actor_user_id, now=now)
    await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="final_exam_version_create",
        key=idempotency_key,
        fingerprint=fingerprint,
        resource_type="assessment_version",
        resource_id=version.id,
        response_status=200,
        now=now,
    )
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="final_exam_version_created",
            target_type="assessment_version",
            target_id=version.id,
            old_values=None,
            new_values={"question_count": len(rows)},
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return await get_final_exam_readiness(db, **scope, assessment_version_id=version.id)
