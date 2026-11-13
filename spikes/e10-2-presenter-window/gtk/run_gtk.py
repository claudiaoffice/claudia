#!/usr/bin/env python3
"""E10.2 spike on Linux: the probe page in a WebKitGTK view set up like the Claudia GTK shell, or with the changes a
presenter mode would need. Needs python3-gi, GTK 4 and WebKitGTK 6 (what the Claudia GTK client already needs).

    python3 gtk/run_gtk.py today       # the shell's settings as now (webpage.py): new windows load in this one
    python3 gtk/run_gtk.py candidate   # windows may open (create); the window honours WebKit's fullscreen request

Both start the spike's static server on 127.0.0.1:8777 and load /index.html (or /frame.html with --frame).
Not tested by the author: written without a Linux desktop at hand. If it fails to start, the traceback is the finding.
"""

import argparse
import functools
import http.server
import pathlib
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gtk, WebKit  # noqa: E402

PAGE = pathlib.Path(__file__).resolve().parent.parent / "page"
PORT = 8777


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):  # quiet
        pass


def serve() -> None:
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), functools.partial(_Quiet, directory=str(PAGE)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()


def make_view(mode: str, related: WebKit.WebView | None = None) -> tuple[Gtk.Window, WebKit.WebView]:
    settings = WebKit.Settings()
    # As clients/linux/src/claudia_shell_gtk/webpage.py has it today:
    settings.set_javascript_can_open_windows_automatically(mode == "candidate")
    settings.set_enable_developer_extras(True)
    settings.set_enable_fullscreen(True)  # WebKit's default; written down because the question is about it
    view = WebKit.WebView(settings=settings, related_view=related) if related else WebKit.WebView(settings=settings)
    win = Gtk.Window(title="E10.2 spike · " + mode)
    win.set_default_size(1100, 820)
    win.set_child(view)

    def on_decide(_v, decision, kind):
        if kind == WebKit.PolicyDecisionType.NEW_WINDOW_ACTION and mode == "today":
            uri = decision.get_navigation_action().get_request().get_uri()
            decision.ignore()
            view.load_uri(uri)  # webpage.py: "a page of ours that wants a window: use this one"
            print("today: NEW_WINDOW_ACTION loaded in the same view:", uri)
            return True
        return False

    view.connect("decide-policy", on_decide)
    if mode == "candidate":

        def on_create(_v, _action):
            new_win, new_view = make_view(mode, related=view)
            new_win.present()
            print("candidate: opened a window")
            return new_view

        view.connect("create", on_create)
        view.connect("close", lambda _v: win.close())

        def enter(_v):
            win.fullscreen()
            print("candidate: entered fullscreen")
            return True

        def leave(_v):
            win.unfullscreen()
            return True

        view.connect("enter-fullscreen", enter)
        view.connect("leave-fullscreen", leave)
    return win, view


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["today", "candidate"])
    ap.add_argument("--frame", action="store_true", help="load frame.html (the web app in a frame)")
    ap.add_argument("--allow-fullscreen", action="store_true", help="with --frame: allow=fullscreen on the frame")
    a = ap.parse_args()
    serve()
    print("WebKitGTK", WebKit.get_major_version(), WebKit.get_minor_version(), WebKit.get_micro_version())
    app = Gtk.Application(application_id="org.claudia.PresenterSpike")

    def on_activate(app_):
        win, view = make_view(a.mode)
        win.set_application(app_)
        path = "frame.html?allow=" + ("fullscreen" if a.allow_fullscreen else "none") if a.frame else "index.html"
        view.load_uri(f"http://127.0.0.1:{PORT}/{path}")
        win.present()

    app.connect("activate", on_activate)
    app.run(None)


if __name__ == "__main__":
    main()
