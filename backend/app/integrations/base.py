"""The contract every messaging integration fulfils.

The rest of the backend depends on this interface, never on a specific system.
Chatwoot is the first implementation. A second one would live in its own folder
and implement the same six methods.
"""

from collections.abc import Mapping
from typing import Protocol

from app.schemas import ConversationSnapshot, InboundEvent, IntegrationStatus, MessageOut


class MessagingAdapter(Protocol):
    key: str  # short name stored in the `source` column, for example "chatwoot"

    def status(self) -> IntegrationStatus:
        """Report whether the integration is configured and reachable. Never raises."""

    def list_conversations(self) -> list[ConversationSnapshot]:
        """Fetch conversations from the external system."""

    def list_messages(self, external_conversation_id: str) -> list[MessageOut]:
        """Fetch one conversation's messages, oldest first."""

    def send_message(self, external_conversation_id: str, content: str) -> MessageOut:
        """Send a reply to the customer and return the message that was created."""

    def add_private_note(self, external_conversation_id: str, content: str) -> None:
        """Leave a note only agents can see, never the customer."""

    def verify_webhook(self, raw_body: bytes, headers: Mapping[str, str]) -> None:
        """Raise InvalidSignature unless the request provably came from the system."""

    def parse_event(self, payload: dict) -> InboundEvent:
        """Translate a webhook body into a normalized event."""
