from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import APIError
from app.models import (
    AuditEvent,
    Lesson,
    LessonContentBlock,
    LessonTranslation,
    LessonVersion,
    OperationalRole,
    StandardRule,
    StandardRuleVersion,
    StandardSet,
    StandardSetVersion,
    TrainingModule,
    TrainingModuleAudience,
    TrainingModuleStandardDependency,
    TrainingModuleTranslation,
    TrainingModuleVersion,
    TrainingVersion,
    TrainingVersionAudience,
)
from app.services.idempotency import (
    find_idempotency_replay,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.training_catalog import COURSES, NOTICE


class ContentPackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0)
    acknowledge_generic_content: bool
    waiter_role_id: UUID | None = None


class ContentPackResponse(BaseModel):
    training_version_id: UUID
    revision: int
    module_count: int = 3
    lesson_count: int = 23
    question_count: int = 45
    replayed: bool


async def install_content_pack(
    db: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    version_id: UUID,
    actor_user_id: UUID,
    request_id: UUID,
    payload: ContentPackRequest,
    idempotency_key: str,
    now: datetime,
) -> ContentPackResponse:
    if not payload.acknowledge_generic_content:
        raise APIError(
            status_code=422,
            code="CONTENT_REVIEW_REQUIRED",
            message="Підтвердьте ознайомлення із загальним матеріалом.",
        )
    fingerprint = request_fingerprint(
        {"version_id": str(version_id), **payload.model_dump(mode="json")}
    )
    replay = await find_idempotency_replay(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="training_content_pack",
        key=idempotency_key,
        fingerprint=fingerprint,
        now=now,
    )
    version = await db.scalar(
        select(TrainingVersion)
        .where(
            TrainingVersion.id == version_id,
            TrainingVersion.organization_id == organization_id,
            TrainingVersion.location_id == location_id,
        )
        .with_for_update()
    )
    if version is None:
        raise APIError(status_code=404, code="RESOURCE_NOT_FOUND", message="Ресурс не знайдено.")
    if replay:
        return ContentPackResponse(
            training_version_id=version.id, revision=version.revision, replayed=True
        )
    if version.status != "draft":
        raise APIError(
            status_code=409,
            code="TRAINING_VERSION_IMMUTABLE",
            message="Імпорт доступний лише для чернетки.",
        )
    if version.revision != payload.expected_revision:
        raise APIError(status_code=409, code="REVISION_CONFLICT", message="Чернетку вже змінено.")
    installed = await db.scalar(
        select(func.count(TrainingModuleStandardDependency.id))
        .join(
            StandardSetVersion,
            StandardSetVersion.id == TrainingModuleStandardDependency.standard_set_version_id,
        )
        .join(StandardSet, StandardSet.id == StandardSetVersion.standard_set_id)
        .where(
            TrainingModuleStandardDependency.training_version_id == version.id,
            StandardSet.code.in_([f"cra288.{course.code}.v1" for course in COURSES]),
        )
    )
    if installed:
        if installed != len(COURSES):
            raise APIError(
                status_code=409,
                code="CONTENT_PACK_PARTIAL",
                message="Частина пакета вже існує. Перевірте модулі вручну.",
            )
        return ContentPackResponse(
            training_version_id=version.id, revision=version.revision, replayed=True
        )

    scope = {"organization_id": organization_id, "location_id": location_id}
    roles: dict[str, UUID] = {}
    for code, title in (("waiter", "Офіціант"), ("runner", "Runner"), ("bartender", "Бармен")):
        if code == "waiter" and payload.waiter_role_id:
            role = await db.scalar(
                select(OperationalRole).where(
                    OperationalRole.id == payload.waiter_role_id,
                    OperationalRole.organization_id == organization_id,
                    OperationalRole.status == "active",
                )
            )
        else:
            await db.execute(
                insert(OperationalRole)
                .values(
                    id=uuid4(),
                    organization_id=organization_id,
                    code=code,
                    name_uk=title,
                    status="active",
                )
                .on_conflict_do_nothing()
            )
            role = await db.scalar(
                select(OperationalRole).where(
                    OperationalRole.organization_id == organization_id,
                    OperationalRole.code == code,
                    OperationalRole.status == "active",
                )
            )
        if role is None:
            raise APIError(
                status_code=409,
                code="POSITION_UNAVAILABLE",
                message="Перевірте активні посади організації.",
            )
        roles[code] = role.id
    if len(set(roles.values())) != 3:
        raise APIError(
            status_code=409,
            code="POSITION_MAPPING_CONFLICT",
            message="Для офіціанта оберіть окрему посаду, відмінну від Runner і Bartender.",
        )
    if not version.all_positions:
        existing_roles = set(
            await db.scalars(
                select(TrainingVersionAudience.operational_role_id).where(
                    TrainingVersionAudience.training_version_id == version.id,
                )
            )
        )
        db.add_all(
            [
                TrainingVersionAudience(
                    **scope, training_version_id=version.id, operational_role_id=role_id
                )
                for role_id in set(roles.values()) - existing_roles
            ]
        )
    highest = await db.scalar(
        select(func.max(TrainingModuleVersion.position)).where(
            TrainingModuleVersion.training_version_id == version.id,
        )
    )
    for offset, course in enumerate(COURSES, start=1):
        identity = TrainingModule(training_id=version.training_id, domain_type="service")
        db.add(identity)
        await db.flush()
        module = TrainingModuleVersion(
            training_id=version.training_id,
            training_version_id=version.id,
            training_module_id=identity.id,
            position=(highest if highest is not None else -1) + offset,
            required=True,
            all_positions=False,
        )
        db.add(module)
        await db.flush()
        db.add(
            TrainingModuleTranslation(
                training_module_version_id=module.id,
                locale="uk",
                title=course.title,
                description=NOTICE,
            )
        )
        db.add_all(
            [
                TrainingModuleAudience(
                    **scope,
                    training_version_id=version.id,
                    training_module_version_id=module.id,
                    operational_role_id=roles[code],
                )
                for code in course.positions
            ]
        )
        for position, unit in enumerate(course.lessons):
            lesson = Lesson(training_module_id=identity.id)
            db.add(lesson)
            await db.flush()
            lesson_version = LessonVersion(
                training_module_version_id=module.id,
                lesson_id=lesson.id,
                position=position,
                required=True,
                estimated_minutes=5,
            )
            db.add(lesson_version)
            await db.flush()
            db.add(
                LessonTranslation(
                    lesson_version_id=lesson_version.id, locale="uk", title=unit.title
                )
            )
            db.add(
                LessonContentBlock(
                    lesson_version_id=lesson_version.id,
                    type="text",
                    position=0,
                    payload={"text_uk": unit.text},
                )
            )
            facts = [fact for fact in course.scenarios if fact.lesson == position]
            for index, fact in enumerate(facts, start=1):
                db.add(
                    LessonContentBlock(
                        lesson_version_id=lesson_version.id,
                        type="callout",
                        position=index,
                        payload={
                            "tone": "tip",
                            "title_uk": "Практична ситуація",
                            "text_uk": f"{fact.scenario} {fact.action} {fact.explanation}",
                        },
                    )
                )
        source = await db.scalar(
            select(StandardSet).where(
                StandardSet.organization_id == organization_id,
                StandardSet.location_id == location_id,
                StandardSet.code == f"cra288.{course.code}.v1",
            )
        )
        if source is None:
            source = StandardSet(**scope, code=f"cra288.{course.code}.v1", domain_type="service")
            db.add(source)
            await db.flush()
        number = await db.scalar(
            select(func.max(StandardSetVersion.version_number)).where(
                StandardSetVersion.standard_set_id == source.id
            )
        )
        source_version = StandardSetVersion(
            **scope,
            standard_set_id=source.id,
            version_number=(number or 0) + 1,
            title_uk=course.title,
        )
        db.add(source_version)
        await db.flush()
        for position, fact in enumerate(course.scenarios):
            code = f"scenario_{position + 1}"
            rule = await db.scalar(
                select(StandardRule).where(
                    StandardRule.standard_set_id == source.id, StandardRule.code == code
                )
            )
            if rule is None:
                rule = StandardRule(standard_set_id=source.id, code=code)
                db.add(rule)
                await db.flush()
            db.add(
                StandardRuleVersion(
                    **scope,
                    standard_set_id=source.id,
                    standard_set_version_id=source_version.id,
                    standard_rule_id=rule.id,
                    position=position,
                    scenario_uk=fact.scenario,
                    allowed_action_uk=fact.action,
                    prohibited_actions_uk=list(fact.alternatives),
                    explanation_uk=fact.explanation,
                    verified=True,
                    provenance={
                        "catalog": "cra288.v1",
                        "course": course.code,
                        "lesson": fact.lesson,
                        "kind": "generic_educational_material",
                        "reviewed_by": str(actor_user_id),
                    },
                )
            )
        await db.flush()
        source_version.status = "published"
        source_version.published_by_user_id = actor_user_id
        source_version.published_at = now
        db.add(
            TrainingModuleStandardDependency(
                **scope,
                training_version_id=version.id,
                training_module_version_id=module.id,
                standard_set_version_id=source_version.id,
            )
        )
    version.revision += 1
    await reserve_idempotency(
        db,
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        action="training_content_pack",
        key=idempotency_key,
        fingerprint=fingerprint,
        resource_type="training_version",
        resource_id=version.id,
        response_status=200,
        now=now,
    )
    db.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            actor_type="user",
            action="training_content_pack_imported",
            target_type="training_version",
            target_id=version.id,
            old_values=None,
            new_values={"catalog": "cra288.v1", "module_count": 3, "lesson_count": 23},
            request_id=request_id,
            outcome="success",
        )
    )
    await db.commit()
    return ContentPackResponse(
        training_version_id=version.id, revision=version.revision, replayed=False
    )
