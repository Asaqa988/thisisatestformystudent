"""NEXUS voice service.

    GET  /health     liveness, and which settings are missing
    WS   /ws?token=  one voice conversation (the token comes from the NEXUS backend)
"""

import httpx
from fastapi import FastAPI, WebSocket
from loguru import logger

from app.bot import run_session
from app.config import get_settings
from app.gate import Refused, SessionGate, verify_ticket
from app.prompt import VoiceContext

app = FastAPI(title="NEXUS voice", version="0.1.0")
_settings = get_settings()
gate = SessionGate(
    max_concurrent=_settings.voice_max_concurrent,
    max_per_ip_hour=_settings.voice_max_sessions_per_ip_hour,
)


@app.get("/health")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "service": "nexus-voice",
        "ready": not settings.missing,
        "missing": settings.missing,
        "active_sessions": gate.active,
    }


async def load_context() -> VoiceContext:
    """Products and the Knowledge Base, fresh for every session."""
    settings = get_settings()
    headers = {"X-NEXUS-API-Key": settings.nexus_api_key} if settings.nexus_api_key else {}
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            f"{settings.nexus_api_url.rstrip('/')}/api/v1/voice/context", headers=headers
        )
        response.raise_for_status()
        return VoiceContext.model_validate(response.json())


def client_ip(websocket: WebSocket) -> str:
    forwarded = websocket.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return websocket.client.host if websocket.client else "unknown"


async def refuse(websocket: WebSocket, code: str, reason: str) -> None:
    """Accept only to say why, then close. The page shows the reason."""
    await websocket.accept()
    await websocket.send_json({"type": "error", "code": code, "message": reason})
    await websocket.close(code=1008)


@app.websocket("/ws")
async def voice(websocket: WebSocket):
    settings = get_settings()

    origin = websocket.headers.get("origin", "").rstrip("/")
    if settings.allowed_origins and origin not in settings.allowed_origins:
        await websocket.close(code=1008)  # not our page: no explanation
        return
    if settings.missing:
        await refuse(websocket, "not_configured", "The voice assistant is not set up yet.")
        return

    try:
        sid = verify_ticket(websocket.query_params.get("token", ""), settings.voice_session_secret)
        gate.admit(sid, client_ip(websocket))
    except Refused as refused:
        await refuse(websocket, refused.code, refused.reason)
        return

    try:
        try:
            context = await load_context()
        except httpx.HTTPError as exc:
            logger.warning(f"Could not load the voice context: {exc!r}")
            await refuse(websocket, "unavailable", "The assistant cannot reach the shop right now.")
            return
        await websocket.accept()
        await run_session(websocket, settings, context)
    finally:
        gate.release()
