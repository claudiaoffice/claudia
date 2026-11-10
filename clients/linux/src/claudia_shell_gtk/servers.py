"""Which servers a Claudia client may connect to, and the list of them that it remembers (E5.8). No GTK, no network.

Two rules live here, both about what a person can type or a page can ask for:

* an **address** names one origin (``https://host:port``) and nothing else. Plain ``http`` is only for this computer,
  so a password or a document never crosses a network unencrypted because of a typing slip (the page's own "Connect to
  a server…" builds an ``http://`` address from the page it is on, and the page of the local server is plain http);
* the **list** of servers is the shell's, not the page's: the page may rename entries and hand a list back, but only
  what passes :func:`sanitize` is ever kept, at most :data:`MAX_SERVERS` of them, and this computer's own server —
  whose port changes with every start — is never written down (:func:`for_page` adds it fresh each time).

An entry has the shape of the web app's own bookmark (``web/app/lib/server-bookmarks.ts``): ``origin``, ``label`` and
``custom`` (``true`` once a person has named it, after which a refreshed default label no longer replaces it). The one
extra field, ``local``, marks this computer's server.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from .i18n import translate as _

__all__ = [
    "MAX_LABEL",
    "MAX_SERVERS",
    "Address",
    "AddressRefused",
    "Entry",
    "default_label",
    "for_page",
    "is_loopback_host",
    "parse_address",
    "remember",
    "sanitize",
]

MAX_SERVERS = 64
"""The most servers that are remembered per app."""
MAX_LABEL = 128
MAX_ADDRESS = 255

Entry = dict[str, Any]
"""``{"origin": ..., "label": ..., "custom": ...}``, and ``"local": True`` for this computer's own server."""

_DEFAULT_PORTS = {"http": 80, "https": 443}
_BARE_HOST = re.compile(r"^(\[[0-9A-Fa-f:.]+\]|[^:/\s\[\]]+)(:\d+)?$")
_DNS_NAME = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*$")


class AddressRefused(ValueError):
    """Something that is not an address a client may connect to. ``code`` is ``bad_address`` or ``insecure``; the
    message is written for the person who typed it."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class Address:
    """One server's origin."""

    scheme: str
    """``http`` (this computer only) or ``https``."""
    host: str
    """Lower case; an IPv6 address without its brackets."""
    port: int | None
    """``None`` for the scheme's own port (80 or 443)."""

    @property
    def origin(self) -> str:
        """``https://demo.example.org:8420`` — the one canonical spelling, and the key everything else is stored by."""
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"{self.scheme}://{host}" + (f":{self.port}" if self.port is not None else "")

    @property
    def is_loopback(self) -> bool:
        """Does this address reach only the computer the client runs on?"""
        return is_loopback_host(self.host)


def is_loopback_host(host: str) -> bool:
    """``localhost`` and the loopback addresses (``127.0.0.0/8``, ``::1``) — not names that merely start like them."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _bad() -> AddressRefused:
    return AddressRefused("bad_address", _("Type the address of a server, such as demo.example.org:8420."))


def _valid_host(host: str) -> bool:
    if _DNS_NAME.fullmatch(host):
        return True
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def parse_address(raw: str, *, default_scheme: str = "https") -> Address:
    """The server that ``raw`` names, or :class:`AddressRefused`.

    A bare ``host`` or ``host:port`` gets ``default_scheme`` — ``https``, never something weaker. Anything but a plain
    origin is refused: other schemes, a user name or password, a path, a query, a fragment, a bad port, a host that is
    not a DNS name or an IP address (an internationalised name has to be typed in its ``xn--`` form), and plain
    ``http`` to anything but this computer.
    """
    text = raw.strip()
    if not text or len(text) > MAX_ADDRESS:
        raise _bad()
    if "://" not in text:
        if not _BARE_HOST.fullmatch(text):
            raise _bad()  # also catches "javascript:alert(1)": a scheme is only taken from "scheme://"
        text = f"{default_scheme}://{text}"
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        raise _bad() from None
    host = (parts.hostname or "").lower()
    if (
        parts.scheme not in _DEFAULT_PORTS
        or parts.username is not None
        or parts.password is not None
        or not host
        or not _valid_host(host)
        or parts.path not in ("", "/")
        or parts.query
        or parts.fragment
        or port == 0
        or ("?" in text or "#" in text)
    ):
        raise _bad()
    if port == _DEFAULT_PORTS[parts.scheme]:
        port = None
    address = Address(parts.scheme, host, port)
    if address.scheme == "http" and not address.is_loopback:
        raise AddressRefused("insecure", _("Use https:// — plain http is only allowed for this computer."))
    return address


# ----------------------------------------------------------------------------------------------------------- lists


def default_label(origin: str) -> str:
    """The name a server gets until a person renames it: its host and port."""
    return urlsplit(origin).netloc or origin


def sanitize(raw: object) -> list[Entry]:
    """What may be remembered of ``raw`` — a list from the settings file or one that the page sent.

    Entries that are not a valid origin are dropped, origins are made canonical, a server stays in the list once (the
    first wins), a missing or unusable label becomes the default one, a long one is cut, this computer's own entry is
    never kept, and the list is cut at :data:`MAX_SERVERS`. Anything that is not a list is no list at all.
    """
    if not isinstance(raw, list):
        return []
    kept: list[Entry] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict) or item.get("local") is True or not isinstance(item.get("origin"), str):
            continue
        if "://" not in item["origin"]:
            continue  # a stored origin names its scheme; only what a person types may be a bare host
        try:
            origin = parse_address(item["origin"]).origin
        except AddressRefused:
            continue
        if origin in seen:
            continue
        seen.add(origin)
        label = item.get("label")
        label = label.strip()[:MAX_LABEL] if isinstance(label, str) and label.strip() else default_label(origin)
        kept.append({"origin": origin, "label": label, "custom": item.get("custom") is True})
        if len(kept) == MAX_SERVERS:
            break
    return kept


def for_page(saved: Iterable[Entry], *, local_origin: str | None, local_label: str) -> list[Entry]:
    """The list the page shows: this computer's server first (when there is one), then the remembered ones.

    The local entry is named by the shell and never by the page (``custom``), and a remembered entry at the same
    address — left over from an earlier start that happened to get the same port — is not shown a second time.
    """
    shown: list[Entry] = []
    if local_origin is not None:
        shown.append({"origin": local_origin, "label": local_label, "custom": True, "local": True})
    shown.extend(dict(entry) for entry in saved if entry["origin"] != local_origin)
    return shown


def remember(saved: Iterable[Entry], origin: str) -> list[Entry]:
    """``saved`` with the server at ``origin`` added when it is not in it yet. What is there already stays as it is,
    so a name a person gave a server is never replaced by the default one."""
    kept = [dict(entry) for entry in saved]
    canonical = parse_address(origin).origin
    if all(entry["origin"] != canonical for entry in kept):
        kept.append({"origin": canonical, "label": default_label(canonical), "custom": False})
    return kept
