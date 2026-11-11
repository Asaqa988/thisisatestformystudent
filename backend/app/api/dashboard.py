"""Dashboard numbers, the event stream and integration status."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_adapter
from app.core.config import get_settings
from app.core.db import get_db
from app.integrations.base import MessagingAdapter
from app.schemas import DashboardSummary, IntegrationStatus, WebhookEventList, WebhookEventOut
from app.services import events
from app.services.ai_agent import get_ai_settings

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


@router.get("/dashboard/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db), adapter: MessagingAdapter = Depends(get_adapter)):
    return DashboardSummary(
        conversations=events.conversation_counts(db),
        events=events.event_counts(db),
        integrations=[adapter.status(), _ai_status(db)],
    )


def _ai_status(db: Session) -> IntegrationStatus:
    configured = bool(get_settings().anthropic_api_key)
    enabled = get_ai_settings(db).enabled
    if not configured:
        detail = "Add ANTHROPIC_API_KEY on the server."
    elif not enabled:
        detail = "Switched off in AI Employees."
    else:
        detail = f"Answering customers with {get_settings().ai_model}"
    return IntegrationStatus(
        key="ai",
        name="AI agent (Claude)",
        configured=configured,
        ok=configured and enabled,
        detail=detail,
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
