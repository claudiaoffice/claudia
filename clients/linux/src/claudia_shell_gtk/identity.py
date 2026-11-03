"""Which Claudia app a shell shows: its application id, name and the server model behind it. No GTK in here.

Only composes has a Linux client so far. Computes and creates get an entry here when their shells are written; the
window, the bridge and the server launcher already take everything app-specific from an :class:`AppIdentity`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = ["APPS_DIR", "AppIdentity", "UnknownApp", "get"]

APPS_DIR = Path(__file__).resolve().parents[2] / "apps"
"""Desktop entry, icon and AppStream data of each app (``apps/<app>/``)."""


class UnknownApp(KeyError):
    """There is no Linux client for that app (yet)."""

    def __str__(self) -> str:  # KeyError would show the message in quotes
        return str(self.args[0])


@dataclass(frozen=True, slots=True)
class AppIdentity:
    """What distinguishes one app's shell from another."""

    name: str
    """Short name used in commands and directories, such as ``composes``."""
    title: str
    """What the person sees, such as ``Claudia Composes``."""
    application_id: str
    """The D-Bus/GApplication id, also the name of the desktop entry and the icon (lower case, no underscore)."""
    model: str
    """The server model that the local server loads for this app (``module:Class``)."""

    @property
    def icon_search_path(self) -> Path:
        """The directory that holds this app's icon theme (``hicolor/scalable/apps/<application id>.svg``)."""
        return APPS_DIR / self.name / "icons"


_APPS = {
    "composes": AppIdentity(
        name="composes",
        title="Claudia Composes",
        application_id="de.claudiaoffice.composes",
        model="claudia_composes:TextModel",
    ),
}


def get(name: str) -> AppIdentity:
    """The identity of the app ``name``; :class:`UnknownApp` (naming the available ones) if there is none."""
    try:
        return _APPS[name]
    except KeyError:
        raise UnknownApp(f"there is no Linux client for '{name}' yet; available: {', '.join(sorted(_APPS))}") from None
