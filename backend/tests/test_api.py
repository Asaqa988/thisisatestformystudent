"""Health, Inbox and dashboard endpoints, including what happens when Chatwoot misbehaves."""

import json

from tests import samples
from tests.conftest import API_TOKEN, WEBHOOK_PATH, signed


def seed_conversation(client) -> str:
    """Create one conversation the normal way, through a webhook. Returns its NEXUS id."""
    client.post(WEBHOOK_PATH, **signed(samples.webhook_message_created()))
    return client.get("/api/v1/conversations").json()["items"][0]["id"]


# --- Health -----------------------------------------------------------------------


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_reports_database_and_chatwoot(client):
    body = client.get("/health/ready").json()

    assert body["status"] == "ready"
    assert body["checks"]["database"]["ok"] is True
    assert body["checks"]["chatwoot"] == {
        "ok": True,
        "configured": True,
        "detail": "Connected to account 1",
    }


def test_ready_stays_up_when_chatwoot_is_not_configured(client, use_settings):
    use_settings(chatwoot_api_token="")

    response = client.get("/health/ready")

    assert response.status_code == 200  # NEXUS itself is fine
    assert response.json()["checks"]["chatwoot"]["configured"] is False


# --- Conversations ----------------------------------------------------------------


def test_list_is_empty_before_any_event(client):
    assert client.get("/api/v1/conversations").json() == {"items": []}


def test_list_returns_normalized_conversations(client):
    seed_conversation(client)

    item = client.get("/api/v1/conversations").json()["items"][0]

    assert item["source"] == "chatwoot"
    assert item["external_id"] == "12"
    assert item["channel"] == "api"
    assert item["inbox_name"] == "NEXUS Demo Channel"
    assert item["contact"]["name"] == "Lina Haddad"
    assert item["last_message"]["direction"] == "inbound"
    # No Chatwoot field names leak into the NEXUS shape.
    assert "meta" not in item and "inbox_id" not in item and "message_type" not in json.dumps(item)


def test_list_can_filter_by_status(client):
    seed_conversation(client)

    assert len(client.get("/api/v1/conversations?status=open").json()["items"]) == 1
    assert client.get("/api/v1/conversations?status=resolved").json()["items"] == []
    assert client.get("/api/v1/conversations?status=nonsense").status_code == 422


def test_sync_pulls_conversations_from_chatwoot(client, fake_chatwoot):
    fake_chatwoot.conversations = [
        samples.rest_conversation(conversation_id=12),
        samples.rest_conversation(conversation_id=13, status="resolved"),
    ]

    response = client.post("/api/v1/conversations/sync")

    assert response.json() == {"synced": 2}
    assert len(client.get("/api/v1/conversations").json()["items"]) == 2


def test_sync_twice_does_not_duplicate_conversations(client):
    client.post("/api/v1/conversations/sync")
    client.post("/api/v1/conversations/sync")

    assert len(client.get("/api/v1/conversations").json()["items"]) == 1


def test_messages_are_fetched_from_chatwoot_oldest_first(client, fake_chatwoot):
    conversation_id = seed_conversation(client)

    response = client.get(f"/api/v1/conversations/{conversation_id}/messages")

    assert response.status_code == 200
    messages = response.json()["items"]
    assert [m["id"] for m in messages] == ["345", "346"]
    assert messages[0]["direction"] == "inbound"
    assert messages[1]["direction"] == "outbound"
    assert messages[1]["author"] == {"type": "agent", "name": "Nour"}
    # The call used the external id and carried the token as a header.
    assert fake_chatwoot.last_request.url.path == "/api/v1/accounts/1/conversations/12/messages"
    assert fake_chatwoot.last_request.headers["api_access_token"] == API_TOKEN


def test_reply_is_sent_through_chatwoot(client, fake_chatwoot):
    conversation_id = seed_conversation(client)

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages", json={"content": "  Yes, we do.  "}
    )

    assert response.status_code == 201
    assert response.json()["direction"] == "outbound"
    assert response.json()["content"] == "Yes, we do."

    sent = fake_chatwoot.last_request
    assert sent.method == "POST"
    assert sent.url.path == "/api/v1/accounts/1/conversations/12/messages"
    assert json.loads(sent.content) == {
        "content": "Yes, we do.",
        "message_type": "outgoing",
        "private": False,
    }
    # The list preview is updated without waiting for the webhook.
    last = client.get("/api/v1/conversations").json()["items"][0]["last_message"]
    assert last == {**last, "preview": "Yes, we do.", "direction": "outbound"}


def test_the_token_never_appears_in_a_response(client):
    conversation_id = seed_conversation(client)
    bodies = [
        client.get("/health/ready").text,
        client.get("/api/v1/integrations/chatwoot/status").text,
        client.get("/api/v1/dashboard/summary").text,
        client.get(f"/api/v1/conversations/{conversation_id}/messages").text,
    ]

    assert all(API_TOKEN not in body for body in bodies)


def test_empty_reply_is_refused_before_calling_chatwoot(client, fake_chatwoot):
    conversation_id = seed_conversation(client)
    calls_before = len(fake_chatwoot.requests)

    response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages", json={"content": ""}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert len(fake_chatwoot.requests) == calls_before


def test_unknown_conversation_is_404(client):
    response = client.get("/api/v1/conversations/00000000-0000-0000-0000-000000000000/messages")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# --- When Chatwoot misbehaves --------------------------------------------------------


def test_chatwoot_down_gives_a_clear_502_and_the_list_still_works(client, fake_chatwoot):
    conversation_id = seed_conversation(client)
    fake_chatwoot.mode = "down"

    messages = client.get(f"/api/v1/conversations/{conversation_id}/messages")
    reply = client.post(f"/api/v1/conversations/{conversation_id}/messages", json={"content": "Hi"})

    assert messages.status_code == reply.status_code == 502
    assert messages.json()["error"]["code"] == "upstream_unavailable"
    # The list comes from our own database, so it is unaffected.
    assert len(client.get("/api/v1/conversations").json()["items"]) == 1


def test_chatwoot_500_is_reported_as_unavailable(client, fake_chatwoot):
    conversation_id = seed_conversation(client)
    fake_chatwoot.mode = "error"

    response = client.get(f"/api/v1/conversations/{conversation_id}/messages")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "upstream_unavailable"


def test_rejected_token_is_reported_as_an_auth_failure(client, fake_chatwoot):
    conversation_id = seed_conversation(client)
    fake_chatwoot.mode = "unauthorized"

    response = client.get(f"/api/v1/conversations/{conversation_id}/messages")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "upstream_auth_failed"


def test_missing_credentials_give_503_without_calling_chatwoot(client, fake_chatwoot, use_settings):
    conversation_id = seed_conversation(client)
    use_settings(chatwoot_api_token="")
    calls_before = len(fake_chatwoot.requests)

    messages = client.get(f"/api/v1/conversations/{conversation_id}/messages")
    sync = client.post("/api/v1/conversations/sync")

    assert messages.status_code == sync.status_code == 503
    assert messages.json()["error"]["code"] == "integration_not_configured"
    assert len(fake_chatwoot.requests) == calls_before


# --- Dashboard --------------------------------------------------------------------


def test_dashboard_summary_counts(client):
    request = signed(samples.webhook_message_created(), delivery="a")
    client.post(WEBHOOK_PATH, **request)
    client.post(WEBHOOK_PATH, **request)  # duplicate

    body = client.get("/api/v1/dashboard/summary").json()

    assert body["conversations"] == {"total": 1, "open": 1, "awaiting_reply": 1, "resolved": 0}
    assert body["events"]["received_24h"] == 1
    assert body["events"]["duplicates_ignored"] == 1
    assert body["integrations"][0]["key"] == "chatwoot"
    assert body["integrations"][0]["ok"] is True


def test_events_endpoint_lists_newest_first(client):
    client.post(
        WEBHOOK_PATH, **signed(samples.webhook_message_created(content="one"), delivery="a")
    )
    client.post(WEBHOOK_PATH, **signed(samples.webhook_status_changed(), delivery="b"))

    items = client.get("/api/v1/events?limit=5").json()["items"]

    assert [item["event_type"] for item in items] == [
        "conversation_status_changed",
        "message_created",
    ]
    assert items[1]["summary"] == "Lina Haddad: one"


def test_integration_status_when_not_configured(client, use_settings):
    use_settings(chatwoot_api_token="", chatwoot_webhook_secret="")

    body = client.get("/api/v1/integrations/chatwoot/status").json()

    assert body["configured"] is False
    assert body["ok"] is False
    assert body["webhook_verification"] == "disabled"
