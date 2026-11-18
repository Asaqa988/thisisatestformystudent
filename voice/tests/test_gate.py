"""Tickets and session limits: the cost brakes."""

import base64
import hashlib
import hmac
import json

import pytest

from app.gate import Refused, SessionGate, verify_ticket

SECRET = "s3cret"


def ticket(sid="a" * 32, exp=2_000, secret=SECRET):
    payload = base64.urlsafe_b64encode(json.dumps({"sid": sid, "exp": exp}).encode())
    payload = payload.rstrip(b"=").decode()
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return f"{payload}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def test_good_ticket_gives_its_id():
    assert verify_ticket(ticket(), SECRET, now=1_000) == "a" * 32


@pytest.mark.parametrize(
    "token", ["", "nonsense", "a.b", ticket(secret="other"), ticket()[:-3] + "AAA"]
)
def test_bad_tickets_are_refused(token):
    with pytest.raises(Refused) as caught:
        verify_ticket(token, SECRET, now=1_000)
    assert caught.value.code == "bad_ticket"


def test_expired_ticket_is_refused():
    with pytest.raises(Refused) as caught:
        verify_ticket(ticket(exp=999), SECRET, now=1_000)
    assert caught.value.code == "expired"


def test_ticket_works_once():
    gate = SessionGate(max_concurrent=5, max_per_ip_hour=10)
    gate.admit("t1", "1.1.1.1", now=0)
    gate.release()
    with pytest.raises(Refused) as caught:
        gate.admit("t1", "1.1.1.1", now=1)
    assert caught.value.code == "ticket_used"


def test_concurrent_sessions_are_capped():
    gate = SessionGate(max_concurrent=2, max_per_ip_hour=10)
    gate.admit("t1", "1.1.1.1", now=0)
    gate.admit("t2", "2.2.2.2", now=0)
    with pytest.raises(Refused) as caught:
        gate.admit("t3", "3.3.3.3", now=0)
    assert caught.value.code == "busy"

    gate.release()
    gate.admit("t3", "3.3.3.3", now=0)
    assert gate.active == 2


def test_sessions_per_ip_are_capped_for_an_hour():
    gate = SessionGate(max_concurrent=10, max_per_ip_hour=2)
    for n in range(2):
        gate.admit(f"t{n}", "1.1.1.1", now=0)
        gate.release()
    with pytest.raises(Refused) as caught:
        gate.admit("t9", "1.1.1.1", now=10)
    assert caught.value.code == "too_many"

    gate.admit("t9", "1.1.1.1", now=3_601)  # an hour later
    gate.admit("x", "2.2.2.2", now=3_601)  # other visitors are not affected


def test_release_never_goes_negative():
    gate = SessionGate(max_concurrent=1, max_per_ip_hour=1)
    gate.release()
    assert gate.active == 0
