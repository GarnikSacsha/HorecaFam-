from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import cron
from app.core.config import Settings


@pytest.mark.parametrize(
    "task",
    ["stale-jobs", "attempt-expiry", "retake-deadlines", "security-cleanup", "audit-retention"],
)
@pytest.mark.parametrize("fail", [False, True])
async def test_cron_uses_transaction_and_disposes_engine_on_each_outcome(
    monkeypatch: pytest.MonkeyPatch, task: cron.CronTask, fail: bool
) -> None:
    now = datetime(2031, 1, 2, tzinfo=UTC)
    settings = Settings(app_env="test", database_url="postgresql+asyncpg://localhost/horeca_test")
    engine = MagicMock()
    engine.dispose = AsyncMock()
    session = MagicMock()
    transaction = MagicMock()
    session.begin.return_value = transaction
    scope = MagicMock()
    scope.__aenter__ = AsyncMock(return_value=session)
    session_factory = MagicMock(return_value=scope)
    schedule = AsyncMock()
    recover = AsyncMock()
    operation = recover if task == "stale-jobs" else schedule
    if fail:
        operation.side_effect = RuntimeError("private-provider-message")
    log_error = MagicMock()
    monkeypatch.setattr(cron, "get_settings", lambda: settings)
    monkeypatch.setattr(cron, "configure_observability", MagicMock())
    monkeypatch.setattr(cron, "create_engine", lambda _: engine)
    monkeypatch.setattr(cron, "create_session_factory", lambda _: session_factory)
    monkeypatch.setattr(cron, "schedule_cron_task", schedule)
    monkeypatch.setattr(cron, "recover_stale_jobs", recover)
    monkeypatch.setattr(cron.logger, "error", log_error)
    if fail:
        with pytest.raises(RuntimeError, match="private-provider-message"):
            await cron.run_cron_task(task=task, now=now)
        transaction.__aexit__.assert_awaited_once()
        assert transaction.__aexit__.call_args.args[0] is RuntimeError
        assert log_error.call_args.args == ("cron.failed",)
        extra = log_error.call_args.kwargs["extra"]
        assert set(extra) == {"duration_ms", "exception_type"}
        assert extra["exception_type"] == "RuntimeError"
        assert "private-provider-message" not in str(log_error.call_args)
    else:
        await cron.run_cron_task(task=task, now=now)
        transaction.__aexit__.assert_awaited_once_with(None, None, None)
        log_error.assert_not_called()
    transaction.__aenter__.assert_awaited_once()
    engine.dispose.assert_awaited_once()
    if task == "stale-jobs":
        recover.assert_awaited_once_with(session, now=now, lease_timeout=timedelta(minutes=5))
        schedule.assert_not_awaited()
    else:
        schedule.assert_awaited_once_with(session, task=task, now=now)
        recover.assert_not_awaited()


def test_cron_cli_dispatches_only_a_supported_task(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatch = AsyncMock()
    monkeypatch.setattr(cron, "run_cron_task", dispatch)
    monkeypatch.setattr("sys.argv", ["cron", "security-cleanup"])
    cron.main()
    dispatch.assert_awaited_once_with(task="security-cleanup")
    dispatch.reset_mock()
    monkeypatch.setattr("sys.argv", ["cron", "unknown-task"])
    with pytest.raises(SystemExit) as rejected:
        cron.main()
    assert rejected.value.code == 2
    dispatch.assert_not_called()
