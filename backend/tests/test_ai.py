"""The AI agent and the knowledge base. Claude is replaced by FakeLLM: no network, no cost."""

import json

import pytest
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import AIReply, AISettings, Conversation
from app.schemas import Author, MessageOut
from app.services import ai_agent
from app.services.ai_agent import AIDecision, AIError, LLMResult, build_history
from tests import samples
from tests.conftest import WEBHOOK_PATH, make_settings, signed


class FakeLLM:
    """Stands in for Claude. Records what it was shown and returns a fixed decision."""

    def __init__(
        self, action="reply", reply="Our monthly plan is 450 JOD.", reason="Answered from pricing"
    ):
        self.decision = AIDecision(action=action, reply=reply, reason=reason)
        self.error: str | None = None
        self.calls: list[dict] = []

    def decide(self, system, messages):
        self.calls.append({"system": system, "messages": messages})
        if self.error:
            raise AIError(self.error)
        return LLMResult(
            decision=self.decision, model="fake-claude", input_tokens=120, output_tokens=30
        )


@pytest.fixture
def llm(monkeypatch):
    fake = FakeLLM()
    monkeypatch.setattr(ai_agent, "ClaudeModel", lambda *args, **kwargs: fake)
    monkeypatch.setattr(
        ai_agent,
        "get_settings",
        lambda: make_settings(anthropic_api_key="test", ai_debounce_seconds=0),
    )
    return fake


@pytest.fixture
def ai_on():
    with SessionLocal() as db:
        db.add(AISettings(id=1, enabled=True, business_name="Acme Agency", instructions="Be warm."))
        db.commit()


@pytest.fixture
def customer_last(fake_chatwoot):
    """Chatwoot's view of the conversation: the customer spoke last."""
    fake_chatwoot.messages = [
        samples.rest_message(message_id=345, content="How much is the monthly plan?")
    ]
    return fake_chatwoot


def customer_writes(
    client, message_id=345, delivery="d-345", content="How much is the monthly plan?"
):
    payload = samples.webhook_message_created(message_id=message_id, content=content)
    return client.post(WEBHOOK_PATH, **signed(payload, delivery=delivery))


def posted(fake_chatwoot) -> list[dict]:
    """Bodies of messages NEXUS posted to Chatwoot."""
    return [json.loads(r.content) for r in fake_chatwoot.requests if r.method == "POST"]


def replies() -> list[AIReply]:
    with SessionLocal() as db:
        return list(db.scalars(select(AIReply)))


def conversation() -> Conversation:
    with SessionLocal() as db:
        return db.scalars(select(Conversation)).one()


# --- Answering -----------------------------------------------------------------------


def test_customer_message_gets_an_ai_reply(client, llm, ai_on, customer_last):
    customer_writes(client)

    [reply] = replies()
    assert reply.status == "sent"
    assert reply.reply_text == "Our monthly plan is 450 JOD."
    assert reply.external_message_id == "900"
    assert reply.input_tokens == 120
    assert posted(customer_last) == [
        {"content": "Our monthly plan is 450 JOD.", "message_type": "outgoing", "private": False}
    ]
    # The model saw the customer's message as the last user turn.
    assert llm.calls[0]["messages"][-1] == {
        "role": "user",
        "content": "How much is the monthly plan?",
    }


def test_nothing_happens_while_the_agent_is_switched_off(client, llm, customer_last):
    customer_writes(client)

    assert replies() == []
    assert llm.calls == []
    assert posted(customer_last) == []


def test_a_repeated_webhook_never_produces_a_second_reply(client, llm, ai_on, customer_last):
    customer_writes(client, delivery="same")
    customer_writes(client, delivery="same")  # exact repeat: stopped by webhook dedupe
    customer_writes(client, delivery="other-delivery")  # same message, new delivery id

    assert len(replies()) == 1
    assert len(llm.calls) == 1
    assert len(posted(customer_last)) == 1


def test_handoff_tells_the_customer_notes_the_team_and_pauses(client, llm, ai_on, customer_last):
    llm.decision = AIDecision(
        action="handoff",
        reply="A team member will get back to you shortly.",
        reason="Customer asks for a refund",
    )

    customer_writes(client)

    [reply] = replies()
    assert reply.status == "handoff"
    bodies = posted(customer_last)
    assert bodies[0]["content"] == "A team member will get back to you shortly."
    assert bodies[0]["private"] is False
    assert bodies[1]["private"] is True
    assert "Customer asks for a refund" in bodies[1]["content"]
    assert conversation().ai_enabled is False
    assert "refund" in conversation().ai_paused_reason


def test_after_a_handoff_the_ai_stays_quiet(client, llm, ai_on, customer_last):
    llm.decision = AIDecision(action="handoff", reply="", reason="Unknown topic")
    customer_writes(client)
    customer_last.messages = [samples.rest_message(message_id=347, content="Hello?")]
    customer_writes(client, message_id=347, delivery="d-347", content="Hello?")

    assert len(llm.calls) == 1


def test_missing_api_key_is_recorded_not_crashed(client, monkeypatch, ai_on, customer_last):
    monkeypatch.setattr(ai_agent, "get_settings", lambda: make_settings(ai_debounce_seconds=0))

    customer_writes(client)

    [reply] = replies()
    assert reply.status == "skipped"
    assert "ANTHROPIC_API_KEY" in reply.reason
    assert posted(customer_last) == []


def test_model_errors_are_recorded_and_nothing_is_sent(client, llm, ai_on, customer_last):
    llm.error = "Anthropic rate limit reached. Try again shortly."

    customer_writes(client)

    [reply] = replies()
    assert reply.status == "error"
    assert "rate limit" in reply.reason
    assert posted(customer_last) == []


def test_an_already_answered_conversation_is_skipped(client, llm, ai_on, fake_chatwoot):
    # Default fake history ends with an outgoing message.
    customer_writes(client)

    [reply] = replies()
    assert reply.status == "skipped"
    assert llm.calls == []


def test_only_the_newest_of_several_quick_messages_is_answered(client, llm, ai_on, fake_chatwoot):
    fake_chatwoot.messages = [
        samples.rest_message(message_id=345, content="Hi"),
        samples.rest_message(
            message_id=346, content="Do you do Instagram ads?", created_at=1768468900
        ),
    ]
    customer_writes(client, message_id=345, delivery="d1", content="Hi")
    customer_writes(client, message_id=346, delivery="d2", content="Do you do Instagram ads?")

    statuses = sorted(r.status for r in replies())
    assert statuses == ["sent", "skipped"]
    assert len(llm.calls) == 1
    # Both messages reached the model as one customer turn.
    assert llm.calls[0]["messages"] == [{"role": "user", "content": "Hi\nDo you do Instagram ads?"}]


def test_hourly_limit_pauses_the_ai(client, llm, ai_on, customer_last, monkeypatch):
    monkeypatch.setattr(
        ai_agent,
        "get_settings",
        lambda: make_settings(
            anthropic_api_key="t", ai_debounce_seconds=0, ai_max_replies_per_hour=1
        ),
    )
    customer_writes(client)
    conv_id = conversation().id
    with SessionLocal() as db:  # pretend the conversation is still waiting
        db.get(Conversation, conv_id).ai_enabled = True
        db.commit()
    customer_last.messages = [samples.rest_message(message_id=350, content="And yearly?")]
    customer_writes(client, message_id=350, delivery="d-350", content="And yearly?")

    statuses = [r.status for r in sorted(replies(), key=lambda r: r.created_at)]
    assert statuses == ["sent", "skipped"]
    assert conversation().ai_enabled is False


# --- Stepping back for humans ---------------------------------------------------------


def test_a_reply_from_nexus_pauses_the_ai(client, llm, ai_on, customer_last):
    llm.decision = AIDecision(action="reply", reply="Hello!", reason="Greeting")
    customer_writes(client)
    conv_id = conversation().id

    client.post(
        f"/api/v1/conversations/{conv_id}/messages", json={"content": "I'll take it from here."}
    )

    assert conversation().ai_enabled is False
    assert "team member" in conversation().ai_paused_reason


def test_a_team_member_replying_in_chatwoot_pauses_the_ai(client, llm, ai_on, customer_last):
    customer_writes(client)
    assert conversation().ai_enabled is True

    agent_message = samples.webhook_message_created(
        message_id=901, message_type="outgoing", content="Hi, this is Nour from the team."
    )
    client.post(WEBHOOK_PATH, **signed(agent_message, delivery="agent-901"))

    assert conversation().ai_enabled is False


def test_the_echo_of_the_ais_own_reply_does_not_pause_it(client, llm, ai_on, customer_last):
    customer_writes(client)

    echo = samples.webhook_message_created(
        message_id=900, message_type="outgoing", content="Our monthly plan is 450 JOD."
    )
    client.post(WEBHOOK_PATH, **signed(echo, delivery="echo-900"))

    assert conversation().ai_enabled is True


def test_the_switch_turns_the_ai_back_on(client, llm, ai_on, customer_last):
    customer_writes(client)
    conv_id = conversation().id

    off = client.post(f"/api/v1/conversations/{conv_id}/ai", json={"enabled": False})
    on = client.post(f"/api/v1/conversations/{conv_id}/ai", json={"enabled": True})

    assert off.json()["ai_enabled"] is False
    assert on.json()["ai_enabled"] is True
    assert on.json()["ai_paused_reason"] is None


def test_ai_written_messages_are_labelled_in_the_thread(client, llm, ai_on, customer_last):
    customer_writes(client)
    conv_id = conversation().id
    customer_last.messages = [
        samples.rest_message(message_id=345),
        samples.rest_message(
            message_id=900, message_type=1, content="Our monthly plan is 450 JOD."
        ),
    ]

    messages = client.get(f"/api/v1/conversations/{conv_id}/messages").json()["items"]

    assert messages[1]["author"] == {"type": "bot", "name": "NEXUS AI"}
    assert messages[0]["author"]["type"] == "contact"


# --- Knowledge base -------------------------------------------------------------------


def test_knowledge_base_crud(client):
    created = client.post(
        "/api/v1/knowledge",
        json={"title": "Pricing", "content": "Starter plan: 450 JOD per month."},
    )
    assert created.status_code == 201
    article_id = created.json()["id"]

    updated = client.put(
        f"/api/v1/knowledge/{article_id}",
        json={"title": "Pricing", "content": "Starter plan: 500 JOD per month."},
    )
    listing = client.get("/api/v1/knowledge").json()
    deleted = client.delete(f"/api/v1/knowledge/{article_id}")

    assert updated.json()["content"] == "Starter plan: 500 JOD per month."
    assert [a["title"] for a in listing["items"]] == ["Pricing"]
    assert listing["total_chars"] == len("Pricing") + len("Starter plan: 500 JOD per month.")
    assert deleted.status_code == 204
    assert client.get("/api/v1/knowledge").json()["items"] == []


def test_empty_article_is_refused(client):
    response = client.post("/api/v1/knowledge", json={"title": "", "content": "x"})
    assert response.status_code == 422


def test_the_whole_small_knowledge_base_reaches_the_model(client, llm, ai_on, customer_last):
    client.post("/api/v1/knowledge", json={"title": "Pricing", "content": "Monthly plan: 450 JOD."})
    client.post("/api/v1/knowledge", json={"title": "Hours", "content": "Open Sunday to Thursday."})

    customer_writes(client)

    system_text = "\n".join(block["text"] for block in llm.calls[0]["system"])
    assert "Monthly plan: 450 JOD." in system_text
    assert "Open Sunday to Thursday." in system_text
    assert "Acme Agency" in system_text
    assert "Be warm." in system_text
    # The stable part of the prompt is marked for caching.
    assert llm.calls[0]["system"][-1]["cache_control"] == {"type": "ephemeral"}


def test_a_large_knowledge_base_is_searched(client, llm, ai_on, customer_last, monkeypatch):
    monkeypatch.setattr(
        ai_agent,
        "get_settings",
        lambda: make_settings(
            anthropic_api_key="t", ai_debounce_seconds=0, kb_full_context_chars=10
        ),
    )
    client.post(
        "/api/v1/knowledge", json={"title": "Pricing", "content": "The monthly plan costs 450 JOD."}
    )
    client.post(
        "/api/v1/knowledge", json={"title": "Careers", "content": "We are hiring designers."}
    )

    customer_writes(client, content="How much is the monthly plan?")

    system_text = "\n".join(block["text"] for block in llm.calls[0]["system"])
    assert "450 JOD" in system_text
    assert "hiring designers" not in system_text


def test_arabic_articles_are_found_by_search(client, llm, ai_on, fake_chatwoot, monkeypatch):
    monkeypatch.setattr(
        ai_agent,
        "get_settings",
        lambda: make_settings(
            anthropic_api_key="t", ai_debounce_seconds=0, kb_full_context_chars=10
        ),
    )
    client.post(
        "/api/v1/knowledge", json={"title": "الأسعار", "content": "سعر الباقة الشهرية 450 دينار"}
    )
    client.post("/api/v1/knowledge", json={"title": "الوظائف", "content": "نبحث عن مصممين"})
    fake_chatwoot.messages = [
        samples.rest_message(message_id=345, content="كم سعر الباقة الشهرية؟")
    ]

    customer_writes(client, content="كم سعر الباقة الشهرية؟")

    system_text = "\n".join(block["text"] for block in llm.calls[0]["system"])
    assert "450 دينار" in system_text
    assert "مصممين" not in system_text


# --- Settings and activity --------------------------------------------------------------


def test_settings_start_switched_off_and_can_be_saved(client):
    first = client.get("/api/v1/ai/settings").json()
    saved = client.put(
        "/api/v1/ai/settings",
        json={"enabled": True, "business_name": "Acme", "instructions": "Use a friendly tone."},
    ).json()

    assert first["enabled"] is False
    assert saved["enabled"] is True
    assert saved["business_name"] == "Acme"
    assert "anthropic_api_key" not in json.dumps(saved)


def test_activity_lists_what_the_ai_did(client, llm, ai_on, customer_last):
    customer_writes(client)

    [item] = client.get("/api/v1/ai/activity").json()["items"]

    assert item["status"] == "sent"
    assert item["contact_name"] == "Lina Haddad"
    assert item["reply_text"] == "Our monthly plan is 450 JOD."


# --- Building the conversation for the model ------------------------------------------


def _message(i, direction, content, private=False):
    return MessageOut(
        id=str(i),
        direction=direction,
        author=Author(type="contact" if direction == "inbound" else "agent", name="x"),
        content=content,
        private=private,
        sent_at="2026-01-15T09:00:00Z",
    )


def test_history_merges_turns_and_drops_notes():
    history = build_history(
        [
            _message(1, "outbound", "Welcome!"),  # dropped: must start with the customer
            _message(2, "inbound", "Hi"),
            _message(3, "inbound", "Prices?"),
            _message(4, "outbound", "Internal: VIP", private=True),
            _message(5, "system", "Assigned to Nour"),
            _message(6, "outbound", "450 JOD."),
            _message(7, "inbound", ""),
        ]
    )

    assert history == [
        {"role": "user", "content": "Hi\nPrices?"},
        {"role": "assistant", "content": "450 JOD."},
        {"role": "user", "content": "[The customer sent an attachment or a sticker]"},
    ]
