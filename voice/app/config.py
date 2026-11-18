"""Voice service settings, read from environment variables. None of them reach the browser."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    # Speech: OpenAI hears (speech-to-text) and speaks (text-to-speech).
    openai_api_key: str = ""
    openai_stt_model: str = ""  # empty: Pipecat's default transcription model
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "marin"
    # Claude writes the answers.
    anthropic_api_key: str = ""
    voice_ai_model: str = "claude-opus-5-5"
    voice_ai_effort: str = "low"  # short spoken answers: the fastest setting
    voice_max_tokens: int = 400

    # Where the products and the Knowledge Base come from.
    nexus_api_url: str = "http://backend:8000"
    nexus_api_key: str = ""

    # Who may open a session, and how much it may cost.
    voice_session_secret: str = ""  # the same value as on the backend
    voice_allowed_origins: str = "http://localhost:3100"  # comma-separated
    voice_max_concurrent: int = 4
    voice_max_session_seconds: int = 180
    voice_max_sessions_per_ip_hour: int = 10

    @field_validator(
        "openai_api_key", "anthropic_api_key", "nexus_api_key", "voice_session_secret",
        mode="before",
    )
    @classmethod
    def _strip(cls, value):
        return value.strip() if isinstance(value, str) else value

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.voice_allowed_origins.split(",") if o.strip()]

    @property
    def missing(self) -> list[str]:
        """Settings without which a session cannot start."""
        required = {
            "OPENAI_API_KEY": self.openai_api_key,
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
            "VOICE_SESSION_SECRET": self.voice_session_secret,
        }
        return [name for name, value in required.items() if not value]


@lru_cache
def get_settings() -> Settings:
    return Settings()
