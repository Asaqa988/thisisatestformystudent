"""NEXUS backend entry point.

    uvicorn app.main:app

Interactive API documentation is generated at /docs.
"""

from fastapi import FastAPI

from app.api import conversations, dashboard, health, webhooks
from app.core.errors import register_error_handlers

app = FastAPI(
    title="NEXUS API",
    version="0.1.0",
    description="Integration backend for NEXUS AI. Lesson 01: foundation and Chatwoot.",
)

register_error_handlers(app)

app.include_router(health.router)
app.include_router(dashboard.router)
app.include_router(conversations.router)
app.include_router(webhooks.router)
