"""Chatwoot behind the MessagingAdapter contract."""

import time
from collections.abc import Mapping

import httpx

from app.core.config import Settings
from app.core.errors import AppError, IntegrationNotConfigured
from app.integrations.chatwoot import mapper, signature
from app.integrations.chatwoot.client import ChatwootClient
from app.schemas import ConversationSnapshot, InboundEvent, IntegrationStatus, MessageOut

# The dashboard asks for the status every few seconds. Remember the answer
# briefly so we do not call Chatwoot on every poll.
_STATUS_TTL_SECONDS = 8.0
_MAX_CONVERSATION_PAGES = 4  # Chatwoot returns 25 conversations per page


class ChatwootAdapter:
    key = "chatwoot"
    name = "Chatwoot"

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self._settings = settings
        self.client = ChatwootClient(settings, transport=transport)
        self._status_cache: tuple[float, IntegrationStatus] | None = None

    # --- Status ----------------------------------------------------------------

    def status(self) -> IntegrationStatus:
        now = time.monotonic()
        if self._status_cache and now - self._status_cache[0] < _STATUS_TTL_SECONDS:
            return self._status_cache[1]

        result = self._check()
        self._status_cache = (now, result)
        return result

    def _check(self) -> IntegrationStatus:
        verification = "hmac" if self._settings.chatwoot_webhook_secret else "disabled"

        def report(*, configured: bool, ok: bool, detail: str) -> IntegrationStatus:
            return IntegrationStatus(
                key=self.key,
                name=self.name,
                configured=configured,
                ok=ok,
                detail=detail,
                webhook_verification=verification,
            )

        if not self._settings.chatwoot_configured:
            return report(
                configured=False,
                ok=False,
                detail="Add CHATWOOT_API_TOKEN and CHATWOOT_ACCOUNT_ID to .env.",
            )
        try:
            profile = self.client.get_profile()
        except AppError as error:
            return report(configured=True, ok=False, detail=error.message)

        account_ids = {account.get("id") for account in profile.get("accounts", [])}
        if self._settings.chatwoot_account_id not in account_ids:
            return report(
                configured=True,
                ok=False,
                detail=f"The token has no access to account {self._settings.chatwoot_account_id}.",
            )
        return report(
            configured=True,
            ok=True,
            detail=f"Connected to account {self._settings.chatwoot_account_id}",
        )

    # --- Conversations and messages ----------------------------------------------

    def list_conversations(self) -> list[ConversationSnapshot]:
        inbox_names = {inbox["id"]: inbox.get("name") for inbox in self.client.list_inboxes()}

        snapshots: list[ConversationSnapshot] = []
        for page in range(1, _MAX_CONVERSATION_PAGES + 1):
            batch = self.client.list_conversations(status="all", page=page)
            snapshots.extend(mapper.to_conversation(raw, inbox_names) for raw in batch)
            if len(batch) < 25:
                break
        return snapshots

    def list_messages(self, external_conversation_id: str) -> list[MessageOut]:
        raw_messages = self.client.list_messages(external_conversation_id)
        messages = [mapper.to_message(raw) for raw in raw_messages]
        return sorted(messages, key=lambda message: message.sent_at)

    def send_message(self, external_conversation_id: str, content: str) -> MessageOut:
        return mapper.to_message(self.client.create_message(external_conversation_id, content))

    # --- Webhooks ----------------------------------------------------------------

    def verify_webhook(self, raw_body: bytes, headers: Mapping[str, str]) -> None:
        secret = self._settings.chatwoot_webhook_secret
        if not secret:
            # Fail closed: without a secret we cannot tell Chatwoot from a stranger,
            # so we accept nothing rather than accept everything.
            raise IntegrationNotConfigured(
                "Webhooks are not accepted until CHATWOOT_WEBHOOK_SECRET is set in .env."
            )
        signature.verify_signature(
            secret=secret,
            raw_body=raw_body,
            signature=headers.get(signature.SIGNATURE_HEADER),
            timestamp=headers.get(signature.TIMESTAMP_HEADER),
            max_age_seconds=self._settings.webhook_max_age_seconds,
        )

    def parse_event(self, payload: dict) -> InboundEvent:
        return mapper.to_event(payload)
