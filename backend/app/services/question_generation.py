import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Allergen,
    LessonContentBlock,
    LessonVersion,
    MenuComponentVersionTranslation,
    MenuItemVersion,
    MenuItemVersionAllergen,
    MenuItemVersionComponent,
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
    AllergenFact,
    AllergenGenerationRule,
    CandidateAnswerPayload,
    CandidateExplanationPayload,
    CandidateOption,
    CandidatePromptPayload,
    CandidateSource,
    CategoryFact,
    CategoryGenerationRule,
    ComponentFact,
    ComponentGenerationRule,
    DescriptionFact,
    DescriptionGenerationRule,
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


def _candidate(
    *,
    scope: GenerationScope,
    rule_code: str,
    rule_version: int,
    mechanic: Literal["single_choice", "multiple_choice", "recognition"],
    stem: str,
    options: list[CandidateOption],
    correct_option_keys: list[str],
    explanation: str,
    sources: list[CandidateSource],
    target_payload: dict[str, object],
) -> GeneratedCandidate:
    fingerprint_payload: dict[str, object] = {
        "rule": {"code": rule_code, "version": rule_version},
        "scope": scope.model_dump(mode="json"),
        "target": target_payload,
        "options": [option.model_dump(mode="json") for option in options],
        "sources": [source.model_dump(mode="json") for source in sources],
    }
    return GeneratedCandidate(
        mechanic=mechanic,
        prompt_payload=CandidatePromptPayload(stem=stem, options=options),
        answer_payload=CandidateAnswerPayload(correct_option_keys=correct_option_keys),
        explanation_payload=CandidateExplanationPayload(text=explanation),
        source_fingerprint=_canonical_fingerprint(fingerprint_payload),
        sources=sources,
    )


def build_component_candidate(
    scope: GenerationScope,
    rule: ComponentGenerationRule,
    target_item_version_id: UUID,
    facts: list[ComponentFact],
) -> GeneratedCandidate | None:
    target_rows = [fact for fact in facts if fact.menu_item_version_id == target_item_version_id]
    if len(target_rows) < 2 or any(
        not fact.verified or not fact.item_name.strip() or not fact.component_name.strip()
        for fact in target_rows
    ):
        return None

    option_facts: dict[str, ComponentFact] = {}
    normalized_labels: dict[str, str] = {}
    for fact in facts:
        if not fact.verified or not fact.component_name.strip():
            continue
        stable_key = f"component:{fact.menu_component_version_id}"
        normalized = fact.component_name.casefold()
        existing_key = normalized_labels.get(normalized)
        if existing_key is not None and existing_key != stable_key:
            return None
        normalized_labels[normalized] = stable_key
        option_facts.setdefault(stable_key, fact)

    correct_keys = sorted({f"component:{fact.menu_component_version_id}" for fact in target_rows})
    distractor_keys = sorted(set(option_facts) - set(correct_keys))
    if not distractor_keys or len(option_facts) > 20:
        return None
    options = sorted(
        [
            CandidateOption(stable_key=key, text=fact.component_name)
            for key, fact in option_facts.items()
        ],
        key=lambda option: (option.text.casefold(), option.stable_key),
    )
    distractor_sources = [
        CandidateSource(
            source_role="distractor_basis",
            menu_item_version_component_id=option_facts[key].menu_item_version_component_id,
        )
        for key in distractor_keys
    ]
    sources = [
        *[
            CandidateSource(
                source_role="correct_fact",
                menu_item_version_component_id=fact.menu_item_version_component_id,
            )
            for fact in sorted(
                target_rows,
                key=lambda row: (row.position, str(row.menu_item_version_component_id)),
            )
        ],
        CandidateSource(
            source_role="explanation_source",
            menu_item_version_id=target_item_version_id,
        ),
        *distractor_sources,
    ]
    item_name = target_rows[0].item_name
    component_names = ", ".join(
        fact.component_name for fact in sorted(target_rows, key=lambda row: row.position)
    )
    return _candidate(
        scope=scope,
        rule_code=rule.code,
        rule_version=rule.version,
        mechanic=rule.mechanic,
        stem=f"Оберіть усі підтверджені компоненти позиції «{item_name}».",
        options=options,
        correct_option_keys=correct_keys,
        explanation=f"Підтверджені компоненти «{item_name}»: {component_names}.",
        sources=sources,
        target_payload={
            "menu_item_version_id": str(target_item_version_id),
            "component_keys": correct_keys,
        },
    )


def build_missing_component_candidate(
    scope: GenerationScope,
    rule: ComponentGenerationRule,
    target_item_version_id: UUID,
    facts: list[ComponentFact],
) -> GeneratedCandidate | None:
    target_rows = [fact for fact in facts if fact.menu_item_version_id == target_item_version_id]
    if not target_rows or any(
        not fact.verified or not fact.item_name.strip() or not fact.component_name.strip()
        for fact in target_rows
    ):
        return None

    target_keys = {f"component:{fact.menu_component_version_id}" for fact in target_rows}
    alternatives = sorted(
        (
            fact
            for fact in facts
            if fact.verified
            and fact.menu_item_version_id != target_item_version_id
            and fact.component_name.strip()
            and f"component:{fact.menu_component_version_id}" not in target_keys
        ),
        key=lambda fact: (fact.component_name.casefold(), str(fact.menu_component_version_id)),
    )
    if not alternatives:
        return None
    missing = alternatives[0]
    option_facts = [*target_rows, missing]
    normalized_labels = [fact.component_name.casefold() for fact in option_facts]
    if len(normalized_labels) != len(set(normalized_labels)) or len(option_facts) > 20:
        return None

    options = sorted(
        [
            CandidateOption(
                stable_key=f"component:{fact.menu_component_version_id}",
                text=fact.component_name,
            )
            for fact in option_facts
        ],
        key=lambda option: (option.text.casefold(), option.stable_key),
    )
    missing_key = f"component:{missing.menu_component_version_id}"
    item_name = target_rows[0].item_name
    sources = [
        CandidateSource(
            source_role="correct_fact",
            menu_item_version_component_id=missing.menu_item_version_component_id,
        ),
        CandidateSource(
            source_role="explanation_source",
            menu_item_version_id=target_item_version_id,
        ),
        *[
            CandidateSource(
                source_role="distractor_basis",
                menu_item_version_component_id=fact.menu_item_version_component_id,
            )
            for fact in sorted(target_rows, key=lambda row: row.position)
        ],
    ]
    return _candidate(
        scope=scope,
        rule_code=f"{rule.code}.missing",
        rule_version=rule.version,
        mechanic=rule.mechanic,
        stem=f"Якого компонента немає у підтвердженому складі позиції «{item_name}»?",
        options=options,
        correct_option_keys=[missing_key],
        explanation=(
            f"Компонент «{missing.component_name}» не входить "
            f"до підтвердженого складу «{item_name}»."
        ),
        sources=sources,
        target_payload={
            "menu_item_version_id": str(target_item_version_id),
            "included_component_keys": sorted(target_keys),
            "missing_component_key": missing_key,
        },
    )


def build_allergen_candidate(
    scope: GenerationScope,
    rule: AllergenGenerationRule,
    target_item_version_id: UUID,
    facts: list[AllergenFact],
) -> GeneratedCandidate | None:
    target_rows = [fact for fact in facts if fact.menu_item_version_id == target_item_version_id]
    if not target_rows or any(
        not fact.verified or not fact.item_name.strip() or not fact.allergen_name.strip()
        for fact in target_rows
    ):
        return None

    option_facts: dict[str, AllergenFact] = {}
    normalized_labels: dict[str, str] = {}
    for fact in facts:
        if not fact.verified or not fact.allergen_name.strip():
            continue
        stable_key = f"allergen:{fact.allergen_id}"
        normalized = fact.allergen_name.casefold()
        existing_key = normalized_labels.get(normalized)
        if existing_key is not None and existing_key != stable_key:
            return None
        normalized_labels[normalized] = stable_key
        option_facts.setdefault(stable_key, fact)

    correct_keys = sorted({f"allergen:{fact.allergen_id}" for fact in target_rows})
    distractor_keys = sorted(set(option_facts) - set(correct_keys))
    if not distractor_keys or len(option_facts) > 20:
        return None
    options = sorted(
        [
            CandidateOption(stable_key=key, text=fact.allergen_name)
            for key, fact in option_facts.items()
        ],
        key=lambda option: (option.text.casefold(), option.stable_key),
    )
    sources = [
        *[
            CandidateSource(
                source_role="correct_fact",
                menu_item_version_allergen_id=fact.menu_item_version_allergen_id,
            )
            for fact in sorted(target_rows, key=lambda row: str(row.menu_item_version_allergen_id))
        ],
        CandidateSource(
            source_role="explanation_source",
            menu_item_version_id=target_item_version_id,
        ),
        *[
            CandidateSource(
                source_role="distractor_basis",
                menu_item_version_allergen_id=option_facts[key].menu_item_version_allergen_id,
            )
            for key in distractor_keys
        ],
    ]
    item_name = target_rows[0].item_name
    allergen_names = ", ".join(sorted(fact.allergen_name for fact in target_rows))
    return _candidate(
        scope=scope,
        rule_code=rule.code,
        rule_version=rule.version,
        mechanic=rule.mechanic,
        stem=f"Оберіть усі підтверджені алергени позиції «{item_name}».",
        options=options,
        correct_option_keys=correct_keys,
        explanation=f"Підтверджені алергени «{item_name}»: {allergen_names}.",
        sources=sources,
        target_payload={
            "menu_item_version_id": str(target_item_version_id),
            "allergen_keys": correct_keys,
        },
    )


def build_description_candidate(
    scope: GenerationScope,
    rule: DescriptionGenerationRule,
    target: DescriptionFact,
    facts: list[DescriptionFact],
) -> GeneratedCandidate | None:
    if not target.verified or not target.item_name.strip() or not target.description.strip():
        return None
    usable = [
        fact
        for fact in facts
        if fact.verified and fact.item_name.strip() and fact.description.strip()
    ]
    if len(usable) < 2 or len(usable) > 20:
        return None
    names: dict[str, DescriptionFact] = {}
    descriptions: dict[str, DescriptionFact] = {}
    for fact in usable:
        normalized_name = fact.item_name.casefold()
        normalized_description = fact.description.casefold()
        if normalized_name in names or normalized_description in descriptions:
            return None
        names[normalized_name] = fact
        descriptions[normalized_description] = fact
    if target.menu_item_version_id not in {fact.menu_item_version_id for fact in usable}:
        return None

    options = sorted(
        [
            CandidateOption(
                stable_key=f"item:{fact.menu_item_version_id}",
                text=fact.item_name,
            )
            for fact in usable
        ],
        key=lambda option: (option.text.casefold(), option.stable_key),
    )
    correct_key = f"item:{target.menu_item_version_id}"
    sources = [
        CandidateSource(
            source_role="correct_fact",
            menu_item_version_id=target.menu_item_version_id,
        ),
        CandidateSource(
            source_role="explanation_source",
            menu_item_version_id=target.menu_item_version_id,
        ),
        *[
            CandidateSource(
                source_role="distractor_basis",
                menu_item_version_id=fact.menu_item_version_id,
            )
            for fact in usable
            if fact.menu_item_version_id != target.menu_item_version_id
        ],
    ]
    return _candidate(
        scope=scope,
        rule_code=rule.code,
        rule_version=rule.version,
        mechanic=rule.mechanic,
        stem=f"Якій позиції відповідає опис: «{target.description.strip()}»?",
        options=options,
        correct_option_keys=[correct_key],
        explanation=f"Цей опис належить позиції «{target.item_name}».",
        sources=sources,
        target_payload={
            "menu_item_version_id": str(target.menu_item_version_id),
            "description": target.description.strip(),
        },
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


async def _component_facts(
    db: AsyncSession,
    menu_version_id: UUID,
) -> dict[UUID, list[ComponentFact]]:
    rows = await db.execute(
        select(
            MenuItemVersion,
            MenuItemVersionTranslation.name,
            MenuItemVersionComponent,
            MenuComponentVersionTranslation.name,
        )
        .join(
            MenuItemVersionTranslation,
            MenuItemVersionTranslation.menu_item_version_id == MenuItemVersion.id,
        )
        .join(
            MenuItemVersionComponent,
            MenuItemVersionComponent.menu_item_version_id == MenuItemVersion.id,
        )
        .join(
            MenuComponentVersionTranslation,
            MenuComponentVersionTranslation.menu_component_version_id
            == MenuItemVersionComponent.menu_component_version_id,
        )
        .where(
            MenuItemVersion.menu_version_id == menu_version_id,
            MenuItemVersion.component_data_status == "confirmed_present",
            MenuItemVersion.verified_by_user_id.is_not(None),
            MenuItemVersion.verified_at.is_not(None),
            MenuItemVersionComponent.verified_by_user_id.is_not(None),
            MenuItemVersionComponent.verified_at.is_not(None),
            MenuItemVersionTranslation.locale == "uk",
            MenuItemVersionTranslation.status == "ready",
            MenuComponentVersionTranslation.locale == "uk",
            MenuComponentVersionTranslation.status == "ready",
        )
    )
    result: dict[UUID, list[ComponentFact]] = {}
    for item, item_name, link, component_name in rows:
        result.setdefault(item.menu_item_id, []).append(
            ComponentFact(
                menu_item_version_component_id=link.id,
                menu_component_version_id=link.menu_component_version_id,
                menu_item_version_id=item.id,
                menu_item_id=item.menu_item_id,
                item_name=item_name,
                component_name=component_name,
                position=link.position,
                verified=True,
            )
        )
    return result


async def _allergen_facts(
    db: AsyncSession,
    menu_version_id: UUID,
) -> dict[UUID, list[AllergenFact]]:
    rows = await db.execute(
        select(
            MenuItemVersion,
            MenuItemVersionTranslation.name,
            MenuItemVersionAllergen,
            Allergen.label_uk,
        )
        .join(
            MenuItemVersionTranslation,
            MenuItemVersionTranslation.menu_item_version_id == MenuItemVersion.id,
        )
        .join(
            MenuItemVersionAllergen,
            MenuItemVersionAllergen.menu_item_version_id == MenuItemVersion.id,
        )
        .join(Allergen, Allergen.id == MenuItemVersionAllergen.allergen_id)
        .where(
            MenuItemVersion.menu_version_id == menu_version_id,
            MenuItemVersion.allergen_data_status == "confirmed_present",
            MenuItemVersion.verified_by_user_id.is_not(None),
            MenuItemVersion.verified_at.is_not(None),
            MenuItemVersionAllergen.verified_by_user_id.is_not(None),
            MenuItemVersionAllergen.verified_at.is_not(None),
            MenuItemVersionTranslation.locale == "uk",
            MenuItemVersionTranslation.status == "ready",
            Allergen.status == "active",
        )
    )
    result: dict[UUID, list[AllergenFact]] = {}
    for item, item_name, link, allergen_name in rows:
        result.setdefault(item.menu_item_id, []).append(
            AllergenFact(
                menu_item_version_allergen_id=link.id,
                allergen_id=link.allergen_id,
                menu_item_version_id=item.id,
                menu_item_id=item.menu_item_id,
                item_name=item_name,
                allergen_name=allergen_name,
                verified=True,
            )
        )
    return result


async def _description_facts(
    db: AsyncSession,
    menu_version_id: UUID,
) -> dict[UUID, DescriptionFact]:
    rows = await db.execute(
        select(
            MenuItemVersion,
            MenuItemVersionTranslation.name,
            MenuItemVersionTranslation.description,
        )
        .join(
            MenuItemVersionTranslation,
            MenuItemVersionTranslation.menu_item_version_id == MenuItemVersion.id,
        )
        .where(
            MenuItemVersion.menu_version_id == menu_version_id,
            MenuItemVersion.verified_by_user_id.is_not(None),
            MenuItemVersion.verified_at.is_not(None),
            MenuItemVersionTranslation.locale == "uk",
            MenuItemVersionTranslation.status == "ready",
            MenuItemVersionTranslation.description.is_not(None),
        )
    )
    return {
        item.menu_item_id: DescriptionFact(
            menu_item_version_id=item.id,
            menu_item_id=item.menu_item_id,
            item_name=item_name,
            description=description,
            verified=True,
        )
        for item, item_name, description in rows
        if description is not None and description.strip()
    }


@dataclass(frozen=True, slots=True)
class GenerationFacts:
    categories: dict[UUID, CategoryFact]
    components: dict[UUID, list[ComponentFact]]
    allergens: dict[UUID, list[AllergenFact]]
    descriptions: dict[UUID, DescriptionFact]


async def _generation_facts(
    db: AsyncSession,
    menu_version_id: UUID,
) -> GenerationFacts:
    return GenerationFacts(
        categories=await _category_facts(db, menu_version_id),
        components=await _component_facts(db, menu_version_id),
        allergens=await _allergen_facts(db, menu_version_id),
        descriptions=await _description_facts(db, menu_version_id),
    )


SUPPORTED_RULE_MECHANICS = {
    "menu.category": "single_choice",
    "menu.components": "multiple_choice",
    "menu.allergens": "recognition",
    "menu.description": "recognition",
}


def _generated_candidates_for_rule(
    *,
    rule_row: QuestionGenerationRule,
    scope: GenerationScope,
    item_ids: set[UUID],
    facts: GenerationFacts,
) -> list[GeneratedCandidate]:
    if SUPPORTED_RULE_MECHANICS.get(rule_row.code) != rule_row.mechanic:
        return []

    if rule_row.code == "menu.category":
        category_facts = sorted(
            (facts.categories[item_id] for item_id in item_ids if item_id in facts.categories),
            key=lambda fact: str(fact.menu_item_version_id),
        )
        category_rule = CategoryGenerationRule(code=rule_row.code, version=rule_row.version)
        return [
            candidate
            for target in category_facts
            if (
                candidate := build_category_candidate(
                    scope,
                    category_rule,
                    target,
                    category_facts,
                )
            )
            is not None
        ]

    if rule_row.code == "menu.components":
        component_facts = sorted(
            (fact for item_id in item_ids for fact in facts.components.get(item_id, [])),
            key=lambda fact: (
                str(fact.menu_item_version_id),
                fact.position,
                str(fact.menu_item_version_component_id),
            ),
        )
        target_ids = sorted({fact.menu_item_version_id for fact in component_facts}, key=str)
        component_rule = ComponentGenerationRule(code=rule_row.code, version=rule_row.version)
        generated: list[GeneratedCandidate] = []
        for target_id in target_ids:
            component_candidate = build_component_candidate(
                scope,
                component_rule,
                target_id,
                component_facts,
            )
            missing_candidate = build_missing_component_candidate(
                scope,
                component_rule,
                target_id,
                component_facts,
            )
            if component_candidate is not None:
                generated.append(component_candidate)
            if missing_candidate is not None:
                generated.append(missing_candidate)
        return generated

    if rule_row.code == "menu.allergens":
        allergen_facts = sorted(
            (fact for item_id in item_ids for fact in facts.allergens.get(item_id, [])),
            key=lambda fact: (
                str(fact.menu_item_version_id),
                str(fact.menu_item_version_allergen_id),
            ),
        )
        target_ids = sorted({fact.menu_item_version_id for fact in allergen_facts}, key=str)
        allergen_rule = AllergenGenerationRule(code=rule_row.code, version=rule_row.version)
        return [
            candidate
            for target_id in target_ids
            if (
                candidate := build_allergen_candidate(
                    scope,
                    allergen_rule,
                    target_id,
                    allergen_facts,
                )
            )
            is not None
        ]

    description_facts = sorted(
        (facts.descriptions[item_id] for item_id in item_ids if item_id in facts.descriptions),
        key=lambda fact: str(fact.menu_item_version_id),
    )
    description_rule = DescriptionGenerationRule(code=rule_row.code, version=rule_row.version)
    return [
        candidate
        for target in description_facts
        if (
            candidate := build_description_candidate(
                scope,
                description_rule,
                target,
                description_facts,
            )
        )
        is not None
    ]


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
                QuestionGenerationRule.code.in_(SUPPORTED_RULE_MECHANICS),
                QuestionGenerationRule.status == "active",
            )
            .with_for_update()
        )
    )
    lesson_items = await _lesson_item_ids(db, training_version_id)
    facts = await _generation_facts(db, menu_version_id)
    created_count = 0
    existing_count = 0
    stale_candidate_count = 0
    stale_question_count = 0

    for rule_row in rules:
        for lesson_version_id, item_ids in lesson_items.items():
            scope = GenerationScope(
                organization_id=organization_id,
                location_id=location_id,
                menu_version_id=menu_version_id,
                training_version_id=training_version_id,
                lesson_version_id=lesson_version_id,
            )
            generated_candidates = _generated_candidates_for_rule(
                rule_row=rule_row,
                scope=scope,
                item_ids=item_ids,
                facts=facts,
            )
            current_fingerprints = {
                generated.source_fingerprint for generated in generated_candidates
            }
            for generated in generated_candidates:
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
                            menu_item_version_component_id=(source.menu_item_version_component_id),
                            menu_item_version_allergen_id=(source.menu_item_version_allergen_id),
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
        or SUPPORTED_RULE_MECHANICS.get(rule_row.code) != rule_row.mechanic
    ):
        return False
    lesson_items = await _lesson_item_ids(db, candidate.training_version_id)
    item_ids = lesson_items.get(candidate.lesson_version_id, set())
    facts = await _generation_facts(db, dependency.menu_version_id)
    generated = _generated_candidates_for_rule(
        rule_row=rule_row,
        scope=GenerationScope(
            organization_id=candidate.organization_id,
            location_id=candidate.location_id,
            menu_version_id=dependency.menu_version_id,
            training_version_id=candidate.training_version_id,
            lesson_version_id=candidate.lesson_version_id,
        ),
        item_ids=item_ids,
        facts=facts,
    )
    return candidate.source_fingerprint in {
        generated_candidate.source_fingerprint for generated_candidate in generated
    }
