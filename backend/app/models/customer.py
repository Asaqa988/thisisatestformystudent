"""People who have written to the business, on any channel."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Customer(Base):
    """A customer as NEXUS knows them. Chatwoot is the source of these details;
    NEXUS keeps a copy so the Customers page loads fast and can be searched."""

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_customers_source_external_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(64))

    name: Mapped[str] = mapped_column(String(200), default="Unknown contact")
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    phone: Mapped[str | None] = mapped_column(String(40), index=True)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    identifier: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(120))
    company: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    social_profiles: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    custom_attributes: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    channels: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
