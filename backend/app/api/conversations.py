"""Inbox endpoints. See docs/api-contracts.md."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_adapter
from app.core.db import get_db
from app.integrations.base import MessagingAdapter
from app.schemas import (
    ConversationList,
    ConversationOut,
    ConversationStatus,
    MessageList,
    MessageOut,
    ReplyIn,
    SyncResult,
)
from app.services import inbox

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get("", response_model=ConversationList)
def list_conversations(status: ConversationStatus | None = None, db: Session = Depends(get_db)):
    """Read from the NEXUS database, so the list works even if Chatwoot is slow or down."""
    rows = inbox.list_conversations(db, status)
    return ConversationList(items=[inbox.to_out(row) for row in rows])


@router.post("/sync", response_model=SyncResult)
def sync_conversations(
    db: Session = Depends(get_db), adapter: MessagingAdapter = Depends(get_adapter)
):
    return SyncResult(synced=inbox.sync_from_source(db, adapter))


@router.get("/{conversation_id}", response_model=ConversationOut)
def get_conversation(conversation_id: uuid.UUID, db: Session = Depends(get_db)):
    return inbox.to_out(inbox.get_conversation(db, conversation_id))


@router.get("/{conversation_id}/messages", response_model=MessageList)
def list_messages(
    conversation_id: uuid.UUID,
    db: Session = Depends(get_db),
    adapter: MessagingAdapter = Depends(get_adapter),
):
    return MessageList(items=inbox.list_messages(db, adapter, conversation_id))


@router.post(
    "/{conversation_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED
)
def send_reply(
    conversation_id: uuid.UUID,
    reply: ReplyIn,
    db: Session = Depends(get_db),
    adapter: MessagingAdapter = Depends(get_adapter),
):
    return inbox.send_reply(db, adapter, conversation_id, reply.content.strip())
