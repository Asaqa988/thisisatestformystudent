"""The API key that protects a deployed backend."""

import pytest

from app.api import deps
from tests import samples
from tests.conftest import WEBHOOK_PATH, make_settings, signed

KEY = "deployed-api-key"


@pytest.fixture
def key_required(monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: make_settings(nexus_api_key=KEY))


def test_without_a_configured_key_the_api_is_open(client):
    assert client.get("/api/v1/conversations").status_code == 200


def test_missing_key_is_refused(client, key_required):
    response = client.get("/api/v1/conversations")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_wrong_key_is_refused(client, key_required):
    response = client.get("/api/v1/dashboard/summary", headers={"X-NEXUS-API-Key": "guess"})

    assert response.status_code == 401


def test_correct_key_is_accepted(client, key_required):
    response = client.get("/api/v1/conversations", headers={"X-NEXUS-API-Key": KEY})

    assert response.status_code == 200


def test_health_and_webhooks_do_not_need_the_key(client, key_required):
    assert client.get("/health").status_code == 200
    # Webhooks prove themselves with Chatwoot's HMAC signature instead.
    response = client.post(WEBHOOK_PATH, **signed(samples.webhook_message_created()))
    assert response.status_code == 200


def test_hosting_platform_database_urls_get_the_psycopg_driver():
    for url in ("postgres://u:p@db:5432/x", "postgresql://u:p@db:5432/x"):
        assert make_settings(database_url=url).database_url == "postgresql+psycopg://u:p@db:5432/x"
