"""What a window does when a person asks it to connect to a server (E5.8). No GTK: everything GTK-specific — how
the answer reaches the main thread, how a window switches, how a person is asked — is handed in.

The page asks with the shell contract's ``connect`` message (or the person types ``--server`` on the command line);
:class:`Connector` runs the checks of ``connection`` on a worker thread (they take a moment, and a window must
never block), asks the person about a certificate when that is needed (``trust``), and in the end either **switches
the window to the server** and remembers it in the list of this app, or reports *why not* with one of the codes that
the contract's ``connect_failed`` message knows. The newest request wins: an older one that finishes later is dropped.

:class:`ServerBook` is the list of servers that this window's app remembers (``servers``, ``settings``) as the
page sees it: this computer's own server first when there is one, then the remembered ones. The page may rename or
remove entries and hands the list back; only what passes :func:`claudia_shell_gtk.servers.sanitize` is kept.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from . import settings
from .connection import NeedsTrust, Outcome, Reached, Refused
from .connection import check as default_check
from .i18n import translate as _
from .servers import Address, AddressRefused, Entry, for_page, parse_address, remember, sanitize
from .trust import TrustStore

__all__ = ["Connector", "ServerBook", "run_threaded"]

log = logging.getLogger(__name__)

T = TypeVar("T")
Work = Callable[[Callable[[], T], Callable[[T], None]], None]
"""``work(job, done)``: run ``job()`` somewhere else and call ``done(result)`` where the window lives."""


def run_threaded(deliver: Callable[[Callable[[], None]], None]) -> Work:
    """A ``Work`` that runs jobs on a daemon thread and hands each result to ``deliver`` (in a GTK window:
    ``GLib.idle_add``, wrapped so that it runs once) to be called on the main thread."""

    def work(job: Callable[[], T], done: Callable[[T], None]) -> None:
        def run() -> None:
            result = job()
            deliver(lambda: done(result))

        threading.Thread(target=run, name="claudia-connect", daemon=True).start()

    return work


class ServerBook:
    """The servers that one app remembers, and this computer's own."""

    def __init__(self, app: str, *, local_origin: str | None, local_label: str, path: Path | None = None) -> None:
        self._app = app
        self._path = path
        self._local_label = local_label
        self.local_origin = local_origin
        """The origin of the server this window started (it changes with every start), or ``None``."""

    def entries(self) -> list[Entry]:
        """The list for the page."""
        saved = settings.load_servers(self._app, self._path)
        return for_page(saved, local_origin=self.local_origin, local_label=self._local_label)

    def replace(self, raw: object) -> None:
        """Keep the list that the page handed back (what is valid of it)."""
        settings.save_servers(self._app, sanitize(raw), self._path)

    def remember(self, origin: str) -> None:
        """Add the server at ``origin`` unless it is this computer's own or already there."""
        if origin == self.local_origin:
            return
        saved = settings.load_servers(self._app, self._path)
        settings.save_servers(self._app, remember(saved, origin), self._path)


class Connector:
    """Connects a window of ``app`` to servers. See the module docstring.

    ``switch(origin)`` shows that server in the window; ``fail(code, message)`` reports a refusal to the page.
    ``ask_trust(needs, answer)``, once set, asks the person about the certificate in ``needs`` and calls
    ``answer(True)`` or ``answer(False)`` (once); without it a certificate nobody vouches for is simply refused.
    """

    def __init__(
        self,
        app: str,
        *,
        book: ServerBook,
        trust: TrustStore,
        switch: Callable[[str], None],
        fail: Callable[[str, str], None],
        work: Work,
        check: Callable[..., Outcome] = default_check,
        ask_trust: Callable[[NeedsTrust, Callable[[bool], None]], None] | None = None,
    ) -> None:
        self._app = app
        self._book = book
        self._trust = trust
        self._switch = switch
        self._fail = fail
        self._work = work
        self._check = check
        self.ask_trust = ask_trust
        self._generation = 0

    def connect(self, raw: str) -> None:
        """Connect to the server that ``raw`` (an address as a person types it) names."""
        self._generation += 1
        try:
            address = parse_address(raw)
        except AddressRefused as refused:
            self._fail(refused.code, str(refused))
            return
        self._start(address, self._generation, asked=False)

    # ------------------------------------------------------------------------------------------------ steps

    def _start(self, address: Address, generation: int, *, asked: bool) -> None:
        trusted = self._trust.snapshot()

        def job() -> Outcome:
            try:
                return self._check(address, self._app, trusted=trusted)
            except Exception:  # a bug must not leave the person waiting: say that nothing answered
                log.exception("checking %s failed", address.origin)
                return Refused("unreachable", _("Could not reach {address}.").format(address=address.host))

        self._work(job, lambda outcome: self._finished(outcome, address, generation, asked=asked))

    def _finished(self, outcome: Outcome, address: Address, generation: int, *, asked: bool) -> None:
        if generation != self._generation:
            return  # the person has asked for something else in the meantime
        if isinstance(outcome, Reached):
            self._book.remember(outcome.origin)
            self._switch(outcome.origin)
        elif isinstance(outcome, Refused):
            self._fail(outcome.code, outcome.message)
        elif asked or self.ask_trust is None:
            # Nobody can be asked (no dialog yet) or she was already asked and the server shows yet another one.
            self._fail(
                "certificate_invalid",
                _("The certificate of {host} is not issued by an authority this computer trusts.").format(
                    host=address.host
                ),
            )
        else:
            self._ask(outcome, address, generation)

    def _ask(self, needs: NeedsTrust, address: Address, generation: int) -> None:
        answered = False

        def answer(trusted: bool) -> None:
            nonlocal answered
            if answered or generation != self._generation:
                return
            answered = True
            if not trusted:
                self._fail("not_trusted", _("Not connected: you did not trust this server's certificate."))
                return
            self._trust.trust(needs.origin, needs.certificate.sha256)
            self._start(address, generation, asked=True)  # again, so that what is connected to is what was trusted

        assert self.ask_trust is not None
        self.ask_trust(needs, answer)
