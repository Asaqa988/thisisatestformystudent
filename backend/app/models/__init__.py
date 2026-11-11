"""NEXUS database tables. Importing this package registers every model on Base."""

from app.models.ai import AIReply, AISettings, KnowledgeArticle
from app.models.conversation import Conversation
from app.models.webhook_event import WebhookEvent

__all__ = ["AIReply", "AISettings", "Conversation", "KnowledgeArticle", "WebhookEvent"]
