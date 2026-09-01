import asyncio
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.enums import BackgroundJobType
from app.services.background_jobs import (
    ClaimedJob,
    claim_next_job,
    complete_job,
    fail_job,
    heartbeat_job,
)

JobHandler = Callable[[ClaimedJob], Awaitable[None]]


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

    handler = handlers.get(BackgroundJobType(claimed.job_type))
    if handler is None:
        async with session_factory() as session, session.begin():
            await fail_job(
                session,
                job_id=claimed.job_id,
                attempt_id=claimed.attempt_id,
                worker_id=worker_id,
                now=datetime.now(UTC),
                error_code="JOB_HANDLER_UNAVAILABLE",
                error_message="No approved handler is registered for this Job type.",
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
    except Exception:
        handler_failed = True
    finally:
        stop_heartbeat.set()
        await heartbeat_task

    if lease_lost.is_set():
        return True
    if handler_failed:
        # Виняток обробника не записується дослівно, щоб не перенести секрети до Job history.
        async with session_factory() as session, session.begin():
            await fail_job(
                session,
                job_id=claimed.job_id,
                attempt_id=claimed.attempt_id,
                worker_id=worker_id,
                now=datetime.now(UTC),
                error_code="JOB_HANDLER_ERROR",
                error_message="Approved Job handler failed.",
            )
    else:
        async with session_factory() as session, session.begin():
            await complete_job(
                session,
                job_id=claimed.job_id,
                attempt_id=claimed.attempt_id,
                worker_id=worker_id,
                now=datetime.now(UTC),
            )
    return True


async def run_worker(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    worker_id: str,
    handlers: Mapping[BackgroundJobType, JobHandler],
    idle_seconds: float = 1.0,
) -> None:
    while True:
        claimed = await run_worker_once(
            session_factory,
            worker_id=worker_id,
            handlers=handlers,
        )
        if not claimed:
            await asyncio.sleep(idle_seconds)
