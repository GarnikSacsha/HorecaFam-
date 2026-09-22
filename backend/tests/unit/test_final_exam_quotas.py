from collections import Counter
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.assessment import FinalExamQuotaPolicy
from app.services.final_exam_readiness import (
    FinalExamPoolCandidate,
    quota_readiness,
    required_question_replacement_index,
    select_final_exam_questions,
)


def quota_fixture() -> tuple[list[FinalExamPoolCandidate], FinalExamQuotaPolicy]:
    candidates = [
        FinalExamPoolCandidate(
            UUID(int=100 + group * 100 + index),
            str(index),
            str(UUID(int=group + 1)),
            "menu.description.authored",
            "recognition",
            False,
        )
        for group, count in enumerate((30, 12, 8, 10))
        for index in range(count)
    ]
    policy = FinalExamQuotaPolicy.model_validate(
        {
            "question_version_ids": [row.question_version_id for row in candidates],
            "buckets": [
                {"key": key, "count": count, "category_ids": [UUID(int=index + 1)]}
                for index, (key, count) in enumerate(
                    (("food", 10), ("drinks", 4), ("desserts", 3), ("other", 3))
                )
            ],
        }
    )
    return candidates, policy


def test_exact_quotas_rotate_without_repeating_previous_attempt() -> None:
    candidates, policy = quota_fixture()
    previous: list[UUID] = []
    usage: Counter[UUID] = Counter()
    for _ in range(6):
        selected = select_final_exam_questions(
            candidates, previous_question_ids=previous, policy=policy, question_usage=dict(usage)
        )
        assert len(selected) == 20
        assert Counter(row.section_key for row in selected) == {
            str(UUID(int=index + 1)): count for index, count in enumerate((10, 4, 3, 3))
        }
        assert not set(previous) & {row.question_version_id for row in selected}
        previous = [row.question_version_id for row in selected]
        usage.update(previous)
    assert len(usage) == len(candidates)
    assert quota_readiness(candidates, policy) == ("ready", True, [], [])


def test_large_total_cannot_hide_bucket_shortage_or_duplicate_questions() -> None:
    candidates, policy = quota_fixture()
    reduced = [row for row in candidates if row.section_key != str(UUID(int=3))]
    assert len(reduced) > 40
    assert select_final_exam_questions(reduced * 3, previous_question_ids=[], policy=policy) == []
    assert quota_readiness(reduced, policy) == ("blocked", False, ["INSUFFICIENT_BUCKET_POOL"], [])


def test_limited_rotation_warns_and_unlisted_questions_are_excluded() -> None:
    candidates, policy = quota_fixture()
    selected = select_final_exam_questions(candidates, previous_question_ids=[], policy=policy)
    assert quota_readiness(selected, policy) == ("warning", False, [], ["REPEAT_ROTATION_LIMITED"])
    policy.question_version_ids = [row.question_version_id for row in selected]
    assert set(
        select_final_exam_questions(candidates, previous_question_ids=[], policy=policy)
    ) == set(selected)


def test_overlapping_categories_are_rejected() -> None:
    _, policy = quota_fixture()
    payload = policy.model_dump(mode="json")
    payload["buckets"][1]["category_ids"] = payload["buckets"][0]["category_ids"]
    with pytest.raises(ValidationError):
        FinalExamQuotaPolicy.model_validate(payload)


def test_critical_retake_replacement_keeps_its_bucket_and_rejects_unmapped_target() -> None:
    candidates, policy = quota_fixture()
    selected = select_final_exam_questions(candidates, previous_question_ids=[], policy=policy)
    required = candidates[20]
    assert required not in selected
    index = required_question_replacement_index(selected, required, policy)
    assert index >= 0 and selected[index].section_key == required.section_key
    before = Counter(row.section_key for row in selected)
    selected[index] = required
    assert Counter(row.section_key for row in selected) == before
    unavailable = FinalExamPoolCandidate(
        UUID(int=9999), "unknown", "unmapped", "menu.allergens", "recognition", True
    )
    assert required_question_replacement_index(selected, unavailable, policy) == -1
    assert required_question_replacement_index([], required, policy) == -1
