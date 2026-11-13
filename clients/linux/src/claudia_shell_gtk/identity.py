"""Which Claudia app a shell shows: its application id, name and the server model behind it. No GTK in here.

This table is the one place that tells the three apps apart (D97): the window, the application, the local server and
the command line all take an :class:`AppIdentity` and never name an app themselves. A fourth app would be one more
entry here, one more manifest (``manifest.py``), and its own folder under ``apps/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = ["APPS_DIR", "AppIdentity", "UnknownApp", "get", "names"]

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
    def command(self) -> str:
        """The command that starts this app from a terminal or a launcher (``claudia-composes``)."""
        return f"claudia-{self.name}"

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
    "computes": AppIdentity(
        name="computes",
        title="Claudia Computes",
        application_id="de.claudiaoffice.computes",
        model="claudia_computes:WorkbookModel",
    ),
    "creates": AppIdentity(
        name="creates",
        title="Claudia Creates",
        application_id="de.claudiaoffice.creates",
        model="claudia_creates:SlideModel",
    ),
}


def names() -> tuple[str, ...]:
    """The apps there is a Linux client for, in the order of the suite."""
    return tuple(_APPS)


def get(name: str) -> AppIdentity:
    """The identity of the app ``name``; :class:`UnknownApp` (naming the available ones) if there is none."""
    try:
        return _APPS[name]
    except KeyError:
        raise UnknownApp(f"there is no Linux client for '{name}' yet; available: {', '.join(sorted(_APPS))}") from None
