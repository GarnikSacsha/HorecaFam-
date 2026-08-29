import pytest

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
