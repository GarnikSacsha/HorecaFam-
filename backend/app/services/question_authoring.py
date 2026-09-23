"""Авторські описи проходять той самий review без автоматичної публікації."""

from datetime import datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import AuditEvent, QuestionCandidate, QuestionGenerationRule, QuestionSourceLink
from app.schemas.assessment import AuthoredQuestionRequest, QuestionCandidateResponse
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.question_generation import (
    _description_facts,
    _generation_scope,
    _lesson_item_ids,
)

AUTHORED_RULE = "menu.description.authored"


async def _source_fingerprint(
    db: AsyncSession, *, organization_id: UUID, location_id: UUID, payload: AuthoredQuestionRequest
) -> str:
    evidence = payload.explanation_payload.authoring
    assert evidence is not None
    await _generation_scope(
        db,
        organization_id=organization_id,
        location_id=location_id,
        menu_version_id=evidence.menu_version_id,
        training_version_id=payload.training_version_id,
    )
    lesson_items = await _lesson_item_ids(db, payload.training_version_id)
    facts = await _description_facts(db, evidence.menu_version_id)
    fact = next(
        (
            fact
            for item_id, fact in facts.items()
            if item_id in lesson_items.get(payload.lesson_version_id, set())
            and fact.menu_item_version_id == evidence.menu_item_version_id
        ),
        None,
    )
    if fact is None or evidence.source_quote not in fact.description:
        raise APIError(
            status_code=422,
            code="QUESTION_PROVENANCE_INVALID",
            message="Опис або прив'язка до уроку не підтверджені.",
        )
    return request_fingerprint(
        {
            "organization_id": str(organization_id),
            "location_id": str(location_id),
            "request": payload.model_dump(mode="json"),
            "evidence": evidence.model_dump(mode="json"),
            "fact": fact.model_dump(mode="json"),
        }
    )


async def authored_source_is_current(db: AsyncSession, candidate: QuestionCandidate) -> bool:
    try:
        payload = AuthoredQuestionRequest(
            training_version_id=candidate.training_version_id,
            lesson_version_id=candidate.lesson_version_id,
            prompt_payload=candidate.prompt_payload,
            answer_payload=candidate.answer_payload,
            explanation_payload=candidate.explanation_payload,
        )
        current = await _source_fingerprint(
            db,
            organization_id=candidate.organization_id,
            location_id=candidate.location_id,
            payload=payload,
        )
    except (ValidationError, APIError):
        return False
    return candidate.source_fingerprint == current


async def create_authored_question(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    payload: AuthoredQuestionRequest,
    actor_user_id: UUID,
    idempotency_key: str,
    request_id: UUID,
    now: datetime,
) -> QuestionCandidateResponse:
    from app.services.question_review import get_question_candidate

    evidence = payload.explanation_payload.authoring
    assert evidence is not None
    fingerprint = request_fingerprint(
        {
            "location_id": str(location_id),
            "payload": payload.model_dump(mode="json"),
            "evidence": evidence.model_dump(mode="json"),
        }
    )
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="authored_question_create",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    if replay is not None:
        return await get_question_candidate(
            db,
            organization_id=organization_id,
            location_id=location_id,
            candidate_id=replay.resource_id,
        )
    source_fingerprint = await _source_fingerprint(
        db,
        organization_id=organization_id,
        location_id=location_id,
        payload=payload,
    )
    await db.execute(
        insert(QuestionGenerationRule)
        .values(
            code=AUTHORED_RULE,
            version=1,
            mechanic="recognition",
            configuration={"authoring": True},
        )
        .on_conflict_do_nothing(index_elements=["code", "version"])
    )
    rule = await db.scalar(
        select(QuestionGenerationRule)
        .where(
            QuestionGenerationRule.code == AUTHORED_RULE,
            QuestionGenerationRule.version == 1,
        )
        .with_for_update()
    )
    assert rule is not None
    if rule.status != "active":
        raise APIError(
            status_code=409,
            code="QUESTION_AUTHORING_UNAVAILABLE",
            message="Створення авторських питань призупинено.",
        )
    candidate = await db.scalar(
        select(QuestionCandidate).where(
            QuestionCandidate.generation_rule_id == rule.id,
            QuestionCandidate.lesson_version_id == payload.lesson_version_id,
            QuestionCandidate.source_fingerprint == source_fingerprint,
        )
    )
    if candidate is None:
        explanation = payload.explanation_payload.model_dump(mode="json")
        explanation["authoring"] = evidence.model_dump(mode="json")
        candidate = QuestionCandidate(
            organization_id=organization_id,
            location_id=location_id,
            generation_rule_id=rule.id,
            training_version_id=payload.training_version_id,
            lesson_version_id=payload.lesson_version_id,
            mechanic="recognition",
            prompt_payload=payload.prompt_payload.model_dump(mode="json"),
            answer_payload=payload.answer_payload.model_dump(mode="json"),
            explanation_payload=explanation,
            is_critical=False,
            source_fingerprint=source_fingerprint,
        )
        db.add(candidate)
        await db.flush()
        db.add_all(
            [
                QuestionSourceLink(
                    organization_id=organization_id,
                    location_id=location_id,
                    question_candidate_id=candidate.id,
                    source_role=role,
                    menu_item_version_id=evidence.menu_item_version_id,
                )
                for role in ("correct_fact", "distractor_basis", "explanation_source")
            ]
        )
        db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_type="user",
                action="authored_question_created",
                target_type="question_candidate",
                target_id=candidate.id,
                old_values=None,
                new_values=None,
                request_id=request_id,
                outcome="success",
            )
        )
    await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="authored_question_create",
        key=idempotency_key,
        fingerprint=fingerprint,
        resource_type="question_candidate",
        resource_id=candidate.id,
        response_status=200,
        now=now,
    )
    await db.commit()
    return await get_question_candidate(
        db, organization_id=organization_id, location_id=location_id, candidate_id=candidate.id
    )
