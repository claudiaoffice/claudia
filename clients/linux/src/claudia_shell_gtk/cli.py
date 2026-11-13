"""The command line of the Linux client (E5.8): ``claudia-composes``, ``claudia-computes``, ``claudia-creates``. No GTK.

Every command is the same program for another app::

    claudia-computes                       # starts this app's own server on this computer, shows its start page
    claudia-computes --server HOST[:PORT]  # no local server: connects to that one (https; http only for this computer)
    python3 -m claudia_shell_gtk computes  # the same, for a checkout that has not been installed

There is no command that asks which app to open: a window is one app, which is also why a window connects only to
servers of its own app (``connection``). Arguments that are not ours (GTK's own, ``--gapplication-service``…) are
handed on untouched.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field

from . import identity
from ._version import __version__
from .servers import Address, AddressRefused, parse_address

__all__ = ["Options", "parse", "split_module_arguments"]


@dataclass(frozen=True, slots=True)
class Options:
    """What the command line asked for."""

    app: str
    server: Address | None
    """The server to connect to instead of starting one, or ``None`` to start the app's own."""
    debug: bool
    rest: list[str] = field(default_factory=list)
    """Everything else, for GTK."""


def _address(text: str) -> Address:
    try:
        return parse_address(text)
    except AddressRefused as refused:
        raise argparse.ArgumentTypeError(str(refused)) from refused


def parse(app: str, argv: Sequence[str]) -> Options:
    """The options for ``app`` from ``argv`` (without the program name). Exits with a message for ``--help``,
    ``--version`` and a bad ``--server``; raises ``identity.UnknownApp`` for an app that does not exist."""
    who = identity.get(app)
    parser = argparse.ArgumentParser(
        prog=who.command,
        description=f"{who.title} for the Linux desktop",
        epilog="Other arguments are handed to GTK.",
    )
    parser.add_argument("--version", action="version", version=f"{who.command} {__version__}")
    parser.add_argument("--debug", action="store_true", help="log more and enable the web inspector")
    parser.add_argument(
        "--server",
        metavar="URL",
        type=_address,
        help="connect to this server instead of starting one on this computer "
        "(https://host[:port]; plain http is only accepted for this computer)",
    )
    args, rest = parser.parse_known_args(list(argv))
    return Options(app=app, server=args.server, debug=args.debug, rest=rest)


def split_module_arguments(argv: Sequence[str]) -> tuple[str, list[str]]:
    """``python3 -m claudia_shell_gtk APP …``: the app and the arguments after it. Without an app it is an error —
    this client has no picker."""
    if not argv or argv[0].startswith("-"):
        names = ", ".join(identity.names())
        print(
            f"usage: python3 -m claudia_shell_gtk {{{'|'.join(identity.names())}}} [options]\n"
            f"error: say which app to start: {names}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return argv[0], list(argv[1:])
