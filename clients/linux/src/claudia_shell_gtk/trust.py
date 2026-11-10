"""The certificates a person has chosen to trust (E5.8). No GTK.

A server whose certificate no authority vouches for — a self-signed one on a small team's machine, say — can still be
connected to once a person has looked at its fingerprint and said "trust this server". What is remembered is **that one
certificate for that one origin** (its SHA-256 fingerprint), never "this host" or "any certificate": when the server
shows another certificate the person is asked again (dialog B of the mock-up), because that is exactly what an
interception looks like. The pins live in ``shell.json`` (``settings``).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from datetime import date
from pathlib import Path

from . import settings

__all__ = ["TrustStore", "format_fingerprint", "may_override"]

_FINGERPRINT = re.compile(r"^[0-9a-fA-F]{64}$")


def format_fingerprint(sha256: str) -> list[str]:
    """The fingerprint as the dialog shows it: four lines of eight upper case hex bytes, ``01:23:…``."""
    if not _FINGERPRINT.fullmatch(sha256):
        raise ValueError("a fingerprint is 64 hex digits (the SHA-256 of a certificate)")
    pairs = [sha256[i : i + 2].upper() for i in range(0, 64, 2)]
    return [":".join(pairs[i : i + 8]) for i in range(0, 32, 8)]


# Gio.TlsCertificateFlags: what a pinned certificate may be let through for. Anything else (expired, not yet valid,
# revoked, insecure, any other error) is a real problem with the certificate that no pin makes right.
_UNKNOWN_CA = 1
_BAD_IDENTITY = 2
_OVERRIDABLE = _UNKNOWN_CA | _BAD_IDENTITY


def may_override(der: bytes, pinned: str | None, errors: int) -> bool:
    """May the web view go on although the system found ``errors`` (``Gio.TlsCertificateFlags``) in the certificate
    ``der`` of its own connection? Only when the problem is that nobody vouches for it (unknown authority, a name that
    is not the server's) **and** it is the very certificate that was trusted for this address (``pinned``)."""
    return pinned is not None and errors & ~_OVERRIDABLE == 0 and hashlib.sha256(der).hexdigest() == pinned


class TrustStore:
    """Pins of trusted certificates, read from and written to the settings file at ``path`` on every call (the file
    is small and other parts of the shell write to it too, so nothing is cached)."""

    def __init__(self, path: Path | None = None, *, today: Callable[[], date] = date.today) -> None:
        self._path = path
        self._today = today

    def snapshot(self) -> dict[str, dict[str, str]]:
        """All pins, ``origin → {"sha256": …, "since": …}``, as a copy that may be changed freely."""
        return settings.load_trusted(self._path)

    def pinned(self, origin: str) -> str | None:
        """The fingerprint trusted for ``origin``, or ``None``."""
        entry = self.snapshot().get(origin)
        return entry["sha256"] if entry else None

    def is_trusted(self, origin: str, sha256: str) -> bool:
        return self.pinned(origin) == sha256.lower()

    def trust(self, origin: str, sha256: str) -> None:
        """Trust exactly this certificate for ``origin``, replacing an earlier one."""
        if not origin.startswith("https://"):
            raise ValueError("only an https origin has a certificate to trust")
        if not _FINGERPRINT.fullmatch(sha256):
            raise ValueError("a fingerprint is 64 hex digits (the SHA-256 of a certificate)")
        pins = self.snapshot()
        pins[origin] = {"sha256": sha256.lower(), "since": self._today().isoformat()}
        settings.save_trusted(pins, self._path)

    def forget(self, origin: str) -> None:
        """Stop trusting whatever certificate was trusted for ``origin`` (nothing to forget is fine)."""
        pins = self.snapshot()
        if pins.pop(origin, None) is not None:
            settings.save_trusted(pins, self._path)
