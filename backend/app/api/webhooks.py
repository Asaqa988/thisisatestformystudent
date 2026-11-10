"""Where Chatwoot delivers events. Called by Chatwoot, never by the browser."""

import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_adapter, read_raw_body
from app.core.db import get_db
from app.core.errors import AppError
from app.integrations.base import MessagingAdapter
from app.integrations.chatwoot.signature import DELIVERY_HEADER
from app.schemas import WebhookAck
from app.services.events import ingest_webhook

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


class InvalidPayload(AppError):
    status_code = 400
    code = "invalid_payload"


@router.post("/chatwoot", response_model=WebhookAck)
def chatwoot_webhook(
    request: Request,
    raw_body: bytes = Depends(read_raw_body),
    db: Session = Depends(get_db),
    adapter: MessagingAdapter = Depends(get_adapter),
):
    # 1. Authenticate first, against the raw bytes. Nothing is parsed or stored
    #    for a request that fails this check.
    adapter.verify_webhook(raw_body, request.headers)

    # 2. Only now read the content.
    try:
        payload = json.loads(raw_body)
    except ValueError:
        raise InvalidPayload("The webhook body is not valid JSON.") from None
    if not isinstance(payload, dict):
        raise InvalidPayload("The webhook body must be a JSON object.")

    # 3. Store once, then act.
    return ingest_webhook(
        db,
        adapter,
        raw_body=raw_body,
        payload=payload,
        delivery_id=request.headers.get(DELIVERY_HEADER),
    )
