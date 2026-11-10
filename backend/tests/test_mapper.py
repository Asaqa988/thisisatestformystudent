"""Chatwoot JSON becomes NEXUS shapes, whichever dialect Chatwoot used."""

from datetime import UTC, datetime

from app.integrations.chatwoot import mapper
from tests import samples


def test_rest_and_webhook_messages_normalize_to_the_same_shape():
    from_rest = mapper.to_message(samples.rest_message(message_type=0, created_at=1768468811))
    from_webhook = mapper.to_message(
        samples.webhook_message_created(created_at="2026-01-15T09:20:11.000Z")
    )

    assert from_rest.direction == from_webhook.direction == "inbound"
    assert from_rest.author.type == from_webhook.author.type == "contact"
    assert from_rest.author.name == "Lina Haddad"
    assert from_rest.sent_at == datetime.fromtimestamp(1768468811, tz=UTC)
    assert from_webhook.sent_at == datetime(2026, 1, 15, 9, 20, 11, tzinfo=UTC)


def test_message_types_map_to_directions():
    assert mapper.to_direction(0) == mapper.to_direction("incoming") == "inbound"
    assert mapper.to_direction(1) == mapper.to_direction("outgoing") == "outbound"
    assert mapper.to_direction(2) == mapper.to_direction("activity") == "system"
    assert mapper.to_direction("something-new") == "system"


def test_channel_names_lose_their_chatwoot_prefix():
    assert mapper.to_channel("Channel::Api") == "api"
    assert mapper.to_channel("Channel::WebWidget") == "web_widget"
    assert mapper.to_channel("Channel::Brandnew") == "brandnew"
    assert mapper.to_channel(None) == "unknown"


def test_rest_conversation_becomes_a_snapshot():
    snapshot = mapper.to_conversation(samples.rest_conversation(), {3: "NEXUS Demo Channel"})

    assert snapshot.external_id == "12"
    assert snapshot.channel == "api"
    assert snapshot.inbox_name == "NEXUS Demo Channel"
    assert snapshot.contact.name == "Lina Haddad"
    assert snapshot.contact.email == "lina@example.com"
    assert snapshot.last_message.preview == "Do you offer monthly plans?"
    assert snapshot.last_message.direction == "inbound"
    assert snapshot.unread_count == 2


def test_message_webhook_becomes_an_event_with_a_conversation():
    event = mapper.to_event(samples.webhook_message_created())

    assert event.event_type == "message_created"
    assert event.external_account_id == "1"
    assert event.external_conversation_id == "12"
    assert event.summary == "Lina Haddad: Do you offer monthly plans?"
    assert event.conversation.inbox_name == "NEXUS Demo Channel"
    assert event.conversation.last_message.direction == "inbound"


def test_internal_notes_are_never_quoted_or_used_as_the_preview():
    event = mapper.to_event(
        samples.webhook_message_created(
            message_type="outgoing", private=True, content="VIP, be careful"
        )
    )

    assert event.summary == "Internal note by Nour"
    assert event.conversation.last_message is None


def test_status_change_webhook_carries_the_new_status():
    event = mapper.to_event(samples.webhook_status_changed(status="resolved"))

    assert event.event_type == "conversation_status_changed"
    assert event.conversation.status == "resolved"
    assert "resolved" in event.summary


def test_unknown_events_are_kept_but_carry_no_conversation():
    event = mapper.to_event({"event": "webwidget_triggered", "account": {"id": 1}})

    assert event.event_type == "webwidget_triggered"
    assert event.conversation is None


def test_long_previews_are_shortened():
    assert len(mapper.to_preview("word " * 200)) == mapper.PREVIEW_LENGTH
