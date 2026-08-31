import hashlib
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Assessment,
    AssessmentQuestionPool,
    AssessmentReadiness,
    AssessmentVersion,
    AuditEvent,
    LessonVersion,
    MenuItemVersion,
    Question,
    QuestionCandidate,
    QuestionGenerationRule,
    QuestionOption,
    QuestionOptionTranslation,
    QuestionSourceLink,
    QuestionVersion,
    QuestionVersionTranslation,
    TrainingVersion,
)
from app.schemas.assessment import (
    CandidateAnswerPayload,
    CandidateEditedPayload,
    CandidateExplanationPayload,
    CandidatePromptPayload,
    CandidateSourceResponse,
    InteractiveTrainingReadinessResponse,
    LessonAssessmentReadinessResponse,
    QuestionCandidateApprovalResponse,
    QuestionCandidateBatchApprovalResponse,
    QuestionCandidateBatchItem,
    QuestionCandidateCollection,
    QuestionCandidateResponse,
)
from app.services.question_generation import candidate_source_fingerprint_is_current


def _error(status_code: int, code: str, message: str) -> APIError:
    return APIError(status_code=status_code, code=code, message=message)


def _not_found() -> APIError:
    return _error(404, "RESOURCE_NOT_FOUND", "Ресурс не знайдено.")


def _revision_conflict() -> APIError:
    return _error(409, "REVISION_CONFLICT", "Кандидата вже змінено.")


def _candidate_stale() -> APIError:
    return _error(409, "QUESTION_CANDIDATE_STALE", "Джерело кандидата вже змінилося.")


def _provenance_invalid() -> APIError:
    return _error(422, "QUESTION_PROVENANCE_INVALID", "Джерела кандидата неповні.")


def derive_readiness_state(
    eligible_count: int,
    *,
    required_count: int = 5,
) -> tuple[str, bool, list[str], list[str]]:
    rotation_supported = eligible_count >= required_count * 2
    blocking_codes = ["INSUFFICIENT_QUESTION_POOL"] if eligible_count < required_count else []
    warning_codes = (
        ["REPEAT_ROTATION_LIMITED"]
        if eligible_count >= required_count and not rotation_supported
        else []
    )
    status = "blocked" if blocking_codes else "warning" if warning_codes else "ready"
    return status, rotation_supported, blocking_codes, warning_codes


async def ensure_practice_readiness(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    training_version_id: UUID,
    actor_user_id: UUID,
    now: datetime,
) -> AssessmentReadiness:
    training_version = await db.scalar(
        select(TrainingVersion).where(
            TrainingVersion.id == training_version_id,
            TrainingVersion.organization_id == organization_id,
            TrainingVersion.location_id == location_id,
            TrainingVersion.status == "published",
        )
    )
    if training_version is None:
        raise _not_found()
    assessment = await db.scalar(
        select(Assessment).where(
            Assessment.training_id == training_version.training_id,
            Assessment.assessment_type == "whole_menu_knowledge_check",
        )
    )
    if assessment is None:
        assessment = Assessment(
            organization_id=organization_id,
            location_id=location_id,
            training_id=training_version.training_id,
            lesson_id=None,
            assessment_type="whole_menu_knowledge_check",
        )
        db.add(assessment)
        await db.flush()
    version = await db.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.assessment_id == assessment.id,
            AssessmentVersion.training_version_id == training_version_id,
            AssessmentVersion.status == "published",
        )
    )
    if version is None:
        version_number = (
            await db.scalar(
                select(func.coalesce(func.max(AssessmentVersion.version_number), 0)).where(
                    AssessmentVersion.assessment_id == assessment.id
                )
            )
            or 0
        ) + 1
        version = AssessmentVersion(
            organization_id=organization_id,
            location_id=location_id,
            assessment_id=assessment.id,
            training_version_id=training_version_id,
            lesson_id=None,
            lesson_version_id=None,
            version_number=version_number,
            status="published",
            question_count=10,
            threshold_percent=40,
            feedback_policy="after_final_submission",
            sampling_configuration={
                "strategy": "distinct_menu_item_coverage_first",
                "rotation_minimum": 20,
            },
            published_by_user_id=actor_user_id,
            published_at=now,
        )
        db.add(version)
        await db.flush()

    eligible_rows = list(
        (
            await db.execute(
                select(QuestionVersion, MenuItemVersion.menu_item_id)
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
                .join(
                    MenuItemVersion,
                    MenuItemVersion.id == QuestionSourceLink.menu_item_version_id,
                )
                .where(
                    QuestionCandidate.training_version_id == training_version_id,
                    QuestionVersion.status == "published",
                    QuestionGenerationRule.code.in_(["menu.components", "menu.allergens"]),
                )
            )
        ).all()
    )
    current_pools = {
        row.question_version_id: row
        for row in await db.scalars(
            select(AssessmentQuestionPool).where(
                AssessmentQuestionPool.assessment_version_id == version.id
            )
        )
    }
    eligible_question_ids: set[UUID] = set()
    for question, menu_item_id in eligible_rows:
        eligible_question_ids.add(question.id)
        pool = current_pools.get(question.id)
        values = {
            "coverage_key": f"menu_item:{menu_item_id}",
            "mechanic": question.mechanic,
            "eligible": True,
            "exclusion_reason": None,
        }
        if pool is None:
            db.add(
                AssessmentQuestionPool(
                    assessment_version_id=version.id,
                    question_version_id=question.id,
                    weight=1,
                    **values,
                )
            )
        else:
            for key, value in values.items():
                setattr(pool, key, value)
    for question_id, pool in current_pools.items():
        if question_id not in eligible_question_ids:
            pool.eligible = False
            pool.exclusion_reason = "SOURCE_NOT_ELIGIBLE"
    await db.flush()

    pool_rows = list(
        (
            await db.execute(
                select(AssessmentQuestionPool, QuestionVersion)
                .join(
                    QuestionVersion,
                    QuestionVersion.id == AssessmentQuestionPool.question_version_id,
                )
                .where(
                    AssessmentQuestionPool.assessment_version_id == version.id,
                    AssessmentQuestionPool.eligible.is_(True),
                    QuestionVersion.status == "published",
                )
            )
        ).all()
    )
    coverage_keys = sorted({pool.coverage_key for pool, _question in pool_rows})
    mechanics = sorted({pool.mechanic for pool, _question in pool_rows})
    status, rotation_supported, blocking_codes, warning_codes = derive_readiness_state(
        len(coverage_keys), required_count=10
    )
    basis_payload = [
        {
            "id": str(question.id),
            "fingerprint": question.source_fingerprint,
            "coverage_key": pool.coverage_key,
            "mechanic": pool.mechanic,
        }
        for pool, question in sorted(pool_rows, key=lambda row: str(row[1].id))
    ]
    basis_fingerprint = hashlib.sha256(
        json.dumps(basis_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    readiness = await db.scalar(
        select(AssessmentReadiness).where(AssessmentReadiness.assessment_version_id == version.id)
    )
    values = {
        "status": status,
        "eligible_count": len(coverage_keys),
        "required_count": 10,
        "coverage_evidence": {
            "distinct_menu_item_count": len(coverage_keys),
            "coverage_keys": coverage_keys,
            "mechanics": mechanics,
        },
        "rotation_supported": rotation_supported,
        "basis_fingerprint": basis_fingerprint,
        "blocking_codes": blocking_codes,
        "warning_codes": warning_codes,
        "computed_at": now,
    }
    if readiness is None:
        readiness = AssessmentReadiness(assessment_version_id=version.id, **values)
        db.add(readiness)
    else:
        for key, value in values.items():
            setattr(readiness, key, value)
    await db.flush()
    return readiness


def _candidate_response(
    candidate: QuestionCandidate,
    sources: list[QuestionSourceLink],
) -> QuestionCandidateResponse:
    return QuestionCandidateResponse(
        id=candidate.id,
        training_version_id=candidate.training_version_id,
        lesson_version_id=candidate.lesson_version_id,
        mechanic=candidate.mechanic,
        prompt_payload=candidate.prompt_payload,
        answer_payload=candidate.answer_payload,
        explanation_payload=candidate.explanation_payload,
        source_fingerprint=candidate.source_fingerprint,
        status=candidate.status,
        revision=candidate.revision,
        reviewed_at=candidate.reviewed_at,
        rejection_reason_code=candidate.rejection_reason_code,
        sources=[
            CandidateSourceResponse(
                source_role=source.source_role,
                menu_item_version_id=source.menu_item_version_id,
                menu_item_version_component_id=source.menu_item_version_component_id,
                menu_item_version_allergen_id=source.menu_item_version_allergen_id,
            )
            for source in sources
        ],
    )


async def _sources(db: AsyncSession, candidate_id: UUID) -> list[QuestionSourceLink]:
    return list(
        await db.scalars(
            select(QuestionSourceLink)
            .where(QuestionSourceLink.question_candidate_id == candidate_id)
            .order_by(QuestionSourceLink.source_role, QuestionSourceLink.id)
        )
    )


async def _scoped_candidate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    candidate_id: UUID,
    lock: bool = False,
) -> QuestionCandidate:
    query = select(QuestionCandidate).where(
        QuestionCandidate.id == candidate_id,
        QuestionCandidate.organization_id == organization_id,
        QuestionCandidate.location_id == location_id,
    )
    if lock:
        query = query.with_for_update()
    candidate = await db.scalar(query)
    if candidate is None:
        raise _not_found()
    return candidate


async def list_question_candidates(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    status: str | None = None,
) -> QuestionCandidateCollection:
    query = select(QuestionCandidate).where(
        QuestionCandidate.organization_id == organization_id,
        QuestionCandidate.location_id == location_id,
    )
    if status is not None:
        query = query.where(QuestionCandidate.status == status)
    candidates = list(await db.scalars(query.order_by(QuestionCandidate.created_at)))
    return QuestionCandidateCollection(
        items=[
            _candidate_response(candidate, await _sources(db, candidate.id))
            for candidate in candidates
        ],
        total=len(candidates),
    )


async def get_question_candidate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    candidate_id: UUID,
) -> QuestionCandidateResponse:
    candidate = await _scoped_candidate(
        db,
        organization_id=organization_id,
        location_id=location_id,
        candidate_id=candidate_id,
    )
    return _candidate_response(candidate, await _sources(db, candidate.id))


def _validated_payloads(
    candidate: QuestionCandidate,
    edited: CandidateEditedPayload | None,
) -> tuple[CandidatePromptPayload, CandidateAnswerPayload, CandidateExplanationPayload]:
    current_prompt = CandidatePromptPayload.model_validate(candidate.prompt_payload)
    current_answer = CandidateAnswerPayload.model_validate(candidate.answer_payload)
    current_explanation = CandidateExplanationPayload.model_validate(candidate.explanation_payload)
    if edited is None:
        return current_prompt, current_answer, current_explanation
    if (
        edited.prompt_payload.options != current_prompt.options
        or edited.answer_payload != current_answer
    ):
        raise _provenance_invalid()
    return edited.prompt_payload, edited.answer_payload, edited.explanation_payload


async def _validate_reviewable(
    db: AsyncSession,
    candidate: QuestionCandidate,
    *,
    expected_revision: int,
    edited_payload: CandidateEditedPayload | None,
) -> tuple[
    CandidatePromptPayload,
    CandidateAnswerPayload,
    CandidateExplanationPayload,
    list[QuestionSourceLink],
]:
    if candidate.revision != expected_revision:
        raise _revision_conflict()
    if candidate.status == "stale":
        raise _candidate_stale()
    if candidate.status != "needs_review":
        raise _revision_conflict()
    if not await candidate_source_fingerprint_is_current(db, candidate):
        raise _candidate_stale()
    sources = await _sources(db, candidate.id)
    if (
        not any(source.source_role == "correct_fact" for source in sources)
        or not any(source.source_role == "distractor_basis" for source in sources)
        or any(
            source.organization_id != candidate.organization_id
            or source.location_id != candidate.location_id
            for source in sources
        )
    ):
        raise _provenance_invalid()
    return (*_validated_payloads(candidate, edited_payload), sources)


async def _assessment_version(
    db: AsyncSession,
    candidate: QuestionCandidate,
    *,
    actor_user_id: UUID,
    now: datetime,
) -> AssessmentVersion:
    lesson = await db.get(LessonVersion, candidate.lesson_version_id)
    training_version = await db.get(TrainingVersion, candidate.training_version_id)
    if lesson is None or training_version is None:
        raise _not_found()
    assessment = await db.scalar(
        select(Assessment).where(
            Assessment.lesson_id == lesson.lesson_id,
            Assessment.assessment_type == "interactive_training",
        )
    )
    if assessment is None:
        assessment = Assessment(
            organization_id=candidate.organization_id,
            location_id=candidate.location_id,
            training_id=training_version.training_id,
            lesson_id=lesson.lesson_id,
            assessment_type="interactive_training",
        )
        db.add(assessment)
        await db.flush()
    version = await db.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.assessment_id == assessment.id,
            AssessmentVersion.training_version_id == candidate.training_version_id,
            AssessmentVersion.lesson_version_id == candidate.lesson_version_id,
            AssessmentVersion.status == "published",
        )
    )
    if version is None:
        version_number = (
            await db.scalar(
                select(func.coalesce(func.max(AssessmentVersion.version_number), 0)).where(
                    AssessmentVersion.assessment_id == assessment.id
                )
            )
            or 0
        ) + 1
        version = AssessmentVersion(
            organization_id=candidate.organization_id,
            location_id=candidate.location_id,
            assessment_id=assessment.id,
            training_version_id=candidate.training_version_id,
            lesson_id=lesson.lesson_id,
            lesson_version_id=lesson.id,
            version_number=version_number,
            status="published",
            question_count=5,
            feedback_policy="immediate",
            sampling_configuration={"strategy": "coverage_first", "rotation_minimum": 10},
            published_by_user_id=actor_user_id,
            published_at=now,
        )
        db.add(version)
        await db.flush()
    return version


async def recompute_readiness(
    db: AsyncSession,
    assessment_version: AssessmentVersion,
    *,
    now: datetime,
) -> LessonAssessmentReadinessResponse:
    pool_rows = list(
        (
            await db.execute(
                select(AssessmentQuestionPool, QuestionVersion)
                .join(
                    QuestionVersion,
                    QuestionVersion.id == AssessmentQuestionPool.question_version_id,
                )
                .where(
                    AssessmentQuestionPool.assessment_version_id == assessment_version.id,
                    AssessmentQuestionPool.eligible.is_(True),
                    QuestionVersion.status == "published",
                )
            )
        ).all()
    )
    eligible_count = len(pool_rows)
    coverage_keys = sorted({pool.coverage_key for pool, _question in pool_rows})
    mechanics = sorted({pool.mechanic for pool, _question in pool_rows})
    status, rotation_supported, blocking_codes, warning_codes = derive_readiness_state(
        eligible_count
    )
    basis_payload = [
        {
            "id": str(question.id),
            "fingerprint": question.source_fingerprint,
            "coverage_key": pool.coverage_key,
            "mechanic": pool.mechanic,
        }
        for pool, question in sorted(pool_rows, key=lambda row: str(row[1].id))
    ]
    basis_fingerprint = hashlib.sha256(
        json.dumps(basis_payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    readiness = await db.scalar(
        select(AssessmentReadiness).where(
            AssessmentReadiness.assessment_version_id == assessment_version.id
        )
    )
    values: dict[str, object] = {
        "status": status,
        "eligible_count": eligible_count,
        "required_count": 5,
        "coverage_evidence": {
            "distinct_source_count": len(coverage_keys),
            "coverage_keys": coverage_keys,
            "mechanics": mechanics,
        },
        "rotation_supported": rotation_supported,
        "basis_fingerprint": basis_fingerprint,
        "blocking_codes": blocking_codes,
        "warning_codes": warning_codes,
        "computed_at": now,
    }
    if readiness is None:
        readiness = AssessmentReadiness(assessment_version_id=assessment_version.id, **values)
        db.add(readiness)
    else:
        for key, value in values.items():
            setattr(readiness, key, value)
    await db.flush()
    return LessonAssessmentReadinessResponse(
        assessment_version_id=assessment_version.id,
        lesson_id=assessment_version.lesson_id,
        lesson_version_id=assessment_version.lesson_version_id,
        status=status,
        eligible_count=eligible_count,
        coverage_evidence=values["coverage_evidence"],
        rotation_supported=rotation_supported,
        basis_fingerprint=basis_fingerprint,
        blocking_codes=blocking_codes,
        warning_codes=warning_codes,
        computed_at=now,
        can_start=status in {"ready", "warning"},
    )


async def _publish_candidate(
    db: AsyncSession,
    candidate: QuestionCandidate,
    *,
    prompt: CandidatePromptPayload,
    answer: CandidateAnswerPayload,
    explanation: CandidateExplanationPayload,
    sources: list[QuestionSourceLink],
    actor_user_id: UUID,
    request_id: UUID,
    now: datetime,
) -> QuestionCandidateApprovalResponse:
    question = Question(
        organization_id=candidate.organization_id,
        location_id=candidate.location_id,
    )
    db.add(question)
    await db.flush()
    question_version = QuestionVersion(
        organization_id=candidate.organization_id,
        location_id=candidate.location_id,
        question_id=question.id,
        candidate_id=candidate.id,
        version_number=1,
        status="published",
        mechanic=candidate.mechanic,
        prompt_payload=prompt.model_dump(mode="json"),
        grading_payload=answer.model_dump(mode="json"),
        explanation_payload=explanation.model_dump(mode="json"),
        is_critical=candidate.is_critical,
        source_fingerprint=candidate.source_fingerprint,
        published_by_user_id=actor_user_id,
        published_at=now,
    )
    db.add(question_version)
    await db.flush()
    db.add(
        QuestionVersionTranslation(
            question_version_id=question_version.id,
            locale="uk",
            prompt_payload={"stem": prompt.stem},
            explanation_payload=explanation.model_dump(mode="json"),
        )
    )
    correct_keys = set(answer.correct_option_keys)
    for position, option in enumerate(prompt.options):
        option_row = QuestionOption(
            question_version_id=question_version.id,
            stable_key=option.stable_key,
            position=position,
            payload={"stable_key": option.stable_key},
            is_correct=option.stable_key in correct_keys,
        )
        db.add(option_row)
        await db.flush()
        db.add(
            QuestionOptionTranslation(
                question_option_id=option_row.id,
                locale="uk",
                payload={"text": option.text},
            )
        )
    db.add_all(
        [
            QuestionSourceLink(
                organization_id=candidate.organization_id,
                location_id=candidate.location_id,
                question_version_id=question_version.id,
                source_role=source.source_role,
                menu_item_version_id=source.menu_item_version_id,
                menu_item_version_component_id=source.menu_item_version_component_id,
                menu_item_version_allergen_id=source.menu_item_version_allergen_id,
            )
            for source in sources
        ]
    )
    assessment_version = await _assessment_version(
        db, candidate, actor_user_id=actor_user_id, now=now
    )
    correct_source = next(source for source in sources if source.source_role == "correct_fact")
    coverage_id = (
        correct_source.menu_item_version_id
        or correct_source.menu_item_version_component_id
        or correct_source.menu_item_version_allergen_id
    )
    if coverage_id is None:
        raise _provenance_invalid()
    db.add(
        AssessmentQuestionPool(
            assessment_version_id=assessment_version.id,
            question_version_id=question_version.id,
            coverage_key=f"source:{coverage_id}",
            mechanic=candidate.mechanic,
            weight=1,
            eligible=True,
        )
    )
    candidate.status = "approved"
    candidate.reviewed_by_user_id = actor_user_id
    candidate.reviewed_at = now
    candidate.revision += 1
    await db.flush()
    readiness = await recompute_readiness(db, assessment_version, now=now)
    db.add(
        AuditEvent(
            organization_id=candidate.organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="question_candidate_approved",
            target_type="question_candidate",
            target_id=candidate.id,
            old_values={"status": "needs_review"},
            new_values={
                "status": "approved",
                "question_version_id": str(question_version.id),
            },
            request_id=request_id,
            outcome="success",
        )
    )
    return QuestionCandidateApprovalResponse(
        candidate=_candidate_response(candidate, sources),
        question_version_id=question_version.id,
        readiness=readiness,
    )


async def approve_question_candidate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    candidate_id: UUID,
    expected_revision: int,
    edited_payload: CandidateEditedPayload | None,
    actor_user_id: UUID,
    request_id: UUID,
    now: datetime,
) -> QuestionCandidateApprovalResponse:
    candidate = await _scoped_candidate(
        db,
        organization_id=organization_id,
        location_id=location_id,
        candidate_id=candidate_id,
        lock=True,
    )
    prompt, answer, explanation, sources = await _validate_reviewable(
        db,
        candidate,
        expected_revision=expected_revision,
        edited_payload=edited_payload,
    )
    response = await _publish_candidate(
        db,
        candidate,
        prompt=prompt,
        answer=answer,
        explanation=explanation,
        sources=sources,
        actor_user_id=actor_user_id,
        request_id=request_id,
        now=now,
    )
    await db.commit()
    return response


async def approve_question_candidate_batch(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    items: list[QuestionCandidateBatchItem],
    actor_user_id: UUID,
    request_id: UUID,
    now: datetime,
) -> QuestionCandidateBatchApprovalResponse:
    validated: list[
        tuple[
            QuestionCandidate,
            CandidatePromptPayload,
            CandidateAnswerPayload,
            CandidateExplanationPayload,
            list[QuestionSourceLink],
        ]
    ] = []
    for item in sorted(items, key=lambda value: str(value.candidate_id)):
        candidate = await _scoped_candidate(
            db,
            organization_id=organization_id,
            location_id=location_id,
            candidate_id=item.candidate_id,
            lock=True,
        )
        prompt, answer, explanation, sources = await _validate_reviewable(
            db,
            candidate,
            expected_revision=item.expected_revision,
            edited_payload=None,
        )
        validated.append((candidate, prompt, answer, explanation, sources))
    responses = [
        await _publish_candidate(
            db,
            candidate,
            prompt=prompt,
            answer=answer,
            explanation=explanation,
            sources=sources,
            actor_user_id=actor_user_id,
            request_id=request_id,
            now=now,
        )
        for candidate, prompt, answer, explanation, sources in validated
    ]
    await db.commit()
    return QuestionCandidateBatchApprovalResponse(items=responses)


async def reject_question_candidate(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    candidate_id: UUID,
    expected_revision: int,
    reason_code: str,
    actor_user_id: UUID,
    request_id: UUID,
    now: datetime,
) -> QuestionCandidateResponse:
    candidate = await _scoped_candidate(
        db,
        organization_id=organization_id,
        location_id=location_id,
        candidate_id=candidate_id,
        lock=True,
    )
    if candidate.revision != expected_revision:
        raise _revision_conflict()
    if candidate.status == "stale":
        raise _candidate_stale()
    if candidate.status != "needs_review":
        raise _revision_conflict()
    candidate.status = "rejected"
    candidate.reviewed_by_user_id = actor_user_id
    candidate.reviewed_at = now
    candidate.rejection_reason_code = reason_code
    candidate.revision += 1
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="question_candidate_rejected",
            target_type="question_candidate",
            target_id=candidate.id,
            old_values={"status": "needs_review"},
            new_values={"status": "rejected", "reason_code": reason_code},
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return _candidate_response(candidate, await _sources(db, candidate.id))


async def get_interactive_training_readiness(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    training_version_id: UUID,
) -> InteractiveTrainingReadinessResponse:
    version = await db.scalar(
        select(TrainingVersion).where(
            TrainingVersion.id == training_version_id,
            TrainingVersion.organization_id == organization_id,
            TrainingVersion.location_id == location_id,
        )
    )
    if version is None:
        raise _not_found()
    rows = list(
        (
            await db.execute(
                select(AssessmentVersion, AssessmentReadiness)
                .join(
                    AssessmentReadiness,
                    AssessmentReadiness.assessment_version_id == AssessmentVersion.id,
                )
                .where(
                    AssessmentVersion.training_version_id == training_version_id,
                    AssessmentVersion.status == "published",
                )
                .order_by(AssessmentVersion.lesson_version_id)
            )
        ).all()
    )
    return InteractiveTrainingReadinessResponse(
        training_version_id=training_version_id,
        lessons=[
            LessonAssessmentReadinessResponse(
                assessment_version_id=assessment_version.id,
                lesson_id=assessment_version.lesson_id,
                lesson_version_id=assessment_version.lesson_version_id,
                status=readiness.status,
                eligible_count=readiness.eligible_count,
                coverage_evidence=readiness.coverage_evidence,
                rotation_supported=readiness.rotation_supported,
                basis_fingerprint=readiness.basis_fingerprint,
                blocking_codes=readiness.blocking_codes,
                warning_codes=readiness.warning_codes,
                computed_at=readiness.computed_at,
                can_start=readiness.status in {"ready", "warning"},
            )
            for assessment_version, readiness in rows
        ],
    )
