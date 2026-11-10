"""Translate Chatwoot JSON into NEXUS shapes.

This is the only file that knows Chatwoot's field names. Chatwoot describes the
same thing differently depending on where it appears:

    REST API     message_type: 0 | 1 | 2 | 3      created_at: 1731254400
    Webhooks     message_type: "incoming" | ...   created_at: "2026-11-10T16:20:11.000Z"

Every function here accepts both, and returns one consistent shape.
"""

from datetime import UTC, datetime
from typing import Any

from app.schemas import (
    Author,
    Contact,
    ConversationSnapshot,
    InboundEvent,
    LastMessage,
    MessageOut,
)

PREVIEW_LENGTH = 140

_DIRECTIONS = {
    0: "inbound",
    "incoming": "inbound",
    1: "outbound",
    "outgoing": "outbound",
    2: "system",
    "activity": "system",
    3: "outbound",
    "template": "outbound",
}

_CHANNELS = {
    "Channel::Api": "api",
    "Channel::WebWidget": "web_widget",
    "Channel::Email": "email",
    "Channel::Whatsapp": "whatsapp",
    "Channel::Telegram": "telegram",
    "Channel::Sms": "sms",
    "Channel::TwilioSms": "sms",
    "Channel::FacebookPage": "facebook",
    "Channel::Instagram": "instagram",
    "Channel::Line": "line",
}

_STATUSES = {"open", "pending", "snoozed", "resolved"}

_AUTHOR_TYPES = {
    "contact": "contact",
    "user": "agent",
    "agent_bot": "bot",
    "captain_assistant": "bot",
}

# Events that describe a conversation. Others are stored but not acted on yet.
CONVERSATION_EVENTS = {
    "conversation_created",
    "conversation_updated",
    "conversation_status_changed",
}
MESSAGE_EVENTS = {"message_created", "message_updated"}


# --- Small converters --------------------------------------------------------


def to_datetime(value: Any) -> datetime:
    """Accept a Unix timestamp, an ISO string or Chatwoot's 'YYYY-MM-DD HH:MM:SS UTC'."""
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str) and value:
        text = value.strip()
        if text.isdigit():
            return datetime.fromtimestamp(int(text), tz=UTC)
        text = text.replace(" UTC", "+00:00").replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return datetime.now(tz=UTC)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return datetime.now(tz=UTC)


def to_direction(message_type: Any) -> str:
    return _DIRECTIONS.get(message_type, "system")


def to_channel(channel: str | None) -> str:
    if not channel:
        return "unknown"
    return _CHANNELS.get(channel, channel.removeprefix("Channel::").lower())


def to_status(status: Any) -> str:
    return status if status in _STATUSES else "open"


def to_preview(content: str | None) -> str:
    text = " ".join((content or "").split())
    return text if len(text) <= PREVIEW_LENGTH else text[: PREVIEW_LENGTH - 1] + "…"


def to_contact(sender: dict | None) -> Contact:
    sender = sender or {}
    return Contact(
        name=sender.get("name") or "Unknown contact",
        email=sender.get("email") or None,
        avatar_url=sender.get("thumbnail") or sender.get("avatar") or None,
    )


def to_author(sender: dict | None, direction: str) -> Author:
    if direction == "system":
        return Author(type="system", name="System")
    sender = sender or {}
    fallback = "contact" if direction == "inbound" else "agent"
    author_type = _AUTHOR_TYPES.get(sender.get("type", ""), fallback)
    default_name = "Customer" if author_type == "contact" else "Agent"
    return Author(type=author_type, name=sender.get("name") or default_name)


# --- Messages ----------------------------------------------------------------


def to_message(raw: dict) -> MessageOut:
    direction = to_direction(raw.get("message_type"))
    return MessageOut(
        id=str(raw.get("id")),
        direction=direction,
        author=to_author(raw.get("sender"), direction),
        content=raw.get("content") or "",
        private=bool(raw.get("private")),
        sent_at=to_datetime(raw.get("created_at")),
    )


def to_last_message(raw: dict | None) -> LastMessage | None:
    """Build the list preview from a message. Internal notes never become the preview."""
    if not raw or raw.get("private"):
        return None
    direction = to_direction(raw.get("message_type"))
    if direction == "system":
        return None
    return LastMessage(
        preview=to_preview(raw.get("content")),
        direction=direction,
        at=to_datetime(raw.get("created_at")),
    )


# --- Conversations -----------------------------------------------------------


def to_conversation(raw: dict, inbox_names: dict[int, str] | None = None) -> ConversationSnapshot:
    """Normalize a conversation from the REST API or from a conversation webhook."""
    meta = raw.get("meta") or {}
    messages = raw.get("messages") or []
    last = raw.get("last_non_activity_message") or (messages[-1] if messages else None)
    inbox_id = raw.get("inbox_id")

    return ConversationSnapshot(
        external_id=str(raw.get("id")),
        external_account_id=_optional_str(raw.get("account_id")),
        channel=to_channel(meta.get("channel") or raw.get("channel")),
        inbox_name=(inbox_names or {}).get(inbox_id),
        status=to_status(raw.get("status")),
        contact=to_contact(meta.get("sender")),
        last_message=to_last_message(last),
        unread_count=int(raw.get("unread_count") or 0),
    )


# --- Webhook events ----------------------------------------------------------


def to_event(payload: dict) -> InboundEvent:
    event_type = str(payload.get("event") or "unknown")
    account_id = _optional_str(
        (payload.get("account") or {}).get("id") or payload.get("account_id")
    )

    if event_type in MESSAGE_EVENTS:
        return _message_event(event_type, account_id, payload)
    if event_type in CONVERSATION_EVENTS:
        return _conversation_event(event_type, account_id, payload)

    conversation = payload.get("conversation") or {}
    return InboundEvent(
        event_type=event_type,
        external_account_id=account_id,
        external_conversation_id=_optional_str(conversation.get("id")),
        summary=event_type.replace("_", " ").capitalize(),
    )


def _message_event(event_type: str, account_id: str | None, payload: dict) -> InboundEvent:
    conversation_raw = dict(payload.get("conversation") or {})
    # The message is the top level of the payload; make it the conversation's last message.
    conversation_raw["messages"] = [payload]
    conversation_raw.pop("last_non_activity_message", None)
    conversation_raw.setdefault("account_id", account_id)

    inbox = payload.get("inbox") or {}
    inbox_names = {inbox["id"]: inbox.get("name")} if inbox.get("id") is not None else None
    snapshot = (
        to_conversation(conversation_raw, inbox_names) if conversation_raw.get("id") else None
    )

    direction = to_direction(payload.get("message_type"))
    author = to_author(payload.get("sender"), direction)
    if payload.get("private"):
        # Internal notes can be sensitive, so the event list does not quote them.
        summary = f"Internal note by {author.name}"
    else:
        summary = f"{author.name}: {to_preview(payload.get('content'))}"

    return InboundEvent(
        event_type=event_type,
        external_account_id=account_id,
        external_conversation_id=snapshot.external_id if snapshot else None,
        summary=summary[:300],
        conversation=snapshot,
    )


def _conversation_event(event_type: str, account_id: str | None, payload: dict) -> InboundEvent:
    payload = {**payload, "account_id": payload.get("account_id") or account_id}
    snapshot = to_conversation(payload)
    labels = {
        "conversation_created": "New conversation with",
        "conversation_updated": "Conversation updated for",
        "conversation_status_changed": f"Conversation marked {snapshot.status} for",
    }
    return InboundEvent(
        event_type=event_type,
        external_account_id=account_id,
        external_conversation_id=snapshot.external_id,
        summary=f"{labels[event_type]} {snapshot.contact.name}"[:300],
        conversation=snapshot,
    )


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)
