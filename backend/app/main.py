"""NEXUS backend entry point.

    uvicorn app.main:app

Interactive API documentation is generated at /docs.
"""

from fastapi import Depends, FastAPI

from app.api import conversations, dashboard, health, webhooks
from app.api.deps import require_api_key
from app.core.errors import register_error_handlers

app = FastAPI(
    title="NEXUS API",
    version="0.1.0",
    description="Integration backend for NEXUS AI. Lesson 01: foundation and Chatwoot.",
)

register_error_handlers(app)

# Open: liveness checks, and webhooks (they prove themselves with an HMAC signature).
app.include_router(health.router)
app.include_router(webhooks.router)

# Application API: only the NEXUS frontend server, once NEXUS_API_KEY is set.
app.include_router(dashboard.router, dependencies=[Depends(require_api_key)])
app.include_router(conversations.router, dependencies=[Depends(require_api_key)])
