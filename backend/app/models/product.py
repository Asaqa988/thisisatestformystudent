"""Products shown on the public shop page and known to the voice assistant.

The image is stored in the database (a few hundred KB at most), so it survives
redeploys without a separate file store.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Integer, LargeBinary, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, deferred, mapped_column

from app.core.db import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    category: Mapped[str] = mapped_column(String(80), default="", server_default="")
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(8), default="JOD", server_default="JOD")
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Loaded only when the image itself is requested, so listing stays light.
    image: Mapped[bytes | None] = deferred(mapped_column(LargeBinary))
    image_type: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
