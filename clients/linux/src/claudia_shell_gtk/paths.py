"""Where the shell keeps documents and state, and where it finds the bundled web frontend (D43).

Documents and state follow the XDG base directory specification: ``$XDG_DATA_HOME``, ``$XDG_STATE_HOME`` and
``$XDG_CONFIG_HOME``, each ignored when empty or relative, with ``~/.local/share``, ``~/.local/state`` and
``~/.config`` as the defaults. Nothing here imports GTK.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["config_dir", "default_repo", "documents_dir", "find_frontend", "state_dir"]


def _xdg(variable: str, fallback: str) -> Path:
    value = os.environ.get(variable, "")
    if value and os.path.isabs(value):
        return Path(value)
    return Path.home() / fallback


def documents_dir(app: str) -> Path:
    """Where the sealed documents of ``app`` are kept (the server's ``--dir``)."""
    return _xdg("XDG_DATA_HOME", ".local/share") / "claudia" / app / "documents"


def state_dir(app: str) -> Path:
    """Where the server of ``app`` keeps its own state (the server's ``--state-dir``)."""
    return _xdg("XDG_STATE_HOME", ".local/state") / "claudia" / app


def config_dir() -> Path:
    """Where the shell itself keeps its own settings (``settings.py``'s ``shell.json`` — the person's chosen
    language among them, E5.7). Suite-wide, not one per ``app`` like :func:`documents_dir`/:func:`state_dir`:
    picking a language in one app's Config menu is meant to be found again in the other two (``web/app/lib/
    locale.ts``'s own ``localStorage`` key is single and shared for the same reason)."""
    return _xdg("XDG_CONFIG_HOME", ".config") / "claudia"


def default_repo() -> Path:
    """The repository this client was started from (development only; an installed client has none)."""
    return Path(__file__).resolve().parents[4]


def _is_frontend(folder: Path | None) -> bool:
    return folder is not None and (folder / "index.html").is_file()


def find_frontend(*, repo: Path | None = None, packaged: Path | None = None) -> Path | None:
    """The folder with the built web frontend that the local server will serve, or ``None``.

    In this order: the folder named by ``$CLAUDIA_WEB_DIR`` (if it is set it is the only candidate: a wrong path is
    reported, not quietly replaced by another frontend), the frontend shipped inside this package, and the build of a
    development checkout (``web/.output/public``). A folder counts when it holds an ``index.html``.
    """
    explicit = os.environ.get("CLAUDIA_WEB_DIR")
    if explicit:
        folder = Path(explicit)
        return folder if _is_frontend(folder) else None
    shipped = packaged if packaged is not None else Path(__file__).resolve().parent / "frontend"
    checkout = (repo or default_repo()) / "web" / ".output" / "public"
    for candidate in (shipped, checkout):
        if _is_frontend(candidate):
            return candidate
    return None
