"""Webhook intake: store once, then act."""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.integrations.base import MessagingAdapter
from app.models import Conversation, WebhookEvent
from app.schemas import ConversationCounts, EventCounts, WebhookAck
from app.services.ai_agent import is_ai_message
from app.services.inbox import upsert_conversation


@dataclass
class AITrigger:
    """A new customer message the AI agent should look at."""

    conversation_id: uuid.UUID
    message_id: str


@dataclass
class IngestResult:
    ack: WebhookAck
    ai_trigger: AITrigger | None = None

    @property
    def status(self) -> str:
        return self.ack.status


def dedupe_key_for(delivery_id: str | None, raw_body: bytes) -> str:
    """Identify a delivery.

    Chatwoot gives each delivery an id in the X-Chatwoot-Delivery header. If a
    request has none, fall back to a fingerprint of the exact bytes received:
    a byte-for-byte repeat is then still recognized.
    """
    if delivery_id:
        return f"delivery:{delivery_id.strip()}"[:255]
    return "sha256:" + hashlib.sha256(raw_body).hexdigest()


def ingest_webhook(
    db: Session,
    adapter: MessagingAdapter,
    *,
    raw_body: bytes,
    payload: dict,
    delivery_id: str | None,
) -> IngestResult:
    """Record a verified webhook exactly once and apply what it tells us.

    Webhook senders retry when they are unsure a delivery arrived, so receiving
    the same event twice is normal. The INSERT below relies on the unique
    constraint (source, dedupe_key): the database lets only the first copy in.
    """
    event = adapter.parse_event(payload)
    key = dedupe_key_for(delivery_id, raw_body)
    acted_on = event.conversation is not None

    inserted_id = db.execute(
        pg_insert(WebhookEvent)
        .values(
            id=uuid.uuid4(),
            source=adapter.key,
            dedupe_key=key,
            event_type=event.event_type,
            external_account_id=event.external_account_id,
            external_conversation_id=event.external_conversation_id,
            summary=event.summary,
            status="processed" if acted_on else "ignored",
            payload=payload,
        )
        .on_conflict_do_nothing(constraint="uq_webhook_events_source_dedupe_key")
        .returning(WebhookEvent.id)
    ).scalar_one_or_none()

    if inserted_id is None:
        # Seen before. Count it, change nothing else, and still answer 200 so
        # the sender stops retrying.
        existing_id = db.execute(
            update(WebhookEvent)
            .where(WebhookEvent.source == adapter.key, WebhookEvent.dedupe_key == key)
            .values(
                duplicate_count=WebhookEvent.duplicate_count + 1,
                last_duplicate_at=datetime.now(tz=UTC),
            )
            .returning(WebhookEvent.id)
        ).scalar_one()
        db.commit()
        return IngestResult(WebhookAck(status="duplicate", event_id=existing_id))

    trigger = None
    if event.conversation is not None:
        conversation = upsert_conversation(db, adapter.key, event.conversation)
        trigger = _react_to_message(db, conversation, event)

    # One commit: the event row and the conversation change succeed or fail together.
    db.commit()
    ack = WebhookAck(status="accepted" if acted_on else "ignored", event_id=inserted_id)
    return IngestResult(ack, trigger)


def _react_to_message(db: Session, conversation: Conversation, event) -> AITrigger | None:
    """Decide what a new message means for the AI agent.

    - A customer message: the agent should look at it.
    - A reply a team member wrote (not the AI): the agent steps back from this
      conversation, so it never talks over a person.
    """
    message = event.message
    if event.event_type != "message_created" or message is None or message.private:
        return None

    if message.direction == "inbound" and message.author_type == "contact":
        return AITrigger(conversation_id=conversation.id, message_id=message.external_id)

    if (
        message.direction == "outbound"
        and message.author_type == "agent"
        and conversation.ai_enabled
        and not is_ai_message(db, conversation.id, message.external_id, message.content)
    ):
        conversation.ai_enabled = False
        conversation.ai_paused_reason = "A team member replied, so the AI stepped back."
    return None


def recent_events(db: Session, limit: int = 20) -> list[WebhookEvent]:
    return list(
        db.scalars(select(WebhookEvent).order_by(WebhookEvent.received_at.desc()).limit(limit))
    )


def event_counts(db: Session) -> EventCounts:
    since = datetime.now(tz=UTC) - timedelta(hours=24)
    received, duplicates, last = db.execute(
        select(
            func.count().filter(WebhookEvent.received_at >= since),
            func.coalesce(func.sum(WebhookEvent.duplicate_count), 0),
            func.max(WebhookEvent.received_at),
        )
    ).one()
    return EventCounts(received_24h=received, duplicates_ignored=duplicates, last_received_at=last)


def conversation_counts(db: Session) -> ConversationCounts:
    not_resolved = Conversation.status != "resolved"
    total, open_, awaiting, resolved = db.execute(
        select(
            func.count(),
            func.count().filter(not_resolved),
            func.count().filter(not_resolved, Conversation.last_message_direction == "inbound"),
            func.count().filter(Conversation.status == "resolved"),
        )
    ).one()
    return ConversationCounts(total=total, open=open_, awaiting_reply=awaiting, resolved=resolved)
