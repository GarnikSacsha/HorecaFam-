import asyncio
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import APIError
from app.db.session import create_engine, create_session_factory
from app.models import ApiIdempotencyRecord, BackgroundJob, EmailDelivery
from app.security.invitation_tokens import InvitationTokenManager
from app.security.tokens import hash_secret
from app.services.idempotency import (
    IdempotencyDecision,
    request_fingerprint,
    reserve_idempotency,
)
from app.services.invitation_delivery import (
    EmailAdapterResult,
    InvitationEmailMessage,
    deliver_invitation_email,
    enqueue_invitation_email,
)
from tests.factories import (
    make_background_job,
    make_email_delivery,
    make_invitation,
    make_organization,
    make_user,
)


class CapturingEmailAdapter:
    def __init__(self) -> None:
        self.messages: list[InvitationEmailMessage] = []

    async def send_invitation(self, message: InvitationEmailMessage) -> EmailAdapterResult:
        self.messages.append(message)
        return EmailAdapterResult(provider="fake", provider_message_id="fake-message-1")


def token_manager() -> InvitationTokenManager:
    return InvitationTokenManager([SecretStr("current-key-" + "a" * 32)])


@pytest.mark.integration
async def test_delivery_reconstructs_token_only_inside_adapter_boundary(
    db_session: AsyncSession,
) -> None:
    manager = token_manager()
    organization = make_organization()
    inviter = make_user(email_normalized="admin@example.com")
    db_session.add_all([organization, inviter])
    await db_session.flush()
    invitation_id = uuid4()
    raw_token = manager.derive(invitation_id, token_version=1, key_index=0)
    invitation = make_invitation(
        organization,
        inviter,
        id=invitation_id,
        token_hash=hash_secret(raw_token),
    )
    db_session.add(invitation)
    await db_session.flush()
    job, delivery = await enqueue_invitation_email(db_session, invitation=invitation)
    adapter = CapturingEmailAdapter()
    now = datetime.now(UTC)

    delivered = await deliver_invitation_email(
        db_session,
        job_id=job.id,
        token_manager=manager,
        adapter=adapter,
        now=now,
    )
    await db_session.flush()

    assert delivered is True
    assert adapter.messages == [
        InvitationEmailMessage(
            organization_id=organization.id,
            invitation_id=invitation.id,
            email=invitation.email_normalized,
            token=raw_token,
            expires_at=invitation.expires_at,
        )
    ]
    assert raw_token not in json.dumps(job.payload)
    assert raw_token not in invitation.token_hash
    assert job.status == "completed"
    assert delivery.status == "accepted"

    repeated = await deliver_invitation_email(
        db_session,
        job_id=job.id,
        token_manager=manager,
        adapter=adapter,
        now=now,
    )
    assert repeated is False
    assert len(adapter.messages) == 1


@pytest.mark.integration
async def test_delivery_rejects_superseded_job_without_adapter_call(
    db_session: AsyncSession,
) -> None:
    manager = token_manager()
    organization = make_organization()
    inviter = make_user(email_normalized="admin@example.com")
    db_session.add_all([organization, inviter])
    await db_session.flush()
    invitation_id = uuid4()
    current_token = manager.derive(invitation_id, token_version=2, key_index=0)
    invitation = make_invitation(
        organization,
        inviter,
        id=invitation_id,
        token_hash=hash_secret(current_token),
        token_version=2,
    )
    db_session.add(invitation)
    await db_session.flush()
    job = make_background_job(
        organization,
        invitation,
        payload={"invitation_id": str(invitation.id), "token_version": 1},
        idempotency_key=f"invitation:{invitation.id}:v1",
    )
    db_session.add(job)
    await db_session.flush()
    delivery = make_email_delivery(organization, invitation, job)
    db_session.add(delivery)
    await db_session.flush()
    adapter = CapturingEmailAdapter()

    delivered = await deliver_invitation_email(
        db_session,
        job_id=job.id,
        token_manager=manager,
        adapter=adapter,
        now=datetime.now(UTC),
    )
    await db_session.flush()

    assert delivered is False
    assert adapter.messages == []
    assert job.status == "failed"
    assert job.last_error_code == "INVITATION_SUPERSEDED"
    assert delivery.status == "failed"


@pytest.mark.integration
async def test_delivery_rejects_revoked_invitation_without_adapter_call(
    db_session: AsyncSession,
) -> None:
    manager = token_manager()
    organization = make_organization()
    inviter = make_user(email_normalized="admin@example.com")
    db_session.add_all([organization, inviter])
    await db_session.flush()
    invitation_id = uuid4()
    raw_token = manager.derive(invitation_id, token_version=1, key_index=0)
    invitation = make_invitation(
        organization,
        inviter,
        id=invitation_id,
        token_hash=hash_secret(raw_token),
    )
    db_session.add(invitation)
    await db_session.flush()
    job, delivery = await enqueue_invitation_email(db_session, invitation=invitation)
    invitation.status = "revoked"
    invitation.revoked_at = datetime.now(UTC)
    adapter = CapturingEmailAdapter()

    delivered = await deliver_invitation_email(
        db_session,
        job_id=job.id,
        token_manager=manager,
        adapter=adapter,
        now=datetime.now(UTC),
    )
    await db_session.flush()

    assert delivered is False
    assert adapter.messages == []
    assert job.status == "failed"
    assert delivery.status == "failed"


@pytest.mark.integration
async def test_enqueue_rolls_back_with_its_business_transaction(
    db_session: AsyncSession,
) -> None:
    manager = token_manager()
    organization = make_organization()
    inviter = make_user(email_normalized="admin@example.com")
    db_session.add_all([organization, inviter])
    await db_session.flush()
    invitation_id = uuid4()
    invitation = make_invitation(
        organization,
        inviter,
        id=invitation_id,
        token_hash=hash_secret(manager.derive(invitation_id, token_version=1, key_index=0)),
    )
    db_session.add(invitation)
    await db_session.commit()

    job, delivery = await enqueue_invitation_email(db_session, invitation=invitation)
    job_id = job.id
    delivery_id = delivery.id
    await db_session.rollback()

    assert (
        await db_session.scalar(
            select(func.count()).select_from(BackgroundJob).where(BackgroundJob.id == job_id)
        )
        == 0
    )
    assert (
        await db_session.scalar(
            select(func.count()).select_from(EmailDelivery).where(EmailDelivery.id == delivery_id)
        )
        == 0
    )


@pytest.mark.integration
async def test_idempotency_replays_same_request_and_rejects_changed_request(
    db_session: AsyncSession,
) -> None:
    organization = make_organization()
    actor = make_user(email_normalized="admin@example.com")
    db_session.add_all([organization, actor])
    await db_session.flush()
    now = datetime.now(UTC)
    resource_id = uuid4()
    fingerprint = request_fingerprint({"email": "employee@example.com"})

    async def reserve(fingerprint_value: str) -> IdempotencyDecision:
        return await reserve_idempotency(
            db_session,
            organization_id=organization.id,
            actor_user_id=actor.id,
            action="invitation.create",
            key="create-key",
            fingerprint=fingerprint_value,
            resource_type="invitation",
            resource_id=resource_id,
            response_status=201,
            now=now,
        )

    created = await reserve(fingerprint)
    replayed = await reserve(fingerprint)

    assert created.replayed is False
    assert replayed.replayed is True
    assert replayed.record.id == created.record.id
    with pytest.raises(APIError) as exc_info:
        await reserve(request_fingerprint({"email": "other@example.com"}))
    assert exc_info.value.code == "IDEMPOTENCY_KEY_REUSED"


@pytest.mark.integration
async def test_expired_idempotency_record_can_be_reused(db_session: AsyncSession) -> None:
    organization = make_organization()
    actor = make_user(email_normalized="admin@example.com")
    db_session.add_all([organization, actor])
    await db_session.flush()
    old_resource_id = uuid4()
    old = ApiIdempotencyRecord(
        organization_id=organization.id,
        actor_user_id=actor.id,
        action="invitation.create",
        key="expired-key",
        request_fingerprint="a" * 64,
        resource_type="invitation",
        resource_id=old_resource_id,
        response_status=201,
        created_at=datetime.now(UTC) - timedelta(hours=25),
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(old)
    await db_session.flush()
    new_resource_id = uuid4()

    decision = await reserve_idempotency(
        db_session,
        organization_id=organization.id,
        actor_user_id=actor.id,
        action="invitation.create",
        key="expired-key",
        fingerprint="b" * 64,
        resource_type="invitation",
        resource_id=new_resource_id,
        response_status=201,
        now=datetime.now(UTC),
    )

    assert decision.replayed is False
    assert decision.record.resource_id == new_resource_id
    assert decision.record.request_fingerprint == "b" * 64


@pytest.mark.integration
async def test_concurrent_idempotency_reservations_choose_one_resource(
    db_session: AsyncSession,
    migrated_test_database: Settings,
) -> None:
    organization = make_organization()
    actor = make_user(email_normalized="admin@example.com")
    db_session.add_all([organization, actor])
    await db_session.commit()
    organization_id = organization.id
    actor_id = actor.id
    now = datetime.now(UTC)
    fingerprint = request_fingerprint({"email": "employee@example.com"})
    engine = create_engine(migrated_test_database)
    session_factory = create_session_factory(engine)

    async def reserve(candidate_resource_id: UUID) -> tuple[bool, UUID, UUID]:
        async with session_factory() as session:
            decision = await reserve_idempotency(
                session,
                organization_id=organization_id,
                actor_user_id=actor_id,
                action="invitation.create",
                key="concurrent-key",
                fingerprint=fingerprint,
                resource_type="invitation",
                resource_id=candidate_resource_id,
                response_status=201,
                now=now,
            )
            await session.commit()
            return decision.replayed, decision.record.id, decision.record.resource_id

    try:
        results = await asyncio.gather(reserve(uuid4()), reserve(uuid4()))
    finally:
        await engine.dispose()

    assert sorted(result[0] for result in results) == [False, True]
    assert results[0][1] == results[1][1]
    assert results[0][2] == results[1][2]
