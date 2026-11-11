"""Knowledge base and AI agent tables."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class KnowledgeArticle(Base):
    """One piece of business knowledge the AI may use: prices, hours, policies..."""

    __tablename__ = "knowledge_articles"
    __table_args__ = (Index("ix_knowledge_articles_search", "search", postgresql_using="gin"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    # Kept up to date by PostgreSQL. The "simple" configuration splits words
    # without language-specific stemming, so it works for Arabic and English alike.
    search: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', title || ' ' || content)", persisted=True),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AISettings(Base):
    """Workspace-wide AI settings. There is exactly one row (id = 1)."""

    __tablename__ = "ai_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    business_name: Mapped[str] = mapped_column(String(120), default="", server_default="")
    instructions: Mapped[str] = mapped_column(Text, default="", server_default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIReply(Base):
    """What the AI did about one customer message. One row per message, so a
    repeated webhook can never produce a second answer."""

    __tablename__ = "ai_replies"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id", "trigger_message_id", name="uq_ai_replies_conversation_trigger"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    trigger_message_id: Mapped[str] = mapped_column(String(64))
    # pending -> sending -> sent, or handoff / skipped / error
    status: Mapped[str] = mapped_column(String(16), default="pending")
    reply_text: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(String(500))
    external_message_id: Mapped[str | None] = mapped_column(String(64), index=True)
    model: Mapped[str | None] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cache_read_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
