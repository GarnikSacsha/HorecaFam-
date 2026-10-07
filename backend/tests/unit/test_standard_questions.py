from uuid import uuid4

import pytest

from app.models import StandardRuleVersion
from app.services.standard_questions import build_standard_candidate


def source_rule() -> StandardRuleVersion:
    return StandardRuleVersion(
        id=uuid4(),
        organization_id=uuid4(),
        location_id=uuid4(),
        standard_set_id=uuid4(),
        standard_set_version_id=uuid4(),
        standard_rule_id=uuid4(),
        position=0,
        scenario_uk="Гість повідомив про алергію. Яка дія безпечна?",
        allowed_action_uk="Передати інформацію відповідальному та уточнити склад.",
        prohibited_actions_uk=["Вгадати склад страви.", "Пообіцяти безпеку без перевірки."],
        conditions_uk=[],
        action_order_uk=[],
        explanation_uk="Не можна гарантувати безпеку без перевіреної інформації.",
        provenance={"source": "approved generic training"},
        verified=True,
        is_critical=True,
    )


def test_verified_standard_generates_deterministic_source_bound_candidate() -> None:
    source = source_rule()
    scope = dict(training_version_id=uuid4(), lesson_version_id=uuid4())
    candidate = build_standard_candidate(source, **scope)
    assert candidate is not None
    assert candidate == build_standard_candidate(source, **scope)
    assert candidate.mechanic == "single_choice"
    assert len(candidate.prompt_payload.options) == 3
    assert len(candidate.answer_payload.correct_option_keys) == 1
    source.provenance = {"source": "different approved source"}
    changed = build_standard_candidate(source, **scope)
    assert changed is not None
    assert candidate.source_fingerprint != changed.source_fingerprint


@pytest.mark.parametrize(
    "field,value",
    [
        ("verified", False),
        ("scenario_uk", None),
        ("allowed_action_uk", ""),
        ("prohibited_actions_uk", []),
        ("explanation_uk", None),
        ("provenance", {}),
        ("prohibited_actions_uk", ["Одна дія.", "Одна дія."]),
    ],
)
def test_incomplete_or_unverified_standard_never_generates(field: str, value: object) -> None:
    source = source_rule()
    setattr(source, field, value)
    assert (
        build_standard_candidate(
            source,
            training_version_id=uuid4(),
            lesson_version_id=uuid4(),
        )
        is None
    )
