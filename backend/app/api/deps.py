"""Shared FastAPI dependencies."""

from functools import lru_cache

from fastapi import Request

from app.core.config import get_settings
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


async def read_raw_body(request: Request) -> bytes:
    """The request body exactly as it arrived. Signatures are checked against these bytes."""
    return await request.body()
