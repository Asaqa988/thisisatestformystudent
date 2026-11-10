"""Verify that a webhook really came from our Chatwoot.

Chatwoot signs each delivery (documented in its "How to use webhooks" guide):

    X-Chatwoot-Timestamp: 1731254400
    X-Chatwoot-Signature: sha256=<hex>

    hex = HMAC-SHA256(key=webhook_secret, message="{timestamp}.{raw_body}")

Only Chatwoot and NEXUS know the secret, so only Chatwoot can produce a
signature that matches. Two details matter:

* The raw bytes are signed. Parsing the JSON and writing it back can change
  spacing or key order, and then the signature no longer matches.
* The comparison is constant-time, so an attacker cannot learn the correct
  signature one character at a time by measuring how long we take.
"""

import hashlib
import hmac
import time

from app.core.errors import InvalidSignature

SIGNATURE_HEADER = "x-chatwoot-signature"
TIMESTAMP_HEADER = "x-chatwoot-timestamp"
DELIVERY_HEADER = "x-chatwoot-delivery"


def compute_signature(secret: str, timestamp: str, raw_body: bytes) -> str:
    message = f"{timestamp}.".encode() + raw_body
    return "sha256=" + hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_signature(
    *,
    secret: str,
    raw_body: bytes,
    signature: str | None,
    timestamp: str | None,
    max_age_seconds: int,
    now: float | None = None,
) -> None:
    """Return normally when the request is authentic, otherwise raise InvalidSignature."""
    if not signature or not timestamp:
        raise InvalidSignature("The webhook is missing its signature headers.")

    expected = compute_signature(secret, timestamp, raw_body)
    if not hmac.compare_digest(expected, signature):
        raise InvalidSignature("The webhook signature does not match.")

    # A valid signature on an old request means someone is replaying a capture.
    try:
        signed_at = int(timestamp)
    except ValueError:
        raise InvalidSignature("The webhook timestamp is not a number.") from None

    current = time.time() if now is None else now
    if abs(current - signed_at) > max_age_seconds:
        raise InvalidSignature("The webhook timestamp is too old.")
