import pytest

from app.services.final_exam_readiness import derive_final_exam_readiness_state
from app.services.question_review import derive_readiness_state


@pytest.mark.parametrize(
    ("eligible_count", "expected"),
    [
        (0, ("blocked", False, ["INSUFFICIENT_QUESTION_POOL"], [])),
        (4, ("blocked", False, ["INSUFFICIENT_QUESTION_POOL"], [])),
        (5, ("warning", False, [], ["REPEAT_ROTATION_LIMITED"])),
        (9, ("warning", False, [], ["REPEAT_ROTATION_LIMITED"])),
        (10, ("ready", True, [], [])),
    ],
)
def test_readiness_state_requires_one_attempt_then_rotation(
    eligible_count: int,
    expected: tuple[str, bool, list[str], list[str]],
) -> None:
    assert derive_readiness_state(eligible_count) == expected


@pytest.mark.parametrize(
    ("distinct_item_count", "expected"),
    [
        (9, ("blocked", False, ["INSUFFICIENT_QUESTION_POOL"], [])),
        (10, ("warning", False, [], ["REPEAT_ROTATION_LIMITED"])),
        (19, ("warning", False, [], ["REPEAT_ROTATION_LIMITED"])),
        (20, ("ready", True, [], [])),
    ],
)
def test_practice_readiness_requires_ten_distinct_menu_items(
    distinct_item_count: int,
    expected: tuple[str, bool, list[str], list[str]],
) -> None:
    assert derive_readiness_state(distinct_item_count, required_count=10) == expected


@pytest.mark.parametrize(
    ("eligible_count", "expected"),
    [
        (19, ("blocked", False, ["INSUFFICIENT_QUESTION_POOL"], [])),
        (20, ("warning", False, [], ["REPEAT_ROTATION_LIMITED"])),
        (39, ("warning", False, [], ["REPEAT_ROTATION_LIMITED"])),
        (40, ("ready", True, [], [])),
    ],
)
def test_final_exam_readiness_requires_twenty_questions_and_targets_forty(
    eligible_count: int,
    expected: tuple[str, bool, list[str], list[str]],
) -> None:
    assert derive_final_exam_readiness_state(eligible_count) == expected
