"""Chatwoot payloads used by the tests.

They follow the shapes Chatwoot really sends: note that the webhook uses words
and ISO dates where the REST API uses numbers and Unix timestamps.
"""

CONTACT = {"id": 7, "name": "Lina Haddad", "email": "lina@example.com", "type": "contact"}
AGENT = {"id": 1, "name": "Nour", "email": "nour@acme.test", "type": "user"}


def webhook_message_created(
    *,
    message_id: int = 345,
    conversation_id: int = 12,
    content: str = "Do you offer monthly plans?",
    message_type: str = "incoming",
    private: bool = False,
    created_at: str = "2026-01-15T09:20:11.000Z",
) -> dict:
    sender = CONTACT if message_type == "incoming" else AGENT
    return {
        "event": "message_created",
        "id": message_id,
        "content": content,
        "message_type": message_type,
        "private": private,
        "created_at": created_at,
        "content_type": "text",
        "sender": sender,
        "account": {"id": 1, "name": "Acme Agency"},
        "inbox": {"id": 3, "name": "NEXUS Demo Channel"},
        "conversation": {
            "id": conversation_id,
            "inbox_id": 3,
            "status": "open",
            "channel": "Channel::Api",
            "unread_count": 1,
            "meta": {"sender": CONTACT, "assignee": None},
            "messages": [],
        },
    }


def webhook_status_changed(*, conversation_id: int = 12, status: str = "resolved") -> dict:
    return {
        "event": "conversation_status_changed",
        "id": conversation_id,
        "account_id": 1,
        "inbox_id": 3,
        "status": status,
        "channel": "Channel::Api",
        "unread_count": 0,
        "meta": {"sender": CONTACT, "assignee": AGENT},
        "messages": [],
    }


def rest_conversation(*, conversation_id: int = 12, status: str = "open") -> dict:
    return {
        "id": conversation_id,
        "account_id": 1,
        "inbox_id": 3,
        "status": status,
        "unread_count": 2,
        "meta": {"sender": CONTACT, "channel": "Channel::Api", "assignee": None},
        "messages": [rest_message(message_id=345)],
        "last_non_activity_message": rest_message(message_id=345),
        "timestamp": 1768468811,
    }


def rest_message(
    *,
    message_id: int = 345,
    content: str = "Do you offer monthly plans?",
    message_type: int = 0,
    created_at: int = 1768468811,
    private: bool = False,
) -> dict:
    return {
        "id": message_id,
        "content": content,
        "message_type": message_type,
        "created_at": created_at,
        "private": private,
        "sender": CONTACT if message_type == 0 else AGENT,
    }
