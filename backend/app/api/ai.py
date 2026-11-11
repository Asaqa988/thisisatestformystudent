"""AI agent endpoints: settings, activity log, and the per-conversation switch."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models import AIReply, Conversation
from app.schemas import (
    AIReplyList,
    AIReplyOut,
    AISettingsIn,
    AISettingsOut,
    ConversationAIIn,
    ConversationOut,
)
from app.services import inbox
from app.services.ai_agent import get_ai_settings

router = APIRouter(prefix="/api/v1", tags=["ai"])


def _settings_out(db: Session) -> AISettingsOut:
    row = get_ai_settings(db)
    config = get_settings()
    return AISettingsOut(
        enabled=row.enabled,
        business_name=row.business_name,
        instructions=row.instructions,
        configured=bool(config.anthropic_api_key),
        model=config.ai_model,
    )


@router.get("/ai/settings", response_model=AISettingsOut)
def read_settings(db: Session = Depends(get_db)):
    return _settings_out(db)


@router.put("/ai/settings", response_model=AISettingsOut)
def update_settings(data: AISettingsIn, db: Session = Depends(get_db)):
    row = get_ai_settings(db)
    row.enabled = data.enabled
    row.business_name = data.business_name.strip()
    row.instructions = data.instructions.strip()
    row.updated_at = datetime.now(tz=UTC)
    db.commit()
    return _settings_out(db)


@router.get("/ai/activity", response_model=AIReplyList)
def activity(limit: int = Query(30, ge=1, le=200), db: Session = Depends(get_db)):
    rows = db.execute(
        select(AIReply, Conversation.contact_name)
        .join(Conversation, Conversation.id == AIReply.conversation_id)
        .order_by(AIReply.created_at.desc())
        .limit(limit)
    ).all()
    return AIReplyList(
        items=[
            AIReplyOut(
                id=reply.id,
                conversation_id=reply.conversation_id,
                contact_name=contact_name,
                status=reply.status,
                reply_text=reply.reply_text,
                reason=reply.reason,
                input_tokens=reply.input_tokens + reply.cache_read_tokens,
                output_tokens=reply.output_tokens,
                created_at=reply.created_at,
            )
            for reply, contact_name in rows
        ]
    )


@router.post("/conversations/{conversation_id}/ai", response_model=ConversationOut)
def set_conversation_ai(
    conversation_id: uuid.UUID, data: ConversationAIIn, db: Session = Depends(get_db)
):
    return inbox.to_out(inbox.set_ai_enabled(db, conversation_id, data.enabled))
