"""A lightweight reference to a conversation that lives in an external system.

NEXUS does not copy the conversation. It remembers which one it is, who it is
with and what was said last, so the Inbox list loads from our own database.
The messages themselves are fetched from the source when a thread is opened.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_conversations_source_external_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Where it really lives.
    source: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(64))
    external_account_id: Mapped[str | None] = mapped_column(String(64))

    channel: Mapped[str] = mapped_column(String(32), default="unknown")
    inbox_name: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)

    contact_name: Mapped[str] = mapped_column(String(200), default="Unknown contact")
    contact_email: Mapped[str | None] = mapped_column(String(320))
    contact_avatar_url: Mapped[str | None] = mapped_column(Text)

    last_message_preview: Mapped[str | None] = mapped_column(String(280))
    last_message_direction: Mapped[str | None] = mapped_column(String(16))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unread_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    # The AI agent answers this conversation only while this is true. It turns
    # itself off when it hands over to a human, or when a human replies.
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    ai_paused_reason: Mapped[str | None] = mapped_column(String(300))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
