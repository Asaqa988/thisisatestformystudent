"""The webhook signature check, on its own."""

import pytest

from app.core.errors import InvalidSignature
from app.integrations.chatwoot.signature import compute_signature, verify_signature

SECRET = "s3cret"
BODY = b'{"event":"message_created","id":1}'
NOW = 1_800_000_000


def check(**overrides):
    values = {
        "secret": SECRET,
        "raw_body": BODY,
        "timestamp": str(NOW),
        "signature": compute_signature(SECRET, str(NOW), BODY),
        "max_age_seconds": 300,
        "now": NOW,
    }
    values.update(overrides)
    verify_signature(**values)


def test_matches_the_documented_formula():
    # sha256=HMAC-SHA256(secret, "{timestamp}.{raw_body}"), from Chatwoot's webhook guide.
    import hashlib
    import hmac

    expected = "sha256=" + hmac.new(b"s3cret", b"1800000000." + BODY, hashlib.sha256).hexdigest()
    assert compute_signature(SECRET, "1800000000", BODY) == expected


def test_accepts_a_correctly_signed_request():
    check()


def test_rejects_a_signature_made_with_another_secret():
    with pytest.raises(InvalidSignature):
        check(signature=compute_signature("wrong", str(NOW), BODY))


def test_rejects_a_body_changed_after_signing():
    with pytest.raises(InvalidSignature):
        check(raw_body=BODY.replace(b"1", b"2"))


@pytest.mark.parametrize("missing", ["signature", "timestamp"])
def test_rejects_missing_headers(missing):
    with pytest.raises(InvalidSignature):
        check(**{missing: None})


def test_rejects_an_old_request_even_with_a_valid_signature():
    with pytest.raises(InvalidSignature, match="too old"):
        check(now=NOW + 301)


def test_accepts_a_request_inside_the_time_window():
    check(now=NOW + 299)
