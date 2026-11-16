"""Motion-graphic ad videos written by Claude from the Knowledge Base.

Only the storyboard is stored. The browser draws the animation from it, so the
same ad plays on the page and downloads as a video, identically every time.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AdVideo(Base):
    __tablename__ = "ad_videos"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    brief: Mapped[str | None] = mapped_column(Text)  # optional focus, e.g. "the Growth package"
    language: Mapped[str] = mapped_column(String(8), default="en")
    aspect: Mapped[str] = mapped_column(String(8), default="9:16")
    title: Mapped[str] = mapped_column(String(200), default="New ad")
    # building -> ready | failed
    status: Mapped[str] = mapped_column(String(16), default="building", index=True)
    error: Mapped[str | None] = mapped_column(Text)
    storyboard: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
