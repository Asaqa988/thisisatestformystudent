"""Products: managed in NEXUS, shown on the public shop page, known to the voice assistant.

Three routers with different doors:

    /api/v1/products        the team manages products        (NEXUS API key)
    /api/v1/voice/context   the voice service reads context   (NEXUS API key)
    /api/v1/public/...      the public shop page              (open, read-only + tickets)
"""

import uuid
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.errors import IntegrationNotConfigured, NotFound
from app.models import Product
from app.services import knowledge, products
from app.services.ai_agent import get_ai_settings

router = APIRouter(prefix="/api/v1/products", tags=["products"])
voice_router = APIRouter(prefix="/api/v1/voice", tags=["voice"])
public_router = APIRouter(prefix="/api/v1/public", tags=["public shop"])


class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field("", max_length=4000)
    category: str = Field("", max_length=80)
    price: Decimal | None = Field(None, ge=0, max_digits=12, decimal_places=2)
    currency: str = Field("JOD", max_length=8)
    is_active: bool = True
    sort_order: int = Field(0, ge=-10_000, le=10_000)
    # A new image as a data: URL (PNG, JPEG or WebP, up to 1.5 MB). Omit to keep the current one.
    image_data_url: str | None = Field(None, max_length=2_100_000)
    remove_image: bool = False


class ProductOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    category: str
    price: str | None
    currency: str
    is_active: bool
    sort_order: int
    # Path on the NEXUS API, e.g. /api/v1/public/products/<id>/image?v=1731900000
    image_path: str | None
    created_at: datetime
    updated_at: datetime


class ProductList(BaseModel):
    items: list[ProductOut]


def _out(p: Product) -> ProductOut:
    return ProductOut(
        id=p.id,
        name=p.name,
        description=p.description,
        category=p.category,
        price=None if p.price is None else f"{p.price:.2f}",
        currency=p.currency,
        is_active=p.is_active,
        sort_order=p.sort_order,
        image_path=(
            f"/api/v1/public/products/{p.id}/image?v={int(p.updated_at.timestamp())}"
            if p.image_type
            else None
        ),
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _fields(data: ProductIn) -> dict:
    return data.model_dump(exclude={"image_data_url", "remove_image"})


# ------------------------------------------------------------------ team


@router.get("", response_model=ProductList)
def list_all(db: Session = Depends(get_db)):
    return ProductList(items=[_out(p) for p in products.list_products(db, active_only=False)])


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create(data: ProductIn, db: Session = Depends(get_db)):
    product = Product(id=uuid.uuid4())
    products.apply(product, _fields(data), data.image_data_url, data.remove_image)
    db.add(product)
    db.commit()
    db.refresh(product)
    return _out(product)


@router.put("/{product_id}", response_model=ProductOut)
def update(product_id: uuid.UUID, data: ProductIn, db: Session = Depends(get_db)):
    product = products.get_product(db, product_id)
    products.apply(product, _fields(data), data.image_data_url, data.remove_image)
    db.commit()
    db.refresh(product)
    return _out(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(product_id: uuid.UUID, db: Session = Depends(get_db)):
    db.delete(products.get_product(db, product_id))
    db.commit()


# ------------------------------------------------------------ voice service


class VoiceContext(BaseModel):
    business_name: str
    instructions: str
    products_text: str
    knowledge_text: str


@voice_router.get("/context", response_model=VoiceContext)
def voice_context(db: Session = Depends(get_db)):
    """What the voice assistant knows: active products and the Knowledge Base."""
    config = get_ai_settings(db)
    limit = get_settings().kb_full_context_chars
    return VoiceContext(
        business_name=config.business_name,
        instructions=config.instructions,
        products_text=products.render_for_voice(products.list_products(db, active_only=True)),
        knowledge_text=knowledge.render(knowledge.list_articles(db))[:limit],
    )


# ------------------------------------------------------------------ public


class ShopOut(BaseModel):
    business_name: str
    voice_enabled: bool
    products: list[ProductOut]


class VoiceTicket(BaseModel):
    ws_url: str
    token: str
    expires_in: int


def _voice_ready() -> bool:
    settings = get_settings()
    return bool(settings.voice_session_secret and settings.voice_public_ws_url)


@public_router.get("/shop", response_model=ShopOut)
def shop(db: Session = Depends(get_db)):
    return ShopOut(
        business_name=get_ai_settings(db).business_name,
        voice_enabled=_voice_ready(),
        products=[_out(p) for p in products.list_products(db, active_only=True)],
    )


@public_router.get("/products/{product_id}/image")
def product_image(product_id: uuid.UUID, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if product is None or not product.is_active or not product.image_type:
        raise NotFound("That image does not exist.")
    return Response(
        content=product.image,
        media_type=product.image_type,
        # The URL carries ?v=<updated_at>, so a changed image gets a new URL.
        headers={"Cache-Control": "public, max-age=86400"},
    )


@public_router.post("/voice-ticket", response_model=VoiceTicket)
def voice_ticket():
    """A short-lived, one-use ticket to open a voice session."""
    if not _voice_ready():
        raise IntegrationNotConfigured("The voice assistant is not set up yet.")
    settings = get_settings()
    token, expires_in = products.issue_voice_ticket(settings)
    return VoiceTicket(ws_url=settings.voice_public_ws_url, token=token, expires_in=expires_in)
