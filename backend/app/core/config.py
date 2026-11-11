"""Application settings, read once from environment variables.

Nothing here is ever sent to the browser. Secrets enter the process through the
environment (set in docker-compose.yml from your .env file) and stay server-side.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # NEXUS database
    database_url: str = "postgresql+psycopg://nexus:nexus@localhost:5433/nexus"

    # When set, every /api/v1 call except webhooks must send this value in the
    # X-NEXUS-API-Key header. Leave empty for local development.
    nexus_api_key: str = ""

    # Chatwoot: where it lives
    chatwoot_base_url: str = "http://chatwoot-rails:3000"  # used by the backend
    chatwoot_public_url: str = "http://localhost:3110"  # shown to humans
    chatwoot_timeout_seconds: float = 10.0

    # Chatwoot: credentials (empty until the student completes setup)
    chatwoot_account_id: int | None = None
    chatwoot_api_token: str = ""
    chatwoot_webhook_secret: str = ""
    chatwoot_inbox_identifier: str = ""

    # Webhooks
    nexus_webhook_url: str = "http://backend:8000/api/v1/webhooks/chatwoot"
    webhook_max_age_seconds: int = 300

    # AI agent (Claude). Without a key the agent stays off and says why.
    anthropic_api_key: str = ""
    ai_model: str = "claude-opus-5-5"
    # Thinking depth: low | medium | high | xhigh | max. "low" suits short chat replies.
    ai_effort: str = "low"
    # Wait this long after a customer message before answering, so several
    # quick messages get one reply instead of one each.
    ai_debounce_seconds: float = 4.0
    # Safety brake: at most this many AI replies per conversation per hour.
    ai_max_replies_per_hour: int = 12
    # Below this size the whole knowledge base is given to the model; above it,
    # only the articles that best match the conversation.
    kb_full_context_chars: int = 120_000

    @field_validator("database_url", mode="before")
    @classmethod
    def _use_psycopg_driver(cls, value):
        # Hosting platforms hand out "postgres://..." or "postgresql://...".
        # SQLAlchemy needs to be told which driver to use.
        if isinstance(value, str):
            for prefix in ("postgres://", "postgresql://"):
                if value.startswith(prefix):
                    return "postgresql+psycopg://" + value.removeprefix(prefix)
        return value

    @field_validator("chatwoot_account_id", mode="before")
    @classmethod
    def _blank_means_missing(cls, value):
        # docker-compose passes unset variables as "", which is not a number.
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator(
        "chatwoot_api_token",
        "chatwoot_webhook_secret",
        "chatwoot_inbox_identifier",
        "nexus_api_key",
        "anthropic_api_key",
        mode="before",
    )
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value

    @property
    def chatwoot_configured(self) -> bool:
        """True when the backend has what it needs to call the Chatwoot API."""
        return bool(self.chatwoot_api_token and self.chatwoot_account_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
