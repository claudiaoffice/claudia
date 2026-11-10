"""The shell's own small, persisted settings: the person's chosen app language (E5.7, D31), the servers each app
remembers, and the certificates that a person has chosen to trust (E5.8).

One JSON file, ``shell.json`` in :func:`claudia_shell_gtk.paths.config_dir`::

    {"locale": "de",
     "servers": {"computes": [{"origin": "https://demo.example.org:8420", "label": "demo", "custom": false}]},
     "trusted": {"https://demo.example.org:8420": {"sha256": "<64 hex digits>", "since": "2026-11-10"}}}

Every save reads the file, changes **its own key only** and writes the whole file back through a temporary file and a
rename — so one setting can never erase another, and a crash cannot leave half a file. Nothing is a settings system
yet: a key is added here when a feature needs one.

A problem with the file is never fatal: an unreadable or unexpected file reads as "nothing saved", and a write that is
impossible (a read-only home, a full disk) is logged and otherwise ignored; the choice still applies for the rest of
the session, it just does not survive a restart. Nothing here imports GTK, so it is tested without a display.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Any

from .paths import config_dir
from .servers import AddressRefused, Entry, parse_address, sanitize

__all__ = [
    "load_servers",
    "load_shell_locale",
    "load_trusted",
    "save_servers",
    "save_shell_locale",
    "save_trusted",
]

log = logging.getLogger(__name__)

_FILENAME = "shell.json"
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _settings_path(path: Path | None) -> Path:
    return path if path is not None else config_dir() / _FILENAME


def _read(path: Path | None) -> dict[str, Any]:
    """The whole settings file, or an empty one when it is missing, unreadable or not a JSON object."""
    try:
        data = json.loads(_settings_path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _update(path: Path | None, what: str, change: Callable[[dict[str, Any]], None]) -> None:
    """Apply ``change`` to the settings and write them back, best-effort (``what`` names the setting in the log)."""
    target = _settings_path(path)
    data = _read(path)
    change(data)
    temporary: str | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=target.parent, prefix=".shell-", suffix=".tmp", delete=False
        ) as handle:
            temporary = handle.name
            json.dump(data, handle)
        os.replace(temporary, target)
    except OSError as problem:
        log.warning("could not save %s to %s: %s", what, target, problem)
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


# ------------------------------------------------------------------------------------------------------ language


def load_shell_locale(path: Path | None = None) -> str | None:
    """The locale last chosen from Config ▸ App Language, or ``None`` if nothing was ever chosen — in every such
    case the caller falls back to ``i18n.detect_system_locale``."""
    locale = _read(path).get("locale")
    return locale if isinstance(locale, str) and locale else None


def save_shell_locale(locale: str, path: Path | None = None) -> None:
    """Remember ``locale`` for next launch."""
    _update(path, "the chosen app language", lambda data: data.update(locale=locale))


# ------------------------------------------------------------------------------------------------------ servers


def load_servers(app: str, path: Path | None = None) -> list[Entry]:
    """The servers that ``app`` remembers; only what :func:`~claudia_shell_gtk.servers.sanitize` accepts is returned."""
    servers = _read(path).get("servers")
    return sanitize(servers.get(app) if isinstance(servers, dict) else None)


def save_servers(app: str, servers: Iterable[Entry], path: Path | None = None) -> None:
    """Remember ``servers`` for ``app``, replacing its list. Only what passes ``servers.sanitize`` is written."""
    kept = sanitize(list(servers))

    def change(data: dict[str, Any]) -> None:
        if not isinstance(data.get("servers"), dict):
            data["servers"] = {}
        data["servers"][app] = kept

    _update(path, f"the servers of {app}", change)


# ------------------------------------------------------------------------------------------------------- trust


def _valid_trust(raw: object) -> dict[str, dict[str, str]]:
    if not isinstance(raw, Mapping):
        return {}
    kept: dict[str, dict[str, str]] = {}
    for origin, entry in raw.items():
        if not (isinstance(origin, str) and isinstance(entry, Mapping)):
            continue
        fingerprint, since = entry.get("sha256"), entry.get("since")
        if not (isinstance(fingerprint, str) and _FINGERPRINT.fullmatch(fingerprint)):
            continue
        try:
            address = parse_address(origin)
        except AddressRefused:
            continue
        if address.scheme == "https" and address.origin == origin:  # plain http has no certificate to trust
            day = since if isinstance(since, str) and _DAY.fullmatch(since) else ""
            kept[origin] = {"sha256": fingerprint, "since": day}
    return kept


def load_trusted(path: Path | None = None) -> dict[str, dict[str, str]]:
    """The certificates a person has chosen to trust: origin → ``{"sha256": 64 lower case hex digits, "since":
    "YYYY-MM-DD" or ""}``."""
    return _valid_trust(_read(path).get("trusted"))


def save_trusted(trusted: Mapping[str, Mapping[str, str]], path: Path | None = None) -> None:
    """Remember which certificate is trusted for which origin, replacing the whole list."""
    kept = _valid_trust(trusted)
    _update(path, "the trusted certificates", lambda data: data.update(trusted=kept))
