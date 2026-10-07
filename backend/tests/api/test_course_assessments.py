from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AssessmentAttempt,
    AssessmentQuestionPool,
    AssessmentReadiness,
    AssessmentVersion,
    LessonCompletion,
    OrganizationMembership,
    TrainingModuleVersion,
    User,
)
from app.security.tokens import hash_secret
from tests.api.test_employee_menu_api import attach_employee
from tests.factories.assessments import (
    make_assessment,
    make_assessment_question_pool,
    make_assessment_readiness,
    make_assessment_version,
    make_question,
    make_question_option,
    make_question_version,
)
from tests.factories.auth import make_session
from tests.factories.training import make_lesson_completion
from tests.integration.test_assessment_persistence import AssessmentContext, _make_context


async def _arrange_course(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    count: int,
) -> AssessmentContext:
    context = await _make_context(db_session)
    membership = await db_session.get_one(OrganizationMembership, context.employee.membership_id)
    user = await db_session.get_one(User, membership.user_id)
    now = datetime.now(UTC)
    auth_app.state.clock = lambda: now
    session = make_session(
        user,
        token_hash=hash_secret("course-test-session"),
        csrf_token_hash=hash_secret("course-test-csrf"),
    )
    assessment = make_assessment(
        context.training,
        context.lesson_version,
        assessment_type="course_knowledge_check",
    )
    db_session.add_all([session, assessment])
    await db_session.flush()
    version = make_assessment_version(
        assessment,
        context.training_version,
        context.lesson_version,
        question_count=count,
        feedback_policy="after_final_submission",
        threshold_percent=None,
    )
    db_session.add(version)
    await db_session.flush()
    for index in range(count):
        question = make_question(context.candidate)
        db_session.add(question)
        await db_session.flush()
        question_version = make_question_version(
            question,
            context.candidate,
            context.actor.id,
            prompt_payload={"stem": f"Ситуація {index}"},
        )
        db_session.add(question_version)
        await db_session.flush()
        db_session.add_all(
            [
                make_assessment_question_pool(
                    version, question_version, coverage_key=f"source:{index}"
                ),
                make_question_option(question_version, 0, payload={"text": "Дія A"}),
                make_question_option(question_version, 1, payload={"text": "Дія B"}),
            ]
        )
    db_session.add(
        make_assessment_readiness(
            version,
            status="warning",
            eligible_count=count,
            required_count=count,
        )
    )
    db_session.add(make_lesson_completion(context.assignment, context.lesson_version, user.id))
    await db_session.commit()
    auth_client.cookies.set("horeca_session", "course-test-session", path="/api/v1")
    return context


@pytest.mark.parametrize("count", [10, 15, 20])
async def test_course_attempt_uses_full_pool_and_hides_answers_until_finish(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    count: int,
) -> None:
    context = await _arrange_course(auth_client, auth_app, db_session, count)
    headers = {"X-CSRF-Token": "course-test-csrf", "Idempotency-Key": "course-start"}
    start_url = (
        f"/api/v1/me/training/modules/{context.lesson_version.training_module_version_id}"
        "/course/attempts"
    )
    denied = await auth_client.post(start_url, headers={"Idempotency-Key": "missing-csrf"})
    assert denied.status_code == 403
    start = await auth_client.post(
        start_url,
        headers=headers,
    )
    assert start.status_code == 200, start.text
    attempt = start.json()
    replay_start = await auth_client.post(start_url, headers=headers)
    assert replay_start.status_code == 200
    assert replay_start.json()["id"] == attempt["id"]
    for family in ("practice", "final-exam", "interactive-training"):
        hidden = await auth_client.get(f"/api/v1/me/training/{family}/attempts/{attempt['id']}")
        assert hidden.status_code == 404
    assert len(attempt["questions"]) == count
    assert attempt["result"] is None
    for question in attempt["questions"]:
        assert question["review"] is None
        assert all("is_correct" not in option for option in question["options"])
    url = f"/api/v1/me/training/course/attempts/{attempt['id']}"
    incomplete = await auth_client.post(
        url + "/finish",
        headers={**headers, "Idempotency-Key": "early"},
        json={"lease_generation": attempt["lease_generation"]},
    )
    assert incomplete.status_code == 409
    for index, question in enumerate(attempt["questions"]):
        saved = await auth_client.post(
            url + "/answer",
            headers={
                **headers,
                "Idempotency-Key": f"course-answer-{index}",
            },
            json={
                "attempt_question_id": question["id"],
                "lease_generation": attempt["lease_generation"],
                "answer_payload": {
                    "mechanic": "single_choice",
                    "option_id": question["options"][1 if index == 0 else 0]["id"],
                },
            },
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["result"] is None
        assert all(item["review"] is None for item in saved.json()["questions"])
    finished = await auth_client.post(
        url + "/finish",
        headers={
            **headers,
            "Idempotency-Key": "course-finish",
        },
        json={"lease_generation": attempt["lease_generation"]},
    )
    assert finished.status_code == 200, finished.text
    result = finished.json()["result"]
    assert result["total_count"] == count
    assert result["correct_count"] == count - 1
    assert result["score_basis_points"] == (count - 1) * 10000 // count
    assert result["pass_status"] is None
    assert all(question["review"] is not None for question in finished.json()["questions"])
    replay_finish = await auth_client.post(
        url + "/finish",
        headers={**headers, "Idempotency-Key": "course-finish"},
        json={"lease_generation": attempt["lease_generation"]},
    )
    assert replay_finish.status_code == 200
    assert replay_finish.json()["result"]["id"] == result["id"]
    retry = await auth_client.post(
        start_url, headers={**headers, "Idempotency-Key": "course-retry"}
    )
    assert retry.status_code == 200
    assert retry.json()["id"] != attempt["id"]
    await attach_employee(
        auth_client,
        db_session,
        organization_id=context.training.organization_id,
        location_id=context.training.location_id,
    )
    assert (await auth_client.get(url)).status_code == 404
    auth_client.cookies.clear()
    auth_client.cookies.set("horeca_session", "course-test-session", path="/api/v1")
    module = await db_session.get_one(
        TrainingModuleVersion, context.lesson_version.training_module_version_id
    )
    module.all_positions = False
    await db_session.commit()
    assert (await auth_client.get(url)).status_code == 404
    assert (
        await auth_client.post(start_url, headers={**headers, "Idempotency-Key": "hidden-course"})
    ).status_code == 404


@pytest.mark.parametrize(
    "problem,code",
    [
        ("completion", "COURSE_INCOMPLETE"),
        ("readiness", "ASSESSMENT_NOT_READY"),
        ("pool", "ASSESSMENT_NOT_READY"),
        ("audience", "RESOURCE_NOT_FOUND"),
    ],
)
async def test_course_start_rejects_missing_prerequisites_without_attempt(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    problem: str,
    code: str,
) -> None:
    context = await _arrange_course(auth_client, auth_app, db_session, 3)
    version = await db_session.scalar(
        select(AssessmentVersion).where(
            AssessmentVersion.assessment_type == "course_knowledge_check",
        )
    )
    assert version is not None
    if problem == "completion":
        await db_session.execute(delete(LessonCompletion))
    elif problem == "readiness":
        await db_session.execute(
            delete(AssessmentReadiness).where(
                AssessmentReadiness.assessment_version_id == version.id,
            )
        )
    elif problem == "pool":
        await db_session.execute(
            delete(AssessmentQuestionPool).where(
                AssessmentQuestionPool.assessment_version_id == version.id,
            )
        )
    else:
        module = await db_session.get_one(
            TrainingModuleVersion, context.lesson_version.training_module_version_id
        )
        module.all_positions = False
    await db_session.commit()
    module_id = context.lesson_version.training_module_version_id
    response = await auth_client.post(
        f"/api/v1/me/training/modules/{module_id}/course/attempts",
        headers={
            "X-CSRF-Token": "course-test-csrf",
            "Idempotency-Key": "missing-course-prerequisite",
        },
    )
    assert response.status_code == (404 if problem == "audience" else 409)
    assert response.json()["code"] == code
    assert await db_session.scalar(select(AssessmentAttempt.id)) is None


@pytest.mark.parametrize(
    "problem,code",
    [
        ("paused", "ATTEMPT_NOT_WRITABLE"),
        ("revoked", "ATTEMPT_NOT_WRITABLE"),
        ("expired", "ATTEMPT_EXPIRED"),
        ("lease", "ATTEMPT_DEVICE_CONFLICT"),
    ],
)
async def test_course_writes_obey_pause_revocation_expiry_and_device_lease(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
    problem: str,
    code: str,
) -> None:
    context = await _arrange_course(auth_client, auth_app, db_session, 3)
    headers = {"X-CSRF-Token": "course-test-csrf", "Idempotency-Key": "course-start"}
    module_id = context.lesson_version.training_module_version_id
    started = await auth_client.post(
        f"/api/v1/me/training/modules/{module_id}/course/attempts",
        headers=headers,
    )
    assert started.status_code == 200
    attempt = started.json()
    if problem == "paused":
        membership = await db_session.get_one(
            OrganizationMembership, context.employee.membership_id
        )
        membership.training_participation_status = "paused"
        membership.training_paused_at = datetime.now(UTC)
    elif problem == "revoked":
        context.assignment.status = "revoked"
        context.assignment.revoked_at = datetime.now(UTC)
        context.assignment.revoke_reason = "admin"
    elif problem == "expired":
        later = datetime.now(UTC) + timedelta(days=8)
        auth_app.state.clock = lambda: later
    await db_session.commit()
    question = attempt["questions"][0]
    saved = await auth_client.post(
        f"/api/v1/me/training/course/attempts/{attempt['id']}/answer",
        headers={**headers, "Idempotency-Key": "blocked-course-answer"},
        json={
            "attempt_question_id": question["id"],
            "lease_generation": 999 if problem == "lease" else attempt["lease_generation"],
            "answer_payload": {
                "mechanic": "single_choice",
                "option_id": question["options"][0]["id"],
            },
        },
    )
    assert saved.status_code == 409
    assert saved.json()["code"] == code
    stored = await db_session.get_one(AssessmentAttempt, UUID(attempt["id"]))
    await db_session.refresh(stored)
    assert stored.status == ("expired" if problem == "expired" else "in_progress")


async def test_course_takeover_invalidates_previous_session_and_replays_once(
    auth_client: AsyncClient,
    auth_app: FastAPI,
    db_session: AsyncSession,
) -> None:
    context = await _arrange_course(auth_client, auth_app, db_session, 3)
    headers = {"X-CSRF-Token": "course-test-csrf", "Idempotency-Key": "start"}
    started = await auth_client.post(
        f"/api/v1/me/training/modules/{context.lesson_version.training_module_version_id}/course/attempts",
        headers=headers,
    )
    assert started.status_code == 200
    attempt = started.json()
    url = f"/api/v1/me/training/course/attempts/{attempt['id']}"
    membership = await db_session.get_one(OrganizationMembership, context.employee.membership_id)
    user = await db_session.get_one(User, membership.user_id)
    db_session.add(
        make_session(
            user,
            token_hash=hash_secret("course-second-session"),
            csrf_token_hash=hash_secret("course-second-csrf"),
        )
    )
    await db_session.commit()
    auth_client.cookies.clear()
    auth_client.cookies.set("horeca_session", "course-second-session", path="/api/v1")
    headers["X-CSRF-Token"] = "course-second-csrf"
    assert not (await auth_client.get(url)).json()["writable"]
    taken = await auth_client.post(
        url + "/takeover", headers={**headers, "Idempotency-Key": "take"}
    )
    assert taken.status_code == 200
    assert taken.json()["writable"]
    generation = taken.json()["lease_generation"]
    assert generation == attempt["lease_generation"] + 1
    replay = await auth_client.post(
        url + "/takeover", headers={**headers, "Idempotency-Key": "take"}
    )
    assert replay.json()["lease_generation"] == generation
    question = attempt["questions"][0]
    payload = {
        "attempt_question_id": question["id"],
        "lease_generation": generation,
        "answer_payload": {"mechanic": "single_choice", "option_id": question["options"][0]["id"]},
    }
    auth_client.cookies.clear()
    auth_client.cookies.set("horeca_session", "course-test-session", path="/api/v1")
    headers["X-CSRF-Token"] = "course-test-csrf"
    rejected = await auth_client.post(
        url + "/answer", headers={**headers, "Idempotency-Key": "old"}, json=payload
    )
    assert rejected.status_code == 409
    assert rejected.json()["code"] == "ATTEMPT_DEVICE_CONFLICT"
    auth_client.cookies.clear()
    auth_client.cookies.set("horeca_session", "course-second-session", path="/api/v1")
    headers["X-CSRF-Token"] = "course-second-csrf"
    saved = await auth_client.post(
        url + "/answer", headers={**headers, "Idempotency-Key": "new"}, json=payload
    )
    assert saved.status_code == 200
    assert saved.json()["questions"][0]["answer_payload"] is not None
