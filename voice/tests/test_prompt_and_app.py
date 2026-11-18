"""The assistant's instructions, the service wiring, and the WebSocket door."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app import main
from app.bot import build_services
from app.config import Settings
from app.prompt import VoiceContext, greeting, system_prompt, transcription_hint

CONTEXT = VoiceContext(
    business_name="Nova Store",
    instructions="Mention free delivery in Amman.",
    products_text="- Smart Watch (category: Wearables) - price: 120 JOD\n  Waterproof.\n"
    "- Wireless Earbuds - price: 45 JOD",
    knowledge_text='<article title="Hours">Open 10 to 10</article>',
)


def test_system_prompt_holds_products_rules_and_notes():
    prompt = system_prompt(CONTEXT)

    assert "Nova Store" in prompt
    assert "Smart Watch" in prompt and "120 JOD" in prompt
    assert "Open 10 to 10" in prompt
    assert "Mention free delivery in Amman." in prompt
    assert "Arabic" in prompt
    assert "Never invent" in prompt


def test_empty_shop_still_gets_a_prompt():
    prompt = system_prompt(VoiceContext())
    assert "(no products listed yet)" in prompt


def test_greeting_is_arabic_and_names_the_business():
    assert "Nova Store" in greeting(CONTEXT)
    assert greeting(VoiceContext()).startswith("أهلًا")


def test_transcription_hint_lists_product_names():
    assert transcription_hint(CONTEXT) == "Smart Watch، Wireless Earbuds"


def test_services_build_without_network():
    settings = Settings(openai_api_key="sk-test", anthropic_api_key="ak-test")
    stt, llm, tts = build_services(settings, CONTEXT)
    assert stt and llm and tts


@pytest.fixture
def client(monkeypatch):
    settings = Settings(
        openai_api_key="sk-test",
        anthropic_api_key="ak-test",
        voice_session_secret="s3cret",
        voice_allowed_origins="https://shop.test",
    )
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    return TestClient(main.app)


def test_health_reports_readiness(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["ready"] is True


def test_foreign_origin_is_closed_without_a_session(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws?token=x", headers={"origin": "https://evil.test"}) as ws:
            ws.receive_json()


def test_bad_ticket_gets_a_readable_reason(client):
    with client.websocket_connect("/ws?token=nope", headers={"origin": "https://shop.test"}) as ws:
        message = ws.receive_json()
    assert message == {
        "type": "error",
        "code": "bad_ticket",
        "message": "This voice session link is not valid.",
    }


def test_missing_keys_are_reported(monkeypatch):
    empty = Settings(
        openai_api_key="", anthropic_api_key="", voice_session_secret="", voice_allowed_origins=""
    )
    monkeypatch.setattr(main, "get_settings", lambda: empty)
    client = TestClient(main.app)

    assert client.get("/health").json()["missing"] == [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "VOICE_SESSION_SECRET",
    ]
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["code"] == "not_configured"
