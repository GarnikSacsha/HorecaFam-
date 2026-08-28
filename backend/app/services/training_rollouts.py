import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    AuditEvent,
    LessonCompletion,
    LessonContentBlock,
    LessonTranslation,
    LessonVersion,
    RolloutEmployeeImpact,
    RolloutLessonRuleRecord,
    Training,
    TrainingAssignment,
    TrainingModuleVersion,
    TrainingRollout,
    TrainingVersion,
)
from app.schemas.training import (
    TrainingRolloutEmployeeImpactResponse,
    TrainingRolloutImpactCounts,
    TrainingRolloutLessonRuleResponse,
    TrainingRolloutResponse,
    TrainingRolloutVersionSummary,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)

type _RuleValue = Literal[
    "preserve_completion",
    "needs_repeat",
    "new_incomplete",
    "removed_historical",
]
type _VersionStatus = Literal["published", "archived"]
type _RolloutStatus = Literal[
    "draft",
    "preview_ready",
    "confirmed",
    "processing",
    "completed",
    "failed",
    "cancelled",
    "stale",
]


@dataclass(frozen=True)
class _LessonSnapshot:
    version_id: UUID
    required: bool
    signature: str


@dataclass(frozen=True)
class _RuleSpec:
    lesson_id: UUID
    from_lesson_version_id: UUID | None
    to_lesson_version_id: UUID | None
    rule: str | None
    requires_admin_decision: bool


def _not_found() -> APIError:
    return APIError(
        status_code=404,
        code="RESOURCE_NOT_FOUND",
        message="Ресурс не знайдено.",
    )


def _revision_conflict() -> APIError:
    return APIError(
        status_code=409,
        code="REVISION_CONFLICT",
        message="Rollout уже змінено. Оновіть дані та повторіть дію.",
    )


def _version_invalid() -> APIError:
    return APIError(
        status_code=409,
        code="ROLLOUT_VERSION_INVALID",
        message="Версії навчання не утворюють дозволений Rollout.",
    )


def _rollout_exists() -> APIError:
    return APIError(
        status_code=409,
        code="TRAINING_ROLLOUT_EXISTS",
        message="Активний Rollout для цих версій уже існує.",
    )


def _canonical_hash(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _scoped_rollout(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    rollout_id: UUID,
    lock: bool = False,
) -> TrainingRollout:
    query = select(TrainingRollout).where(
        TrainingRollout.id == rollout_id,
        TrainingRollout.organization_id == organization_id,
        TrainingRollout.location_id == location_id,
    )
    if lock:
        query = query.with_for_update()
    rollout = await db.scalar(query)
    if rollout is None:
        raise _not_found()
    return rollout


async def _validated_versions(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    from_version_id: UUID,
    to_version_id: UUID,
    lock: bool,
) -> tuple[TrainingVersion, TrainingVersion]:
    query = (
        select(TrainingVersion)
        .where(
            TrainingVersion.id.in_((from_version_id, to_version_id)),
            TrainingVersion.organization_id == organization_id,
            TrainingVersion.location_id == location_id,
        )
        .order_by(TrainingVersion.id)
    )
    if lock:
        query = query.with_for_update()
    versions = {row.id: row for row in (await db.scalars(query)).all()}
    source = versions.get(from_version_id)
    target = versions.get(to_version_id)
    if source is None or target is None:
        raise _not_found()
    if (
        source.id == target.id
        or source.training_id != target.training_id
        or source.status != "archived"
        or target.status != "published"
        or target.base_version_id != source.id
    ):
        raise _version_invalid()
    return source, target


async def _lesson_snapshots(
    db: AsyncSession,
    *,
    training_version_id: UUID,
) -> dict[UUID, _LessonSnapshot]:
    lessons = list(
        (
            await db.scalars(
                select(LessonVersion)
                .join(
                    TrainingModuleVersion,
                    TrainingModuleVersion.id == LessonVersion.training_module_version_id,
                )
                .where(TrainingModuleVersion.training_version_id == training_version_id)
                .order_by(LessonVersion.lesson_id)
            )
        ).all()
    )
    if not lessons:
        return {}
    lesson_version_ids = [lesson.id for lesson in lessons]
    translations = {
        row.lesson_version_id: row
        for row in (
            await db.scalars(
                select(LessonTranslation).where(
                    LessonTranslation.lesson_version_id.in_(lesson_version_ids),
                    LessonTranslation.locale == "uk",
                )
            )
        ).all()
    }
    blocks_by_lesson: dict[UUID, list[LessonContentBlock]] = {
        lesson_version_id: [] for lesson_version_id in lesson_version_ids
    }
    for block in (
        await db.scalars(
            select(LessonContentBlock)
            .where(LessonContentBlock.lesson_version_id.in_(lesson_version_ids))
            .order_by(LessonContentBlock.lesson_version_id, LessonContentBlock.position)
        )
    ).all():
        blocks_by_lesson[block.lesson_version_id].append(block)
    snapshots: dict[UUID, _LessonSnapshot] = {}
    for lesson in lessons:
        translation = translations.get(lesson.id)
        signature = _canonical_hash(
            {
                "required": lesson.required,
                "estimated_minutes": lesson.estimated_minutes,
                "translation": (
                    {
                        "title": translation.title,
                        "description": translation.description,
                    }
                    if translation is not None
                    else None
                ),
                "blocks": [
                    {
                        "position": block.position,
                        "type": block.type,
                        "payload": block.payload,
                        "menu_item_id": str(block.menu_item_id) if block.menu_item_id else None,
                        "asset_id": str(block.asset_id) if block.asset_id else None,
                    }
                    for block in blocks_by_lesson[lesson.id]
                ],
            }
        )
        snapshots[lesson.lesson_id] = _LessonSnapshot(
            version_id=lesson.id,
            required=lesson.required,
            signature=signature,
        )
    return snapshots


async def _rule_specs(
    db: AsyncSession,
    *,
    from_version_id: UUID,
    to_version_id: UUID,
) -> list[_RuleSpec]:
    source = await _lesson_snapshots(db, training_version_id=from_version_id)
    target = await _lesson_snapshots(db, training_version_id=to_version_id)
    specs: list[_RuleSpec] = []
    for lesson_id in sorted(source.keys() | target.keys(), key=str):
        before = source.get(lesson_id)
        after = target.get(lesson_id)
        if before is None and after is not None:
            specs.append(_RuleSpec(lesson_id, None, after.version_id, "new_incomplete", False))
        elif before is not None and after is None:
            specs.append(_RuleSpec(lesson_id, before.version_id, None, "removed_historical", False))
        elif before is not None and after is not None:
            unchanged = before.signature == after.signature
            specs.append(
                _RuleSpec(
                    lesson_id,
                    before.version_id,
                    after.version_id,
                    "preserve_completion" if unchanged else None,
                    not unchanged,
                )
            )
    return specs


async def _source_assignments(
    db: AsyncSession,
    *,
    rollout: TrainingRollout,
    lock: bool,
) -> list[TrainingAssignment]:
    query = (
        select(TrainingAssignment)
        .where(
            TrainingAssignment.organization_id == rollout.organization_id,
            TrainingAssignment.location_id == rollout.location_id,
            TrainingAssignment.training_id == rollout.training_id,
            TrainingAssignment.training_version_id == rollout.from_version_id,
            TrainingAssignment.status != "revoked",
        )
        .order_by(TrainingAssignment.id)
    )
    if lock:
        query = query.with_for_update()
    return list((await db.scalars(query)).all())


async def _completions_by_assignment(
    db: AsyncSession,
    assignments: list[TrainingAssignment],
) -> dict[UUID, set[UUID]]:
    result: dict[UUID, set[UUID]] = {assignment.id: set() for assignment in assignments}
    if not assignments:
        return result
    rows = (
        await db.execute(
            select(LessonCompletion.assignment_id, LessonCompletion.lesson_id)
            .where(LessonCompletion.assignment_id.in_(result))
            .order_by(LessonCompletion.assignment_id, LessonCompletion.lesson_id)
        )
    ).tuples()
    for assignment_id, lesson_id in rows:
        result[assignment_id].add(lesson_id)
    return result


def _source_fingerprint(
    assignments: list[TrainingAssignment],
    completions: dict[UUID, set[UUID]],
) -> str:
    return _canonical_hash(
        [
            {
                "assignment_id": str(assignment.id),
                "employee_profile_id": str(assignment.employee_profile_id),
                "status": assignment.status,
                "completion_lesson_ids": [
                    str(lesson_id) for lesson_id in sorted(completions[assignment.id], key=str)
                ],
            }
            for assignment in assignments
        ]
    )


def _rule_response(rule: RolloutLessonRuleRecord) -> TrainingRolloutLessonRuleResponse:
    return TrainingRolloutLessonRuleResponse(
        lesson_id=rule.lesson_id,
        from_lesson_version_id=rule.from_lesson_version_id,
        to_lesson_version_id=rule.to_lesson_version_id,
        rule=cast(_RuleValue | None, rule.rule),
        requires_admin_decision=rule.requires_admin_decision,
        decided_by_user_id=rule.decided_by_user_id,
        decided_at=rule.decided_at,
    )


def _impact_response(impact: RolloutEmployeeImpact) -> TrainingRolloutEmployeeImpactResponse:
    return TrainingRolloutEmployeeImpactResponse(
        employee_profile_id=impact.employee_profile_id,
        source_assignment_id=impact.source_assignment_id,
        current_required_count=impact.current_required_count,
        current_completed_count=impact.current_completed_count,
        current_progress_percentage=impact.current_progress_percentage,
        projected_required_count=impact.projected_required_count,
        projected_completed_count=impact.projected_completed_count,
        projected_progress_percentage=impact.projected_progress_percentage,
        lesson_impact={
            key: [UUID(value) for value in impact.lesson_impact[key]]
            for key in ("preserved", "repeat", "new", "removed")
        },
        validation_codes=list(impact.validation_codes),
        warning_codes=list(impact.warning_codes),
    )


async def _rollout_is_stale(db: AsyncSession, rollout: TrainingRollout) -> bool:
    if rollout.status == "stale":
        return True
    if rollout.previewed_at is None:
        return False
    source = await db.get(TrainingVersion, rollout.from_version_id)
    target = await db.get(TrainingVersion, rollout.to_version_id)
    if source is None or target is None:
        return True
    if (
        source.revision != rollout.from_version_revision
        or target.revision != rollout.to_version_revision
    ):
        return True
    assignments = await _source_assignments(db, rollout=rollout, lock=False)
    completions = await _completions_by_assignment(db, assignments)
    return rollout.source_assignment_set_fingerprint != _source_fingerprint(
        assignments, completions
    )


async def _response(db: AsyncSession, rollout: TrainingRollout) -> TrainingRolloutResponse:
    source = await db.get_one(TrainingVersion, rollout.from_version_id)
    target = await db.get_one(TrainingVersion, rollout.to_version_id)
    rules = list(
        (
            await db.scalars(
                select(RolloutLessonRuleRecord)
                .where(RolloutLessonRuleRecord.rollout_id == rollout.id)
                .order_by(RolloutLessonRuleRecord.lesson_id)
            )
        ).all()
    )
    impacts = list(
        (
            await db.scalars(
                select(RolloutEmployeeImpact)
                .where(RolloutEmployeeImpact.rollout_id == rollout.id)
                .order_by(
                    RolloutEmployeeImpact.employee_profile_id,
                    RolloutEmployeeImpact.source_assignment_id,
                )
            )
        ).all()
    )
    stale = await _rollout_is_stale(db, rollout)
    unresolved_count = sum(rule.requires_admin_decision and rule.rule is None for rule in rules)
    warning_codes: list[str] = []
    if unresolved_count:
        warning_codes.append("ROLLOUT_RULE_REQUIRED")
    if stale:
        warning_codes.append("TRAINING_ROLLOUT_STALE")
    return TrainingRolloutResponse(
        id=rollout.id,
        organization_id=rollout.organization_id,
        location_id=rollout.location_id,
        training_id=rollout.training_id,
        from_version=TrainingRolloutVersionSummary(
            id=source.id,
            version_number=source.version_number,
            status=cast(_VersionStatus, source.status),
            revision=source.revision,
        ),
        to_version=TrainingRolloutVersionSummary(
            id=target.id,
            version_number=target.version_number,
            status=cast(_VersionStatus, target.status),
            revision=target.revision,
        ),
        status=cast(_RolloutStatus, rollout.status),
        revision=rollout.revision,
        rules=[_rule_response(rule) for rule in rules],
        employee_impacts=[_impact_response(impact) for impact in impacts],
        impact_counts=TrainingRolloutImpactCounts(
            employee_count=len(impacts),
            unresolved_rule_count=unresolved_count,
        ),
        is_stale=stale,
        warning_codes=warning_codes,
        previewed_at=rollout.previewed_at,
        created_at=rollout.created_at,
    )


async def create_training_rollout(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    from_version_id: UUID,
    to_version_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    idempotency_key: str,
    now: datetime,
) -> TrainingRolloutResponse:
    fingerprint = request_fingerprint(
        {
            "from_version_id": str(from_version_id),
            "to_version_id": str(to_version_id),
        }
    )
    try:
        replay = await find_idempotency_replay(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="training_rollout.create",
            key=idempotency_key,
            fingerprint=fingerprint,
            now=now,
        )
        if replay is not None:
            rollout = await _scoped_rollout(
                db,
                organization_id=organization_id,
                location_id=location_id,
                rollout_id=replay.resource_id,
            )
            return await _response(db, rollout)
        source, target = await _validated_versions(
            db,
            organization_id=organization_id,
            location_id=location_id,
            from_version_id=from_version_id,
            to_version_id=to_version_id,
            lock=True,
        )
        await db.scalar(select(Training).where(Training.id == source.training_id).with_for_update())
        existing = await db.scalar(
            select(TrainingRollout).where(
                TrainingRollout.training_id == source.training_id,
                TrainingRollout.from_version_id == source.id,
                TrainingRollout.to_version_id == target.id,
                TrainingRollout.status.in_(("draft", "preview_ready", "confirmed", "processing")),
            )
        )
        if existing is not None:
            raise _rollout_exists()
        rollout = TrainingRollout(
            id=uuid4(),
            organization_id=organization_id,
            location_id=location_id,
            training_id=source.training_id,
            from_version_id=source.id,
            to_version_id=target.id,
            status="draft",
            revision=0,
            from_version_revision=source.revision,
            to_version_revision=target.revision,
            created_by_user_id=actor_user_id,
        )
        db.add(rollout)
        await reserve_idempotency(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="training_rollout.create",
            key=idempotency_key,
            fingerprint=fingerprint,
            resource_type="training_rollout",
            resource_id=rollout.id,
            response_status=201,
            now=now,
        )
        db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_type="user",
                action="training_rollout_created",
                target_type="training_rollout",
                target_id=rollout.id,
                old_values=None,
                new_values={
                    "location_id": str(location_id),
                    "training_id": str(source.training_id),
                    "from_version_id": str(source.id),
                    "to_version_id": str(target.id),
                },
                request_id=request_id,
                outcome="success",
            )
        )
        await db.commit()
        return await _response(db, rollout)
    except Exception:
        await db.rollback()
        raise


async def get_training_rollout(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    rollout_id: UUID,
) -> TrainingRolloutResponse:
    rollout = await _scoped_rollout(
        db,
        organization_id=organization_id,
        location_id=location_id,
        rollout_id=rollout_id,
    )
    return await _response(db, rollout)


async def _rebuild_preview(
    db: AsyncSession,
    *,
    rollout: TrainingRollout,
    now: datetime,
) -> None:
    source, target = await _validated_versions(
        db,
        organization_id=rollout.organization_id,
        location_id=rollout.location_id,
        from_version_id=rollout.from_version_id,
        to_version_id=rollout.to_version_id,
        lock=True,
    )
    previous_rules = {
        row.lesson_id: row
        for row in (
            await db.scalars(
                select(RolloutLessonRuleRecord).where(
                    RolloutLessonRuleRecord.rollout_id == rollout.id
                )
            )
        ).all()
    }
    specs = await _rule_specs(
        db,
        from_version_id=source.id,
        to_version_id=target.id,
    )
    await db.execute(
        delete(RolloutEmployeeImpact).where(RolloutEmployeeImpact.rollout_id == rollout.id)
    )
    await db.execute(
        delete(RolloutLessonRuleRecord).where(RolloutLessonRuleRecord.rollout_id == rollout.id)
    )
    await db.flush()
    rules: list[RolloutLessonRuleRecord] = []
    for spec in specs:
        previous = previous_rules.get(spec.lesson_id)
        retained_decision = (
            previous
            if spec.requires_admin_decision
            and previous is not None
            and previous.rule in ("preserve_completion", "needs_repeat")
            else None
        )
        rules.append(
            RolloutLessonRuleRecord(
                rollout_id=rollout.id,
                lesson_id=spec.lesson_id,
                from_lesson_version_id=spec.from_lesson_version_id,
                to_lesson_version_id=spec.to_lesson_version_id,
                rule=retained_decision.rule if retained_decision is not None else spec.rule,
                requires_admin_decision=spec.requires_admin_decision,
                decided_by_user_id=(
                    retained_decision.decided_by_user_id if retained_decision is not None else None
                ),
                decided_at=retained_decision.decided_at if retained_decision is not None else None,
            )
        )
    db.add_all(rules)
    assignments = await _source_assignments(db, rollout=rollout, lock=True)
    completions = await _completions_by_assignment(db, assignments)
    source_lessons = await _lesson_snapshots(db, training_version_id=source.id)
    target_lessons = await _lesson_snapshots(db, training_version_id=target.id)
    source_required = {lesson_id for lesson_id, lesson in source_lessons.items() if lesson.required}
    target_required = {lesson_id for lesson_id, lesson in target_lessons.items() if lesson.required}
    rule_by_lesson = {rule.lesson_id: rule for rule in rules}
    source_fingerprint = _source_fingerprint(assignments, completions)
    rules_fingerprint = _canonical_hash(
        [
            {
                "lesson_id": str(rule.lesson_id),
                "rule": rule.rule,
                "requires_admin_decision": rule.requires_admin_decision,
            }
            for rule in rules
        ]
    )
    for assignment in assignments:
        completed = completions[assignment.id]
        current_completed = len(source_required & completed)
        projected_completed_ids = {
            lesson_id
            for lesson_id in target_required
            if lesson_id in completed and rule_by_lesson[lesson_id].rule == "preserve_completion"
        }
        unresolved = any(rule.requires_admin_decision and rule.rule is None for rule in rules)
        lesson_impact = {
            "preserved": [
                str(rule.lesson_id) for rule in rules if rule.rule == "preserve_completion"
            ],
            "repeat": [str(rule.lesson_id) for rule in rules if rule.rule == "needs_repeat"],
            "new": [str(rule.lesson_id) for rule in rules if rule.rule == "new_incomplete"],
            "removed": [str(rule.lesson_id) for rule in rules if rule.rule == "removed_historical"],
        }
        current_required_count = len(source_required)
        projected_required_count = len(target_required)
        db.add(
            RolloutEmployeeImpact(
                rollout_id=rollout.id,
                employee_profile_id=assignment.employee_profile_id,
                source_assignment_id=assignment.id,
                current_required_count=current_required_count,
                current_completed_count=current_completed,
                current_progress_percentage=(
                    current_completed * 100 // current_required_count
                    if current_required_count
                    else 0
                ),
                projected_required_count=projected_required_count,
                projected_completed_count=len(projected_completed_ids),
                projected_progress_percentage=(
                    len(projected_completed_ids) * 100 // projected_required_count
                    if projected_required_count
                    else 0
                ),
                lesson_impact=lesson_impact,
                validation_codes=["ROLLOUT_RULE_REQUIRED"] if unresolved else [],
                warning_codes=[],
                preview_fingerprint=_canonical_hash(
                    {
                        "rollout_id": str(rollout.id),
                        "assignment_id": str(assignment.id),
                        "source_state": source_fingerprint,
                        "rules": rules_fingerprint,
                        "from_revision": source.revision,
                        "to_revision": target.revision,
                    }
                ),
                previewed_at=now,
            )
        )
    rollout.status = "preview_ready"
    rollout.revision += 1
    rollout.source_assignment_set_fingerprint = source_fingerprint
    rollout.from_version_revision = source.revision
    rollout.to_version_revision = target.revision
    rollout.previewed_at = now


async def preview_training_rollout(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    rollout_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    idempotency_key: str,
    now: datetime,
) -> TrainingRolloutResponse:
    fingerprint = request_fingerprint(
        {"rollout_id": str(rollout_id), "expected_revision": expected_revision}
    )
    try:
        replay = await find_idempotency_replay(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="training_rollout.preview",
            key=idempotency_key,
            fingerprint=fingerprint,
            now=now,
        )
        rollout = await _scoped_rollout(
            db,
            organization_id=organization_id,
            location_id=location_id,
            rollout_id=rollout_id,
            lock=replay is None,
        )
        if replay is not None:
            if replay.resource_id != rollout.id:
                raise RuntimeError("Idempotent Rollout preview target is inconsistent")
            return await _response(db, rollout)
        if rollout.status not in ("draft", "preview_ready", "stale"):
            raise APIError(
                status_code=409,
                code="TRAINING_ROLLOUT_NOT_READY",
                message="Rollout не доступний для попереднього перегляду.",
            )
        if rollout.revision != expected_revision:
            raise _revision_conflict()
        await _rebuild_preview(
            db,
            rollout=rollout,
            now=now,
        )
        await reserve_idempotency(
            db,
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="training_rollout.preview",
            key=idempotency_key,
            fingerprint=fingerprint,
            resource_type="training_rollout",
            resource_id=rollout.id,
            response_status=200,
            now=now,
        )
        db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_type="user",
                action="training_rollout_previewed",
                target_type="training_rollout",
                target_id=rollout.id,
                old_values={"revision": expected_revision},
                new_values={"revision": rollout.revision},
                request_id=request_id,
                outcome="success",
            )
        )
        await db.commit()
        return await _response(db, rollout)
    except Exception:
        await db.rollback()
        raise


async def update_training_rollout_lesson_rule(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    rollout_id: UUID,
    lesson_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    expected_revision: int,
    rule_value: str,
    now: datetime,
) -> TrainingRolloutResponse:
    try:
        rollout = await _scoped_rollout(
            db,
            organization_id=organization_id,
            location_id=location_id,
            rollout_id=rollout_id,
            lock=True,
        )
        if rollout.status not in ("preview_ready", "stale"):
            raise APIError(
                status_code=409,
                code="TRAINING_ROLLOUT_NOT_READY",
                message="Спочатку підготуйте попередній перегляд Rollout.",
            )
        if rollout.revision != expected_revision:
            raise _revision_conflict()
        lesson_rule = await db.scalar(
            select(RolloutLessonRuleRecord)
            .where(
                RolloutLessonRuleRecord.rollout_id == rollout.id,
                RolloutLessonRuleRecord.lesson_id == lesson_id,
            )
            .with_for_update()
        )
        if lesson_rule is None:
            raise _not_found()
        if not lesson_rule.requires_admin_decision:
            raise APIError(
                status_code=409,
                code="ROLLOUT_RULE_REQUIRED",
                message="Серверне правило для цього Lesson не можна змінити.",
            )
        previous = lesson_rule.rule
        lesson_rule.rule = rule_value
        lesson_rule.decided_by_user_id = actor_user_id
        lesson_rule.decided_at = now
        rollout.status = "stale"
        rollout.revision += 1
        db.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_type="user",
                action="training_rollout_rule_updated",
                target_type="training_rollout",
                target_id=rollout.id,
                old_values={"lesson_id": str(lesson_id), "rule": previous},
                new_values={"lesson_id": str(lesson_id), "rule": rule_value},
                request_id=request_id,
                outcome="success",
            )
        )
        await db.commit()
        return await _response(db, rollout)
    except Exception:
        await db.rollback()
        raise


async def prepare_replacement_rollout(
    db: AsyncSession,
    *,
    source: TrainingVersion,
    target: TrainingVersion,
    actor_user_id: UUID,
    request_id: UUID,
    now: datetime,
) -> TrainingRollout:
    rollout = TrainingRollout(
        id=uuid4(),
        organization_id=target.organization_id,
        location_id=target.location_id,
        training_id=target.training_id,
        from_version_id=source.id,
        to_version_id=target.id,
        status="draft",
        revision=0,
        from_version_revision=source.revision,
        to_version_revision=target.revision,
        created_by_user_id=actor_user_id,
    )
    db.add(rollout)
    await db.flush()
    await _rebuild_preview(
        db,
        rollout=rollout,
        now=now,
    )
    db.add(
        AuditEvent(
            organization_id=target.organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="training_rollout_prepared",
            target_type="training_rollout",
            target_id=rollout.id,
            old_values=None,
            new_values={
                "location_id": str(target.location_id),
                "training_id": str(target.training_id),
                "from_version_id": str(source.id),
                "to_version_id": str(target.id),
            },
            request_id=request_id,
            outcome="success",
        )
    )
    return rollout
