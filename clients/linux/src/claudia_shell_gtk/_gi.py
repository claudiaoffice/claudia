"""The GTK libraries, with the versions the shell is written for. Import GTK from here and nowhere else.

Raises ``ImportError`` or ``ValueError`` (from PyGObject) when GTK 4 or libadwaita 1.5 are not installed;
``__main__`` turns that into a message that says which packages to install.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk  # noqa: E402  (after require_version, on purpose)

__all__ = ["Adw", "Gdk", "GLib", "GObject", "Gio", "Gtk"]
