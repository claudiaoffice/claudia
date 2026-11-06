"""The application of a Claudia shell: window, local server and the way they start and stop together.

The window appears at once with a "starting" page; the server is started without waiting for it, and the main loop asks
now and then whether it answers (a window must never block, E0.2). When the application ends the server is stopped.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from importlib import resources
from pathlib import Path
from typing import Any, Protocol

from ._gi import Adw, Gdk, Gio, GLib, Gtk
from .identity import AppIdentity
from .launch import SetupProblem, prepare_server
from .manifest import Manifest, composes
from .server import ServerStartError
from .window import ComposesWindow, PageFactory

__all__ = ["ComposesApp"]

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


class ComposesApp(Adw.Application):
    """claudia composes for the Linux desktop."""

    def __init__(
        self,
        identity: AppIdentity,
        *,
        server_factory: Callable[[AppIdentity], Server] = prepare_server,
        page_factory: PageFactory = default_page_factory,
        manifest: Manifest | None = None,
        poll_ms: int = POLL_MS,
        flags: Gio.ApplicationFlags = Gio.ApplicationFlags.DEFAULT_FLAGS,
    ) -> None:
        super().__init__(application_id=identity.application_id, flags=flags)
        self._identity = identity
        self._server_factory = server_factory
        self._page_factory = page_factory
        self._manifest = manifest or composes()
        self._poll_ms = poll_ms
        self._server: Server | None = None
        self._poll_source = 0
        self.window: ComposesWindow | None = None

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
        for action in self._manifest.actions:
            if action.accelerators:
                self.set_accels_for_action(f"win.{action.id}", list(action.accelerators))

    def do_activate(self) -> None:
        if self.window is not None:
            self.window.present()
            return
        self.window = ComposesWindow(self._identity, self._manifest, page_factory=self._page_factory, application=self)
        self.window.present()
        try:
            self._server = self._server_factory(self._identity)
            self._server.spawn()
        except SetupProblem as problem:
            self.window.show_error("Claudia Composes cannot start yet", str(problem))
            return
        except OSError as problem:
            self.window.show_error("Claudia Composes could not start its server", str(problem))
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
            window.show_error("Claudia Composes could not start its server", str(problem))
            return False
        self._poll_source = 0  # the source ends itself by returning False
        window.show_page(server.url)
        return False

    def _stop_server(self) -> None:
        if self._poll_source:
            GLib.source_remove(self._poll_source)
            self._poll_source = 0
        if self._server is not None:
            self._server.stop()
            self._server = None
