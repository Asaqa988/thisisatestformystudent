"""Customers: built from conversations and contact events, searchable, linked to conversations."""

import httpx
from sqlalchemy import select

from app.core.db import SessionLocal
from app.integrations.chatwoot import mapper
from app.models import Conversation, Customer
from tests import samples
from tests.conftest import WEBHOOK_PATH, signed

FULL_CONTACT = {
    "id": 7,
    "name": "Lina Haddad",
    "email": "lina@example.com",
    "phone_number": "+962791234567",
    "thumbnail": "https://example.com/lina.png",
    "identifier": None,
    "blocked": False,
    "created_at": 1768000000,
    "last_activity_at": 1768468811,
    "additional_attributes": {
        "city": "Amman",
        "country": "Jordan",
        "company_name": "Haddad Bakery",
        "description": "Owns two branches",
        "social_profiles": {"instagram": "haddadbakery", "facebook": ""},
    },
    "custom_attributes": {"plan": "growth"},
    "contact_inboxes": [
        {"source_id": "x", "inbox": {"id": 3, "channel_type": "Channel::Api", "name": "Demo"}},
        {"source_id": "y", "inbox": {"id": 4, "channel_type": "Channel::Whatsapp", "name": "WA"}},
    ],
}


def customers() -> list[Customer]:
    with SessionLocal() as db:
        return list(db.scalars(select(Customer)))


def write(client, *, message_id=345, delivery="d1", contact=None, conversation_id=12):
    payload = samples.webhook_message_created(
        message_id=message_id, conversation_id=conversation_id
    )
    if contact is not None:
        payload["conversation"]["meta"]["sender"] = contact
    return client.post(WEBHOOK_PATH, **signed(payload, delivery=delivery))


# --- Mapping ------------------------------------------------------------------------


def test_a_full_chatwoot_contact_becomes_a_customer():
    customer = mapper.to_customer(FULL_CONTACT)

    assert customer.external_id == "7"
    assert customer.phone == "+962791234567"
    assert customer.city == "Amman"
    assert customer.company == "Haddad Bakery"
    assert customer.social_profiles == {"instagram": "haddadbakery"}  # empty ones dropped
    assert customer.custom_attributes == {"plan": "growth"}
    assert customer.channels == ["api", "whatsapp"]


def test_agents_are_not_customers():
    assert mapper.to_customer({"id": 1, "name": "Nour", "type": "user"}) is None
    assert mapper.to_customer(None) is None


# --- Created from conversations -------------------------------------------------------


def test_a_customer_message_creates_the_customer_and_links_the_conversation(client):
    write(client)

    [customer] = customers()
    assert customer.name == "Lina Haddad"
    assert customer.email == "lina@example.com"
    assert customer.channels == ["api"]
    with SessionLocal() as db:
        assert db.scalars(select(Conversation)).one().customer_id == customer.id


def test_two_conversations_with_one_person_make_one_customer(client):
    write(client, conversation_id=12, delivery="a")
    write(client, conversation_id=13, message_id=346, delivery="b")

    assert len(customers()) == 1
    listing = client.get("/api/v1/customers").json()
    assert listing["total"] == 1
    assert listing["items"][0]["conversation_count"] == 2


def test_details_from_a_later_message_update_the_customer(client):
    write(client, delivery="a")
    write(client, delivery="b", message_id=346, contact={**FULL_CONTACT, "contact_inboxes": []})

    [customer] = customers()
    assert customer.phone == "+962791234567"
    assert customer.city == "Amman"


def test_contact_updated_event_changes_the_customer(client):
    write(client)
    event = {**FULL_CONTACT, "event": "contact_updated", "account": {"id": 1}, "name": "Lina H."}
    event.pop("contact_inboxes")

    response = client.post(WEBHOOK_PATH, **signed(event, delivery="contact-1"))

    assert response.json()["status"] == "accepted"
    [customer] = customers()
    assert customer.name == "Lina H."
    assert customer.company == "Haddad Bakery"


def test_contact_created_event_adds_a_customer_without_a_conversation(client):
    event = {**FULL_CONTACT, "event": "contact_created", "account": {"id": 1}, "id": 99}

    client.post(WEBHOOK_PATH, **signed(event, delivery="contact-99"))

    [customer] = customers()
    assert customer.external_id == "99"
    listing = client.get("/api/v1/customers").json()["items"]
    assert listing[0]["conversation_count"] == 0


# --- Listing, search, detail -------------------------------------------------------------


def test_search_by_name_phone_or_company(client):
    write(client, contact=FULL_CONTACT)
    other = {
        **FULL_CONTACT,
        "id": 8,
        "name": "Omar Khalil",
        "email": None,
        "phone_number": None,
        "additional_attributes": {},
    }
    write(client, conversation_id=20, message_id=400, delivery="o", contact=other)

    def names(query):
        return [c["name"] for c in client.get(f"/api/v1/customers?q={query}").json()["items"]]

    assert names("omar") == ["Omar Khalil"]
    assert names("791234") == ["Lina Haddad"]
    assert names("bakery") == ["Lina Haddad"]
    assert sorted(names("")) == ["Lina Haddad", "Omar Khalil"]


def test_filter_by_channel(client):
    write(client, contact=FULL_CONTACT)  # api + whatsapp

    assert client.get("/api/v1/customers?channel=whatsapp").json()["total"] == 1
    assert client.get("/api/v1/customers?channel=instagram").json()["total"] == 0


def test_customer_detail_lists_their_conversations(client):
    write(client, contact=FULL_CONTACT)
    customer_id = client.get("/api/v1/customers").json()["items"][0]["id"]

    detail = client.get(f"/api/v1/customers/{customer_id}").json()

    assert detail["name"] == "Lina Haddad"
    assert detail["custom_attributes"] == {"plan": "growth"}
    assert detail["social_profiles"] == {"instagram": "haddadbakery"}
    assert [c["external_id"] for c in detail["conversations"]] == ["12"]
    assert detail["conversations"][0]["customer_id"] == customer_id
    assert detail["last_message_preview"] == "Do you offer monthly plans?"


def test_unknown_customer_is_404(client):
    response = client.get("/api/v1/customers/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# --- Syncing from Chatwoot ---------------------------------------------------------------


def test_sync_creates_customers_and_fills_in_their_channels(client, fake_chatwoot):
    original = fake_chatwoot.__call__

    def with_contacts(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/accounts/1/contacts/7":
            return httpx.Response(200, json={"payload": FULL_CONTACT})
        return original(request)

    fake_chatwoot.__class__ = type(
        "FakeWithContacts", (type(fake_chatwoot),), {"__call__": lambda self, r: with_contacts(r)}
    )

    result = client.post("/api/v1/customers/sync").json()

    assert result == {"customers": 1, "conversations": 1}
    [customer] = customers()
    assert customer.channels == ["api", "whatsapp"]
    assert customer.city == "Amman"


def test_sync_survives_a_contact_that_cannot_be_fetched(client):
    # The default fake answers 404 for /contacts/7: the customer is still created.
    result = client.post("/api/v1/customers/sync").json()

    assert result["customers"] == 1
    assert customers()[0].name == "Lina Haddad"
