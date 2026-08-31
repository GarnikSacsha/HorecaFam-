from uuid import uuid4

from app.services.final_exam_readiness import FinalExamPoolCandidate, select_final_exam_questions
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


def test_final_exam_selection_is_unique_balanced_and_minimizes_repeat_overlap() -> None:
    rows = [
        FinalExamPoolCandidate(
            question_version_id=uuid4(),
            menu_item_key=f"item-{index % 24}",
            section_key=f"section-{index % 4}",
            family=f"family-{index % 5}",
            mechanic="single_choice" if index % 2 == 0 else "recognition",
            is_critical=index % 7 == 0,
        )
        for index in range(40)
    ]

    first = select_final_exam_questions(rows, previous_question_ids=[])
    second = select_final_exam_questions(
        rows,
        previous_question_ids=[row.question_version_id for row in first],
    )

    assert len(first) == len(second) == 20
    assert len({row.question_version_id for row in first}) == 20
    assert len({row.menu_item_key for row in first}) >= 16
    assert len({row.section_key for row in first}) == 4
    assert len({row.family for row in first}) == 5
    assert not (
        {row.question_version_id for row in first} & {row.question_version_id for row in second}
    )


def test_final_exam_selection_blocks_when_fewer_than_twenty_versions_exist() -> None:
    rows = [
        FinalExamPoolCandidate(
            question_version_id=uuid4(),
            menu_item_key=f"item-{index}",
            section_key="section",
            family="menu.components",
            mechanic="multiple_choice",
            is_critical=False,
        )
        for index in range(19)
    ]

    assert select_final_exam_questions(rows, previous_question_ids=[]) == []
