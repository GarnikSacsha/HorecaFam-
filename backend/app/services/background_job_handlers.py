from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import BackgroundJobType, TrainingAssignment, TrainingRollout
from app.security.invitation_tokens import InvitationTokenManager
from app.services.background_jobs import ClaimedJob
from app.services.invitation_delivery import (
    InvitationEmailAdapter,
    deliver_claimed_invitation_email,
)
from app.services.maintenance import cleanup_security_records, expire_attempts, run_audit_retention
from app.services.password_reset_delivery import (
    PasswordResetEmailAdapter,
    PasswordResetTokenManager,
    deliver_claimed_password_reset_email,
)
from app.services.retakes import project_retake_deadlines


@dataclass(frozen=True)
class TrainingNotificationMessage:
    organization_id: UUID
    assignment_id: UUID
    rollout_id: UUID | None
    template_code: str
    locale: str


class TrainingNotificationAdapter(Protocol):
    async def send_training_notification(self, message: TrainingNotificationMessage) -> None: ...


def _timestamp(payload: dict[str, object], field: str) -> datetime:
    raw = payload.get(field)
    if not isinstance(raw, str):
        raise RuntimeError("Maintenance Job timestamp is unavailable")
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise RuntimeError("Maintenance Job timestamp must be timezone-aware")
    return value


class BackgroundJobHandlers:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        invitation_token_manager: InvitationTokenManager,
        password_reset_token_manager: PasswordResetTokenManager,
        invitation_adapter: InvitationEmailAdapter,
        password_reset_adapter: PasswordResetEmailAdapter,
        training_notification_adapter: TrainingNotificationAdapter,
    ) -> None:
        self._session_factory = session_factory
        self._invitation_token_manager = invitation_token_manager
        self._password_reset_token_manager = password_reset_token_manager
        self._invitation_adapter = invitation_adapter
        self._password_reset_adapter = password_reset_adapter
        self._training_notification_adapter = training_notification_adapter

    async def invitation_email(self, claimed: ClaimedJob) -> None:
        async with self._session_factory() as session, session.begin():
            await deliver_claimed_invitation_email(
                session,
                job_id=claimed.job_id,
                token_manager=self._invitation_token_manager,
                adapter=self._invitation_adapter,
                now=datetime.now(UTC),
            )

    async def password_reset_email(self, claimed: ClaimedJob) -> None:
        async with self._session_factory() as session, session.begin():
            await deliver_claimed_password_reset_email(
                session,
                job_id=claimed.job_id,
                token_manager=self._password_reset_token_manager,
                adapter=self._password_reset_adapter,
                now=datetime.now(UTC),
            )

    async def training_assignment_notification(self, claimed: ClaimedJob) -> None:
        await self._send_training_notification(claimed, rollout=False)

    async def training_rollout_notification(self, claimed: ClaimedJob) -> None:
        await self._send_training_notification(claimed, rollout=True)

    async def _send_training_notification(self, claimed: ClaimedJob, *, rollout: bool) -> None:
        assignment_id = UUID(str(claimed.payload.get("assignment_id")))
        rollout_id = UUID(str(claimed.payload.get("rollout_id"))) if rollout else None
        template_code = str(claimed.payload.get("template_code"))
        locale = str(claimed.payload.get("locale"))
        async with self._session_factory() as session:
            assignment = await session.scalar(
                select(TrainingAssignment).where(
                    TrainingAssignment.id == assignment_id,
                    TrainingAssignment.organization_id == claimed.organization_id,
                )
            )
            if assignment is None:
                return
            if rollout_id is not None:
                matching_rollout = await session.scalar(
                    select(TrainingRollout.id).where(
                        TrainingRollout.id == rollout_id,
                        TrainingRollout.organization_id == claimed.organization_id,
                    )
                )
                if matching_rollout is None:
                    return
        await self._training_notification_adapter.send_training_notification(
            TrainingNotificationMessage(
                organization_id=assignment.organization_id,
                assignment_id=assignment.id,
                rollout_id=rollout_id,
                template_code=template_code,
                locale=locale,
            )
        )

    async def attempt_expiry(self, claimed: ClaimedJob) -> None:
        async with self._session_factory() as session, session.begin():
            await expire_attempts(
                session,
                cutoff_at=_timestamp(claimed.payload, "cutoff_at"),
            )

    async def retake_deadline_projection(self, claimed: ClaimedJob) -> None:
        async with self._session_factory() as session, session.begin():
            await project_retake_deadlines(
                session,
                now=_timestamp(claimed.payload, "projected_at"),
            )

    async def security_record_cleanup(self, claimed: ClaimedJob) -> None:
        async with self._session_factory() as session, session.begin():
            await cleanup_security_records(
                session,
                cutoff_at=_timestamp(claimed.payload, "cutoff_at"),
            )

    async def audit_retention(self, claimed: ClaimedJob) -> None:
        request_id = UUID(claimed.request_id) if claimed.request_id else uuid4()
        dry_run = claimed.payload.get("dry_run") is True
        async with self._session_factory() as session, session.begin():
            await run_audit_retention(
                session,
                cutoff_at=_timestamp(claimed.payload, "cutoff_at"),
                batch_size=500,
                request_id=request_id,
                dry_run=dry_run,
            )

    def registry(self) -> dict[BackgroundJobType, Callable[[ClaimedJob], Awaitable[None]]]:
        return {
            BackgroundJobType.INVITATION_EMAIL: self.invitation_email,
            BackgroundJobType.PASSWORD_RESET_EMAIL: self.password_reset_email,
            BackgroundJobType.TRAINING_ASSIGNMENT_NOTIFICATION: (
                self.training_assignment_notification
            ),
            BackgroundJobType.TRAINING_ROLLOUT_NOTIFICATION: self.training_rollout_notification,
            BackgroundJobType.ATTEMPT_EXPIRY: self.attempt_expiry,
            BackgroundJobType.RETAKE_DEADLINE_PROJECTION: self.retake_deadline_projection,
            BackgroundJobType.SECURITY_RECORD_CLEANUP: self.security_record_cleanup,
            BackgroundJobType.AUDIT_RETENTION: self.audit_retention,
        }
