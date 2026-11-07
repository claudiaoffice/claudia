"""Short-lived sign-ins to the server settings pages.

A session here is a bearer token for an *administrator* (``admin.py``) — it has nothing to do with a document's
own protocol (``auth.py``) and is never accepted by it, and the reverse. It travels the same way the access
secret already does (``Authorization: Bearer <token>``), never a cookie: there is nothing here for a browser to
send automatically, so there is nothing for another site to ride along on (no CSRF surface to defend).

Sessions live in memory only. A restart signs every administrator out, the same way it drops every open document
connection; there is no "remember me" and nothing of this is written to disk."""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

DEFAULT_SESSION_LIFETIME = 12 * 3600.0  # 12 hours


@dataclass(frozen=True)
class AdminSession:
    """One signed-in administrator: their name, and the clock reading past which the session is no longer valid."""

    admin: str
    expires: float


class AdminSessions:
    """Issues and checks session tokens. ``clock`` is injectable so tests do not have to sleep for real hours."""

    def __init__(self, *, lifetime: float = DEFAULT_SESSION_LIFETIME, clock: Callable[[], float] = time.monotonic):
        self._lifetime = lifetime
        self._clock = clock
        self._sessions: dict[str, AdminSession] = {}

    def issue(self, admin: str) -> str:
        """A new token for ``admin``. It is the only copy kept of it; losing it means signing in again."""
        token = secrets.token_urlsafe(32)
        self._sessions[token] = AdminSession(admin, self._clock() + self._lifetime)
        return token

    def resolve(self, token: object) -> str | None:
        """The administrator's name if ``token`` is a current session, else ``None``. An expired session is
        forgotten the moment it is looked up, so it never lingers in memory past its own lifetime."""
        if not isinstance(token, str):
            return None
        session = self._sessions.get(token)
        if session is None:
            return None
        if self._clock() >= session.expires:
            del self._sessions[token]
            return None
        return session.admin

    def revoke(self, token: object) -> None:
        """End one session (signing out); nothing happens if ``token`` was not one."""
        if isinstance(token, str):
            self._sessions.pop(token, None)

    def revoke_all_of(self, admin: str) -> None:
        """End every session of ``admin``: used when they are removed, so an old token kept somewhere stops
        working at once rather than lingering until it expires on its own."""
        for token, session in list(self._sessions.items()):
            if session.admin == admin:
                del self._sessions[token]

    def __len__(self) -> int:
        return len(self._sessions)
