"""Test setup.

Tests run against a real PostgreSQL database named `<your database>_test`, so
they exercise the same unique constraints the application relies on. Chatwoot
is replaced by FakeChatwoot: no test touches the network.

    docker compose exec backend pytest
"""

import json
import os
import time

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

# --- Point the application at the test database before it is imported --------

_base_url = make_url(
    os.environ.get("DATABASE_URL", "postgresql+psycopg://nexus:nexus@localhost:5433/nexus")
)
_test_url = _base_url.set(database=f"{_base_url.database}_test")

_admin = create_engine(_base_url, isolation_level="AUTOCOMMIT")
with _admin.connect() as _connection:
    _exists = _connection.scalar(
        text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": _test_url.database}
    )
    if not _exists:
        _connection.execute(text(f'CREATE DATABASE "{_test_url.database}"'))
_admin.dispose()

os.environ["DATABASE_URL"] = _test_url.render_as_string(hide_password=False)

from fastapi.testclient import TestClient  # noqa: E402

from app.api.deps import get_adapter  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.core.db import Base, engine  # noqa: E402
from app.integrations.chatwoot import ChatwootAdapter  # noqa: E402
from app.integrations.chatwoot.signature import compute_signature  # noqa: E402
from app.main import app  # noqa: E402
from tests import samples  # noqa: E402

WEBHOOK_SECRET = "test-webhook-secret"
API_TOKEN = "test-api-token"
WEBHOOK_PATH = "/api/v1/webhooks/chatwoot"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture(autouse=True)
def _clean_tables():
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE webhook_events, conversations"))
    yield


class FakeChatwoot:
    """Answers like Chatwoot would and remembers what it was asked.

    `mode` simulates trouble: "down" (cannot connect), "unauthorized" (401), "error" (500).
    """

    def __init__(self):
        self.mode = "ok"
        self.requests: list[httpx.Request] = []
        self.conversations = [samples.rest_conversation()]
        self.messages = [
            samples.rest_message(
                message_id=346, message_type=1, content="Yes, we do.", created_at=1768468900
            ),
            samples.rest_message(message_id=345),
        ]

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.mode == "down":
            raise httpx.ConnectError("connection refused", request=request)
        if self.mode == "unauthorized":
            return httpx.Response(401, json={"error": "Invalid Access Token"})
        if self.mode == "error":
            return httpx.Response(500, text="Internal Server Error")

        path = request.url.path
        if path == "/api/v1/profile":
            return httpx.Response(200, json={"id": 1, "accounts": [{"id": 1, "name": "Acme"}]})
        if path == "/api/v1/accounts/1/inboxes":
            return httpx.Response(200, json={"payload": [{"id": 3, "name": "NEXUS Demo Channel"}]})
        if path == "/api/v1/accounts/1/conversations":
            return httpx.Response(200, json={"data": {"meta": {}, "payload": self.conversations}})
        if path.endswith("/messages") and request.method == "GET":
            return httpx.Response(200, json={"meta": {}, "payload": self.messages})
        if path.endswith("/messages") and request.method == "POST":
            body = json.loads(request.content)
            created = samples.rest_message(
                message_id=900, message_type=1, content=body["content"], created_at=int(time.time())
            )
            return httpx.Response(200, json=created)
        return httpx.Response(404, json={"error": "Resource could not be found"})

    @property
    def last_request(self) -> httpx.Request:
        return self.requests[-1]


def make_settings(**overrides) -> Settings:
    values = {
        "chatwoot_base_url": "http://chatwoot.test",
        "chatwoot_account_id": 1,
        "chatwoot_api_token": API_TOKEN,
        "chatwoot_webhook_secret": WEBHOOK_SECRET,
        "webhook_max_age_seconds": 300,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture
def fake_chatwoot() -> FakeChatwoot:
    return FakeChatwoot()


@pytest.fixture
def adapter(fake_chatwoot) -> ChatwootAdapter:
    return ChatwootAdapter(make_settings(), transport=httpx.MockTransport(fake_chatwoot))


@pytest.fixture
def client(adapter):
    app.dependency_overrides[get_adapter] = lambda: adapter
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def use_settings(fake_chatwoot):
    """Swap in an adapter built from different settings, e.g. with credentials missing."""

    def _use(**overrides) -> None:
        swapped = ChatwootAdapter(
            make_settings(**overrides), transport=httpx.MockTransport(fake_chatwoot)
        )
        app.dependency_overrides[get_adapter] = lambda: swapped

    return _use


def signed(
    payload: dict,
    *,
    delivery: str | None = "delivery-1",
    secret: str = WEBHOOK_SECRET,
    timestamp: int | None = None,
) -> dict:
    """Build the request Chatwoot would send: exact body bytes plus signature headers."""
    body = json.dumps(payload).encode()
    stamp = str(int(time.time()) if timestamp is None else timestamp)
    headers = {
        "Content-Type": "application/json",
        "X-Chatwoot-Timestamp": stamp,
        "X-Chatwoot-Signature": compute_signature(secret, stamp, body),
    }
    if delivery:
        headers["X-Chatwoot-Delivery"] = delivery
    return {"content": body, "headers": headers}
