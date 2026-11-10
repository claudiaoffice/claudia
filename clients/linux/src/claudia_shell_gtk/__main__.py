"""Command line entry points: ``claudia-composes``, ``claudia-computes`` and ``claudia-creates`` each start the Linux
client of that app (``cli`` has the arguments); ``python3 -m claudia_shell_gtk APP`` does it without installing."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Sequence

from . import cli, identity
from .i18n import detect_system_locale, install_translation
from .settings import load_shell_locale

INSTALL_HINT = (
    "Claudia's Linux client needs GTK 4, libadwaita 1.5 or newer and WebKitGTK 6.0 with their Python bindings, "
    "installed by your distribution:\n"
    "  Debian/Ubuntu: sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0\n"
    "  Fedora:        sudo dnf install python3-gobject gtk4 libadwaita webkitgtk6.0\n"
    "Run it with the system Python (/usr/bin/python3), not one from a virtual environment without system packages."
)


def _resolve_locale() -> str:
    """The persisted Config ▸ App Language choice (``settings.load_shell_locale``), if there is one yet, else this
    computer's own locale (``i18n.detect_system_locale``). The one place this is decided: both the native chrome,
    translated below, and the page (via ``ClaudiaApp``'s ``locale``, forwarded into the ``welcome`` message) are
    handed this same value, so they never disagree with each other."""
    return load_shell_locale() or detect_system_locale()


def run(app: str, argv: Sequence[str] | None = None) -> int:
    """Start the app ``app`` with the command line ``argv`` (default ``sys.argv[1:]``); returns the exit code."""
    options = cli.parse(app, sys.argv[1:] if argv is None else argv)
    logging.basicConfig(
        level=logging.DEBUG if options.debug else logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    if options.debug:
        os.environ["CLAUDIA_DEBUG"] = "1"
    # Resolved and installed *before* `.window` is ever imported (by `.app`, just below): the layout of the window is
    # read once, at that import's class-definition time (`window.py`'s `_layout` docstring), so a translation
    # installed any later would simply be too late for it -- which is also why a language picked from the Config ▸ App
    # Language menu only reaches the native chrome on the *next* launch, not this one.
    locale = _resolve_locale()
    install_translation(locale)
    try:
        from .app import ClaudiaApp
        from .webpage import WebPage  # noqa: F401  (fail here, with a hint, instead of when the first page is made)
    except (ImportError, ValueError) as problem:
        print(f"{problem}\n\n{INSTALL_HINT}", file=sys.stderr)
        return 1
    application = ClaudiaApp(identity.get(app), server=options.server, locale=locale)
    return int(application.run([sys.argv[0], *options.rest]))


def composes() -> int:
    """``claudia-composes``."""
    return run("composes")


def computes() -> int:
    """``claudia-computes``."""
    return run("computes")


def creates() -> int:
    """``claudia-creates``."""
    return run("creates")


def main() -> int:
    """``python3 -m claudia_shell_gtk APP [options]``."""
    app, rest = cli.split_module_arguments(sys.argv[1:])
    return run(app, rest)


if __name__ == "__main__":
    sys.exit(main())
