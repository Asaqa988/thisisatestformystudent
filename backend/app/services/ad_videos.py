"""Ad videos: Claude turns the Knowledge Base into a 15-second motion-graphic storyboard.

Claude writes structured scenes (hook, features, list, price, call to action) and
picks a colour palette. NEXUS then checks and tidies the storyboard: at most 15
seconds, sensible scene lengths, short text that fits on screen. The browser
draws the animation from it.
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Literal

import anthropic
from pydantic import BaseModel, ValidationError

from app.core.config import Settings, get_settings
from app.core.db import SessionLocal
from app.models import AdVideo
from app.services import knowledge
from app.services.ai_agent import get_ai_settings

log = logging.getLogger("nexus.ads")

MAX_SECONDS = 15.0
MIN_SECONDS = 9.0
SCENE_MIN, SCENE_MAX = 1.8, 4.5
FALLBACK_BETA = "server-side-fallback-2026-07-01"

Palette = Literal["petrol", "sunset", "midnight", "citrus", "berry"]
SceneKind = Literal["hook", "feature", "list", "price", "cta"]


class Scene(BaseModel):
    kind: SceneKind
    duration: float
    headline: str
    subline: str
    items: list[str]
    price_amount: str
    price_currency: str
    price_period: str


class Storyboard(BaseModel):
    title: str
    palette: Palette
    brand: str
    scenes: list[Scene]
    facts_used: list[str]


STORYBOARD_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Internal name for this ad, max 6 words"},
        "palette": {"type": "string", "enum": ["petrol", "sunset", "midnight", "citrus", "berry"]},
        "brand": {"type": "string", "description": "Business name as shown in the ad"},
        "scenes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "kind": {"type": "string", "enum": ["hook", "feature", "list", "price", "cta"]},
                    "duration": {"type": "number", "description": "Seconds on screen"},
                    "headline": {"type": "string"},
                    "subline": {"type": "string"},
                    "items": {"type": "array", "items": {"type": "string"}},
                    "price_amount": {"type": "string"},
                    "price_currency": {"type": "string"},
                    "price_period": {"type": "string"},
                },
                "required": [
                    "kind",
                    "duration",
                    "headline",
                    "subline",
                    "items",
                    "price_amount",
                    "price_currency",
                    "price_period",
                ],
                "additionalProperties": False,
            },
        },
        "facts_used": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Each Knowledge Base fact the ad states, quoted briefly",
        },
    },
    "required": ["title", "palette", "brand", "scenes", "facts_used"],
    "additionalProperties": False,
}

RULES = """\
You write 15-second vertical (9:16) motion-graphic video ads for social media
(Reels, Stories, TikTok). There is no voice-over: every word is on screen, so
text must be short, punchy and readable in a second or two. Write in English.

Use only facts from the knowledge base below. Never invent prices, discounts,
results, guarantees or contact details. If a fact is not in the knowledge base,
leave it out.

Structure, 4 to 6 scenes, total 12 to 15 seconds:
- First scene kind "hook": a scroll-stopping line, max 6 words in the headline.
- Middle scenes: "feature" (one benefit), "list" (2 or 3 short items, max 5 words
  each), "price" (fill price_amount with digits only, price_currency, and
  price_period such as "/month"; headline is a short label like "Starting at").
- Last scene kind "cta": an action headline (max 5 words) and a subline with how
  to act, using only what the knowledge base says (e.g. book a free consultation).
- Headlines max 7 words. Sublines max 12 words. Leave fields a scene does not use
  as "" or [].
- Durations: 1.8 to 4.5 seconds each; give text-heavy scenes more time.

Pick the palette that suits the business: petrol (calm, professional), sunset
(warm, energetic), midnight (premium, dark), citrus (fresh, bold), berry (playful).
In facts_used, list each knowledge-base fact the ad states."""


class AdBuildError(Exception):
    pass


def write_storyboard(
    knowledge_text: str, business_name: str, brief: str | None, *, config: Settings
) -> tuple[Storyboard, int, int]:
    """One Claude call: knowledge base in, storyboard out."""
    client = anthropic.Anthropic(api_key=config.anthropic_api_key, timeout=120.0, max_retries=2)
    focus = f"\n\nWhat this ad should focus on: {brief.strip()}" if brief and brief.strip() else ""
    try:
        response = client.beta.messages.create(
            model=config.ai_model,
            max_tokens=16_000,
            system=[
                {"type": "text", "text": RULES},
                {
                    "type": "text",
                    "text": f"Business: {business_name or 'the business'}\n\n"
                    f"<knowledge_base>\n{knowledge_text}\n</knowledge_base>",
                    "cache_control": {"type": "ephemeral"},
                },
            ],
            messages=[{"role": "user", "content": f"Write one ad.{focus}"}],
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": STORYBOARD_SCHEMA},
            },
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
    except anthropic.AuthenticationError:
        raise AdBuildError("Anthropic rejected the API key. Check ANTHROPIC_API_KEY.") from None
    except anthropic.RateLimitError:
        raise AdBuildError("Anthropic rate limit reached. Try again in a minute.") from None
    except anthropic.APIStatusError as error:
        raise AdBuildError(f"Anthropic returned an error ({error.status_code}).") from None
    except anthropic.APIConnectionError:
        raise AdBuildError("Could not reach the Anthropic API.") from None

    if response.stop_reason == "refusal":
        raise AdBuildError("The AI model declined to write this ad.")
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        storyboard = Storyboard.model_validate_json(text)
    except ValidationError:
        raise AdBuildError("The AI answer was not a valid storyboard.") from None

    usage = response.usage
    input_tokens = (
        (usage.input_tokens or 0)
        + (usage.cache_creation_input_tokens or 0)
        + (usage.cache_read_input_tokens or 0)
    )
    return storyboard, input_tokens, usage.output_tokens or 0


def tidy(storyboard: Storyboard) -> dict:
    """Make the storyboard safe to animate: 15 s at most, readable lengths."""
    scenes = [s for s in storyboard.scenes if s.headline.strip() or s.kind == "price"][:6]
    if len(scenes) < 3:
        raise AdBuildError("The storyboard had too few scenes to make an ad.")

    def clip(text: str, limit: int) -> str:
        text = " ".join(text.split())
        return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"

    cleaned = []
    for scene in scenes:
        cleaned.append(
            {
                "kind": scene.kind,
                "duration": min(max(float(scene.duration or 2.5), SCENE_MIN), SCENE_MAX),
                "headline": clip(scene.headline, 48),
                "subline": clip(scene.subline, 90),
                "items": [clip(i, 34) for i in scene.items if i.strip()][:3],
                "price_amount": "".join(
                    ch for ch in scene.price_amount if ch.isdigit() or ch in ".,"
                )[:9],
                "price_currency": clip(scene.price_currency, 6),
                "price_period": clip(scene.price_period, 12),
            }
        )

    total = sum(s["duration"] for s in cleaned)
    if total > MAX_SECONDS:
        factor = MAX_SECONDS / total
        for s in cleaned:
            s["duration"] = round(s["duration"] * factor, 2)
    elif total < MIN_SECONDS:
        factor = MIN_SECONDS / total
        for s in cleaned:
            s["duration"] = round(min(s["duration"] * factor, SCENE_MAX + 1), 2)
    # Rounding must never push the total over 15 seconds.
    overflow = sum(s["duration"] for s in cleaned) - MAX_SECONDS
    if overflow > 0:
        cleaned[-1]["duration"] = round(cleaned[-1]["duration"] - overflow, 2)

    return {
        "palette": storyboard.palette,
        "brand": clip(storyboard.brand, 40),
        "scenes": cleaned,
        "facts_used": [clip(f, 160) for f in storyboard.facts_used][:12],
        "duration": round(sum(s["duration"] for s in cleaned), 2),
    }


def build_ad(ad_id: uuid.UUID, *, config: Settings | None = None, writer=None) -> None:
    """Background task: write the storyboard and save it. Never raises."""
    config = config or get_settings()
    writer = writer or write_storyboard
    with SessionLocal() as db:
        ad = db.get(AdVideo, ad_id)
        if ad is None:
            return
        try:
            if not config.anthropic_api_key:
                raise AdBuildError("No ANTHROPIC_API_KEY is configured on the server.")
            knowledge_text, _ = knowledge.context_for(db, ad.brief or "", 400_000)
            if not knowledge_text:
                raise AdBuildError("The Knowledge Base is empty. Add articles first.")
            business = get_ai_settings(db).business_name
            storyboard, input_tokens, output_tokens = writer(
                knowledge_text, business, ad.brief, config=config
            )
            ad.storyboard = tidy(storyboard)
            ad.title = (storyboard.title or "Ad").strip()[:200]
            ad.input_tokens, ad.output_tokens = input_tokens, output_tokens
            ad.status = "ready"
            ad.error = None
        except AdBuildError as error:
            ad.status, ad.error = "failed", str(error)
        except Exception:  # noqa: BLE001 - background task: record, never crash
            log.exception("Building ad %s failed", ad_id)
            ad.status, ad.error = "failed", "Unexpected error while writing the ad."
        ad.updated_at = datetime.now(tz=UTC)
        db.commit()
