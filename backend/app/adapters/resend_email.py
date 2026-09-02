from collections.abc import Awaitable, Callable, Mapping
from html import escape
from typing import Any, cast
from urllib.parse import quote

import resend

from app.services.invitation_delivery import (
    EmailAdapterResult,
    InvitationEmailMessage,
)
from app.services.password_reset_delivery import (
    PasswordResetEmailAdapterResult,
    PasswordResetEmailMessage,
)

ResendSender = Callable[
    [str, dict[str, Any], str],
    Awaitable[Mapping[str, Any]],
]


async def _send_email(
    api_key: str,
    params: dict[str, Any],
    idempotency_key: str,
) -> Mapping[str, Any]:
    resend.api_key = api_key
    typed_params = cast(resend.Emails.SendParams, params)
    options: resend.Emails.SendOptions = {"idempotency_key": idempotency_key}
    return await resend.Emails.send_async(
        typed_params,
        options,
    )


class ResendEmailAdapter:
    def __init__(
        self,
        *,
        api_key: str,
        from_address: str,
        public_app_url: str,
        sender: ResendSender = _send_email,
    ) -> None:
        self._api_key = api_key
        self._from_address = from_address
        self._public_app_url = public_app_url.rstrip("/")
        self._sender = sender

    async def _send(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        idempotency_key: str,
    ) -> str:
        response = await self._sender(
            self._api_key,
            {
                "from": self._from_address,
                "to": [to],
                "subject": subject,
                "html": html,
            },
            idempotency_key,
        )
        provider_message_id = response.get("id")
        if not isinstance(provider_message_id, str) or not provider_message_id:
            raise RuntimeError("Resend accepted response is missing the email identifier")
        return provider_message_id

    async def send_invitation(self, message: InvitationEmailMessage) -> EmailAdapterResult:
        url = f"{self._public_app_url}/invite?token={quote(message.token, safe='')}"
        invitation_link = escape(url, quote=True)
        provider_message_id = await self._send(
            to=message.email,
            subject="Р’Р°СЃ Р·Р°РїСЂРѕС€РµРЅРѕ РґРѕ Bacara Academy",
            html=(
                "<p>Р’Р°СЃ Р·Р°РїСЂРѕС€РµРЅРѕ РґРѕ Bacara Academy.</p>"
                f'<p><a href="{invitation_link}">РџСЂРёР№РЅСЏС‚Рё Р·Р°РїСЂРѕС€РµРЅРЅСЏ</a></p>'
            ),
            idempotency_key=message.idempotency_key,
        )
        return EmailAdapterResult(provider="resend", provider_message_id=provider_message_id)

    async def send_password_reset(
        self,
        message: PasswordResetEmailMessage,
    ) -> PasswordResetEmailAdapterResult:
        url = f"{self._public_app_url}/reset-password?token={quote(message.token, safe='')}"
        provider_message_id = await self._send(
            to=message.email,
            subject="Р’С–РґРЅРѕРІР»РµРЅРЅСЏ РїР°СЂРѕР»СЏ Bacara Academy",
            html=(
                "<p>РњРё РѕС‚СЂРёРјР°Р»Рё Р·Р°РїРёС‚ РЅР° РІС–РґРЅРѕРІР»РµРЅРЅСЏ РїР°СЂРѕР»СЏ.</p>"
                f'<p><a href="{escape(url, quote=True)}">Р’С–РґРЅРѕРІРёС‚Рё РїР°СЂРѕР»СЊ</a></p>'
            ),
            idempotency_key=message.idempotency_key,
        )
        return PasswordResetEmailAdapterResult(
            provider="resend",
            provider_message_id=provider_message_id,
        )
