"""Every webhook NEXUS has received, stored once."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        # The duplicate guard. The database, not our code, guarantees that the
        # same delivery from the same source can be stored only once, even if
        # two copies arrive at the same instant.
        UniqueConstraint("source", "dedupe_key", name="uq_webhook_events_source_dedupe_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(32))
    dedupe_key: Mapped[str] = mapped_column(String(255))

    # Normalized fields: the same columns whatever system sent the event.
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    external_account_id: Mapped[str | None] = mapped_column(String(64))
    external_conversation_id: Mapped[str | None] = mapped_column(String(64), index=True)
    summary: Mapped[str] = mapped_column(String(300), default="")
    status: Mapped[str] = mapped_column(String(16), default="processed")  # processed | ignored

    # The original body, kept for debugging and for future lessons.
    payload: Mapped[dict] = mapped_column(JSONB)

    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_duplicate_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
