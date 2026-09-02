from uuid import UUID

import pytest

from app.core.config import Settings
from app.models import BackgroundJobType
from app.services.background_job_handlers import TrainingNotificationMessage
from app.services.invitation_delivery import EmailAdapterResult, InvitationEmailMessage
from app.services.password_reset_delivery import (
    PasswordResetEmailAdapterResult,
    PasswordResetEmailMessage,
)
from app.worker import InProductTrainingNotificationAdapter, build_worker_runtime


class UnusedInvitationAdapter:
    async def send_invitation(self, message: InvitationEmailMessage) -> EmailAdapterResult:
        raise AssertionError(f"Unexpected invitation for {message.email}")


class UnusedPasswordResetAdapter:
    async def send_password_reset(
        self, message: PasswordResetEmailMessage
    ) -> PasswordResetEmailAdapterResult:
        raise AssertionError(f"Unexpected password reset for {message.email}")


async def test_worker_composition_registers_closed_handler_catalogue() -> None:
    runtime = build_worker_runtime(
        Settings(
            app_env="test",
            database_url="postgresql+asyncpg://postgres:postgres@localhost:5432/horeca_test",
            invitation_token_hmac_keys=["i" * 32],
            password_reset_token_hmac_keys=["r" * 32],
            worker_id="worker-test",
        ),
        invitation_adapter=UnusedInvitationAdapter(),
        password_reset_adapter=UnusedPasswordResetAdapter(),
    )

    try:
        assert runtime.worker_id == "worker-test"
        assert set(runtime.handlers) == set(BackgroundJobType)
    finally:
        await runtime.close()


async def test_in_product_training_adapter_logs_only_safe_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = InProductTrainingNotificationAdapter()
    message = TrainingNotificationMessage(
        organization_id=UUID("5d330d0f-2ef3-48bd-bd9f-c52a8aa5ecaf"),
        assignment_id=UUID("8fa01b96-7d16-4fc4-a64f-0cd028130146"),
        rollout_id=None,
        template_code="training_assigned",
        locale="uk",
    )
    captured: dict[str, object] = {}

    def record_info(event: str, *, extra: dict[str, object]) -> None:
        captured["event"] = event
        captured.update(extra)

    monkeypatch.setattr("app.worker.logger.info", record_info)

    await adapter.send_training_notification(message)

    assert captured["event"] == "training.notification_available"
    assert captured["assignment_id"] == message.assignment_id
    assert "payload" not in captured
