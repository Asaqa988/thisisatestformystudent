"""Command-line helpers for the lesson.

docker compose exec backend python -m app.cli <command>

chatwoot-setup       Create the demo inbox and register the NEXUS webhook
simulate-customer    Send a message to Chatwoot as a customer would
customer-view        Show a conversation the way the customer sees it
replay-webhook       Deliver the most recent webhook a second time
"""

import argparse
import json
import os
import sys
import time

import httpx
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.errors import AppError
from app.integrations.chatwoot import mapper
from app.integrations.chatwoot.client import ChatwootClient
from app.integrations.chatwoot.signature import compute_signature
from app.models import WebhookEvent

DEMO_INBOX_NAME = "NEXUS Demo Channel"

# The events NEXUS wants to hear about.
SUBSCRIPTIONS = [
    "conversation_created",
    "conversation_updated",
    "conversation_status_changed",
    "message_created",
    "message_updated",
]

# The backend running in this same container. Hosting platforms choose the port.
LOCAL_WEBHOOK_URL = f"http://127.0.0.1:{os.environ.get('PORT', '8000')}/api/v1/webhooks/chatwoot"


def chatwoot_setup(_: argparse.Namespace) -> None:
    """Prepare Chatwoot for the lesson. Safe to run again: it reuses what already exists."""
    settings = get_settings()
    client = ChatwootClient(settings)

    profile = client.get_profile()
    print(
        f"Signed in to Chatwoot as {profile.get('name')} (account {settings.chatwoot_account_id})"
    )

    inbox = next((i for i in client.list_inboxes() if i.get("name") == DEMO_INBOX_NAME), None)
    if inbox:
        print(f"Inbox '{DEMO_INBOX_NAME}' already exists (id {inbox['id']})")
    else:
        inbox = client.create_api_inbox(DEMO_INBOX_NAME)
        print(f"Created inbox '{DEMO_INBOX_NAME}' (id {inbox['id']})")

    url = settings.nexus_webhook_url
    webhook = next((w for w in client.list_webhooks() if w.get("url") == url), None)
    if webhook:
        print(f"Webhook to {url} already exists (id {webhook['id']})")
    else:
        webhook = client.create_webhook(url, SUBSCRIPTIONS)
        print(f"Registered webhook to {url} (id {webhook['id']})")

    secret = webhook.get("secret")
    print("\nPut these two lines in your .env file:\n")
    print(f"CHATWOOT_INBOX_IDENTIFIER={inbox.get('inbox_identifier', '')}")
    if secret:
        print(f"CHATWOOT_WEBHOOK_SECRET={secret}")
    else:
        print("CHATWOOT_WEBHOOK_SECRET=<copy it from Chatwoot: Settings > Integrations > Webhooks>")
    print("\nThen reload the backend:  docker compose up -d backend")


def simulate_customer(args: argparse.Namespace) -> None:
    """Play the customer's side through Chatwoot's public Client API."""
    settings = get_settings()
    identifier = _inbox_identifier(settings)
    client = ChatwootClient(settings)

    source_id = args.source_id
    conversation_id = args.conversation
    if not source_id:
        contact = client.public_create_contact(identifier, args.name)
        source_id = contact["source_id"]
        print(f"Created contact '{args.name}'")
    if not conversation_id:
        conversation = client.public_create_conversation(identifier, source_id)
        conversation_id = str(conversation["id"])
        print(f"Started Chatwoot conversation #{conversation_id}")

    message = client.public_create_message(identifier, source_id, conversation_id, args.message)
    print(f"Customer sent message #{message.get('id')}: {args.message}")
    print("\nTo continue this conversation as the same customer, add:")
    print(f"  --source-id {source_id} --conversation {conversation_id}")


def customer_view(args: argparse.Namespace) -> None:
    """Print the conversation as the customer's app would receive it."""
    settings = get_settings()
    client = ChatwootClient(settings)
    raw = client.public_list_messages(
        _inbox_identifier(settings), args.source_id, args.conversation
    )

    messages = sorted((mapper.to_message(m) for m in raw), key=lambda m: m.sent_at)
    print(f"Chatwoot conversation #{args.conversation}, customer's view:\n")
    for message in messages:
        if message.direction == "system":
            continue
        who = "CUSTOMER" if message.direction == "inbound" else "AGENT   "
        print(f"  {who} [{message.sent_at:%H:%M:%S}] {message.content}")


def replay_webhook(_: argparse.Namespace) -> None:
    """Send the latest stored webhook again, exactly as a retry would arrive.

    The copy carries the same delivery id and a fresh, valid signature, so it
    passes authentication. Only the duplicate guard can stop it.
    """
    settings = get_settings()
    if not settings.chatwoot_webhook_secret:
        sys.exit("CHATWOOT_WEBHOOK_SECRET is not set, so a signed copy cannot be produced.")

    with SessionLocal() as db:
        event = db.scalars(
            select(WebhookEvent)
            .where(WebhookEvent.dedupe_key.like("delivery:%"))
            .order_by(WebhookEvent.received_at.desc())
            .limit(1)
        ).first()
        if event is None:
            sys.exit("No stored webhook with a delivery id yet. Send a message first.")
        before = db.scalar(select(func.count()).select_from(WebhookEvent))
        delivery_id = event.dedupe_key.removeprefix("delivery:")
        payload, event_type = event.payload, event.event_type

    body = json.dumps(payload).encode()
    timestamp = str(int(time.time()))
    response = httpx.post(
        LOCAL_WEBHOOK_URL,
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Chatwoot-Timestamp": timestamp,
            "X-Chatwoot-Signature": compute_signature(
                settings.chatwoot_webhook_secret, timestamp, body
            ),
            "X-Chatwoot-Delivery": delivery_id,
        },
        timeout=10,
    )

    with SessionLocal() as db:
        after = db.scalar(select(func.count()).select_from(WebhookEvent))
        duplicates = db.scalar(
            select(WebhookEvent.duplicate_count).where(WebhookEvent.dedupe_key == event.dedupe_key)
        )

    print(f"Replayed '{event_type}' with delivery id {delivery_id}")
    print(f"Response: {response.status_code} {response.text}")
    print(f"Rows in webhook_events: {before} before, {after} after")
    print(f"Duplicate count on that event: {duplicates}")


def _inbox_identifier(settings) -> str:
    if not settings.chatwoot_inbox_identifier:
        sys.exit("CHATWOOT_INBOX_IDENTIFIER is not set. Run `chatwoot-setup` first.")
    return settings.chatwoot_inbox_identifier


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("chatwoot-setup", help=chatwoot_setup.__doc__).set_defaults(
        run=chatwoot_setup
    )

    simulate = commands.add_parser("simulate-customer", help=simulate_customer.__doc__)
    simulate.add_argument("--name", default="Lina Haddad")
    simulate.add_argument("--message", default="Hello, do you offer monthly marketing plans?")
    simulate.add_argument("--source-id", help="continue as an existing customer")
    simulate.add_argument("--conversation", help="continue an existing conversation")
    simulate.set_defaults(run=simulate_customer)

    view = commands.add_parser("customer-view", help=customer_view.__doc__)
    view.add_argument("--source-id", required=True)
    view.add_argument("--conversation", required=True)
    view.set_defaults(run=customer_view)

    commands.add_parser("replay-webhook", help=replay_webhook.__doc__).set_defaults(
        run=replay_webhook
    )

    args = parser.parse_args()
    try:
        args.run(args)
    except AppError as error:
        sys.exit(f"{error.code}: {error.message}")


if __name__ == "__main__":
    main()
