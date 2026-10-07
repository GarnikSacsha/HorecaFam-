import hashlib
import json
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    LessonVersion,
    QuestionCandidate,
    QuestionGenerationRule,
    QuestionSourceLink,
    StandardRuleVersion,
    StandardSet,
    StandardSetVersion,
    TrainingModule,
    TrainingModuleStandardDependency,
    TrainingModuleVersion,
    TrainingVersion,
)
from app.schemas.assessment import (
    CandidateAnswerPayload,
    CandidateExplanationPayload,
    CandidateOption,
    CandidatePromptPayload,
    CandidateSource,
    GeneratedCandidate,
)


def build_standard_candidate(
    source: StandardRuleVersion,
    *,
    training_version_id: UUID,
    lesson_version_id: UUID,
) -> GeneratedCandidate | None:
    if not source.verified or not source.provenance:
        return None
    if not all(
        isinstance(value, str) and value.strip()
        for value in (
            source.scenario_uk,
            source.allowed_action_uk,
            source.explanation_uk,
        )
    ):
        return None
    if not isinstance(source.prohibited_actions_uk, list) or len(source.prohibited_actions_uk) < 2:
        return None
    if any(
        not isinstance(values, list)
        or any(not isinstance(value, str) or not value.strip() for value in values)
        for values in (source.conditions_uk, source.action_order_uk)
    ):
        return None
    actions = [source.allowed_action_uk, *source.prohibited_actions_uk]
    if any(not isinstance(action, str) or not action.strip() for action in actions):
        return None
    labels = [str(action).strip() for action in actions]
    if len({label.casefold() for label in labels}) != len(labels):
        return None
    evidence = {
        "rule": "standards.scenario.v1",
        "organization_id": str(source.organization_id),
        "location_id": str(source.location_id),
        "source_id": str(source.id),
        "set_version_id": str(source.standard_set_version_id),
        "training_version_id": str(training_version_id),
        "lesson_version_id": str(lesson_version_id),
        "scenario": source.scenario_uk,
        "actions": labels,
        "conditions": source.conditions_uk,
        "order": source.action_order_uk,
        "explanation": source.explanation_uk,
        "provenance": source.provenance,
        "critical": source.is_critical,
    }
    try:
        options = [
            CandidateOption(
                stable_key=hashlib.sha256(label.encode()).hexdigest(),
                text=label,
            )
            for label in labels
        ]
        correct_key = options[0].stable_key
        options.sort(key=lambda option: option.stable_key)
        stem = str(source.scenario_uk)
        if source.conditions_uk:
            stem += " Умови: " + " ".join(source.conditions_uk)
        explanation = str(source.explanation_uk)
        if source.action_order_uk:
            explanation += " Послідовність: " + " → ".join(source.action_order_uk)
        return GeneratedCandidate(
            mechanic="single_choice",
            prompt_payload=CandidatePromptPayload(stem=stem, options=options),
            answer_payload=CandidateAnswerPayload(correct_option_keys=[correct_key]),
            explanation_payload=CandidateExplanationPayload(text=explanation),
            source_fingerprint=hashlib.sha256(
                json.dumps(
                    evidence,
                    sort_keys=True,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest(),
            sources=[
                CandidateSource(source_role="correct_fact", standard_rule_version_id=source.id),
                CandidateSource(source_role="distractor_basis", standard_rule_version_id=source.id),
                CandidateSource(
                    source_role="explanation_source", standard_rule_version_id=source.id
                ),
            ],
        )
    except ValidationError:
        return None


STANDARD_RULE_CODES = {"service.scenario", "sales.scenario", "venue_standards.scenario"}


async def generate_training_standard_candidates(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    training_version_id: UUID,
) -> tuple[int, int]:
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
    modules = list(
        await db.scalars(
            select(TrainingModuleStandardDependency.training_module_version_id).where(
                TrainingModuleStandardDependency.training_version_id == training_version_id,
            )
        )
    )
    created, existing = 0, 0
    for module_id in modules:
        added, found = await generate_standard_candidates(
            db,
            organization_id=organization_id,
            location_id=location_id,
            training_version_id=training_version_id,
            module_version_id=module_id,
        )
        created += added
        existing += found
    return created, existing


async def generate_standard_candidates(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    training_version_id: UUID,
    module_version_id: UUID,
) -> tuple[int, int]:
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
    dependency = await db.scalar(
        select(TrainingModuleStandardDependency).where(
            TrainingModuleStandardDependency.training_version_id == training_version_id,
            TrainingModuleStandardDependency.training_module_version_id == module_version_id,
            TrainingModuleStandardDependency.organization_id == organization_id,
            TrainingModuleStandardDependency.location_id == location_id,
        )
    )
    module = await db.scalar(
        select(TrainingModule)
        .join(
            TrainingModuleVersion,
            TrainingModuleVersion.training_module_id == TrainingModule.id,
        )
        .where(TrainingModuleVersion.id == module_version_id)
    )
    if dependency is None or module is None:
        raise APIError(status_code=404, code="RESOURCE_NOT_FOUND", message="Ресурс не знайдено.")
    version = await db.get(StandardSetVersion, dependency.standard_set_version_id)
    source_set = await db.get(StandardSet, version.standard_set_id) if version else None
    lesson = await db.scalar(
        select(LessonVersion)
        .where(
            LessonVersion.training_module_version_id == module_version_id,
        )
        .order_by(LessonVersion.position)
        .limit(1)
    )
    if (
        version is None
        or version.status != "published"
        or source_set is None
        or source_set.domain_type != module.domain_type
        or lesson is None
    ):
        raise APIError(
            status_code=409, code="STANDARD_SOURCE_NOT_READY", message="Джерело ще готується."
        )
    facts = list(
        await db.scalars(
            select(StandardRuleVersion)
            .where(
                StandardRuleVersion.standard_set_version_id == version.id,
            )
            .order_by(StandardRuleVersion.position)
        )
    )
    if not 1 <= len(facts) <= 20:
        raise APIError(
            status_code=409, code="STANDARD_SOURCE_NOT_READY", message="Перевірте кількість правил."
        )
    code = f"{source_set.domain_type}.scenario"
    await db.execute(
        insert(QuestionGenerationRule)
        .values(
            id=uuid4(),
            code=code,
            version=1,
            domain_type=source_set.domain_type,
            mechanic="single_choice",
            status="active",
            configuration={},
        )
        .on_conflict_do_nothing(constraint="uq_question_generation_rules_code_version")
    )
    rule = await db.scalar(
        select(QuestionGenerationRule).where(
            QuestionGenerationRule.code == code,
            QuestionGenerationRule.version == 1,
            QuestionGenerationRule.status == "active",
        )
    )
    if rule is None:
        raise APIError(
            status_code=409,
            code="STANDARD_SOURCE_NOT_READY",
            message="Правило генерації недоступне.",
        )
    created, existing = 0, 0
    for fact in facts:
        generated = build_standard_candidate(
            fact,
            training_version_id=training_version_id,
            lesson_version_id=lesson.id,
        )
        if generated is None:
            continue
        found = await db.scalar(
            select(QuestionCandidate.id).where(
                QuestionCandidate.generation_rule_id == rule.id,
                QuestionCandidate.lesson_version_id == lesson.id,
                QuestionCandidate.source_fingerprint == generated.source_fingerprint,
            )
        )
        if found is not None:
            existing += 1
            continue
        candidate = QuestionCandidate(
            organization_id=organization_id,
            location_id=location_id,
            generation_rule_id=rule.id,
            training_version_id=training_version_id,
            lesson_version_id=lesson.id,
            mechanic=generated.mechanic,
            prompt_payload=generated.prompt_payload.model_dump(mode="json"),
            answer_payload=generated.answer_payload.model_dump(mode="json"),
            explanation_payload=generated.explanation_payload.model_dump(mode="json"),
            is_critical=fact.is_critical,
            source_fingerprint=generated.source_fingerprint,
        )
        db.add(candidate)
        await db.flush()
        db.add_all(
            [
                QuestionSourceLink(
                    organization_id=organization_id,
                    location_id=location_id,
                    question_candidate_id=candidate.id,
                    source_role=source.source_role,
                    standard_rule_version_id=fact.id,
                )
                for source in generated.sources
            ]
        )
        created += 1
    await db.flush()
    return created, existing


async def standard_source_is_current(db: AsyncSession, candidate: QuestionCandidate) -> bool:
    source = await db.scalar(
        select(StandardRuleVersion)
        .join(
            QuestionSourceLink,
            QuestionSourceLink.standard_rule_version_id == StandardRuleVersion.id,
        )
        .where(
            QuestionSourceLink.question_candidate_id == candidate.id,
            QuestionSourceLink.source_role == "correct_fact",
            StandardRuleVersion.organization_id == candidate.organization_id,
            StandardRuleVersion.location_id == candidate.location_id,
        )
    )
    if source is None:
        return False
    version = await db.get(StandardSetVersion, source.standard_set_version_id)
    if version is None or version.status not in {"published", "archived"}:
        return False
    dependency = await db.scalar(
        select(TrainingModuleStandardDependency.id)
        .join(
            LessonVersion,
            LessonVersion.training_module_version_id
            == TrainingModuleStandardDependency.training_module_version_id,
        )
        .where(
            LessonVersion.id == candidate.lesson_version_id,
            TrainingModuleStandardDependency.training_version_id == candidate.training_version_id,
            TrainingModuleStandardDependency.standard_set_version_id
            == source.standard_set_version_id,
        )
    )
    if dependency is None:
        return False
    generated = build_standard_candidate(
        source,
        training_version_id=candidate.training_version_id,
        lesson_version_id=candidate.lesson_version_id,
    )
    return generated is not None and generated.source_fingerprint == candidate.source_fingerprint
