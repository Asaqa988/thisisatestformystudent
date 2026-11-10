"""Dashboard numbers, the event stream and integration status."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_adapter
from app.core.db import get_db
from app.integrations.base import MessagingAdapter
from app.schemas import DashboardSummary, IntegrationStatus, WebhookEventList, WebhookEventOut
from app.services import events

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/dashboard/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db), adapter: MessagingAdapter = Depends(get_adapter)):
    return DashboardSummary(
        conversations=events.conversation_counts(db),
        events=events.event_counts(db),
        integrations=[adapter.status()],
    )


@router.get("/events", response_model=WebhookEventList)
def list_events(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    rows = events.recent_events(db, limit)
    return WebhookEventList(
        items=[
            WebhookEventOut(
                id=row.id,
                source=row.source,
                event_type=row.event_type,
                summary=row.summary,
                external_conversation_id=row.external_conversation_id,
                duplicate_count=row.duplicate_count,
                received_at=row.received_at,
            )
            for row in rows
        ]
    )


@router.get("/integrations/chatwoot/status", response_model=IntegrationStatus)
def chatwoot_status(adapter: MessagingAdapter = Depends(get_adapter)):
    return adapter.status()
