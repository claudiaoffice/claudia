"""What the web view may navigate to, and what it may write to disk. No GTK in here, so it is tested without a display.

The page is the shell's own frontend, served by the local server, but it shows text that other people wrote. A link in
a document must not replace the application, and a file name that the page suggests must not choose where the file goes.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

__all__ = ["external_target", "is_internal", "origin_of", "safe_download_name", "unique_path"]

_OPENABLE_SCHEMES = frozenset({"http", "https", "mailto"})
_MAX_NAME = 200
_FALLBACK_NAME = "download"


def _origin(uri: str) -> tuple[str, str, int | None] | None:
    """``(scheme, host, port)`` of an http(s) address, or ``None`` when it has no clean origin (user info, bad port)."""
    try:
        parts = urlsplit(uri)
        if parts.username is not None or parts.password is not None or not parts.hostname:
            return None
        return parts.scheme, parts.hostname, parts.port
    except ValueError:  # e.g. "127.0.0.1:41233.evil.example": the port is not a number
        return None


def origin_of(uri: str) -> str | None:
    """The canonical origin (``https://host[:port]``, the key of ``servers``, ``trust``) of an https address, or
    ``None`` for anything else: only an https address has a certificate that could have been trusted."""
    found = _origin(uri)
    if found is None or found[0] != "https":
        return None
    _scheme, host, port = found
    shown = f"[{host}]" if ":" in host else host
    return f"https://{shown}" + (f":{port}" if port not in (None, 443) else "")


def is_internal(uri: str, origin: str) -> bool:
    """Is ``uri`` part of the page itself: the same scheme, host and port as the server at ``origin``?

    ``about:blank`` and ``blob:`` addresses created by that origin count (the page makes them for downloads).
    """
    if uri == "about:blank":
        return True
    if uri.startswith("blob:"):
        uri = uri[len("blob:") :]
    wanted = _origin(origin)
    return wanted is not None and _origin(uri) == wanted


def external_target(uri: str) -> str | None:
    """The address to hand to the user's default application, or ``None`` if it must never be opened.

    Only web pages and mail addresses are passed on: ``file:``, ``javascript:``, ``data:`` and the like are refused.
    """
    scheme = uri.partition(":")[0].lower() if ":" in uri else ""
    return uri if scheme in _OPENABLE_SCHEMES else None


def safe_download_name(suggested: str) -> str:
    """A plain file name made from what the page suggested: no directories, no hidden file, no control characters."""
    cleaned = "".join(ch for ch in suggested if ch.isprintable())
    name = cleaned.replace("\\", "/").rsplit("/", 1)[-1].strip().lstrip(".").strip()
    if not name:
        return _FALLBACK_NAME
    if len(name) > _MAX_NAME:
        suffix = Path(name).suffix[:16]
        name = name[: _MAX_NAME - len(suffix)] + suffix if suffix else name[:_MAX_NAME]
    return name


def unique_path(directory: Path, name: str) -> Path:
    """``directory/name``, or ``name (1)``, ``name (2)`` ... when that file exists already: nothing is overwritten."""
    candidate = directory / name
    if not candidate.exists():
        return candidate
    stem, suffix = Path(name).stem, Path(name).suffix
    number = 1
    while (candidate := directory / f"{stem} ({number}){suffix}").exists():
        number += 1
    return candidate
