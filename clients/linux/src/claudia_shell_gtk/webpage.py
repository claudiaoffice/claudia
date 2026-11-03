"""The web page of a Claudia shell: a WebKit web view that shows the local server's frontend and nothing else.

Four jobs, each one a rule of the shell:

* the page adapter (``data/shim.js``) runs in its own script world and only on pages of the server's own origin
  (WebKit admits the host, the adapter checks the port), and its messages reach the shell through one named handler;
* the view never leaves its origin: links to other sites open in the person's browser (web and mail only), everything
  else is dropped (``urls``);
* files the page downloads go to the Downloads folder, under a name the page cannot use to escape it, and never
  overwrite another file;
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
from .urls import external_target, is_internal, safe_download_name, unique_path

import gi  # isort: skip

gi.require_version("WebKit", "6.0")
from gi.repository import WebKit  # noqa: E402

__all__ = ["WebPage"]

log = logging.getLogger(__name__)

WORLD = "claudia-shell"
HANDLER = "claudia"


class WebPage:
    """One web view for the server at ``origin``. See ``window.Page`` for the interface the window uses."""

    def __init__(
        self,
        *,
        origin: str,
        shim: str,
        routes: str,
        downloads_dir: Path,
        on_message: Callable[[str], None],
        on_reset: Callable[[], None],
        on_problem: Callable[[str, str], None],
        on_download: Callable[[Path], None],
        open_external: Callable[[str], None] | None = None,
    ) -> None:
        self._origin = origin.rstrip("/")
        self._downloads_dir = downloads_dir
        self._on_message = on_message
        self._on_reset = on_reset
        self._on_problem = on_problem
        self._on_download = on_download
        self._open_external = open_external or self._launch_default_application

        manager = WebKit.UserContentManager()
        manager.register_script_message_handler(HANDLER, WORLD)
        manager.connect(f"script-message-received::{HANDLER}", self._message_received)
        config = json.dumps({"app": "composes", "origin": self._origin, "routes": json.loads(routes)})
        parts = urlsplit(self._origin)
        manager.add_script(
            WebKit.UserScript.new_for_world(
                f"{shim}\n({config});\n",
                WebKit.UserContentInjectedFrames.TOP_FRAME,
                WebKit.UserScriptInjectionTime.END,
                WORLD,
                # WebKit's URL patterns cannot name a port: this admits the host, the adapter checks the origin
                [f"{parts.scheme}://{parts.hostname}/*"],
                None,
            )
        )

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
        self._view.load_uri(url)

    def send(self, raw: str) -> None:
        """Hand a shell-contract message to the page adapter."""
        script = f"window.__claudiaShell && window.__claudiaShell.receive({json.dumps(raw)})"
        self._view.evaluate_javascript(script, -1, WORLD, None, None, None)

    def run_editing_command(self, command: str) -> None:
        self._view.execute_editing_command(command)

    def close(self) -> None:
        """Let go of the shared network session. Call when the window that shows the page is destroyed."""
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
