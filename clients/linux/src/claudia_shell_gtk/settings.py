"""The shell's own small, persisted settings — today, just the person's chosen app language (E5.7, D31).

One JSON file, ``shell.json`` in :func:`paths.config_dir`, read once at start-up (``__main__.py``, before the first
window is ever built) and written whenever the page reports a new language was picked (``window.py``'s
``set_action_states``). Not a full settings system: there is exactly one key today, and this module stays that
small until there is a second one worth generalising for.

Nothing here imports GTK, so it is tested without a display.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from .paths import config_dir

__all__ = ["load_shell_locale", "save_shell_locale"]

log = logging.getLogger(__name__)

_FILENAME = "shell.json"


def _settings_path(path: Path | None) -> Path:
    return path if path is not None else config_dir() / _FILENAME


def load_shell_locale(path: Path | None = None) -> str | None:
    """The locale last chosen from Config ▸ App Language, or ``None`` if nothing was ever chosen (no settings file
    yet, the file is unreadable, or it holds something unexpected) — in every such case the caller falls back to
    :func:`i18n.detect_system_locale`, so a problem here is never fatal."""
    try:
        raw = _settings_path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError):
        return None
    locale = data.get("locale") if isinstance(data, dict) else None
    return locale if isinstance(locale, str) and locale else None


def save_shell_locale(locale: str, path: Path | None = None) -> None:
    """Remember ``locale`` for next launch. Best-effort: a folder that cannot be created or written (a read-only
    home, a full disk) is logged and otherwise ignored — the person's choice still applies for the rest of this
    session, it just will not survive a restart."""
    target = _settings_path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"locale": locale}), encoding="utf-8")
    except OSError as problem:
        log.warning("could not save the chosen app language to %s: %s", target, problem)
