"""The normalized shapes of NEXUS.

These are what the API returns and what the frontend knows. They contain no
Chatwoot field names. Adapters translate external data into these models, so
adding another messaging system later does not change the API or the UI.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

ConversationStatus = Literal["open", "pending", "snoozed", "resolved"]
MessageDirection = Literal["inbound", "outbound", "system"]
AuthorType = Literal["contact", "agent", "bot", "system"]


# --- Shared pieces -----------------------------------------------------------


class Contact(BaseModel):
    name: str
    email: str | None = None
    avatar_url: str | None = None


class LastMessage(BaseModel):
    preview: str
    direction: MessageDirection
    at: datetime


class Author(BaseModel):
    type: AuthorType
    name: str


# --- What adapters produce ---------------------------------------------------


class ConversationSnapshot(BaseModel):
    """An external conversation as an adapter reports it, before NEXUS stores it."""

    external_id: str
    external_account_id: str | None = None
    channel: str = "unknown"
    inbox_name: str | None = None
    status: ConversationStatus = "open"
    contact: Contact
    last_message: LastMessage | None = None
    unread_count: int = 0


class InboundEvent(BaseModel):
    """A webhook after an adapter has read it."""

    event_type: str
    external_account_id: str | None = None
    external_conversation_id: str | None = None
    summary: str = ""
    # Present when the event tells us something about a conversation.
    conversation: ConversationSnapshot | None = None


# --- What the API returns ----------------------------------------------------


class ConversationOut(BaseModel):
    id: UUID
    source: str
    external_id: str
    channel: str
    inbox_name: str | None
    status: ConversationStatus
    contact: Contact
    last_message: LastMessage | None
    unread_count: int
    updated_at: datetime


class MessageOut(BaseModel):
    id: str
    direction: MessageDirection
    author: Author
    content: str
    private: bool = False
    sent_at: datetime


class ConversationList(BaseModel):
    items: list[ConversationOut]


class MessageList(BaseModel):
    items: list[MessageOut]


class ReplyIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class SyncResult(BaseModel):
    synced: int


class IntegrationStatus(BaseModel):
    key: str
    name: str
    configured: bool
    ok: bool
    detail: str
    webhook_verification: Literal["hmac", "disabled"] | None = None


class WebhookEventOut(BaseModel):
    id: UUID
    source: str
    event_type: str
    summary: str
    external_conversation_id: str | None
    duplicate_count: int
    received_at: datetime


class WebhookEventList(BaseModel):
    items: list[WebhookEventOut]


class WebhookAck(BaseModel):
    status: Literal["accepted", "duplicate", "ignored"]
    event_id: UUID


class ConversationCounts(BaseModel):
    total: int
    open: int
    awaiting_reply: int
    resolved: int


class EventCounts(BaseModel):
    received_24h: int
    duplicates_ignored: int
    last_received_at: datetime | None


class DashboardSummary(BaseModel):
    conversations: ConversationCounts
    events: EventCounts
    integrations: list[IntegrationStatus]
