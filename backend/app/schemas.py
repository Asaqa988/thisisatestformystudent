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
    customer: "CustomerSnapshot | None" = None


class EventMessage(BaseModel):
    """The message a message event is about."""

    external_id: str
    direction: MessageDirection
    author_type: AuthorType
    private: bool = False
    content: str = ""


class InboundEvent(BaseModel):
    """A webhook after an adapter has read it."""

    event_type: str
    external_account_id: str | None = None
    external_conversation_id: str | None = None
    summary: str = ""
    # Present when the event tells us something about a conversation.
    conversation: ConversationSnapshot | None = None
    # Present on message events.
    message: EventMessage | None = None
    # Present on contact events.
    customer: "CustomerSnapshot | None" = None


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
    ai_enabled: bool = True
    ai_paused_reason: str | None = None
    customer_id: UUID | None = None


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


# --- Knowledge base and AI agent ------------------------------------------------


class KnowledgeArticleIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=50_000)


class KnowledgeArticleOut(BaseModel):
    id: UUID
    title: str
    content: str
    updated_at: datetime


class KnowledgeArticleList(BaseModel):
    items: list[KnowledgeArticleOut]
    total_chars: int


class AISettingsIn(BaseModel):
    enabled: bool
    business_name: str = Field(default="", max_length=120)
    instructions: str = Field(default="", max_length=8_000)


class AISettingsOut(AISettingsIn):
    configured: bool  # an API key is present on the server
    model: str


AIReplyStatus = Literal["pending", "sending", "sent", "handoff", "skipped", "error"]


class AIReplyOut(BaseModel):
    id: UUID
    conversation_id: UUID
    contact_name: str
    status: AIReplyStatus
    reply_text: str | None
    reason: str | None
    input_tokens: int
    output_tokens: int
    created_at: datetime


class AIReplyList(BaseModel):
    items: list[AIReplyOut]


class ConversationAIIn(BaseModel):
    enabled: bool


# --- Customers ------------------------------------------------------------------


class CustomerSnapshot(BaseModel):
    """A customer (contact) as an adapter reports it, before NEXUS stores it."""

    external_id: str
    name: str = "Unknown contact"
    email: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    identifier: str | None = None
    city: str | None = None
    country: str | None = None
    company: str | None = None
    description: str | None = None
    social_profiles: dict[str, str] = Field(default_factory=dict)
    custom_attributes: dict = Field(default_factory=dict)
    channels: list[str] = Field(default_factory=list)
    blocked: bool = False
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None


class CustomerSummary(BaseModel):
    id: UUID
    source: str
    external_id: str
    name: str
    email: str | None
    phone: str | None
    avatar_url: str | None
    city: str | None
    country: str | None
    company: str | None
    channels: list[str]
    conversation_count: int
    open_conversations: int
    last_message_at: datetime | None
    last_message_preview: str | None
    first_seen_at: datetime | None


class CustomerList(BaseModel):
    items: list[CustomerSummary]
    total: int


class CustomerDetail(CustomerSummary):
    identifier: str | None
    description: str | None
    social_profiles: dict[str, str]
    custom_attributes: dict
    blocked: bool
    updated_at: datetime
    conversations: list[ConversationOut]


class CustomerSyncResult(BaseModel):
    customers: int
    conversations: int


# Forward references: snapshots mention CustomerSnapshot before it is defined.
ConversationSnapshot.model_rebuild()
InboundEvent.model_rebuild()
