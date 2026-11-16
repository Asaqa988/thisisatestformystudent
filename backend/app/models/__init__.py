"""NEXUS database tables. Importing this package registers every model on Base."""

from app.models.ad_video import AdVideo
from app.models.ai import AIReply, AISettings, KnowledgeArticle
from app.models.automation import Automation, AutomationFile, AutomationRun
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.webhook_event import WebhookEvent

__all__ = [
    "AdVideo",
    "AIReply",
    "AISettings",
    "Automation",
    "AutomationFile",
    "AutomationRun",
    "Conversation",
    "Customer",
    "KnowledgeArticle",
    "WebhookEvent",
]
