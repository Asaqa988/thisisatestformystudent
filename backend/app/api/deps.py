"""Shared FastAPI dependencies."""

import hmac
from functools import lru_cache

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import Unauthorized
from app.integrations.base import MessagingAdapter
from app.integrations.chatwoot import ChatwootAdapter


@lru_cache
def _chatwoot_adapter() -> ChatwootAdapter:
    return ChatwootAdapter(get_settings())


def get_adapter() -> MessagingAdapter:
    """The messaging system behind the Inbox. Routes ask for the interface, not for Chatwoot.

    Tests replace this dependency with an adapter that talks to a fake Chatwoot.
    """
    return _chatwoot_adapter()


def require_api_key(request: Request) -> None:
    """Only the NEXUS frontend server may call the application API once it is deployed.

    Disabled when NEXUS_API_KEY is empty, which is the case in local development.
    """
    expected = get_settings().nexus_api_key
    if not expected:
        return
    given = request.headers.get("x-nexus-api-key", "")
    if not hmac.compare_digest(given.encode(), expected.encode()):
        raise Unauthorized("A valid X-NEXUS-API-Key header is required.")


async def read_raw_body(request: Request) -> bytes:
    """The request body exactly as it arrived. Signatures are checked against these bytes."""
    return await request.body()
