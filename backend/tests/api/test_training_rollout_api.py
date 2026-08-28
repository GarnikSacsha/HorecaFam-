import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditEvent,
    BackgroundJob,
    LessonCompletion,
    Location,
    OperationalRole,
    Organization,
    RolloutEmployeeImpact,
    RolloutLessonRuleRecord,
    TrainingAssignment,
    TrainingRollout,
    TrainingVersion,
)
from app.services import training_rollouts
from tests.api.test_menu_admin_api import FIXED_NOW, arrange_admin, mutation_headers
from tests.api.test_training_publication_api import arrange_ready_training, publish_menu
from tests.factories.identity import make_employee_profile, make_membership, make_user
from tests.factories.training import (
    make_content_block,
    make_lesson,
    make_lesson_completion,
    make_lesson_translation,
    make_lesson_version,
    make_training,
    make_training_assignment,
    make_training_module,
    make_training_module_version,
    make_training_version,
)


async def arrange_rollout_context(
    client: AsyncClient,
    app: FastAPI,
    db: AsyncSession,
) -> tuple[UUID, UUID, UUID, str, TrainingRollout, UUID, UUID]:
    organization_id, location_id, admin_id, csrf = await arrange_admin(client, app, db)
    organization = await db.get_one(Organization, organization_id)
    role = await db.scalar(
        select(OperationalRole).where(OperationalRole.organization_id == organization_id)
    )
    assert role is not None
    employee_user = make_user(email_normalized=f"rollout-{uuid4()}@example.com")
    membership = make_membership(organization, employee_user, activated_at=FIXED_NOW)
    employee = make_employee_profile(
        membership,
        organization_id,
        location_id=location_id,
        operational_role_id=role.id,
    )
    training = make_training(organization_id, location_id)
    source = make_training_version(
        training,
        admin_id,
        status="archived",
        published_by_user_id=admin_id,
        published_at=FIXED_NOW,
        archived_at=FIXED_NOW,
    )
    target = make_training_version(
        training,
        admin_id,
        version_number=2,
        status="published",
        base_version_id=source.id,
        published_by_user_id=admin_id,
        published_at=FIXED_NOW,
    )
    module = make_training_module(training)
    source_module = make_training_module_version(source, module)
    target_module = make_training_module_version(target, module)

    unchanged = make_lesson(module)
    changed = make_lesson(module)
    removed = make_lesson(module)
    added = make_lesson(module)
    source_unchanged = make_lesson_version(source_module, unchanged, position=0)
    target_unchanged = make_lesson_version(target_module, unchanged, position=0)
    source_changed = make_lesson_version(source_module, changed, position=1)
    target_changed = make_lesson_version(target_module, changed, position=1)
    source_removed = make_lesson_version(source_module, removed, position=2)
    target_added = make_lesson_version(target_module, added, position=2)
    translations = [
        make_lesson_translation(source_unchanged, title="Unchanged"),
        make_lesson_translation(target_unchanged, title="Unchanged"),
        make_lesson_translation(source_changed, title="Original"),
        make_lesson_translation(target_changed, title="Materially changed"),
        make_lesson_translation(source_removed, title="Removed"),
        make_lesson_translation(target_added, title="Added"),
    ]
    blocks = [
        make_content_block(source_unchanged, payload={"text_uk": "Same"}),
        make_content_block(target_unchanged, payload={"text_uk": "Same"}),
        make_content_block(source_changed, payload={"text_uk": "Before"}),
        make_content_block(target_changed, payload={"text_uk": "After"}),
        make_content_block(source_removed, payload={"text_uk": "Removed"}),
        make_content_block(target_added, payload={"text_uk": "Added"}),
    ]
    assignment = make_training_assignment(
        employee,
        training,
        source,
        status="in_progress",
        started_at=FIXED_NOW,
        assigned_at=FIXED_NOW,
    )
    completions = [
        make_lesson_completion(assignment, source_unchanged, employee_user.id),
        make_lesson_completion(assignment, source_changed, employee_user.id),
        make_lesson_completion(assignment, source_removed, employee_user.id),
    ]
    rollout = TrainingRollout(
        organization_id=organization_id,
        location_id=location_id,
        training_id=training.id,
        from_version_id=source.id,
        to_version_id=target.id,
        status="draft",
        revision=0,
        from_version_revision=source.revision,
        to_version_revision=target.revision,
        created_by_user_id=admin_id,
    )
    db.add(employee_user)
    await db.flush()
    for completion in completions:
        completion.completed_by_user_id = employee_user.id
    db.add_all([membership, training])
    await db.flush()
    db.add_all([employee, source, target, module])
    await db.flush()
    assignment.employee_profile_id = employee.id
    db.add_all([source_module, target_module, unchanged, changed, removed, added])
    await db.flush()
    db.add_all(
        [
            source_unchanged,
            target_unchanged,
            source_changed,
            target_changed,
            source_removed,
            target_added,
        ]
    )
    await db.flush()
    db.add_all([*translations, *blocks, assignment, rollout])
    await db.flush()
    db.add_all(completions)
    await db.commit()
    return (
        organization_id,
        location_id,
        admin_id,
        csrf,
        rollout,
        changed.id,
        unchanged.id,
    )


async def prepare_confirmable_rollout(
    client: AsyncClient,
    *,
    base: str,
    csrf: str,
    changed_lesson_id: UUID,
    key_prefix: str,
) -> None:
    preview = await client.post(
        f"{base}/preview",
        headers=mutation_headers(csrf, key=f"{key_prefix}-preview"),
        json={"expected_revision": 0},
    )
    assert preview.status_code == 200
    decision = await client.patch(
        f"{base}/lesson-rules/{changed_lesson_id}",
        headers=mutation_headers(csrf),
        json={"expected_revision": 1, "rule": "preserve_completion"},
    )
    assert decision.status_code == 200
    refreshed = await client.post(
        f"{base}/preview",
        headers=mutation_headers(csrf, key=f"{key_prefix}-repreview"),
        json={"expected_revision": 2},
    )
    assert refreshed.status_code == 200


async def test_admin_creates_draft_training_rollout_idempotently(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    organization = await db_session.get_one(Organization, organization_id)
    location = await db_session.get_one(Location, location_id)
    training = make_training(organization.id, location.id)
    source = make_training_version(
        training,
        admin_id,
        status="archived",
        published_by_user_id=admin_id,
        published_at=FIXED_NOW,
        archived_at=FIXED_NOW,
    )
    target = make_training_version(
        training,
        admin_id,
        version_number=2,
        status="published",
        base_version_id=source.id,
        published_by_user_id=admin_id,
        published_at=FIXED_NOW,
    )
    db_session.add_all([training, source, target])
    await db_session.commit()
    url = f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-rollouts"
    headers = mutation_headers(csrf, key="create-training-rollout")
    payload = {
        "from_version_id": str(source.id),
        "to_version_id": str(target.id),
    }

    denied = await auth_client.post(
        url,
        headers={"Idempotency-Key": "csrf-denied-training-rollout"},
        json=payload,
    )
    assert denied.status_code == 403
    assert await db_session.scalar(select(func.count()).select_from(TrainingRollout)) == 0

    created = await auth_client.post(url, headers=headers, json=payload)
    replay = await auth_client.post(url, headers=headers, json=payload)

    assert created.status_code == replay.status_code == 201, created.json()
    assert replay.json() == created.json()
    assert created.json()["organization_id"] == str(organization_id)
    assert created.json()["location_id"] == str(location_id)
    assert created.json()["training_id"] == str(training.id)
    assert created.json()["from_version"]["id"] == str(source.id)
    assert created.json()["to_version"]["id"] == str(target.id)
    assert created.json()["status"] == "draft"
    assert created.json()["revision"] == 0
    assert created.json()["rules"] == []
    assert created.json()["employee_impacts"] == []
    assert created.json()["impact_counts"] == {
        "employee_count": 0,
        "unresolved_rule_count": 0,
    }
    assert created.json()["is_stale"] is False
    assert created.json()["warning_codes"] == []
    duplicate = await auth_client.post(
        url,
        headers=mutation_headers(csrf, key="duplicate-training-rollout"),
        json=payload,
    )
    reused = await auth_client.post(
        url,
        headers=headers,
        json={
            "from_version_id": str(target.id),
            "to_version_id": str(source.id),
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "TRAINING_ROLLOUT_EXISTS"
    assert reused.status_code == 409
    assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    foreign = await auth_client.get(
        f"/api/v1/organizations/{organization_id}/locations/{uuid4()}/"
        f"training-rollouts/{created.json()['id']}"
    )
    assert foreign.status_code == 404
    assert foreign.json()["code"] == "RESOURCE_NOT_FOUND"


async def test_rollout_preview_defaults_rule_decision_and_assignment_staleness(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    (
        organization_id,
        location_id,
        _admin_id,
        csrf,
        rollout,
        changed_lesson_id,
        unchanged_lesson_id,
    ) = await arrange_rollout_context(auth_client, auth_app, db_session)
    base = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/"
        f"training-rollouts/{rollout.id}"
    )

    preview = await auth_client.post(
        f"{base}/preview",
        headers=mutation_headers(csrf, key="preview-training-rollout"),
        json={"expected_revision": 0},
    )
    replay = await auth_client.post(
        f"{base}/preview",
        headers=mutation_headers(csrf, key="preview-training-rollout"),
        json={"expected_revision": 0},
    )

    assert preview.status_code == replay.status_code == 200, preview.json()
    assert replay.json() == preview.json()
    body = preview.json()
    assert body["status"] == "preview_ready"
    assert body["revision"] == 1
    assert body["impact_counts"] == {
        "employee_count": 1,
        "unresolved_rule_count": 1,
    }
    assert body["warning_codes"] == ["ROLLOUT_RULE_REQUIRED"]
    rules = {rule["lesson_id"]: rule for rule in body["rules"]}
    assert rules[str(unchanged_lesson_id)]["rule"] == "preserve_completion"
    assert rules[str(unchanged_lesson_id)]["requires_admin_decision"] is False
    assert rules[str(changed_lesson_id)]["rule"] is None
    assert rules[str(changed_lesson_id)]["requires_admin_decision"] is True
    assert {rule["rule"] for rule in body["rules"]} == {
        "preserve_completion",
        "new_incomplete",
        "removed_historical",
        None,
    }
    impact = body["employee_impacts"][0]
    assert impact["current_required_count"] == 3
    assert impact["current_completed_count"] == 3
    assert impact["current_progress_percentage"] == 100
    assert impact["projected_required_count"] == 3
    assert impact["projected_completed_count"] == 1
    assert impact["projected_progress_percentage"] == 33
    assert impact["validation_codes"] == ["ROLLOUT_RULE_REQUIRED"]
    assert await db_session.scalar(select(func.count()).select_from(TrainingAssignment)) == 1
    stale_revision = await auth_client.post(
        f"{base}/preview",
        headers=mutation_headers(csrf, key="stale-preview-training-rollout"),
        json={"expected_revision": 0},
    )
    assert stale_revision.status_code == 409
    assert stale_revision.json()["code"] == "REVISION_CONFLICT"

    immutable_default = await auth_client.patch(
        f"{base}/lesson-rules/{unchanged_lesson_id}",
        headers=mutation_headers(csrf),
        json={"expected_revision": 1, "rule": "needs_repeat"},
    )
    assert immutable_default.status_code == 409
    assert immutable_default.json()["code"] == "ROLLOUT_RULE_REQUIRED"

    decision = await auth_client.patch(
        f"{base}/lesson-rules/{changed_lesson_id}",
        headers=mutation_headers(csrf),
        json={"expected_revision": 1, "rule": "preserve_completion"},
    )
    assert decision.status_code == 200, decision.json()
    assert decision.json()["status"] == "stale"
    assert decision.json()["revision"] == 2
    assert decision.json()["is_stale"] is True
    assert decision.json()["warning_codes"] == ["TRAINING_ROLLOUT_STALE"]

    refreshed = await auth_client.post(
        f"{base}/preview",
        headers=mutation_headers(csrf, key="repreview-training-rollout"),
        json={"expected_revision": 2},
    )
    assert refreshed.status_code == 200, refreshed.json()
    assert refreshed.json()["status"] == "preview_ready"
    assert refreshed.json()["revision"] == 3
    assert refreshed.json()["is_stale"] is False
    assert refreshed.json()["warning_codes"] == []
    assert refreshed.json()["employee_impacts"][0]["projected_completed_count"] == 2
    assert refreshed.json()["employee_impacts"][0]["projected_progress_percentage"] == 66

    source_assignment = await db_session.scalar(select(TrainingAssignment))
    assert source_assignment is not None
    source_assignment.status = "completed"
    source_assignment.completed_at = FIXED_NOW
    await db_session.commit()
    stale = await auth_client.get(base)
    assert stale.status_code == 200
    assert stale.json()["is_stale"] is True
    assert stale.json()["warning_codes"] == ["TRAINING_ROLLOUT_STALE"]
    assert await db_session.scalar(select(func.count()).select_from(LessonCompletion)) == 3


async def test_admin_confirms_previewed_rollout_with_lineage_and_carried_completions(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    (
        organization_id,
        location_id,
        _admin_id,
        csrf,
        rollout,
        changed_lesson_id,
        _unchanged_lesson_id,
    ) = await arrange_rollout_context(auth_client, auth_app, db_session)
    base = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/"
        f"training-rollouts/{rollout.id}"
    )
    preview = await auth_client.post(
        f"{base}/preview",
        headers=mutation_headers(csrf, key="confirm-preview"),
        json={"expected_revision": 0},
    )
    assert preview.status_code == 200
    decision = await auth_client.patch(
        f"{base}/lesson-rules/{changed_lesson_id}",
        headers=mutation_headers(csrf),
        json={"expected_revision": 1, "rule": "preserve_completion"},
    )
    assert decision.status_code == 200
    refreshed = await auth_client.post(
        f"{base}/preview",
        headers=mutation_headers(csrf, key="confirm-repreview"),
        json={"expected_revision": 2},
    )
    assert refreshed.status_code == 200

    confirmed = await auth_client.post(
        f"{base}/confirm",
        headers=mutation_headers(csrf, key="confirm-rollout"),
        json={"expected_revision": 3},
    )
    replay = await auth_client.post(
        f"{base}/confirm",
        headers=mutation_headers(csrf, key="confirm-rollout"),
        json={"expected_revision": 3},
    )

    assert confirmed.status_code == replay.status_code == 200, confirmed.json()
    assert replay.json() == confirmed.json()
    assert confirmed.json()["status"] == "completed"
    assert confirmed.json()["revision"] == 4
    assert confirmed.json()["is_stale"] is False
    assert confirmed.json()["warning_codes"] == []
    assert confirmed.json()["employee_impacts"][0]["target_assignment_id"] is not None
    assignments = list(
        (
            await db_session.scalars(
                select(TrainingAssignment).order_by(TrainingAssignment.created_at)
            )
        ).all()
    )
    assert len(assignments) == 2
    source, target = assignments
    assert source.status == "revoked"
    assert source.revoke_reason == "rollout"
    assert target.status == "in_progress"
    assert target.source == "rollout"
    assert target.previous_assignment_id == source.id
    assert target.source_rollout_id == rollout.id
    target_completions = list(
        (
            await db_session.scalars(
                select(LessonCompletion).where(LessonCompletion.assignment_id == target.id)
            )
        ).all()
    )
    assert len(target_completions) == 2
    assert {row.completion_source for row in target_completions} == {"rollout_preserved"}
    assert all(row.source_completion_id is not None for row in target_completions)
    assert all(row.source_rollout_id == rollout.id for row in target_completions)
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(BackgroundJob)
            .where(BackgroundJob.job_type == "training_rollout_notification")
        )
        == 1
    )
    job = await db_session.scalar(
        select(BackgroundJob).where(BackgroundJob.job_type == "training_rollout_notification")
    )
    assert job is not None
    assert job.payload == {
        "rollout_id": str(rollout.id),
        "assignment_id": str(target.id),
        "template_code": "training_rollout_completed",
        "locale": "uk",
    }
    audit = await db_session.scalar(
        select(AuditEvent).where(AuditEvent.action == "training_rollout_confirmed")
    )
    assert audit is not None
    assert audit.new_values == {
        "revision": 4,
        "status": "completed",
        "assignment_count": 1,
        "completion_count": 2,
        "notification_count": 1,
    }
    changed_reuse = await auth_client.post(
        f"{base}/confirm",
        headers=mutation_headers(csrf, key="confirm-rollout"),
        json={"expected_revision": 2},
    )
    later_duplicate = await auth_client.post(
        f"{base}/confirm",
        headers=mutation_headers(csrf, key="confirm-rollout-later"),
        json={"expected_revision": 4},
    )
    assert changed_reuse.status_code == 409
    assert changed_reuse.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert later_duplicate.status_code == 409
    assert later_duplicate.json()["code"] == "TRAINING_ROLLOUT_NOT_READY"


async def test_rollout_confirm_rejects_unresolved_and_stale_preview_without_effects(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    (
        organization_id,
        location_id,
        _admin_id,
        csrf,
        rollout,
        changed_lesson_id,
        _unchanged_lesson_id,
    ) = await arrange_rollout_context(auth_client, auth_app, db_session)
    rollout_id = rollout.id
    base = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/"
        f"training-rollouts/{rollout_id}"
    )
    preview = await auth_client.post(
        f"{base}/preview",
        headers=mutation_headers(csrf, key="unresolved-confirm-preview"),
        json={"expected_revision": 0},
    )
    assert preview.status_code == 200
    unresolved = await auth_client.post(
        f"{base}/confirm",
        headers=mutation_headers(csrf, key="unresolved-confirm"),
        json={"expected_revision": 1},
    )
    assert unresolved.status_code == 409
    assert unresolved.json()["code"] == "ROLLOUT_RULE_REQUIRED"
    decision = await auth_client.patch(
        f"{base}/lesson-rules/{changed_lesson_id}",
        headers=mutation_headers(csrf),
        json={"expected_revision": 1, "rule": "preserve_completion"},
    )
    assert decision.status_code == 200
    refreshed = await auth_client.post(
        f"{base}/preview",
        headers=mutation_headers(csrf, key="stale-confirm-repreview"),
        json={"expected_revision": 2},
    )
    assert refreshed.status_code == 200
    source_assignment = await db_session.scalar(
        select(TrainingAssignment).where(TrainingAssignment.status != "revoked")
    )
    assert source_assignment is not None
    source_assignment.status = "completed"
    source_assignment.completed_at = FIXED_NOW
    await db_session.commit()
    stale = await auth_client.post(
        f"{base}/confirm",
        headers=mutation_headers(csrf, key="stale-confirm"),
        json={"expected_revision": 3},
    )

    assert stale.status_code == 409
    assert stale.json()["code"] == "TRAINING_ROLLOUT_STALE"
    db_session.expire_all()
    assert await db_session.scalar(select(func.count()).select_from(TrainingAssignment)) == 1
    assert await db_session.scalar(select(func.count()).select_from(LessonCompletion)) == 3
    assert await db_session.scalar(select(func.count()).select_from(BackgroundJob)) == 0
    stored = await db_session.get_one(TrainingRollout, rollout_id)
    assert stored.status == "preview_ready"
    assert stored.revision == 3
    assert stored.completed_at is None


async def test_concurrent_rollout_confirm_has_one_winner_and_one_effect(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    (
        organization_id,
        location_id,
        _admin_id,
        csrf,
        rollout,
        changed_lesson_id,
        _unchanged_lesson_id,
    ) = await arrange_rollout_context(auth_client, auth_app, db_session)
    base = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/"
        f"training-rollouts/{rollout.id}"
    )
    await prepare_confirmable_rollout(
        auth_client,
        base=base,
        csrf=csrf,
        changed_lesson_id=changed_lesson_id,
        key_prefix="concurrent-confirm",
    )

    first, second = await asyncio.gather(
        auth_client.post(
            f"{base}/confirm",
            headers=mutation_headers(csrf, key="concurrent-confirm-a"),
            json={"expected_revision": 3},
        ),
        auth_client.post(
            f"{base}/confirm",
            headers=mutation_headers(csrf, key="concurrent-confirm-b"),
            json={"expected_revision": 3},
        ),
    )

    assert sorted((first.status_code, second.status_code)) == [200, 409]
    loser = first if first.status_code == 409 else second
    assert loser.json()["code"] == "TRAINING_ROLLOUT_NOT_READY"
    assert await db_session.scalar(select(func.count()).select_from(TrainingAssignment)) == 2
    assert await db_session.scalar(select(func.count()).select_from(LessonCompletion)) == 5
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(BackgroundJob)
            .where(BackgroundJob.job_type == "training_rollout_notification")
        )
        == 1
    )
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "training_rollout_confirmed")
        )
        == 1
    )


async def test_replacement_publish_previews_rollout_without_migrating_assignment(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, _admin_id, csrf = await arrange_admin(
        auth_client, auth_app, db_session
    )
    organization = await db_session.get_one(Organization, organization_id)
    role = await db_session.scalar(
        select(OperationalRole).where(OperationalRole.organization_id == organization_id)
    )
    assert role is not None
    employee_user = make_user(email_normalized=f"replacement-{uuid4()}@example.com")
    membership = make_membership(organization, employee_user, activated_at=FIXED_NOW)
    db_session.add_all([employee_user, membership])
    await db_session.flush()
    employee = make_employee_profile(
        membership,
        organization_id,
        location_id=location_id,
        operational_role_id=role.id,
    )
    db_session.add(employee)
    await db_session.commit()
    await publish_menu(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="rollout-handoff-menu",
    )
    versions_url = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-versions"
    )
    first = await arrange_ready_training(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="rollout-handoff-first",
    )
    first_id = UUID(str(first["id"]))
    first_publish = await auth_client.post(
        f"{versions_url}/{first_id}/publish",
        headers=mutation_headers(csrf, key="rollout-handoff-first-publish"),
        json={"expected_revision": first["revision"]},
    )
    assert first_publish.status_code == 200
    source_assignment = await db_session.scalar(select(TrainingAssignment))
    assert source_assignment is not None
    assert source_assignment.training_version_id == first_id

    second = await arrange_ready_training(
        auth_client,
        organization_id=organization_id,
        location_id=location_id,
        csrf=csrf,
        key_prefix="rollout-handoff-second",
        base_version_id=first_id,
    )
    second_id = UUID(str(second["id"]))
    replacement = await auth_client.post(
        f"{versions_url}/{second_id}/publish",
        headers=mutation_headers(csrf, key="rollout-handoff-second-publish"),
        json={"expected_revision": second["revision"]},
    )

    assert replacement.status_code == 200, replacement.json()
    assert replacement.json()["rollout_count"] == 1
    assert replacement.json()["rollout_id"] is not None
    db_session.expire_all()
    assignments = list((await db_session.scalars(select(TrainingAssignment))).all())
    assert len(assignments) == 1
    assert assignments[0].id == source_assignment.id
    assert assignments[0].training_version_id == first_id
    assert assignments[0].status == "assigned"
    assert (await db_session.get_one(TrainingVersion, first_id)).status == "archived"
    rollout = await db_session.get_one(TrainingRollout, UUID(replacement.json()["rollout_id"]))
    assert rollout.status == "preview_ready"
    detail = await auth_client.get(
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/"
        f"training-rollouts/{rollout.id}"
    )
    assert detail.status_code == 200
    assert detail.json()["impact_counts"]["employee_count"] == 1
    assert detail.json()["employee_impacts"][0]["source_assignment_id"] == str(source_assignment.id)


async def test_rollout_preview_forced_failure_rolls_back_every_preview_effect(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        organization_id,
        location_id,
        admin_id,
        _csrf,
        rollout,
        _changed_lesson_id,
        _unchanged_lesson_id,
    ) = await arrange_rollout_context(auth_client, auth_app, db_session)
    rollout_id = rollout.id

    async def fail_reservation(*args: object, **kwargs: object) -> None:
        raise RuntimeError("forced rollout preview failure")

    monkeypatch.setattr(training_rollouts, "reserve_idempotency", fail_reservation)
    with pytest.raises(RuntimeError, match="forced rollout preview failure"):
        await training_rollouts.preview_training_rollout(
            db_session,
            organization_id=organization_id,
            location_id=location_id,
            rollout_id=rollout_id,
            actor_user_id=admin_id,
            request_id=uuid4(),
            expected_revision=0,
            idempotency_key="forced-preview-rollback",
            now=FIXED_NOW,
        )

    db_session.expire_all()
    stored = await db_session.get_one(TrainingRollout, rollout_id)
    assert stored.status == "draft"
    assert stored.revision == 0
    assert stored.previewed_at is None
    assert await db_session.scalar(select(func.count()).select_from(RolloutLessonRuleRecord)) == 0
    assert await db_session.scalar(select(func.count()).select_from(RolloutEmployeeImpact)) == 0
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "training_rollout_previewed")
        )
        == 0
    )


async def test_rollout_confirm_forced_failure_rolls_back_lineage_and_notifications(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        organization_id,
        location_id,
        admin_id,
        csrf,
        rollout,
        changed_lesson_id,
        _unchanged_lesson_id,
    ) = await arrange_rollout_context(auth_client, auth_app, db_session)
    rollout_id = rollout.id
    base = (
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/"
        f"training-rollouts/{rollout_id}"
    )
    await prepare_confirmable_rollout(
        auth_client,
        base=base,
        csrf=csrf,
        changed_lesson_id=changed_lesson_id,
        key_prefix="forced-confirm",
    )

    async def fail_reservation(*args: object, **kwargs: object) -> None:
        raise RuntimeError("forced rollout confirmation failure")

    db_session.expire_all()
    monkeypatch.setattr(training_rollouts, "reserve_idempotency", fail_reservation)
    with pytest.raises(RuntimeError, match="forced rollout confirmation failure"):
        await training_rollouts.confirm_training_rollout(
            db_session,
            organization_id=organization_id,
            location_id=location_id,
            rollout_id=rollout_id,
            actor_user_id=admin_id,
            request_id=uuid4(),
            expected_revision=3,
            idempotency_key="forced-confirm-rollback",
            now=FIXED_NOW,
        )

    db_session.expire_all()
    assignments = list((await db_session.scalars(select(TrainingAssignment))).all())
    assert len(assignments) == 1
    assert assignments[0].status == "in_progress"
    assert assignments[0].revoked_at is None
    assert await db_session.scalar(select(func.count()).select_from(LessonCompletion)) == 3
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(BackgroundJob)
            .where(BackgroundJob.job_type == "training_rollout_notification")
        )
        == 0
    )
    stored = await db_session.get_one(TrainingRollout, rollout_id)
    assert stored.status == "preview_ready"
    assert stored.revision == 3
    assert stored.confirmed_at is None
    impacts = list((await db_session.scalars(select(RolloutEmployeeImpact))).all())
    assert len(impacts) == 1
    assert impacts[0].target_assignment_id is None
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.action == "training_rollout_confirmed")
        )
        == 0
    )


async def test_rollout_mutation_requires_completed_admin_mfa(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    organization_id, location_id, admin_id, csrf = await arrange_admin(
        auth_client,
        auth_app,
        db_session,
        mfa_verified=False,
    )
    training = make_training(organization_id, location_id)
    source = make_training_version(
        training,
        admin_id,
        status="archived",
        published_by_user_id=admin_id,
        published_at=FIXED_NOW,
        archived_at=FIXED_NOW,
    )
    target = make_training_version(
        training,
        admin_id,
        version_number=2,
        status="published",
        base_version_id=source.id,
        published_by_user_id=admin_id,
        published_at=FIXED_NOW,
    )
    db_session.add_all([training, source, target])
    await db_session.commit()

    denied = await auth_client.post(
        f"/api/v1/organizations/{organization_id}/locations/{location_id}/training-rollouts",
        headers=mutation_headers(csrf, key="mfa-denied-training-rollout"),
        json={
            "from_version_id": str(source.id),
            "to_version_id": str(target.id),
        },
    )

    assert denied.status_code == 403
    assert denied.json()["code"] == "MFA_REQUIRED"
    assert await db_session.scalar(select(func.count()).select_from(TrainingRollout)) == 0


def test_rollout_openapi_exposes_preview_and_confirm_without_assessment(
    auth_app: FastAPI,
) -> None:
    document = auth_app.openapi()
    base = "/api/v1/organizations/{organization_id}/locations/{location_id}/training-rollouts"
    detail = f"{base}/{{rollout_id}}"
    preview = f"{detail}/preview"
    confirm = f"{detail}/confirm"
    lesson_rule = f"{detail}/lesson-rules/{{lesson_id}}"

    assert set(document["paths"][base]) == {"post"}
    assert set(document["paths"][detail]) == {"get"}
    assert set(document["paths"][preview]) == {"post"}
    assert set(document["paths"][confirm]) == {"post"}
    assert set(document["paths"][lesson_rule]) == {"patch"}
    serialized = str(
        {
            "paths": {
                path: document["paths"][path]
                for path in (base, detail, preview, confirm, lesson_rule)
            },
            "schemas": {
                name: schema
                for name, schema in document["components"]["schemas"].items()
                if "Rollout" in name
            },
        }
    ).lower()
    assert "assessment" not in serialized
    assert "answer_key" not in serialized
    assert "certification" not in serialized
