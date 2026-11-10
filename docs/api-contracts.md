# NEXUS Backend API contracts (Lesson 01)

Base URL from the host: `http://localhost:8100`. The browser never calls it
directly; it calls `http://localhost:3100/api/nexus/...`, which the frontend
forwards to the backend with the path unchanged after `/api/nexus`.

Interactive documentation: `http://localhost:8100/docs`.

## Conventions

- JSON in, JSON out. Timestamps are ISO 8601 in UTC.
- NEXUS ids are UUIDs. The id used by the external system is `external_id`.
- Every error has the same shape:

```json
{ "error": { "code": "upstream_unavailable", "message": "Chatwoot is not responding." } }
```

| HTTP | `code` | Meaning |
|---|---|---|
| 401 | `invalid_signature` | Webhook signature missing, wrong, or too old |
| 404 | `not_found` | No such conversation |
| 422 | `validation_error` | The request body is not valid |
| 502 | `upstream_unavailable` | Chatwoot could not be reached or returned 5xx |
| 502 | `upstream_auth_failed` | Chatwoot rejected the API token |
| 502 | `upstream_rejected` | Chatwoot refused the request (4xx) |
| 503 | `integration_not_configured` | Chatwoot credentials are missing from `.env` |

## Normalized shapes

These are the only shapes the frontend knows.

```jsonc
// Conversation
{
  "id": "0b7e…",                 // NEXUS id
  "source": "chatwoot",
  "external_id": "12",
  "channel": "api",              // api | web_widget | email | whatsapp | ...
  "inbox_name": "NEXUS Demo Channel",
  "status": "open",              // open | pending | snoozed | resolved
  "contact": { "name": "Lina Haddad", "email": null, "avatar_url": null },
  "last_message": {
    "preview": "Do you offer monthly plans?",
    "direction": "inbound",      // inbound | outbound | system
    "at": "2026-11-10T16:20:11Z"
  },
  "unread_count": 1,
  "updated_at": "2026-11-10T16:20:11Z"
}

// Message
{
  "id": "345",                   // id in the source system
  "direction": "inbound",        // inbound | outbound | system
  "author": { "type": "contact", "name": "Lina Haddad" },   // contact | agent | bot | system
  "content": "Do you offer monthly plans?",
  "private": false,              // true for internal notes
  "sent_at": "2026-11-10T16:20:11Z"
}
```

## Endpoints

### Health

| Method | Path | Returns |
|---|---|---|
| GET | `/health` | `200 {"status":"ok"}` when the process is alive |
| GET | `/health/ready` | `200` when the database answers, `503` otherwise. Also reports Chatwoot status without failing on it |

```json
{
  "status": "ready",
  "checks": {
    "database": { "ok": true },
    "chatwoot": { "ok": true, "configured": true, "detail": "Connected to account 1" }
  }
}
```

### Dashboard

`GET /api/v1/dashboard/summary`

```json
{
  "conversations": { "total": 4, "open": 3, "awaiting_reply": 2, "resolved": 1 },
  "events": { "received_24h": 18, "duplicates_ignored": 2, "last_received_at": "2026-11-10T16:20:11Z" },
  "integrations": [ { "key": "chatwoot", "name": "Chatwoot", "configured": true, "ok": true, "detail": "Connected to account 1" } ]
}
```

`GET /api/v1/events?limit=20` returns the most recent normalized webhook events.

```json
{ "items": [ { "id": "…", "source": "chatwoot", "event_type": "message_created",
               "summary": "Lina Haddad: Do you offer monthly plans?",
               "external_conversation_id": "12", "duplicate_count": 0,
               "received_at": "2026-11-10T16:20:11Z" } ] }
```

### Conversations

| Method | Path | Notes |
|---|---|---|
| GET | `/api/v1/conversations?status=open` | From the NEXUS database. `status` is optional |
| POST | `/api/v1/conversations/sync` | Pulls conversations from Chatwoot and updates references. Returns `{"synced": 4}` |
| GET | `/api/v1/conversations/{id}` | One conversation reference |
| GET | `/api/v1/conversations/{id}/messages` | Fetched live from Chatwoot through the adapter |
| POST | `/api/v1/conversations/{id}/messages` | Sends a reply through Chatwoot |

Reply request and response:

```json
// request
{ "content": "Yes, we do. I will send the pricing sheet." }

// 201 response: the normalized Message that Chatwoot created
{ "id": "346", "direction": "outbound", "author": { "type": "agent", "name": "Nour" },
  "content": "Yes, we do. I will send the pricing sheet.", "private": false,
  "sent_at": "2026-11-10T16:21:02Z" }
```

### Webhooks

`POST /api/v1/webhooks/chatwoot` is called by Chatwoot, not by the frontend.

Headers Chatwoot sends:

| Header | Use |
|---|---|
| `X-Chatwoot-Signature` | `sha256=` + HMAC-SHA256(secret, `"{timestamp}.{raw_body}"`) |
| `X-Chatwoot-Timestamp` | Unix seconds when the request was signed |
| `X-Chatwoot-Delivery` | Unique id of this delivery, used as the duplicate key |

Responses:

```json
{ "status": "accepted",  "event_id": "…" }   // 200, stored and processed
{ "status": "duplicate", "event_id": "…" }   // 200, seen before, nothing stored again
{ "status": "ignored",   "event_id": "…" }   // 200, stored, event type not used yet
```

A duplicate returns `200`, not an error, so Chatwoot stops retrying.

### Integration status

`GET /api/v1/integrations/chatwoot/status`

```json
{ "key": "chatwoot", "name": "Chatwoot", "configured": true, "ok": true,
  "detail": "Connected to account 1", "webhook_verification": "hmac" }
```

`webhook_verification` is `hmac` when a secret is set and `disabled` when it is
not. The token itself is never returned.

## What the adapter calls on Chatwoot

Each of these was called against the running Chatwoot 4.19.1 while building the
lesson. None is assumed from documentation alone.

| NEXUS action | Chatwoot endpoint |
|---|---|
| Check connection | `GET /api/v1/profile` |
| List inboxes | `GET /api/v1/accounts/{account}/inboxes` |
| List conversations | `GET /api/v1/accounts/{account}/conversations?status=all` |
| List messages | `GET /api/v1/accounts/{account}/conversations/{n}/messages` |
| Send reply | `POST /api/v1/accounts/{account}/conversations/{n}/messages` |
| Create demo inbox | `POST /api/v1/accounts/{account}/inboxes` |
| List and register webhooks | `GET` and `POST /api/v1/accounts/{account}/webhooks` |

Authentication header on every call: `api_access_token: <token>`.

What the running instance confirmed:

- The webhook object returned by the API includes its `secret`.
- Deliveries carry `X-Chatwoot-Signature`, `X-Chatwoot-Timestamp` and
  `X-Chatwoot-Delivery` (a UUID). A real delivery passed our HMAC check.
- Webhooks to a private address are refused unless Chatwoot runs with
  `SAFE_FETCH_ALLOW_PRIVATE_NETWORK=true`.
- Message webhooks describe `message_type` as a word and `created_at` as an ISO
  date; the REST API uses a number and a Unix timestamp for the same fields.

The demo commands in `app/cli.py` also use Chatwoot's public Client API, which
needs the inbox identifier and no agent token:

| Demo action | Chatwoot endpoint |
|---|---|
| Create a contact | `POST /public/api/v1/inboxes/{identifier}/contacts` |
| Start a conversation | `POST .../contacts/{source_id}/conversations` |
| Send a customer message | `POST .../conversations/{n}/messages` |
| Read as the customer | `GET .../conversations/{n}/messages` |
