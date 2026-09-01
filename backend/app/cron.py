import argparse
import asyncio
import logging
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Literal, cast
from uuid import uuid4

from app.core.config import get_settings
from app.core.observability import bind_observability_context, configure_observability
from app.db.session import create_engine, create_session_factory
from app.services.maintenance import recover_stale_jobs, schedule_cron_task

CronTask = Literal[
    "stale-jobs",
    "attempt-expiry",
    "retake-deadlines",
    "security-cleanup",
    "audit-retention",
]
logger = logging.getLogger("app.cron")


async def run_cron_task(*, task: CronTask, now: datetime | None = None) -> None:
    settings = get_settings()
    configure_observability(settings)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    run_at = now or datetime.now(UTC)
    started_at = perf_counter()
    try:
        with bind_observability_context(request_id=str(uuid4()), cron_task=task):
            logger.info("cron.started")
            try:
                async with session_factory() as session, session.begin():
                    if task == "stale-jobs":
                        await recover_stale_jobs(
                            session,
                            now=run_at,
                            lease_timeout=timedelta(minutes=5),
                        )
                    else:
                        await schedule_cron_task(
                            session,
                            task=task,
                            now=run_at,
                        )
            except Exception as exc:
                logger.error(
                    "cron.failed",
                    extra={
                        "duration_ms": round((perf_counter() - started_at) * 1000, 3),
                        "exception_type": type(exc).__name__,
                    },
                )
                raise
            logger.info(
                "cron.completed",
                extra={"duration_ms": round((perf_counter() - started_at) * 1000, 3)},
            )
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one bounded HoReCa maintenance scheduler")
    parser.add_argument(
        "task",
        choices=(
            "stale-jobs",
            "attempt-expiry",
            "retake-deadlines",
            "security-cleanup",
            "audit-retention",
        ),
    )
    arguments = parser.parse_args()
    asyncio.run(run_cron_task(task=cast(CronTask, arguments.task)))


if __name__ == "__main__":
    main()
