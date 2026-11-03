"""Command line entry points: ``claudia-composes`` starts the Linux client of claudia composes."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Sequence

from ._version import __version__

INSTALL_HINT = (
    "Claudia's Linux client needs GTK 4, libadwaita 1.5 or newer and WebKitGTK 6.0 with their Python bindings, "
    "installed by your distribution:\n"
    "  Debian/Ubuntu: sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0\n"
    "  Fedora:        sudo dnf install python3-gobject gtk4 libadwaita webkitgtk6.0\n"
    "Run it with the system Python (/usr/bin/python3), not one from a virtual environment without system packages."
)


def composes(argv: Sequence[str] | None = None) -> int:
    """Start claudia composes. Returns the exit code."""
    parser = argparse.ArgumentParser(prog="claudia-composes", description="Claudia Composes for the Linux desktop")
    parser.add_argument("--version", action="version", version=f"claudia-composes {__version__}")
    parser.add_argument("--debug", action="store_true", help="log more and enable the web inspector")
    args, rest = parser.parse_known_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    if args.debug:
        os.environ["CLAUDIA_DEBUG"] = "1"
    try:
        from .app import ComposesApp
        from .identity import get
        from .webpage import WebPage  # noqa: F401  (fail here, with a hint, instead of when the first page is made)
    except (ImportError, ValueError) as problem:
        print(f"{problem}\n\n{INSTALL_HINT}", file=sys.stderr)
        return 1
    return int(ComposesApp(get("composes")).run([sys.argv[0], *rest]))


if __name__ == "__main__":
    sys.exit(composes())
