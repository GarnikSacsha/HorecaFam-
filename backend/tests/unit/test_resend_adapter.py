from datetime import UTC, datetime
from uuid import UUID

import pytest
import resend

from app.adapters import resend_email
from app.adapters.resend_email import ResendEmailAdapter
from app.services.invitation_delivery import InvitationEmailMessage
from app.services.password_reset_delivery import PasswordResetEmailMessage


class RecordingSender:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object], str]] = []

    async def __call__(
        self,
        api_key: str,
        params: dict[str, object],
        idempotency_key: str,
    ) -> dict[str, str]:
        self.calls.append((api_key, params, idempotency_key))
        return {"id": f"email-{len(self.calls)}"}


async def test_sdk_sender_passes_idempotency_as_resend_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def record_send(
        params: object,
        options: object | None = None,
    ) -> dict[str, str]:
        captured["params"] = params
        captured["options"] = options
        return {"id": "email-sdk"}

    monkeypatch.setattr(resend.Emails, "send_async", record_send)

    response = await resend_email._send_email(
        "provider-secret",
        {"from": "a@example.com", "to": ["b@example.com"], "subject": "s", "html": "h"},
        "job-key",
    )

    assert response == {"id": "email-sdk"}
    assert captured["options"] == {"idempotency_key": "job-key"}


async def test_resend_adapter_sends_invitation_with_job_idempotency() -> None:
    sender = RecordingSender()
    adapter = ResendEmailAdapter(
        api_key="provider-secret",
        from_address="Bacara Academy <academy@example.com>",
        public_app_url="https://academy.example.com",
        sender=sender,
    )

    result = await adapter.send_invitation(
        InvitationEmailMessage(
            organization_id=UUID("5d330d0f-2ef3-48bd-bd9f-c52a8aa5ecaf"),
            invitation_id=UUID("8fa01b96-7d16-4fc4-a64f-0cd028130146"),
            email="employee@example.com",
            token="token+/=value",
            expires_at=datetime(2031, 1, 2, tzinfo=UTC),
            idempotency_key="invitation:8fa01b96:v2",
        )
    )

    assert result.provider == "resend"
    assert result.provider_message_id == "email-1"
    api_key, params, idempotency_key = sender.calls[0]
    assert api_key == "provider-secret"
    assert idempotency_key == "invitation:8fa01b96:v2"
    assert params["to"] == ["employee@example.com"]
    assert "https://academy.example.com/invite?token=token%2B%2F%3Dvalue" in str(params["html"])


async def test_resend_adapter_sends_password_reset_with_job_idempotency() -> None:
    sender = RecordingSender()
    adapter = ResendEmailAdapter(
        api_key="provider-secret",
        from_address="Bacara Academy <academy@example.com>",
        public_app_url="https://academy.example.com",
        sender=sender,
    )

    result = await adapter.send_password_reset(
        PasswordResetEmailMessage(
            email="employee@example.com",
            token="reset-token",
            expires_at=datetime(2031, 1, 2, tzinfo=UTC),
            idempotency_key="password-reset:token-id",
        )
    )

    assert result.provider == "resend"
    assert result.provider_message_id == "email-1"
    assert sender.calls[0][2] == "password-reset:token-id"
    assert "https://academy.example.com/reset-password?token=reset-token" in str(
        sender.calls[0][1]["html"]
    )
