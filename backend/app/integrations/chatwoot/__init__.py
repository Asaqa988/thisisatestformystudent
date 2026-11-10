"""Everything that knows how Chatwoot works lives in this package.

client.py     HTTP calls: URLs, the token header, error translation
mapper.py     Chatwoot JSON  ->  NEXUS shapes
signature.py  webhook signature check
adapter.py    ties the three together behind the MessagingAdapter contract
"""

from app.integrations.chatwoot.adapter import ChatwootAdapter

__all__ = ["ChatwootAdapter"]
