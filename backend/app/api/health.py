"""Health checks.

/health        "Is the process alive?"            Used by Docker's healthcheck.
/health/ready  "Can it do useful work right now?" Checks the database, reports Chatwoot.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_adapter
from app.core.db import get_db
from app.integrations.base import MessagingAdapter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "nexus-backend"}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db), adapter: MessagingAdapter = Depends(get_adapter)):
    try:
        db.execute(text("SELECT 1"))
        database = {"ok": True}
    except SQLAlchemyError:
        database = {"ok": False, "detail": "The NEXUS database is not reachable."}

    chatwoot = adapter.status()
    body = {
        "status": "ready" if database["ok"] else "not_ready",
        "checks": {
            "database": database,
            # Reported, but it does not make NEXUS "not ready": the app still
            # starts and explains what is missing when Chatwoot is not set up.
            "chatwoot": {
                "ok": chatwoot.ok,
                "configured": chatwoot.configured,
                "detail": chatwoot.detail,
            },
        },
    }
    return JSONResponse(body, status_code=200 if database["ok"] else 503)
