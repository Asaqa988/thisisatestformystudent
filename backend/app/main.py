"""NEXUS backend entry point.

    uvicorn app.main:app

Interactive API documentation is generated at /docs.
"""

from fastapi import Depends, FastAPI

from app.api import (
    ad_videos,
    ai,
    automations,
    conversations,
    customers,
    dashboard,
    health,
    knowledge,
    products,
    webhooks,
)
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
# Open: the public shop page (active products, their images, voice tickets).
app.include_router(products.public_router)

# Application API: only the NEXUS frontend server, once NEXUS_API_KEY is set.
app.include_router(dashboard.router, dependencies=[Depends(require_api_key)])
app.include_router(conversations.router, dependencies=[Depends(require_api_key)])
app.include_router(customers.router, dependencies=[Depends(require_api_key)])
app.include_router(knowledge.router, dependencies=[Depends(require_api_key)])
app.include_router(ai.router, dependencies=[Depends(require_api_key)])
app.include_router(ad_videos.router, dependencies=[Depends(require_api_key)])
app.include_router(automations.router, dependencies=[Depends(require_api_key)])
app.include_router(products.router, dependencies=[Depends(require_api_key)])
app.include_router(products.voice_router, dependencies=[Depends(require_api_key)])
