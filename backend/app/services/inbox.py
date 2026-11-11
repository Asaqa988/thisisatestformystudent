"""Inbox logic: conversation references in our database, messages through the adapter."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.integrations.base import MessagingAdapter
from app.models import Conversation
from app.schemas import (
    Author,
    Contact,
    ConversationOut,
    ConversationSnapshot,
    LastMessage,
    MessageOut,
)
from app.services.ai_agent import ai_message_ids

UNKNOWN_CONTACT = "Unknown contact"


def to_out(row: Conversation) -> ConversationOut:
    last = None
    if row.last_message_at and row.last_message_direction:
        last = LastMessage(
            preview=row.last_message_preview or "",
            direction=row.last_message_direction,
            at=row.last_message_at,
        )
    return ConversationOut(
        id=row.id,
        source=row.source,
        external_id=row.external_id,
        channel=row.channel,
        inbox_name=row.inbox_name,
        status=row.status,
        contact=Contact(
            name=row.contact_name, email=row.contact_email, avatar_url=row.contact_avatar_url
        ),
        last_message=last,
        unread_count=row.unread_count,
        updated_at=row.updated_at,
        ai_enabled=row.ai_enabled,
        ai_paused_reason=row.ai_paused_reason,
    )


def list_conversations(db: Session, status: str | None = None) -> list[Conversation]:
    query = select(Conversation)
    if status:
        query = query.where(Conversation.status == status)
    # Most recent activity first.
    query = query.order_by(
        func.coalesce(Conversation.last_message_at, Conversation.updated_at).desc()
    )
    return list(db.scalars(query))


def get_conversation(db: Session, conversation_id: uuid.UUID) -> Conversation:
    row = db.get(Conversation, conversation_id)
    if row is None:
        raise NotFound("That conversation does not exist in NEXUS.")
    return row


def upsert_conversation(db: Session, source: str, snapshot: ConversationSnapshot) -> Conversation:
    """Create the reference if it is new, then bring it up to date.

    Chatwoot often sends `conversation_created` and `message_created` at almost
    the same moment. "Look, then insert" would let both requests insert the
    same conversation. So we insert with ON CONFLICT DO NOTHING (only one can
    win) and then lock the row while we update it.
    """
    db.execute(
        pg_insert(Conversation)
        .values(
            id=uuid.uuid4(),
            source=source,
            external_id=snapshot.external_id,
            contact_name=snapshot.contact.name,
        )
        .on_conflict_do_nothing(constraint="uq_conversations_source_external_id")
    )
    row = db.scalars(
        select(Conversation)
        .where(Conversation.source == source, Conversation.external_id == snapshot.external_id)
        .with_for_update()
    ).one()

    row.status = snapshot.status
    row.unread_count = snapshot.unread_count
    if snapshot.external_account_id:
        row.external_account_id = snapshot.external_account_id
    if snapshot.channel != "unknown":
        row.channel = snapshot.channel
    if snapshot.inbox_name:
        row.inbox_name = snapshot.inbox_name

    # Some events carry no contact details. Never overwrite a real name with a placeholder.
    if snapshot.contact.name != UNKNOWN_CONTACT or not row.contact_name:
        row.contact_name = snapshot.contact.name
    if snapshot.contact.email:
        row.contact_email = snapshot.contact.email
    if snapshot.contact.avatar_url:
        row.contact_avatar_url = snapshot.contact.avatar_url

    # Events can arrive out of order. Only a newer message replaces the preview.
    last = snapshot.last_message
    if last and (row.last_message_at is None or last.at >= row.last_message_at):
        row.last_message_preview = last.preview
        row.last_message_direction = last.direction
        row.last_message_at = last.at

    row.updated_at = datetime.now(tz=UTC)
    return row


def sync_from_source(db: Session, adapter: MessagingAdapter) -> int:
    """Pull every conversation from the source. Used for the first load and as a
    safety net in case a webhook was missed while NEXUS was offline."""
    snapshots = adapter.list_conversations()
    for snapshot in snapshots:
        upsert_conversation(db, adapter.key, snapshot)
    db.commit()
    return len(snapshots)


def list_messages(
    db: Session, adapter: MessagingAdapter, conversation_id: uuid.UUID
) -> list[MessageOut]:
    row = get_conversation(db, conversation_id)
    messages = adapter.list_messages(row.external_id)

    # Show which replies the AI wrote. The source system only knows they were
    # sent with the agent's API token.
    ai_ids = ai_message_ids(db, row.id)
    for message in messages:
        if message.id in ai_ids:
            message.author = Author(type="bot", name="NEXUS AI")
    return messages


def set_ai_enabled(db: Session, conversation_id: uuid.UUID, enabled: bool) -> Conversation:
    row = get_conversation(db, conversation_id)
    row.ai_enabled = enabled
    row.ai_paused_reason = None if enabled else "Turned off by a team member."
    db.commit()
    return row


def send_reply(
    db: Session, adapter: MessagingAdapter, conversation_id: uuid.UUID, content: str
) -> MessageOut:
    row = get_conversation(db, conversation_id)
    message = adapter.send_message(row.external_id, content)

    # A person is handling this conversation now; the AI steps back.
    if row.ai_enabled:
        row.ai_enabled = False
        row.ai_paused_reason = "A team member replied from NEXUS, so the AI stepped back."
        db.commit()

    # Update our reference right away, so the list is correct before the
    # webhook for this same message comes back from Chatwoot.
    if row.last_message_at is None or message.sent_at >= row.last_message_at:
        row.last_message_preview = " ".join(message.content.split())[:140]
        row.last_message_direction = message.direction
        row.last_message_at = message.sent_at
        row.updated_at = datetime.now(tz=UTC)
        db.commit()
    return message
