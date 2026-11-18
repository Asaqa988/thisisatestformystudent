"""Products, the public shop endpoints, and voice tickets."""

import base64
import hashlib
import hmac
import json

import pytest

from app.api import deps
from app.api import products as products_api
from app.services import products
from tests.conftest import make_settings

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PNG_URL = "data:image/png;base64," + base64.b64encode(PNG).decode()


def new_product(client, **overrides):
    body = {"name": "Growth package", "price": "450", "currency": "JOD", **overrides}
    response = client.post("/api/v1/products", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_list_products(client):
    new_product(client, name="B item", sort_order=2)
    new_product(client, name="A item", sort_order=1, description="Twenty posts a month")

    items = client.get("/api/v1/products").json()["items"]

    assert [p["name"] for p in items] == ["A item", "B item"]
    assert items[0]["price"] == "450.00"
    assert items[0]["image_path"] is None


def test_update_and_delete(client):
    product = new_product(client)

    updated = client.put(
        f"/api/v1/products/{product['id']}", json={"name": "Starter", "price": None}
    ).json()
    assert updated["name"] == "Starter"
    assert updated["price"] is None

    assert client.delete(f"/api/v1/products/{product['id']}").status_code == 204
    assert client.get("/api/v1/products").json()["items"] == []


def test_image_upload_is_served_publicly(client):
    product = new_product(client, image_data_url=PNG_URL)

    assert product["image_path"].startswith(f"/api/v1/public/products/{product['id']}/image?v=")
    image = client.get(product["image_path"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"
    assert image.content == PNG


def test_image_can_be_removed(client):
    product = new_product(client, image_data_url=PNG_URL)

    updated = client.put(
        f"/api/v1/products/{product['id']}", json={"name": "Growth", "remove_image": True}
    ).json()

    assert updated["image_path"] is None


@pytest.mark.parametrize(
    "data_url",
    [
        "data:image/gif;base64,R0lGODlh",  # not an allowed type
        "data:image/png;base64,not-base64!!",  # unreadable
        "data:image/png;base64," + base64.b64encode(b"\xff\xd8\xff jpeg bytes").decode(),
    ],
)
def test_bad_images_are_refused(client, data_url):
    response = client.post("/api/v1/products", json={"name": "X", "image_data_url": data_url})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_input"


def test_oversized_image_is_refused():
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * products.MAX_IMAGE_BYTES
    with pytest.raises(Exception) as caught:
        products.decode_image("data:image/png;base64," + base64.b64encode(big).decode())
    assert "1.5 MB" in str(caught.value)


def test_public_shop_lists_only_active_products(client):
    new_product(client, name="Visible")
    new_product(client, name="Hidden", is_active=False)

    shop = client.get("/api/v1/public/shop").json()

    assert [p["name"] for p in shop["products"]] == ["Visible"]
    assert shop["voice_enabled"] is False


def test_hidden_product_image_is_not_served(client):
    product = new_product(client, is_active=False, image_data_url=PNG_URL)

    assert client.get(f"/api/v1/public/products/{product['id']}/image").status_code == 404


def test_public_endpoints_do_not_need_the_api_key(client, monkeypatch):
    monkeypatch.setattr(deps, "get_settings", lambda: make_settings(nexus_api_key="k"))

    assert client.get("/api/v1/public/shop").status_code == 200
    assert client.get("/api/v1/products").status_code == 401
    assert client.get("/api/v1/voice/context").status_code == 401


def test_voice_context_has_products_and_knowledge(client):
    new_product(client, name="Growth package", description="20 posts, 8 reels")
    client.post("/api/v1/knowledge", json={"title": "Hours", "content": "Open 9 to 5"})

    context = client.get("/api/v1/voice/context").json()

    assert "Growth package" in context["products_text"]
    assert "450 JOD" in context["products_text"]
    assert "Open 9 to 5" in context["knowledge_text"]


def test_voice_ticket_needs_configuration(client):
    response = client.post("/api/v1/public/voice-ticket")

    assert response.status_code == 503


def test_voice_ticket_is_signed_and_expires(client, monkeypatch):
    settings = make_settings(
        voice_session_secret="s3cret", voice_public_ws_url="wss://voice.test/ws"
    )
    monkeypatch.setattr(products_api, "get_settings", lambda: settings)

    body = client.post("/api/v1/public/voice-ticket").json()

    assert body["ws_url"] == "wss://voice.test/ws"
    payload, signature = body["token"].split(".")
    expected = hmac.new(b"s3cret", payload.encode(), hashlib.sha256).digest()
    assert base64.urlsafe_b64decode(signature + "==") == expected
    claims = json.loads(base64.urlsafe_b64decode(payload + "=="))
    assert len(claims["sid"]) == 32
    assert claims["exp"] > 0


def test_price_formatting():
    from decimal import Decimal

    assert products.format_price(Decimal("450.00"), "JOD") == "450 JOD"
    assert products.format_price(Decimal("12.50"), "JOD") == "12.5 JOD"
    assert products.format_price(None, "JOD") == ""
