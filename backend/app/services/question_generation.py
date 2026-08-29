import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    LessonContentBlock,
    LessonVersion,
    MenuItemVersion,
    MenuItemVersionTranslation,
    MenuVersion,
    MenuVersionCategoryTranslation,
    QuestionCandidate,
    QuestionCandidateStatus,
    QuestionGenerationRule,
    QuestionSourceLink,
    QuestionVersion,
    QuestionVersionStatus,
    TrainingModuleVersion,
    TrainingVersion,
    TrainingVersionMenuDependency,
)
from app.schemas.assessment import (
    CandidateAnswerPayload,
    CandidateExplanationPayload,
    CandidateOption,
    CandidatePromptPayload,
    CandidateSource,
    CategoryFact,
    CategoryGenerationRule,
    GeneratedCandidate,
    GenerationScope,
)


def _canonical_fingerprint(payload: dict[str, object]) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_category_candidate(
    scope: GenerationScope,
    rule: CategoryGenerationRule,
    target: CategoryFact,
    facts: list[CategoryFact],
) -> GeneratedCandidate | None:
    if not target.verified or not target.item_name.strip() or not target.category_name.strip():
        return None

    categories: dict[str, CategoryFact] = {}
    for fact in facts:
        if not fact.verified or not fact.category_name.strip():
            continue
        normalized = fact.category_name.casefold()
        existing = categories.get(normalized)
        if (
            existing is not None
            and existing.menu_version_category_id != fact.menu_version_category_id
        ):
            return None
        categories[normalized] = fact
    if len(categories) < 2:
        return None

    options = sorted(
        (
            CandidateOption(
                stable_key=f"category:{fact.menu_version_category_id}",
                text=fact.category_name,
            )
            for fact in categories.values()
        ),
        key=lambda option: (option.text.casefold(), option.stable_key),
    )
    correct_key = f"category:{target.menu_version_category_id}"
    if correct_key not in {option.stable_key for option in options}:
        return None

    sources = [
        CandidateSource(
            source_role="correct_fact",
            menu_item_version_id=target.menu_item_version_id,
        ),
        CandidateSource(
            source_role="explanation_source",
            menu_item_version_id=target.menu_item_version_id,
        ),
    ]
    sources.extend(
        CandidateSource(
            source_role="distractor_basis",
            menu_item_version_id=fact.menu_item_version_id,
        )
        for fact in categories.values()
        if fact.menu_version_category_id != target.menu_version_category_id
    )
    fingerprint_payload: dict[str, object] = {
        "rule": {"code": rule.code, "version": rule.version},
        "scope": scope.model_dump(mode="json"),
        "target": {
            "menu_item_version_id": str(target.menu_item_version_id),
            "item_name": target.item_name,
            "menu_version_category_id": str(target.menu_version_category_id),
            "category_name": target.category_name,
        },
        "options": [option.model_dump(mode="json") for option in options],
        "sources": [source.model_dump(mode="json") for source in sources],
    }
    return GeneratedCandidate(
        mechanic=rule.mechanic,
        prompt_payload=CandidatePromptPayload(
            stem=f"До якої категорії належить «{target.item_name}»?",
            options=options,
        ),
        answer_payload=CandidateAnswerPayload(correct_option_keys=[correct_key]),
        explanation_payload=CandidateExplanationPayload(
            text=f"«{target.item_name}» належить до категорії «{target.category_name}»."
        ),
        source_fingerprint=_canonical_fingerprint(fingerprint_payload),
        sources=sources,
    )


@dataclass(frozen=True, slots=True)
class CandidateGenerationResult:
    created_count: int
    existing_count: int
    stale_candidate_count: int
    stale_question_count: int


def _not_found() -> APIError:
    return APIError(
        status_code=404,
        code="RESOURCE_NOT_FOUND",
        message="Ресурс не знайдено.",
    )


async def _generation_scope(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    menu_version_id: UUID,
    training_version_id: UUID,
) -> tuple[MenuVersion, TrainingVersion]:
    menu_version = await db.scalar(
        select(MenuVersion).where(
            MenuVersion.id == menu_version_id,
            MenuVersion.organization_id == organization_id,
            MenuVersion.location_id == location_id,
            MenuVersion.status == "published",
        )
    )
    training_version = await db.scalar(
        select(TrainingVersion).where(
            TrainingVersion.id == training_version_id,
            TrainingVersion.organization_id == organization_id,
            TrainingVersion.location_id == location_id,
            TrainingVersion.status == "published",
        )
    )
    dependency = await db.scalar(
        select(TrainingVersionMenuDependency).where(
            TrainingVersionMenuDependency.training_version_id == training_version_id,
            TrainingVersionMenuDependency.menu_version_id == menu_version_id,
        )
    )
    if menu_version is None or training_version is None or dependency is None:
        raise _not_found()
    return menu_version, training_version


async def _lesson_item_ids(
    db: AsyncSession,
    training_version_id: UUID,
) -> dict[UUID, set[UUID]]:
    rows = await db.execute(
        select(LessonVersion.id, LessonContentBlock.menu_item_id)
        .join(
            TrainingModuleVersion,
            TrainingModuleVersion.id == LessonVersion.training_module_version_id,
        )
        .join(
            LessonContentBlock,
            LessonContentBlock.lesson_version_id == LessonVersion.id,
        )
        .where(
            TrainingModuleVersion.training_version_id == training_version_id,
            LessonContentBlock.type == "menu_item_card",
            LessonContentBlock.menu_item_id.is_not(None),
        )
    )
    result: dict[UUID, set[UUID]] = {}
    for lesson_version_id, menu_item_id in rows:
        if menu_item_id is not None:
            result.setdefault(lesson_version_id, set()).add(menu_item_id)
    return result


async def _category_facts(
    db: AsyncSession,
    menu_version_id: UUID,
) -> dict[UUID, CategoryFact]:
    rows = await db.execute(
        select(
            MenuItemVersion,
            MenuItemVersionTranslation.name,
            MenuVersionCategoryTranslation.name,
        )
        .join(
            MenuItemVersionTranslation,
            MenuItemVersionTranslation.menu_item_version_id == MenuItemVersion.id,
        )
        .join(
            MenuVersionCategoryTranslation,
            MenuVersionCategoryTranslation.menu_version_category_id
            == MenuItemVersion.menu_version_category_id,
        )
        .where(
            MenuItemVersion.menu_version_id == menu_version_id,
            MenuItemVersion.verified_by_user_id.is_not(None),
            MenuItemVersion.verified_at.is_not(None),
            MenuItemVersionTranslation.locale == "uk",
            MenuItemVersionTranslation.status == "ready",
            MenuVersionCategoryTranslation.locale == "uk",
            MenuVersionCategoryTranslation.status == "ready",
        )
    )
    return {
        item.menu_item_id: CategoryFact(
            menu_item_version_id=item.id,
            menu_item_id=item.menu_item_id,
            item_name=item_name,
            menu_version_category_id=item.menu_version_category_id,
            category_name=category_name,
            price_minor=item.price_minor,
            verified=True,
        )
        for item, item_name, category_name in rows
    }


async def generate_question_candidates(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    menu_version_id: UUID,
    training_version_id: UUID,
) -> CandidateGenerationResult:
    await _generation_scope(
        db,
        organization_id=organization_id,
        location_id=location_id,
        menu_version_id=menu_version_id,
        training_version_id=training_version_id,
    )
    rules = list(
        await db.scalars(
            select(QuestionGenerationRule)
            .where(
                QuestionGenerationRule.code == "menu.category",
                QuestionGenerationRule.mechanic == "single_choice",
                QuestionGenerationRule.status == "active",
            )
            .with_for_update()
        )
    )
    lesson_items = await _lesson_item_ids(db, training_version_id)
    facts_by_item = await _category_facts(db, menu_version_id)
    created_count = 0
    existing_count = 0
    stale_candidate_count = 0
    stale_question_count = 0

    for rule_row in rules:
        rule = CategoryGenerationRule(code=rule_row.code, version=rule_row.version)
        for lesson_version_id, item_ids in lesson_items.items():
            facts = [facts_by_item[item_id] for item_id in item_ids if item_id in facts_by_item]
            current_fingerprints: set[str] = set()
            for target in facts:
                generated = build_category_candidate(
                    GenerationScope(
                        organization_id=organization_id,
                        location_id=location_id,
                        menu_version_id=menu_version_id,
                        training_version_id=training_version_id,
                        lesson_version_id=lesson_version_id,
                    ),
                    rule,
                    target,
                    facts,
                )
                if generated is None:
                    continue
                current_fingerprints.add(generated.source_fingerprint)
                existing = await db.scalar(
                    select(QuestionCandidate).where(
                        QuestionCandidate.generation_rule_id == rule_row.id,
                        QuestionCandidate.lesson_version_id == lesson_version_id,
                        QuestionCandidate.source_fingerprint == generated.source_fingerprint,
                    )
                )
                if existing is not None:
                    existing_count += 1
                    continue
                candidate = QuestionCandidate(
                    organization_id=organization_id,
                    location_id=location_id,
                    generation_rule_id=rule_row.id,
                    training_version_id=training_version_id,
                    lesson_version_id=lesson_version_id,
                    mechanic=generated.mechanic,
                    prompt_payload=generated.prompt_payload.model_dump(mode="json"),
                    answer_payload=generated.answer_payload.model_dump(mode="json"),
                    explanation_payload=generated.explanation_payload.model_dump(mode="json"),
                    is_critical=False,
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
                            menu_item_version_id=source.menu_item_version_id,
                        )
                        for source in generated.sources
                    ]
                )
                created_count += 1

            prior_candidates = list(
                await db.scalars(
                    select(QuestionCandidate).where(
                        QuestionCandidate.generation_rule_id == rule_row.id,
                        QuestionCandidate.training_version_id == training_version_id,
                        QuestionCandidate.lesson_version_id == lesson_version_id,
                        QuestionCandidate.status.in_(["needs_review", "approved"]),
                    )
                )
            )
            for candidate in prior_candidates:
                if candidate.source_fingerprint in current_fingerprints:
                    continue
                candidate.status = QuestionCandidateStatus.STALE.value
                candidate.revision += 1
                stale_candidate_count += 1
                published_versions = list(
                    await db.scalars(
                        select(QuestionVersion).where(
                            QuestionVersion.candidate_id == candidate.id,
                            QuestionVersion.status == QuestionVersionStatus.PUBLISHED.value,
                        )
                    )
                )
                for question_version in published_versions:
                    question_version.status = QuestionVersionStatus.STALE.value
                    question_version.stale_at = datetime.now(UTC)
                    stale_question_count += 1

    return CandidateGenerationResult(
        created_count=created_count,
        existing_count=existing_count,
        stale_candidate_count=stale_candidate_count,
        stale_question_count=stale_question_count,
    )


async def candidate_source_fingerprint_is_current(
    db: AsyncSession,
    candidate: QuestionCandidate,
) -> bool:
    rule_row = await db.get(QuestionGenerationRule, candidate.generation_rule_id)
    dependency = await db.scalar(
        select(TrainingVersionMenuDependency).where(
            TrainingVersionMenuDependency.training_version_id == candidate.training_version_id
        )
    )
    if (
        rule_row is None
        or dependency is None
        or rule_row.code != "menu.category"
        or rule_row.mechanic != "single_choice"
    ):
        return False
    source_rows = list(
        await db.scalars(
            select(QuestionSourceLink).where(
                QuestionSourceLink.question_candidate_id == candidate.id,
                QuestionSourceLink.source_role == "correct_fact",
            )
        )
    )
    if len(source_rows) != 1 or source_rows[0].menu_item_version_id is None:
        return False
    lesson_items = await _lesson_item_ids(db, candidate.training_version_id)
    item_ids = lesson_items.get(candidate.lesson_version_id, set())
    facts_by_item = await _category_facts(db, dependency.menu_version_id)
    facts = [facts_by_item[item_id] for item_id in item_ids if item_id in facts_by_item]
    target = next(
        (
            fact
            for fact in facts
            if fact.menu_item_version_id == source_rows[0].menu_item_version_id
        ),
        None,
    )
    if target is None:
        return False
    generated = build_category_candidate(
        GenerationScope(
            organization_id=candidate.organization_id,
            location_id=candidate.location_id,
            menu_version_id=dependency.menu_version_id,
            training_version_id=candidate.training_version_id,
            lesson_version_id=candidate.lesson_version_id,
        ),
        CategoryGenerationRule(code=rule_row.code, version=rule_row.version),
        target,
        facts,
    )
    return generated is not None and generated.source_fingerprint == candidate.source_fingerprint
