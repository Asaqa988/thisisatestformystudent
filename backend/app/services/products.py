"""Products, their images, and the voice assistant's tickets and context."""

import base64
import binascii
import hashlib
import hmac
import json
import re
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import InvalidInput, NotFound
from app.models import Product

MAX_IMAGE_BYTES = 1_500_000
_DATA_URL = re.compile(r"^data:(image/(?:png|jpeg|webp));base64,([A-Za-z0-9+/=\s]+)$")
# The first bytes of each allowed format, so a renamed file cannot pass as an image.
_SIGNATURES = {
    "image/png": lambda b: b.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": lambda b: b.startswith(b"\xff\xd8\xff"),
    "image/webp": lambda b: b[:4] == b"RIFF" and b[8:12] == b"WEBP",
}


def list_products(db: Session, *, active_only: bool) -> list[Product]:
    query = select(Product).order_by(Product.sort_order, Product.name)
    if active_only:
        query = query.where(Product.is_active.is_(True))
    return list(db.scalars(query))


def get_product(db: Session, product_id: uuid.UUID) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise NotFound("That product does not exist.")
    return product


def decode_image(data_url: str) -> tuple[bytes, str]:
    """Bytes and media type from a data: URL, checked for type and size."""
    match = _DATA_URL.match(data_url.strip())
    if not match:
        raise InvalidInput("The image must be a PNG, JPEG or WebP file.")
    media_type, encoded = match.groups()
    try:
        data = base64.b64decode(re.sub(r"\s", "", encoded), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InvalidInput("The image could not be read.") from exc
    if len(data) > MAX_IMAGE_BYTES:
        raise InvalidInput("The image is larger than 1.5 MB. Use a smaller one.")
    if not _SIGNATURES[media_type](data):
        raise InvalidInput("The file is not the image type it claims to be.")
    return data, media_type


def apply(product: Product, fields: dict, image_data_url: str | None, remove_image: bool) -> None:
    for key, value in fields.items():
        setattr(product, key, value.strip() if isinstance(value, str) else value)
    if remove_image:
        product.image = None
        product.image_type = None
    if image_data_url:
        product.image, product.image_type = decode_image(image_data_url)
    product.updated_at = datetime.now(tz=UTC)


def format_price(price: Decimal | None, currency: str) -> str:
    if price is None:
        return ""
    text = f"{price:.2f}".rstrip("0").rstrip(".")
    return f"{text} {currency}".strip()


def render_for_voice(products: list[Product]) -> str:
    """The product list as plain text for the voice assistant's prompt."""
    lines = []
    for p in products:
        parts = [p.name]
        if p.category:
            parts.append(f"(category: {p.category})")
        price = format_price(p.price, p.currency)
        if price:
            parts.append(f"- price: {price}")
        line = " ".join(parts)
        if p.description:
            line += f"\n  {p.description}"
        lines.append(f"- {line}")
    return "\n".join(lines)


# --------------------------------------------------------------- voice tickets


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def issue_voice_ticket(settings: Settings, now: float | None = None) -> tuple[str, int]:
    """A one-use ticket the browser shows the voice service to open a session.

    Format: base64url(json payload) "." base64url(HMAC-SHA256(secret, payload)).
    The voice service checks the signature and the expiry, and accepts each
    ticket id once.
    """
    issued = int(now if now is not None else time.time())
    expires = issued + settings.voice_ticket_seconds
    payload = _b64(json.dumps({"sid": uuid.uuid4().hex, "exp": expires}).encode())
    signature = hmac.new(
        settings.voice_session_secret.encode(), payload.encode(), hashlib.sha256
    ).digest()
    return f"{payload}.{_b64(signature)}", settings.voice_ticket_seconds
