"""The application of a Claudia shell: window, local server and the way they start and stop together.

One class serves every app (``identity.AppIdentity`` says which). There are two ways to start:

* **its own server** (the default): the window appears at once with a "starting" page; the server is started without
  waiting for it, and the main loop asks now and then whether it answers (a window must never block, E0.2). When the
  application ends the server is stopped;
* **a given server** (``--server URL``): no server is started. The window connects to it like it does when the person
  types the address into the page, with the same checks — https, the right app, a certificate someone vouches for —
  and the address is remembered in the server list of this app.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from importlib import resources
from pathlib import Path
from typing import Any, Protocol

from ._gi import Adw, Gdk, Gio, GLib, Gtk
from .i18n import detect_system_locale
from .i18n import translate as _
from .identity import AppIdentity
from .launch import SetupProblem, prepare_server
from .manifest import KeyOwner, Manifest, for_app
from .server import ServerStartError
from .servers import Address
from .window import ClaudiaWindow, PageFactory

__all__ = ["ClaudiaApp"]

log = logging.getLogger(__name__)

POLL_MS = 100


class Server(Protocol):
    """What the application needs from a local server (see ``server.LocalServer``)."""

    url: str

    def spawn(self) -> None: ...
    def check_ready(self) -> bool: ...
    def stop(self) -> None: ...


def downloads_dir() -> Path:
    """Where files that the page downloads are saved: the person's Downloads folder."""
    found = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
    return Path(found) if found else Path.home() / "Downloads"


def default_page_factory(**callbacks: Any) -> Any:
    """The real web page (WebKit is imported only now, so everything else works and is tested without it).

    No app name is passed through: the page itself is app-agnostic (D121, ``webpage.WebPage``) — which app it shows
    is something the web app's own ``hello`` message states, and ``Bridge._hello`` checks that against the window's
    own manifest, not against anything the shell handed the page up front.
    """
    from .webpage import WebPage

    return WebPage(downloads_dir=downloads_dir(), **callbacks)


class ClaudiaApp(Adw.Application):
    """One Claudia app for the Linux desktop."""

    def __init__(
        self,
        identity: AppIdentity,
        *,
        server_factory: Callable[[AppIdentity], Server] = prepare_server,
        page_factory: PageFactory = default_page_factory,
        manifest: Manifest | None = None,
        server: Address | None = None,
        locale: str | None = None,
        poll_ms: int = POLL_MS,
        flags: Gio.ApplicationFlags = Gio.ApplicationFlags.DEFAULT_FLAGS,
    ) -> None:
        super().__init__(application_id=identity.application_id, flags=flags)
        self._identity = identity
        self._server_factory = server_factory
        self._page_factory = page_factory
        self._manifest = manifest or for_app(identity.name)
        self._given_server = server
        self._locale = locale
        self._poll_ms = poll_ms
        self._server: Server | None = None
        self._poll_source = 0
        self.window: ClaudiaWindow | None = None

    # ------------------------------------------------------------------------------------------------ life cycle

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        Gtk.IconTheme.get_for_display(Gdk.Display.get_default()).add_search_path(str(self._identity.icon_search_path))
        provider = Gtk.CssProvider()
        css = resources.files("claudia_shell_gtk").joinpath("data/style.css").read_text(encoding="utf-8")
        provider.load_from_string(css)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        # Only the keys the shell itself listens for are bound natively; every other key belongs to the page (and to
        # the browser or the document view), and the menu only shows it (``manifest.menu_xml``'s ``accel``, UX-35).
        for action in self._manifest.actions:
            if action.accelerators and action.key_owner is KeyOwner.SHELL:
                self.set_accels_for_action(f"win.{action.id}", list(action.accelerators))

    def do_activate(self) -> None:
        if self.window is not None:
            self.window.present()
            return
        self.window = ClaudiaWindow(
            self._identity,
            self._manifest,
            page_factory=self._page_factory,
            locale=self._locale or detect_system_locale(),
            application=self,
        )
        self.window.present()
        if self._given_server is not None:
            self.window.connect_to(self._given_server.origin)
            return
        try:
            self._server = self._server_factory(self._identity)
            self._server.spawn()
        except SetupProblem as problem:
            self.window.show_error(_("{app} cannot start yet").format(app=self._identity.title), str(problem))
            return
        except OSError as problem:
            self.window.show_error(_("{app} could not start its server").format(app=self._identity.title), str(problem))
            return
        self._poll_source = GLib.timeout_add(self._poll_ms, self._poll_server)

    def do_shutdown(self) -> None:
        if self.window is not None:
            self.window.release_page()
        self._stop_server()
        Adw.Application.do_shutdown(self)

    def shutdown_for_test(self) -> None:
        """Stop what the application started, for tests that drive it without ``run()``."""
        self._stop_server()
        if self.window is not None:
            self.window.release_page()
            self.window.destroy()
            self.window = None

    # ---------------------------------------------------------------------------------------------------- server

    def _poll_server(self) -> bool:
        """Called by the main loop until the server answers or fails. ``True`` means: ask again."""
        server, window = self._server, self.window
        if server is None or window is None:
            self._poll_source = 0
            return False
        try:
            if not server.check_ready():
                return True
        except ServerStartError as problem:
            self._poll_source = 0
            window.show_error(_("{app} could not start its server").format(app=self._identity.title), str(problem))
            return False
        self._poll_source = 0  # the source ends itself by returning False
        window.book.local_origin = server.url  # "This computer" in the page's list, from now on
        window.show_page(server.url)
        return False

    def _stop_server(self) -> None:
        if self._poll_source:
            GLib.source_remove(self._poll_source)
            self._poll_source = 0
        if self._server is not None:
            self._server.stop()
            self._server = None
