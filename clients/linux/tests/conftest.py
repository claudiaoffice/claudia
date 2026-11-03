"""Shared test set-up. Tests marked ``gtk`` need PyGObject with GTK 4 and libadwaita and a display (``xvfb-run -a``)."""

from __future__ import annotations

import os

import pytest

# Containers and CI have no GPU and often no user namespaces: ask for software rendering and for WebKit without its
# own sandbox. Only tests get these; the shell itself never sets them.
for _name, _value in {
    "GSK_RENDERER": "cairo",
    "LIBGL_ALWAYS_SOFTWARE": "1",
    "WEBKIT_DISABLE_COMPOSITING_MODE": "1",
    "WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS": "1",
    "GTK_A11Y": "none",
    "NO_AT_BRIDGE": "1",
}.items():
    os.environ.setdefault(_name, _value)


# No session bus in tests: applications register locally, so several can be created one after another in one process.
os.environ["DBUS_SESSION_BUS_ADDRESS"] = "disabled:"


def _gtk_problem() -> str | None:
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Gtk
    except (ImportError, ValueError) as problem:
        return f"GTK 4 and libadwaita are not available for this Python ({problem})"
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return "no display (run the tests with xvfb-run -a)"
    if not Gtk.init_check():
        return "GTK cannot open the display"
    return None


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    problem = None
    for item in items:
        if "gtk" in item.keywords:
            problem = problem or _gtk_problem() or ""
            if problem:
                item.add_marker(pytest.mark.skip(reason=problem))
