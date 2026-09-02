import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.observability import configure_observability
from app.db.session import create_engine, create_session_factory
from app.models.enums import BackgroundJobType
from app.security.invitation_tokens import InvitationTokenManager
from app.services.background_job_handlers import (
    BackgroundJobHandlers,
    TrainingNotificationMessage,
)
from app.services.background_jobs import (
    ClaimedJob,
    claim_next_job,
    complete_job,
    fail_job,
    heartbeat_job,
)
from app.services.invitation_delivery import InvitationEmailAdapter
from app.services.password_reset_delivery import (
    PasswordResetEmailAdapter,
    PasswordResetTokenManager,
)

JobHandler = Callable[[ClaimedJob], Awaitable[None]]
logger = logging.getLogger("app.worker")


class InProductTrainingNotificationAdapter:
    async def send_training_notification(self, message: TrainingNotificationMessage) -> None:
        # РџСЂРёР·РЅР°С‡РµРЅРЅСЏ РІР¶Рµ РІРёРґРёРјРµ Сѓ РїСЂРѕРґСѓРєС‚С–.
        # Job РїС–РґС‚РІРµСЂРґР¶СѓС” РґРѕСЃС‚СѓРїРЅС–СЃС‚СЊ С†СЊРѕРіРѕ СЃС‚Р°РЅСѓ.
        logger.info(
            "training.notification_available",
            extra={
                "organization_id": message.organization_id,
                "assignment_id": message.assignment_id,
                "rollout_id": message.rollout_id,
                "template_code": message.template_code,
                "locale": message.locale,
            },
        )


@dataclass
class WorkerRuntime:
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    worker_id: str
    handlers: Mapping[BackgroundJobType, JobHandler]
    idle_seconds: float
    heartbeat_interval_seconds: float

    async def close(self) -> None:
        await self.engine.dispose()


def build_worker_runtime(
    settings: Settings,
    *,
    invitation_adapter: InvitationEmailAdapter,
    password_reset_adapter: PasswordResetEmailAdapter,
) -> WorkerRuntime:
    settings.validate_invitation_security()
    settings.validate_password_reset_security()
    configure_observability(settings)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    handlers = BackgroundJobHandlers(
        session_factory,
        invitation_token_manager=InvitationTokenManager(settings.invitation_token_hmac_keys),
        password_reset_token_manager=PasswordResetTokenManager(
            [key.get_secret_value() for key in settings.password_reset_token_hmac_keys]
        ),
        invitation_adapter=invitation_adapter,
        password_reset_adapter=password_reset_adapter,
        training_notification_adapter=InProductTrainingNotificationAdapter(),
    ).registry()
    return WorkerRuntime(
        engine=engine,
        session_factory=session_factory,
        worker_id=settings.worker_id,
        handlers=handlers,
        idle_seconds=settings.worker_idle_seconds,
        heartbeat_interval_seconds=settings.worker_heartbeat_interval_seconds,
    )


def _job_log_context(claimed: ClaimedJob) -> dict[str, object]:
    return {
        "request_id": claimed.request_id,
        "job_id": claimed.job_id,
        "attempt_id": claimed.attempt_id,
        "job_type": claimed.job_type,
        "attempt_number": claimed.attempt_number,
    }


def _finalization_time(claim_time: datetime) -> datetime:
    # Тестовий або відновлений clock може випереджати системний,
    # але Job не може завершитися до claim.
    return max(datetime.now(UTC), claim_time)


async def _maintain_heartbeat(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    claimed: ClaimedJob,
    worker_id: str,
    stop: asyncio.Event,
    lease_lost: asyncio.Event,
    heartbeat_interval_seconds: float,
) -> None:
    while True:
        try:
            await asyncio.wait_for(stop.wait(), timeout=heartbeat_interval_seconds)
            return
        except TimeoutError:
            async with session_factory() as session, session.begin():
                owned = await heartbeat_job(
                    session,
                    job_id=claimed.job_id,
                    attempt_id=claimed.attempt_id,
                    worker_id=worker_id,
                    now=datetime.now(UTC),
                )
            if not owned:
                lease_lost.set()
                return


async def run_worker_once(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    worker_id: str,
    handlers: Mapping[BackgroundJobType, JobHandler],
    now: datetime | None = None,
    heartbeat_interval_seconds: float = 15.0,
) -> bool:
    if heartbeat_interval_seconds <= 0:
        raise ValueError("Heartbeat interval must be positive")
    claim_time = now or datetime.now(UTC)
    async with session_factory() as session, session.begin():
        claimed = await claim_next_job(session, worker_id=worker_id, now=claim_time)
    if claimed is None:
        return False

    log_context = _job_log_context(claimed)
    logger.info("job.claimed", extra=log_context)

    handler = handlers.get(BackgroundJobType(claimed.job_type))
    if handler is None:
        async with session_factory() as session, session.begin():
            await fail_job(
                session,
                job_id=claimed.job_id,
                attempt_id=claimed.attempt_id,
                worker_id=worker_id,
                now=_finalization_time(claim_time),
                error_code="JOB_HANDLER_UNAVAILABLE",
                error_message="No approved handler is registered for this Job type.",
            )
        logger.error(
            "job.failed",
            extra={**log_context, "error_code": "JOB_HANDLER_UNAVAILABLE"},
        )
        return True

    stop_heartbeat = asyncio.Event()
    lease_lost = asyncio.Event()
    heartbeat_task = asyncio.create_task(
        _maintain_heartbeat(
            session_factory,
            claimed=claimed,
            worker_id=worker_id,
            stop=stop_heartbeat,
            lease_lost=lease_lost,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
        )
    )
    handler_failed = False
    try:
        await handler(claimed)
    except Exception as exc:
        handler_failed = True
        logger.warning(
            "job.handler_failed",
            extra={**log_context, "exception_type": type(exc).__name__},
        )
    finally:
        stop_heartbeat.set()
        await heartbeat_task

    if lease_lost.is_set():
        logger.warning("job.lease_lost", extra=log_context)
        return True
    if handler_failed:
        # Виняток обробника не записується дослівно, щоб не перенести секрети до Job history.
        async with session_factory() as session, session.begin():
            failure = await fail_job(
                session,
                job_id=claimed.job_id,
                attempt_id=claimed.attempt_id,
                worker_id=worker_id,
                now=_finalization_time(claim_time),
                error_code="JOB_HANDLER_ERROR",
                error_message="Approved Job handler failed.",
            )
        logger.error(
            "job.failed" if failure.status == "failed" else "job.retry_scheduled",
            extra={
                **log_context,
                "error_code": "JOB_HANDLER_ERROR",
                "next_run_at": failure.next_run_at,
            },
        )
    else:
        async with session_factory() as session, session.begin():
            await complete_job(
                session,
                job_id=claimed.job_id,
                attempt_id=claimed.attempt_id,
                worker_id=worker_id,
                now=_finalization_time(claim_time),
            )
        logger.info("job.completed", extra=log_context)
    return True


async def run_worker(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    worker_id: str,
    handlers: Mapping[BackgroundJobType, JobHandler],
    idle_seconds: float = 1.0,
    heartbeat_interval_seconds: float = 15.0,
    settings: Settings | None = None,
) -> None:
    configure_observability(settings or get_settings())
    logger.info("worker.started")
    while True:
        claimed = await run_worker_once(
            session_factory,
            worker_id=worker_id,
            handlers=handlers,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
        )
        if not claimed:
            await asyncio.sleep(idle_seconds)


async def run_worker_runtime(runtime: WorkerRuntime, *, settings: Settings) -> None:
    try:
        await run_worker(
            runtime.session_factory,
            worker_id=runtime.worker_id,
            handlers=runtime.handlers,
            idle_seconds=runtime.idle_seconds,
            heartbeat_interval_seconds=runtime.heartbeat_interval_seconds,
            settings=settings,
        )
    finally:
        await runtime.close()
