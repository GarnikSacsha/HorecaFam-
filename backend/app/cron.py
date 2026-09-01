import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from app.core.config import get_settings
from app.db.session import create_engine, create_session_factory
from app.services.maintenance import recover_stale_jobs, schedule_cron_task

CronTask = Literal[
    "stale-jobs",
    "attempt-expiry",
    "retake-deadlines",
    "security-cleanup",
    "audit-retention",
]


async def run_cron_task(*, task: CronTask, now: datetime | None = None) -> None:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    run_at = now or datetime.now(UTC)
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
