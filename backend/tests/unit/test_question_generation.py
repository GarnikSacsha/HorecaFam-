from uuid import uuid4

import pytest

from app.schemas.assessment import (
    CategoryFact,
    CategoryGenerationRule,
    GenerationScope,
)
from app.services.question_generation import build_category_candidate


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
