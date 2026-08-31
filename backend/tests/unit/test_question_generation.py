from uuid import uuid4

import pytest

from app.schemas.assessment import (
    AllergenFact,
    AllergenGenerationRule,
    CategoryFact,
    CategoryGenerationRule,
    ComponentFact,
    ComponentGenerationRule,
    DescriptionFact,
    DescriptionGenerationRule,
    GenerationScope,
)
from app.services.question_generation import (
    build_allergen_candidate,
    build_category_candidate,
    build_component_candidate,
    build_description_candidate,
    build_missing_component_candidate,
)


def _fact(*, name: str, category: str, price_minor: int = 1000) -> CategoryFact:
    return CategoryFact(
        menu_item_version_id=uuid4(),
        menu_item_id=uuid4(),
        item_name=name,
        menu_version_category_id=uuid4(),
        category_name=category,
        price_minor=price_minor,
        verified=True,
    )


def test_category_generation_is_deterministic_and_price_independent() -> None:
    scope = GenerationScope(
        organization_id=uuid4(),
        location_id=uuid4(),
        menu_version_id=uuid4(),
        training_version_id=uuid4(),
        lesson_version_id=uuid4(),
    )
    rule = CategoryGenerationRule(code="menu.category", version=1)
    target = _fact(name="Борщ", category="Супи")
    distractor = _fact(name="Цезар", category="Салати")

    first = build_category_candidate(scope, rule, target, [target, distractor])
    changed_price = target.model_copy(update={"price_minor": 9999})
    second = build_category_candidate(scope, rule, changed_price, [changed_price, distractor])

    assert first is not None
    assert second is not None
    assert first.source_fingerprint == second.source_fingerprint
    assert first.prompt_payload == second.prompt_payload
    assert first.answer_payload == second.answer_payload
    assert {source.menu_item_version_id for source in first.sources} == {
        target.menu_item_version_id,
        distractor.menu_item_version_id,
    }


@pytest.mark.parametrize(
    ("target_update", "other_update"),
    [
        ({"verified": False}, {}),
        ({"category_name": "Супи"}, {"category_name": "супи"}),
        ({"item_name": "   "}, {}),
    ],
)
def test_category_generation_skips_unsupported_or_ambiguous_facts(
    target_update: dict[str, object],
    other_update: dict[str, object],
) -> None:
    scope = GenerationScope(
        organization_id=uuid4(),
        location_id=uuid4(),
        menu_version_id=uuid4(),
        training_version_id=uuid4(),
        lesson_version_id=uuid4(),
    )
    rule = CategoryGenerationRule(code="menu.category", version=1)
    target = _fact(name="Борщ", category="Супи").model_copy(update=target_update)
    other = _fact(name="Цезар", category="Салати").model_copy(update=other_update)

    assert build_category_candidate(scope, rule, target, [target, other]) is None


def _scope() -> GenerationScope:
    return GenerationScope(
        organization_id=uuid4(),
        location_id=uuid4(),
        menu_version_id=uuid4(),
        training_version_id=uuid4(),
        lesson_version_id=uuid4(),
    )


def test_component_generation_uses_only_verified_target_components() -> None:
    target_item_version_id = uuid4()
    other_item_version_id = uuid4()
    beet = ComponentFact(
        menu_item_version_component_id=uuid4(),
        menu_component_version_id=uuid4(),
        menu_item_version_id=target_item_version_id,
        menu_item_id=uuid4(),
        item_name="Борщ",
        component_name="Буряк",
        position=0,
        verified=True,
    )
    cabbage = beet.model_copy(
        update={
            "menu_item_version_component_id": uuid4(),
            "menu_component_version_id": uuid4(),
            "component_name": "Капуста",
            "position": 1,
        }
    )
    parmesan = beet.model_copy(
        update={
            "menu_item_version_component_id": uuid4(),
            "menu_component_version_id": uuid4(),
            "menu_item_version_id": other_item_version_id,
            "menu_item_id": uuid4(),
            "item_name": "Цезар",
            "component_name": "Пармезан",
            "position": 0,
        }
    )

    candidate = build_component_candidate(
        _scope(),
        ComponentGenerationRule(code="menu.components", version=1),
        target_item_version_id,
        [beet, cabbage, parmesan],
    )

    assert candidate is not None
    assert candidate.mechanic == "multiple_choice"
    assert set(candidate.answer_payload.correct_option_keys) == {
        f"component:{beet.menu_component_version_id}",
        f"component:{cabbage.menu_component_version_id}",
    }
    assert {
        source.menu_item_version_component_id
        for source in candidate.sources
        if source.menu_item_version_component_id is not None
    } == {
        beet.menu_item_version_component_id,
        cabbage.menu_item_version_component_id,
        parmesan.menu_item_version_component_id,
    }


@pytest.mark.parametrize("unsupported", ["unverified", "no_distractor", "ambiguous"])
def test_component_generation_skips_unsupported_facts(unsupported: str) -> None:
    target_item_version_id = uuid4()
    base = ComponentFact(
        menu_item_version_component_id=uuid4(),
        menu_component_version_id=uuid4(),
        menu_item_version_id=target_item_version_id,
        menu_item_id=uuid4(),
        item_name="Борщ",
        component_name="Буряк",
        position=0,
        verified=unsupported != "unverified",
    )
    second = base.model_copy(
        update={
            "menu_item_version_component_id": uuid4(),
            "menu_component_version_id": uuid4(),
            "component_name": "Капуста",
            "position": 1,
        }
    )
    other = base.model_copy(
        update={
            "menu_item_version_component_id": uuid4(),
            "menu_component_version_id": uuid4(),
            "menu_item_version_id": uuid4(),
            "menu_item_id": uuid4(),
            "item_name": "Цезар",
            "component_name": "Пармезан",
        }
    )
    facts = [base, second]
    if unsupported != "no_distractor":
        facts.append(other)
    if unsupported == "ambiguous":
        facts.append(
            other.model_copy(
                update={
                    "menu_item_version_component_id": uuid4(),
                    "menu_component_version_id": uuid4(),
                    "component_name": "пармезан",
                }
            )
        )

    assert (
        build_component_candidate(
            _scope(),
            ComponentGenerationRule(code="menu.components", version=1),
            target_item_version_id,
            facts,
        )
        is None
    )


def test_allergen_generation_requires_confirmed_verified_links() -> None:
    target_item_version_id = uuid4()
    gluten = AllergenFact(
        menu_item_version_allergen_id=uuid4(),
        allergen_id=uuid4(),
        menu_item_version_id=target_item_version_id,
        menu_item_id=uuid4(),
        item_name="Паста",
        allergen_name="Глютен",
        verified=True,
    )
    lactose = gluten.model_copy(
        update={
            "menu_item_version_allergen_id": uuid4(),
            "allergen_id": uuid4(),
            "menu_item_version_id": uuid4(),
            "menu_item_id": uuid4(),
            "item_name": "Десерт",
            "allergen_name": "Лактоза",
        }
    )

    candidate = build_allergen_candidate(
        _scope(),
        AllergenGenerationRule(code="menu.allergens", version=1),
        target_item_version_id,
        [gluten, lactose],
    )

    assert candidate is not None
    assert candidate.mechanic == "recognition"
    assert candidate.answer_payload.correct_option_keys == [f"allergen:{gluten.allergen_id}"]
    assert (
        build_allergen_candidate(
            _scope(),
            AllergenGenerationRule(code="menu.allergens", version=1),
            target_item_version_id,
            [gluten.model_copy(update={"verified": False}), lactose],
        )
        is None
    )


def test_description_generation_rejects_duplicate_descriptions() -> None:
    target = DescriptionFact(
        menu_item_version_id=uuid4(),
        menu_item_id=uuid4(),
        item_name="Борщ",
        description="Традиційний суп з буряком",
        verified=True,
    )
    other = DescriptionFact(
        menu_item_version_id=uuid4(),
        menu_item_id=uuid4(),
        item_name="Цезар",
        description="Салат з куркою та пармезаном",
        verified=True,
    )
    rule = DescriptionGenerationRule(code="menu.description", version=1)

    candidate = build_description_candidate(_scope(), rule, target, [target, other])

    assert candidate is not None
    assert candidate.mechanic == "recognition"
    assert candidate.answer_payload.correct_option_keys == [f"item:{target.menu_item_version_id}"]
    assert (
        build_description_candidate(
            _scope(),
            rule,
            target,
            [target, other.model_copy(update={"description": target.description.casefold()})],
        )
        is None
    )


def test_missing_component_generation_uses_complete_verified_component_sets() -> None:
    target_item_version_id = uuid4()
    included = ComponentFact(
        menu_item_version_component_id=uuid4(),
        menu_component_version_id=uuid4(),
        menu_item_version_id=target_item_version_id,
        menu_item_id=uuid4(),
        item_name="Борщ",
        component_name="Буряк",
        position=0,
        verified=True,
    )
    missing = included.model_copy(
        update={
            "menu_item_version_component_id": uuid4(),
            "menu_component_version_id": uuid4(),
            "menu_item_version_id": uuid4(),
            "menu_item_id": uuid4(),
            "item_name": "Цезар",
            "component_name": "Пармезан",
        }
    )

    candidate = build_missing_component_candidate(
        _scope(),
        ComponentGenerationRule(code="menu.components", version=1),
        target_item_version_id,
        [included, missing],
    )

    assert candidate is not None
    assert candidate.answer_payload.correct_option_keys == [
        f"component:{missing.menu_component_version_id}"
    ]
    assert (
        candidate.sources[0].menu_item_version_component_id
        == missing.menu_item_version_component_id
    )
    assert (
        build_missing_component_candidate(
            _scope(),
            ComponentGenerationRule(code="menu.components", version=1),
            target_item_version_id,
            [included, missing.model_copy(update={"verified": False})],
        )
        is None
    )
