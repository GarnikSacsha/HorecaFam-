from uuid import uuid4

from app.services.interactive_attempts import PoolCandidate, select_attempt_questions


def test_selection_is_coverage_first_and_rotates_when_pool_allows() -> None:
    rows = [
        PoolCandidate(
            question_version_id=uuid4(),
            coverage_key=f"item-{index // 2}",
            mechanic="single_choice",
        )
        for index in range(12)
    ]

    first = select_attempt_questions(rows, previous_order=[])
    second = select_attempt_questions(
        rows,
        previous_order=[row.question_version_id for row in first],
    )

    assert len(first) == 5
    assert len({row.question_version_id for row in first}) == 5
    assert len({row.coverage_key for row in first}) == 5
    assert [row.question_version_id for row in second] != [row.question_version_id for row in first]


def test_practice_selection_requires_ten_distinct_menu_items() -> None:
    rows = [
        PoolCandidate(
            question_version_id=uuid4(),
            coverage_key=f"menu-item-{index}",
            mechanic="multiple_choice",
        )
        for index in range(10)
    ]

    selected = select_attempt_questions(rows, previous_order=[], question_count=10)

    assert len(selected) == 10
    assert len({row.coverage_key for row in selected}) == 10
    assert select_attempt_questions(rows[:9], previous_order=[], question_count=10) == []
