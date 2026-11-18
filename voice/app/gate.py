"""Who may open a voice session.

A session costs money (OpenAI and Claude), so the page cannot open one freely:

1. The browser gets a ticket from the NEXUS backend (POST /api/v1/public/voice-ticket).
   It is signed with VOICE_SESSION_SECRET and valid for about a minute.
2. This service checks the signature and the expiry, and accepts each ticket once.
3. It also caps sessions running at the same time and sessions per IP address per hour.
"""

import base64
import binascii
import hashlib
import hmac
import json
import time
from collections import deque
from dataclasses import dataclass, field


class Refused(Exception):
    """The session may not start. `reason` is safe to show to the visitor."""

    def __init__(self, code: str, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def verify_ticket(token: str, secret: str, now: float | None = None) -> str:
    """The ticket's id, if its signature and expiry are good."""
    try:
        payload, signature = token.split(".", 1)
        given = _unb64(signature)
        claims = json.loads(_unb64(payload))
        sid, expires = str(claims["sid"]), int(claims["exp"])
    except (ValueError, KeyError, TypeError, binascii.Error, json.JSONDecodeError) as exc:
        raise Refused("bad_ticket", "This voice session link is not valid.") from exc

    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    if not hmac.compare_digest(given, expected):
        raise Refused("bad_ticket", "This voice session link is not valid.")
    if (now if now is not None else time.time()) > expires:
        raise Refused("expired", "This voice session link has expired. Try again.")
    return sid


@dataclass
class SessionGate:
    max_concurrent: int
    max_per_ip_hour: int
    active: int = 0
    _used: dict[str, float] = field(default_factory=dict)  # ticket id -> when to forget it
    _by_ip: dict[str, deque] = field(default_factory=dict)

    def admit(self, sid: str, ip: str, now: float | None = None) -> None:
        """Reserve a session slot, or raise Refused. Call release() when it ends."""
        now = now if now is not None else time.time()
        self._forget_old(now)

        if sid in self._used:
            raise Refused("ticket_used", "This voice session link was already used.")
        if self.active >= self.max_concurrent:
            raise Refused("busy", "The assistant is busy right now. Try again in a minute.")
        recent = self._by_ip.setdefault(ip, deque())
        if len(recent) >= self.max_per_ip_hour:
            raise Refused("too_many", "You have reached the limit for now. Try again later.")

        self._used[sid] = now + 3600
        recent.append(now)
        self.active += 1

    def release(self) -> None:
        self.active = max(0, self.active - 1)

    def _forget_old(self, now: float) -> None:
        for sid in [s for s, until in self._used.items() if until < now]:
            del self._used[sid]
        for ip in list(self._by_ip):
            times = self._by_ip[ip]
            while times and times[0] < now - 3600:
                times.popleft()
            if not times:
                del self._by_ip[ip]
