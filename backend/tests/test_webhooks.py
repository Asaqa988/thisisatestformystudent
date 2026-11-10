"""Receiving webhooks: authenticate, store once, update the conversation."""

import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.models import Conversation, WebhookEvent
from app.services.events import ingest_webhook
from tests import samples
from tests.conftest import WEBHOOK_PATH, signed


def count(model) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model))


def test_valid_webhook_is_stored_and_creates_the_conversation(client):
    response = client.post(WEBHOOK_PATH, **signed(samples.webhook_message_created()))

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert count(WebhookEvent) == 1

    with SessionLocal() as db:
        conversation = db.scalars(select(Conversation)).one()
    assert conversation.source == "chatwoot"
    assert conversation.external_id == "12"
    assert conversation.contact_name == "Lina Haddad"
    assert conversation.last_message_preview == "Do you offer monthly plans?"
    assert conversation.last_message_direction == "inbound"


def test_same_delivery_twice_is_stored_once(client):
    request = signed(samples.webhook_message_created(), delivery="delivery-42")

    first = client.post(WEBHOOK_PATH, **request)
    second = client.post(WEBHOOK_PATH, **request)

    assert first.json()["status"] == "accepted"
    assert second.status_code == 200  # 200, so Chatwoot stops retrying
    assert second.json()["status"] == "duplicate"
    assert second.json()["event_id"] == first.json()["event_id"]
    assert count(WebhookEvent) == 1
    assert count(Conversation) == 1

    with SessionLocal() as db:
        assert db.scalars(select(WebhookEvent)).one().duplicate_count == 1


def test_different_deliveries_are_both_stored(client):
    client.post(WEBHOOK_PATH, **signed(samples.webhook_message_created(message_id=1), delivery="a"))
    client.post(WEBHOOK_PATH, **signed(samples.webhook_message_created(message_id=2), delivery="b"))

    assert count(WebhookEvent) == 2
    assert count(Conversation) == 1  # two messages, one conversation


def test_without_a_delivery_id_identical_bodies_are_still_recognized(client):
    payload = samples.webhook_message_created()

    first = client.post(WEBHOOK_PATH, **signed(payload, delivery=None))
    second = client.post(WEBHOOK_PATH, **signed(payload, delivery=None))

    assert first.json()["status"] == "accepted"
    assert second.json()["status"] == "duplicate"
    assert count(WebhookEvent) == 1


def test_many_simultaneous_copies_still_produce_one_row(adapter):
    """The guard is the database constraint, so it holds under real concurrency."""
    payload = samples.webhook_message_created()
    body = b"same-bytes"

    def deliver(_):
        with SessionLocal() as db:
            return ingest_webhook(
                db, adapter, raw_body=body, payload=payload, delivery_id="delivery-race"
            ).status

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(deliver, range(8)))

    assert results.count("accepted") == 1
    assert results.count("duplicate") == 7
    assert count(WebhookEvent) == 1
    assert count(Conversation) == 1


def test_wrong_signature_is_rejected_and_nothing_is_stored(client):
    response = client.post(
        WEBHOOK_PATH, **signed(samples.webhook_message_created(), secret="not-the-secret")
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_signature"
    assert count(WebhookEvent) == 0
    assert count(Conversation) == 0


def test_unsigned_request_is_rejected(client):
    response = client.post(WEBHOOK_PATH, json=samples.webhook_message_created())

    assert response.status_code == 401
    assert count(WebhookEvent) == 0


def test_replayed_old_request_is_rejected(client):
    ten_minutes_ago = int(time.time()) - 600
    response = client.post(
        WEBHOOK_PATH, **signed(samples.webhook_message_created(), timestamp=ten_minutes_ago)
    )

    assert response.status_code == 401
    assert count(WebhookEvent) == 0


def test_webhooks_are_refused_when_no_secret_is_configured(client, use_settings):
    use_settings(chatwoot_webhook_secret="")

    response = client.post(WEBHOOK_PATH, **signed(samples.webhook_message_created()))

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "integration_not_configured"
    assert count(WebhookEvent) == 0


def test_status_change_updates_the_existing_conversation(client):
    client.post(WEBHOOK_PATH, **signed(samples.webhook_message_created(), delivery="a"))
    client.post(
        WEBHOOK_PATH, **signed(samples.webhook_status_changed(status="resolved"), delivery="b")
    )

    with SessionLocal() as db:
        conversation = db.scalars(select(Conversation)).one()
    assert conversation.status == "resolved"
    # The status event has no message; the preview from the earlier event is kept.
    assert conversation.last_message_preview == "Do you offer monthly plans?"


def test_older_message_arriving_late_does_not_replace_the_preview(client):
    newer = samples.webhook_message_created(
        message_id=2, content="Second", created_at="2026-01-15T09:25:00.000Z"
    )
    older = samples.webhook_message_created(
        message_id=1, content="First", created_at="2026-01-15T09:20:00.000Z"
    )
    client.post(WEBHOOK_PATH, **signed(newer, delivery="a"))
    client.post(WEBHOOK_PATH, **signed(older, delivery="b"))

    with SessionLocal() as db:
        assert db.scalars(select(Conversation)).one().last_message_preview == "Second"


def test_unused_event_types_are_stored_as_ignored(client):
    response = client.post(
        WEBHOOK_PATH, **signed({"event": "webwidget_triggered", "account": {"id": 1}})
    )

    assert response.json()["status"] == "ignored"
    assert count(WebhookEvent) == 1
    assert count(Conversation) == 0


def test_body_that_is_not_json_is_refused(client):
    request = signed({})
    request["content"] = b"not json"
    # Re-sign the new body so the request passes authentication and reaches the parser.
    from app.integrations.chatwoot.signature import compute_signature
    from tests.conftest import WEBHOOK_SECRET

    stamp = request["headers"]["X-Chatwoot-Timestamp"]
    request["headers"]["X-Chatwoot-Signature"] = compute_signature(
        WEBHOOK_SECRET, stamp, b"not json"
    )

    response = client.post(WEBHOOK_PATH, **request)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_payload"
