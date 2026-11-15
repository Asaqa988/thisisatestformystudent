"""Automations built from a spoken or typed request, their runs, and the files they make."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Automation(Base):
    """A saved automation: the request, and the plan the crew designed for it.

    The plan is a list of steps from a fixed catalog of NEXUS tools
    (app/automations/tools.py). Re-running it uses the plan, not the AI.
    """

    __tablename__ = "automations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    request_text: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(200), default="New automation")
    summary: Mapped[str | None] = mapped_column(Text)
    # building -> ready | unsupported | failed
    status: Mapped[str] = mapped_column(String(16), default="building", index=True)
    error: Mapped[str | None] = mapped_column(Text)
    plan: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    review_notes: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    run_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AutomationRun(Base):
    """One execution of an automation.

    running -> succeeded | failed, or
    running -> awaiting_approval -> (approve) running -> succeeded | failed
                                 -> (reject) rejected
    """

    __tablename__ = "automation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    automation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("automations.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="running", index=True)
    # What each step produced, for display.
    outputs: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    # For action steps: exactly what will happen, and to whom, once approved.
    pending_actions: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    error: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AutomationFile(Base):
    """A file a run produced, such as an Excel export. Kept in the database because
    the hosting platform's disk is wiped on every deploy."""

    __tablename__ = "automation_files"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("automation_runs.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(200))
    content_type: Mapped[str] = mapped_column(String(120))
    size: Mapped[int] = mapped_column(Integer)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
