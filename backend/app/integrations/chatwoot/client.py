"""HTTP access to Chatwoot.

One place builds the URL, adds the token header and turns every kind of failure
into one of three NEXUS errors, so callers never handle raw HTTP problems:

    cannot connect, timeout, 5xx   ->  UpstreamUnavailable
    401                            ->  UpstreamAuthFailed
    other 4xx                      ->  UpstreamRejected
"""

from typing import Any

import httpx

from app.core.config import Settings
from app.core.errors import (
    IntegrationNotConfigured,
    UpstreamAuthFailed,
    UpstreamRejected,
    UpstreamUnavailable,
)


class ChatwootClient:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self._settings = settings
        # `transport` lets tests replace the network with a fake Chatwoot.
        self._http = httpx.Client(
            base_url=settings.chatwoot_base_url.rstrip("/"),
            timeout=settings.chatwoot_timeout_seconds,
            transport=transport,
        )

    # --- Application API: needs the agent's access token ----------------------

    def get_profile(self) -> dict:
        return self._request("GET", "/api/v1/profile")

    def list_inboxes(self) -> list[dict]:
        return self._request("GET", self._account("/inboxes")).get("payload", [])

    def create_api_inbox(self, name: str) -> dict:
        body = {"name": name, "channel": {"type": "api", "webhook_url": ""}}
        return self._request("POST", self._account("/inboxes"), json=body)

    def list_conversations(self, status: str = "all", page: int = 1) -> list[dict]:
        data = self._request(
            "GET",
            self._account("/conversations"),
            params={"status": status, "assignee_type": "all", "page": page},
        )
        return (data.get("data") or {}).get("payload", [])

    def list_messages(self, conversation_id: str) -> list[dict]:
        data = self._request("GET", self._account(f"/conversations/{conversation_id}/messages"))
        return data.get("payload", [])

    def create_message(self, conversation_id: str, content: str, private: bool = False) -> dict:
        body = {"content": content, "message_type": "outgoing", "private": private}
        return self._request(
            "POST", self._account(f"/conversations/{conversation_id}/messages"), json=body
        )

    def list_webhooks(self) -> list[dict]:
        data = self._request("GET", self._account("/webhooks"))
        return (data.get("payload") or {}).get("webhooks", [])

    def create_webhook(self, url: str, subscriptions: list[str]) -> dict:
        data = self._request(
            "POST", self._account("/webhooks"), json={"url": url, "subscriptions": subscriptions}
        )
        return (data.get("payload") or {}).get("webhook", data)

    # --- Client API: what a customer's app would call. No agent token. --------
    # Used only by the demo commands in app/cli.py to play the customer's side.

    def public_create_contact(self, inbox_identifier: str, name: str) -> dict:
        return self._request(
            "POST",
            f"/public/api/v1/inboxes/{inbox_identifier}/contacts",
            json={"name": name},
            authenticated=False,
        )

    def public_create_conversation(self, inbox_identifier: str, source_id: str) -> dict:
        return self._request(
            "POST",
            f"/public/api/v1/inboxes/{inbox_identifier}/contacts/{source_id}/conversations",
            json={},
            authenticated=False,
        )

    def public_create_message(
        self, inbox_identifier: str, source_id: str, conversation_id: str, content: str
    ) -> dict:
        return self._request(
            "POST",
            f"/public/api/v1/inboxes/{inbox_identifier}/contacts/{source_id}"
            f"/conversations/{conversation_id}/messages",
            json={"content": content},
            authenticated=False,
        )

    def public_list_messages(
        self, inbox_identifier: str, source_id: str, conversation_id: str
    ) -> list[dict]:
        return self._request(
            "GET",
            f"/public/api/v1/inboxes/{inbox_identifier}/contacts/{source_id}"
            f"/conversations/{conversation_id}/messages",
            authenticated=False,
        )

    # --- Internals -------------------------------------------------------------

    def _account(self, path: str) -> str:
        return f"/api/v1/accounts/{self._settings.chatwoot_account_id}{path}"

    def _request(self, method: str, path: str, *, authenticated: bool = True, **kwargs) -> Any:
        headers = {}
        if authenticated:
            if not self._settings.chatwoot_configured:
                raise IntegrationNotConfigured(
                    "Chatwoot is not connected yet. Add CHATWOOT_API_TOKEN and "
                    "CHATWOOT_ACCOUNT_ID to .env, then restart the backend."
                )
            headers["api_access_token"] = self._settings.chatwoot_api_token

        try:
            response = self._http.request(method, path, headers=headers, **kwargs)
        except httpx.TimeoutException:
            raise UpstreamUnavailable("Chatwoot took too long to answer.") from None
        except httpx.HTTPError:
            raise UpstreamUnavailable(
                "Chatwoot is not responding. Check that its containers are running."
            ) from None

        if response.status_code == 401:
            raise UpstreamAuthFailed(
                "Chatwoot rejected the API token. Check CHATWOOT_API_TOKEN in .env."
            )
        if response.status_code >= 500:
            raise UpstreamUnavailable(f"Chatwoot returned an error ({response.status_code}).")
        if response.status_code >= 400:
            raise UpstreamRejected(
                f"Chatwoot refused the request ({response.status_code}): {_reason(response)}"
            )

        try:
            return response.json()
        except ValueError:
            raise UpstreamUnavailable("Chatwoot returned a response that is not JSON.") from None


def _reason(response: httpx.Response) -> str:
    """Pull a short, human explanation out of a Chatwoot error body."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:160] or "no details"
    if isinstance(body, dict):
        for key in ("error", "message", "errors"):
            if body.get(key):
                return str(body[key])[:160]
    return "no details"
