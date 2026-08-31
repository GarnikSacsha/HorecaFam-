import json
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    Assessment,
    AssessmentQuestionPool,
    AssessmentReadiness,
    AssessmentVersion,
    MenuItemVersion,
    QuestionCandidate,
    QuestionGenerationRule,
    QuestionSourceLink,
    QuestionVersion,
    TrainingVersion,
)
from app.schemas.assessment import FinalExamReadinessResponse

FINAL_EXAM_QUESTION_COUNT = 20
FINAL_EXAM_ROTATION_TARGET = 40
SUPPORTED_FINAL_EXAM_FAMILIES = {
    "menu.category",
    "menu.components",
    "menu.components.missing",
    "menu.allergens",
    "menu.description",
}


@dataclass(frozen=True, slots=True)
class FinalExamPoolCandidate:
    question_version_id: UUID
    menu_item_key: str
    section_key: str
    family: str
    mechanic: str
    is_critical: bool


def derive_final_exam_readiness_state(
    eligible_count: int,
) -> tuple[str, bool, list[str], list[str]]:
    rotation_supported = eligible_count >= FINAL_EXAM_ROTATION_TARGET
    blocking_codes = (
        ["INSUFFICIENT_QUESTION_POOL"] if eligible_count < FINAL_EXAM_QUESTION_COUNT else []
    )
    warning_codes = (
        ["REPEAT_ROTATION_LIMITED"]
        if eligible_count >= FINAL_EXAM_QUESTION_COUNT and not rotation_supported
        else []
    )
    status = "blocked" if blocking_codes else "warning" if warning_codes else "ready"
    return status, rotation_supported, blocking_codes, warning_codes


def select_final_exam_questions(
    candidates: list[FinalExamPoolCandidate],
    *,
    previous_question_ids: list[UUID],
) -> list[FinalExamPoolCandidate]:
    unique = {row.question_version_id: row for row in candidates}
    if len(unique) < FINAL_EXAM_QUESTION_COUNT:
        return []

    previous = set(previous_question_ids)
    remaining = list(unique.values())
    selected: list[FinalExamPoolCandidate] = []
    used_items: set[str] = set()
    used_sections: set[str] = set()
    used_families: set[str] = set()
    used_mechanics: set[str] = set()

    while remaining and len(selected) < FINAL_EXAM_QUESTION_COUNT:

        def rank(row: FinalExamPoolCandidate) -> tuple[int, int, int, int, int, int, str]:
            return (
                0 if row.question_version_id not in previous else 1,
                0 if row.menu_item_key not in used_items else 1,
                0 if row.section_key not in used_sections else 1,
                0 if row.family not in used_families else 1,
                0 if row.mechanic not in used_mechanics else 1,
                0 if row.is_critical else 1,
                str(row.question_version_id),
            )

        chosen = min(remaining, key=rank)
        remaining.remove(chosen)
        selected.append(chosen)
        used_items.add(chosen.menu_item_key)
        used_sections.add(chosen.section_key)
        used_families.add(chosen.family)
        used_mechanics.add(chosen.mechanic)
    return selected


def _not_found() -> APIError:
    return APIError(status_code=404, code="RESOURCE_NOT_FOUND", message="Ресурс не знайдено.")


async def ensure_final_exam_readiness(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    training_version_id: UUID,
    actor_user_id: UUID,
    now: datetime,
) -> AssessmentReadiness:
    training_version = await db.scalar(
        select(TrainingVersion)
        .where(
            TrainingVersion.id == training_version_id,
            TrainingVersion.organization_id == organization_id,
            TrainingVersion.location_id == location_id,
            TrainingVersion.status == "published",
        )
        .with_for_update()
    )
    if training_version is None:
        raise _not_found()

    assessment = await db.scalar(
        select(Assessment).where(
            Assessment.training_id == training_version.training_id,
            Assessment.assessment_type == "menu_final_exam",
        )
    )
    if assessment is None:
        assessment = Assessment(
            organization_id=organization_id,
            location_id=location_id,
            training_id=training_version.training_id,
            lesson_id=None,
            assessment_type="menu_final_exam",
        )
        db.add(assessment)
        await db.flush()

    version = await db.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.assessment_id == assessment.id,
            AssessmentVersion.training_version_id == training_version_id,
            AssessmentVersion.status == "published",
        )
    )
    if version is None:
        version_number = (
            await db.scalar(
                select(func.coalesce(func.max(AssessmentVersion.version_number), 0)).where(
                    AssessmentVersion.assessment_id == assessment.id
                )
            )
            or 0
        ) + 1
        version = AssessmentVersion(
            organization_id=organization_id,
            location_id=location_id,
            assessment_id=assessment.id,
            training_version_id=training_version_id,
            lesson_id=None,
            lesson_version_id=None,
            version_number=version_number,
            status="published",
            question_count=FINAL_EXAM_QUESTION_COUNT,
            threshold_percent=70,
            feedback_policy="after_final_submission",
            sampling_configuration={
                "strategy": "balanced_coverage_first",
                "rotation_minimum": FINAL_EXAM_ROTATION_TARGET,
            },
            published_by_user_id=actor_user_id,
            published_at=now,
        )
        db.add(version)
        await db.flush()

    eligible_rows = list(
        (
            await db.execute(
                select(
                    QuestionVersion,
                    MenuItemVersion.menu_item_id,
                    MenuItemVersion.menu_version_category_id,
                    QuestionGenerationRule.code,
                )
                .join(QuestionCandidate, QuestionCandidate.id == QuestionVersion.candidate_id)
                .join(
                    QuestionGenerationRule,
                    QuestionGenerationRule.id == QuestionCandidate.generation_rule_id,
                )
                .join(
                    QuestionSourceLink,
                    (QuestionSourceLink.question_version_id == QuestionVersion.id)
                    & (QuestionSourceLink.source_role == "explanation_source"),
                )
                .join(
                    MenuItemVersion,
                    MenuItemVersion.id == QuestionSourceLink.menu_item_version_id,
                )
                .where(
                    QuestionCandidate.training_version_id == training_version_id,
                    QuestionVersion.organization_id == organization_id,
                    QuestionVersion.location_id == location_id,
                    QuestionVersion.status == "published",
                    QuestionGenerationRule.code.in_(SUPPORTED_FINAL_EXAM_FAMILIES),
                )
            )
        ).all()
    )
    current_pools = {
        row.question_version_id: row
        for row in await db.scalars(
            select(AssessmentQuestionPool).where(
                AssessmentQuestionPool.assessment_version_id == version.id
            )
        )
    }
    eligible: dict[UUID, tuple[QuestionVersion, UUID, UUID, str]] = {}
    for question, menu_item_id, category_id, family in eligible_rows:
        eligible[question.id] = (question, menu_item_id, category_id, family)
        pool = current_pools.get(question.id)
        values = {
            "coverage_key": f"menu_item:{menu_item_id}",
            "mechanic": question.mechanic,
            "eligible": True,
            "exclusion_reason": None,
        }
        if pool is None:
            db.add(
                AssessmentQuestionPool(
                    assessment_version_id=version.id,
                    question_version_id=question.id,
                    weight=1,
                    **values,
                )
            )
        else:
            for key, value in values.items():
                setattr(pool, key, value)
    for question_id, pool in current_pools.items():
        if question_id not in eligible:
            pool.eligible = False
            pool.exclusion_reason = "SOURCE_NOT_ELIGIBLE"
    await db.flush()

    candidates = [
        FinalExamPoolCandidate(
            question_version_id=question.id,
            menu_item_key=str(menu_item_id),
            section_key=str(category_id),
            family=family,
            mechanic=question.mechanic,
            is_critical=question.is_critical,
        )
        for question, menu_item_id, category_id, family in eligible.values()
    ]
    status, rotation_supported, blocking_codes, warning_codes = derive_final_exam_readiness_state(
        len(candidates)
    )
    evidence = {
        "distinct_question_count": len(candidates),
        "distinct_menu_item_count": len({row.menu_item_key for row in candidates}),
        "section_count": len({row.section_key for row in candidates}),
        "families": sorted({row.family for row in candidates}),
        "mechanics": sorted({row.mechanic for row in candidates}),
    }
    basis = json.dumps(
        [
            {
                "id": str(row.question_version_id),
                "item": row.menu_item_key,
                "section": row.section_key,
                "family": row.family,
            }
            for row in sorted(candidates, key=lambda item: str(item.question_version_id))
        ],
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    values = {
        "status": status,
        "eligible_count": len(candidates),
        "required_count": FINAL_EXAM_QUESTION_COUNT,
        "coverage_evidence": evidence,
        "rotation_supported": rotation_supported,
        "basis_fingerprint": sha256(basis).hexdigest(),
        "blocking_codes": blocking_codes,
        "warning_codes": warning_codes,
        "computed_at": now,
    }
    readiness = await db.scalar(
        select(AssessmentReadiness).where(AssessmentReadiness.assessment_version_id == version.id)
    )
    if readiness is None:
        readiness = AssessmentReadiness(assessment_version_id=version.id, **values)
        db.add(readiness)
    else:
        for key, value in values.items():
            setattr(readiness, key, value)
    await db.flush()
    return readiness


async def get_final_exam_readiness(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    training_version_id: UUID,
) -> FinalExamReadinessResponse:
    training_version = await db.scalar(
        select(TrainingVersion).where(
            TrainingVersion.id == training_version_id,
            TrainingVersion.organization_id == organization_id,
            TrainingVersion.location_id == location_id,
        )
    )
    if training_version is None:
        raise _not_found()
    row = (
        await db.execute(
            select(AssessmentVersion, AssessmentReadiness)
            .join(Assessment, Assessment.id == AssessmentVersion.assessment_id)
            .join(
                AssessmentReadiness,
                AssessmentReadiness.assessment_version_id == AssessmentVersion.id,
            )
            .where(
                AssessmentVersion.training_version_id == training_version_id,
                AssessmentVersion.status == "published",
                Assessment.assessment_type == "menu_final_exam",
            )
            .order_by(AssessmentVersion.version_number.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return FinalExamReadinessResponse(
            training_version_id=training_version_id,
            assessment_version_id=None,
            status="processing",
            eligible_count=0,
            coverage_evidence={"distinct_question_count": 0},
            rotation_supported=False,
            basis_fingerprint=None,
            blocking_codes=["ASSESSMENT_NOT_CONFIGURED"],
            warning_codes=[],
            computed_at=None,
            can_start=False,
        )
    assessment_version, readiness = row._tuple()
    return FinalExamReadinessResponse(
        training_version_id=training_version_id,
        assessment_version_id=assessment_version.id,
        status=cast(Literal["processing", "ready", "warning", "blocked"], readiness.status),
        eligible_count=readiness.eligible_count,
        coverage_evidence=readiness.coverage_evidence,
        rotation_supported=readiness.rotation_supported,
        basis_fingerprint=readiness.basis_fingerprint,
        blocking_codes=readiness.blocking_codes,
        warning_codes=readiness.warning_codes,
        computed_at=readiness.computed_at,
        can_start=readiness.status in {"ready", "warning"},
    )
