from uuid import uuid4

import pytest

from app.core.errors import APIError
from app.models import AttemptOption, AttemptQuestion
from app.schemas.assessment import (
    MatchingPairSubmission,
    MatchingSubmission,
    MultipleChoiceSubmission,
    OrderingSubmission,
    SingleChoiceSubmission,
)
from app.services.interactive_answers import (
    _grade_payload,
    _selected_ids,
    grade_selected_options,
    knowledge_level,
)


def test_single_and_multiple_choice_grading_uses_snapshot_option_ids() -> None:
    correct = {uuid4(), uuid4()}
    wrong = uuid4()

    assert grade_selected_options("multiple_choice", correct, correct, [*correct, wrong]) is True
    assert (
        grade_selected_options("multiple_choice", {next(iter(correct))}, correct, [*correct])
        is False
    )
    only = next(iter(correct))
    assert grade_selected_options("single_choice", {only}, {only}, [only, wrong]) is True
    assert grade_selected_options("single_choice", {wrong}, {only}, [only, wrong]) is False


def _question(mechanic: str, grading_payload: dict[str, object]) -> AttemptQuestion:
    return AttemptQuestion(
        id=uuid4(),
        attempt_id=uuid4(),
        question_version_id=uuid4(),
        position=0,
        mechanic=mechanic,
        prompt_payload={},
        grading_payload=grading_payload,
        explanation_payload={},
        is_critical=False,
        coverage_key="menu-item-1",
        presentation_locale="uk",
        provenance_snapshot={},
        version_snapshot={},
    )


def _option(stable_key: str, *, is_correct: bool = False) -> AttemptOption:
    return AttemptOption(
        id=uuid4(),
        attempt_question_id=uuid4(),
        source_option_id=uuid4(),
        position=0,
        payload={"stable_key": stable_key},
        is_correct=is_correct,
    )


def test_payload_selection_supports_every_interactive_shape() -> None:
    first = uuid4()
    second = uuid4()
    assert _selected_ids(SingleChoiceSubmission(mechanic="single_choice", option_id=first)) == {
        first
    }
    assert _selected_ids(
        MultipleChoiceSubmission(mechanic="recognition", option_ids=[first, second])
    ) == {first, second}
    assert _selected_ids(OrderingSubmission(mechanic="assembly", option_ids=[first, second])) == {
        first,
        second,
    }
    assert _selected_ids(
        MatchingSubmission(
            mechanic="matching",
            pairs=[MatchingPairSubmission(left_option_id=first, right_option_id=second)],
        )
    ) == {first, second}


def test_ordering_grading_requires_the_complete_snapshot_sequence() -> None:
    first = _option("first")
    second = _option("second")
    question = _question("ordering", {"correct_option_keys": ["first", "second"]})

    assert (
        _grade_payload(
            question,
            OrderingSubmission(mechanic="ordering", option_ids=[first.id, second.id]),
            [first, second],
        )
        is True
    )
    assert (
        _grade_payload(
            question,
            OrderingSubmission(mechanic="ordering", option_ids=[second.id, first.id]),
            [first, second],
        )
        is False
    )
    assert (
        _grade_payload(
            question,
            OrderingSubmission(mechanic="ordering", option_ids=[first.id, second.id]),
            [first, second, _option("third")],
        )
        is False
    )


def test_matching_grading_compares_snapshot_pairs() -> None:
    left = _option("soup")
    right = _option("borshch")
    payload = MatchingSubmission(
        mechanic="matching",
        pairs=[MatchingPairSubmission(left_option_id=left.id, right_option_id=right.id)],
    )

    assert (
        _grade_payload(
            _question("matching", {"correct_pairs": [["soup", "borshch"]]}),
            payload,
            [left, right],
        )
        is True
    )
    assert _grade_payload(_question("matching", {}), payload, [left, right]) is False


def test_payload_grading_rejects_wrong_mechanic_and_foreign_option() -> None:
    option = _option("answer", is_correct=True)
    question = _question("single_choice", {"correct_option_keys": ["answer"]})

    with pytest.raises(APIError) as wrong_mechanic:
        _grade_payload(
            question,
            MultipleChoiceSubmission(mechanic="multiple_choice", option_ids=[option.id]),
            [option],
        )
    assert wrong_mechanic.value.code == "ANSWER_PAYLOAD_INVALID"

    with pytest.raises(APIError) as foreign_option:
        _grade_payload(
            question,
            SingleChoiceSubmission(mechanic="single_choice", option_id=uuid4()),
            [option],
        )
    assert foreign_option.value.code == "RESOURCE_NOT_FOUND"


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, "very_weak"),
        (3999, "very_weak"),
        (4000, "weak"),
        (5999, "weak"),
        (6000, "good"),
        (7999, "good"),
        (8000, "strong"),
        (10000, "strong"),
    ],
)
def test_knowledge_level_boundaries(score: int, expected: str) -> None:
    assert knowledge_level(score) == expected
