"""The web page of a Claudia shell: a WebKit web view that shows the frontend of one Claudia server and nothing else.

Six jobs, each one a rule of the shell:

* the page speaks the shell contract itself (D121, ``web/app/lib/shell-bridge.ts``) through one named script message
  handler, registered in the view's main world — the page's own compiled JavaScript posts to it directly, so there is
  no separate adapter script or isolated world to inject any more (that was ``data/shim.js``, retired with D121: it
  scraped the DOM of a web app that did not yet know about the shell; the web app now does);
* the view never leaves its origin: links to other sites open in the person's browser (web and mail only), everything
  else is dropped (``urls``). The window moves it to another server only by an explicit :meth:`WebPage.navigate`
  (the person asked to connect, ``connector``), never by a link or a redirect;
* a server whose certificate no authority vouches for loads only when it is the very certificate that the person
  trusted for that address (``trust.may_override``); any other certificate problem is a failed load;
* files the page downloads go to the Downloads folder, under a name the page cannot use to escape it, and never
  overwrite another file;
* a page is never taken from the HTTP cache of an earlier visit (D248): WebKit keeps that cache on disk between runs and
  decides for itself how long a page without ``Cache-Control`` stays fresh, so after a server was updated a window could
  keep showing the previous web app (old menus, no shell contract) — a shell shows what the server serves *now*;
* the page is not asked for permissions (camera, location, notifications): all requests are denied, and the browser
  features that contact other hosts by themselves (DNS prefetching, WebRTC, media streams) are off.

This is the only module that imports WebKit.
"""

from __future__ import annotations

import json
import logging
import os
import warnings
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

from ._gi import Gio, GLib, Gtk
from .trust import may_override
from .urls import external_target, is_internal, origin_of, safe_download_name, unique_path

import gi  # isort: skip

gi.require_version("WebKit", "6.0")
from gi.repository import WebKit  # noqa: E402

__all__ = ["WebPage"]

log = logging.getLogger(__name__)

HANDLER = "claudia"


class WebPage:
    """One web view for the server at ``origin``. See ``window.Page`` for the interface the window uses."""

    def __init__(
        self,
        *,
        origin: str,
        downloads_dir: Path,
        on_message: Callable[[str], None],
        on_reset: Callable[[], None],
        on_problem: Callable[[str, str], None],
        on_download: Callable[[Path], None],
        open_external: Callable[[str], None] | None = None,
        pinned: Callable[[str], str | None] = lambda _origin: None,
    ) -> None:
        self._origin = origin.rstrip("/")
        self._downloads_dir = downloads_dir
        self._on_message = on_message
        self._on_reset = on_reset
        self._on_problem = on_problem
        self._on_download = on_download
        self._open_external = open_external or self._launch_default_application
        self._pinned = pinned
        self._loads = 0  # which load is the newest: a load waits for the cache to be emptied and may be overtaken
        self._closed = False

        # D121: the web app speaks the shell contract itself now (`shell-bridge.ts`) — it calls
        # `window.webkit.messageHandlers.claudia.postMessage(...)` and reads `window.__claudiaShell` from its own,
        # main-world script. No adapter is injected any more, so the handler is registered in the main world (world
        # name ``None``), not a separate isolated one: a handler registered in an isolated world is invisible to the
        # page's own main-world code, which is exactly where the compiled web app runs.
        manager = WebKit.UserContentManager()
        manager.register_script_message_handler(HANDLER, None)
        manager.connect(f"script-message-received::{HANDLER}", self._message_received)

        settings = WebKit.Settings()
        settings.set_enable_developer_extras(bool(os.environ.get("CLAUDIA_DEBUG")))
        settings.set_enable_write_console_messages_to_stdout(bool(os.environ.get("CLAUDIA_DEBUG")))
        settings.set_javascript_can_open_windows_automatically(False)
        settings.set_allow_file_access_from_file_urls(False)
        settings.set_allow_universal_access_from_file_urls(False)
        # Nothing may contact another host before the person has chosen to follow a link, and an office suite has no
        # use for the browser features that do: DNS look-ups for the links of a text, WebRTC, camera and microphone.
        # (Hyperlink auditing, <a ping>, cannot be switched off in this WebKit: the setting is fixed.)
        with warnings.catch_warnings():  # deprecated in newer WebKitGTK, still needed where it is on by default
            warnings.simplefilter("ignore", DeprecationWarning)
            settings.set_enable_dns_prefetching(False)
        settings.set_enable_webrtc(False)
        settings.set_enable_media_stream(False)

        self._view = WebKit.WebView(user_content_manager=manager, settings=settings)
        self._view.set_hexpand(True)
        self._view.set_vexpand(True)
        self._view.connect("decide-policy", self._decide_policy)
        self._view.connect("permission-request", self._deny_permission)
        self._view.connect("load-changed", self._load_changed)
        self._view.connect("load-failed-with-tls-errors", self._load_failed_with_tls_errors)
        self._view.connect("load-failed", self._load_failed)
        self._view.connect("web-process-terminated", self._process_terminated)
        # The network session is shared by all web views of the process: handle only this page's downloads, and let go
        # of the session when the page is closed.
        self._session = self._view.get_network_session()
        self._download_handler = self._session.connect("download-started", self._download_started)

    # ------------------------------------------------------------------------------------ what the window uses

    @property
    def widget(self) -> Gtk.Widget:
        return self._view

    def load(self, url: str) -> None:
        self._load_current(url)

    def navigate(self, origin: str) -> None:
        """Show the frontend of the server at ``origin`` instead of the current one. From this moment only that
        origin is internal: messages of the page that was shown before are no longer accepted."""
        self._origin = origin.rstrip("/")
        self._load_current(self._origin + "/")

    def _load_current(self, url: str) -> None:
        """Load ``url`` after the cached copies of earlier pages are gone. If emptying the cache fails the page is
        loaded anyway (an old page is worse than none only when we knew about it); a newer call overtakes this one."""
        self._loads += 1
        this_load = self._loads
        types = WebKit.WebsiteDataTypes.DISK_CACHE | WebKit.WebsiteDataTypes.MEMORY_CACHE

        def emptied(manager: WebKit.WebsiteDataManager, result: Gio.AsyncResult) -> None:
            try:
                manager.clear_finish(result)
            except GLib.Error as problem:
                log.warning("could not empty the page cache: %s", problem.message)
            if not self._closed and this_load == self._loads:
                self._view.load_uri(url)

        self._session.get_website_data_manager().clear(types, 0, None, emptied)

    def send(self, raw: str) -> None:
        """Hand a shell-contract message to the page, which sets ``window.__claudiaShell`` itself (D121)."""
        script = f"window.__claudiaShell && window.__claudiaShell.receive({json.dumps(raw)})"
        self._view.evaluate_javascript(script, -1, None, None, None, None)

    def run_editing_command(self, command: str) -> None:
        self._view.execute_editing_command(command)

    def close(self) -> None:
        """Let go of the shared network session. Call when the window that shows the page is destroyed."""
        self._closed = True
        if self._download_handler:
            self._session.disconnect(self._download_handler)
            self._download_handler = 0

    # ------------------------------------------------------------------------------------------------ signals

    def _message_received(self, _manager: WebKit.UserContentManager, value: object) -> None:
        if not is_internal(self._view.get_uri() or "", self._origin):
            log.warning("ignored a message from %s", self._view.get_uri())
            return
        self._on_message(value.to_string())  # type: ignore[attr-defined]

    def _decide_policy(
        self, _view: WebKit.WebView, decision: WebKit.PolicyDecision, kind: WebKit.PolicyDecisionType
    ) -> bool:
        if kind not in (WebKit.PolicyDecisionType.NAVIGATION_ACTION, WebKit.PolicyDecisionType.NEW_WINDOW_ACTION):
            return False  # responses and the rest: WebKit's default
        uri = decision.get_navigation_action().get_request().get_uri() or ""
        if is_internal(uri, self._origin):
            if kind is WebKit.PolicyDecisionType.NEW_WINDOW_ACTION:  # a page of ours that wants a window: use this one
                decision.ignore()
                self._view.load_uri(uri)
                return True
            return False
        target = external_target(uri)
        if target is not None:
            self._open_external(target)
        else:
            log.warning("refused to open %s", uri[:80])
        decision.ignore()
        return True

    @staticmethod
    def _deny_permission(_view: WebKit.WebView, request: WebKit.PermissionRequest) -> bool:
        request.deny()
        return True

    def _load_changed(self, _view: WebKit.WebView, event: WebKit.LoadEvent) -> None:
        if event == WebKit.LoadEvent.STARTED:
            self._on_reset()

    def _load_failed_with_tls_errors(
        self, view: WebKit.WebView, uri: str, certificate: Gio.TlsCertificate, errors: Gio.TlsCertificateFlags
    ) -> bool:
        """The system does not vouch for the certificate: go on only for the one that the person trusted (the
        connection check of ``connection.check`` looked at the same server a moment ago). ``False`` hands the load
        on to :meth:`_load_failed`, which reports it."""
        origin = origin_of(uri)
        if origin is None or not is_internal(uri, self._origin):
            return False
        der = bytes(certificate.get_property("certificate") or b"")
        if not may_override(der, self._pinned(origin), int(errors)):
            return False
        self._session.allow_tls_certificate_for_host(certificate, urlsplit(uri).hostname or "")
        view.load_uri(uri)
        return True

    def _load_failed(self, _view: WebKit.WebView, _event: WebKit.LoadEvent, uri: str, error: GLib.Error) -> bool:
        self._on_problem("The page could not be loaded", f"{uri}\n{error.message}")
        return True

    def _process_terminated(self, _view: WebKit.WebView, reason: WebKit.WebProcessTerminationReason) -> None:
        self._on_problem(
            "The page stopped working", f"The web process ended ({reason.value_nick}). Start Claudia again."
        )

    def _download_started(self, _session: WebKit.NetworkSession, download: WebKit.Download) -> None:
        if download.get_web_view() is not self._view:
            return
        chosen: list[Path] = []

        def decide(_download: WebKit.Download, suggested: str) -> bool:
            self._downloads_dir.mkdir(parents=True, exist_ok=True)
            path = unique_path(self._downloads_dir, safe_download_name(suggested))
            chosen.append(path)
            download.set_destination(str(path))
            return True

        download.connect("decide-destination", decide)
        download.connect("finished", lambda _d: chosen and self._on_download(chosen[0]))
        download.connect("failed", lambda _d, error: self._on_problem("The download failed", error.message))

    @staticmethod
    def _launch_default_application(uri: str) -> None:
        Gio.AppInfo.launch_default_for_uri_async(uri, None, None, None)
