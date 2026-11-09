"""The application: it starts the server without blocking the window, shows the page when the server answers, says
what went wrong when it cannot, and never leaves the server running. Fakes stand in for the server and for WebKit."""

from __future__ import annotations

import pytest
from support import pump

from claudia_shell_gtk import identity, launch
from claudia_shell_gtk.server import ServerStartError

pytestmark = pytest.mark.gtk


class FakeServer:
    url = "http://127.0.0.1:41233"

    def __init__(self, answers=(False, False, True), error: Exception | None = None):
        self.answers = list(answers)
        self.error = error
        self.spawned = 0
        self.stopped = 0

    def spawn(self) -> None:
        self.spawned += 1

    def check_ready(self) -> bool:
        if self.error:
            raise self.error
        return self.answers.pop(0) if self.answers else True

    def stop(self) -> None:
        self.stopped += 1


class FakePage:
    def __init__(self, **callbacks):
        self.callbacks = callbacks
        self.loaded: list[str] = []
        from claudia_shell_gtk._gi import Gtk

        self.widget = Gtk.Label(label="page")

    def send(self, raw: str) -> None: ...

    def load(self, url: str) -> None:
        self.loaded.append(url)

    def run_editing_command(self, command: str) -> None: ...

    def close(self) -> None: ...


def make_app(server_factory, pages: list | None = None, locale: str | None = None):
    from claudia_shell_gtk._gi import Adw, Gio
    from claudia_shell_gtk.app import ComposesApp

    Adw.init()

    def page_factory(**callbacks):
        page = FakePage(**callbacks)
        if pages is not None:
            pages.append(page)
        return page

    return ComposesApp(
        identity.get("composes"),
        server_factory=server_factory,
        page_factory=page_factory,
        locale=locale,
        poll_ms=10,
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )


def test_the_window_appears_at_once_and_shows_the_page_when_the_server_answers() -> None:
    server = FakeServer()
    pages: list[FakePage] = []
    app = make_app(lambda _identity: server, pages)
    app.register(None)
    app.activate()
    window = app.window
    assert window.visible_page == "starting"  # the server has not answered yet
    pump(lambda: window.visible_page == "web")
    assert server.spawned == 1
    assert pages[0].loaded == [server.url]
    app.shutdown_for_test()


def test_missing_setup_is_shown_in_the_window_and_no_server_is_started() -> None:
    def refuse(_identity):
        raise launch.SetupProblem("The web frontend has not been built.")

    app = make_app(refuse)
    app.register(None)
    app.activate()
    assert app.window.visible_page == "error"
    assert "has not been built" in app.window.error_details
    app.shutdown_for_test()


def test_a_server_that_does_not_start_is_reported_with_what_it_said() -> None:
    server = FakeServer(error=ServerStartError("the server stopped at start-up (exit code 1)\n--- boom"))
    app = make_app(lambda _identity: server)
    app.register(None)
    app.activate()
    pump(lambda: app.window.visible_page == "error")
    assert "boom" in app.window.error_details
    app.shutdown_for_test()


def test_the_server_is_stopped_when_the_application_ends() -> None:
    from claudia_shell_gtk._gi import GLib

    server = FakeServer()
    app = make_app(lambda _identity: server)
    GLib.timeout_add(200, app.quit)
    assert app.run([]) == 0
    assert server.stopped == 1


def test_a_second_activation_shows_the_same_window_and_starts_no_second_server() -> None:
    server = FakeServer()
    app = make_app(lambda _identity: server)
    app.register(None)
    app.activate()
    first = app.window
    app.activate()
    assert app.window is first
    assert server.spawned == 1
    app.shutdown_for_test()


def test_an_explicit_locale_is_handed_to_the_window_instead_of_the_detected_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E5.7's second round: `__main__.py` resolves a persisted-or-detected locale once, before the window (and this
    app) exist at all, and hands it in here (`do_activate`) -- the app must not go back to the system's own guess
    on top of an already-decided one."""
    import claudia_shell_gtk.app as app_module

    monkeypatch.setattr(app_module, "detect_system_locale", lambda: pytest.fail("should not be called"))
    app = make_app(lambda _identity: FakeServer(), locale="de")
    app.register(None)
    app.activate()
    assert app.window._bridge._locale == "de"  # noqa: SLF001
    app.shutdown_for_test()


def test_with_no_explicit_locale_the_window_falls_back_to_the_detected_one() -> None:
    app = make_app(lambda _identity: FakeServer())
    app.register(None)
    app.activate()
    assert app.window._bridge._locale  # noqa: SLF001 -- whatever detect_system_locale() found, just not empty/None
    app.shutdown_for_test()


def test_the_accelerators_come_from_the_manifest() -> None:
    app = make_app(lambda _identity: FakeServer())
    app.register(None)
    from claudia_shell_gtk._gi import Gtk

    def keys(action: str) -> list:
        return [Gtk.accelerator_parse(accel) for accel in app.get_accels_for_action(action)]

    assert keys("win.file.open") == [Gtk.accelerator_parse("<Primary>o")]
    assert keys("win.file.quit") == [Gtk.accelerator_parse("<Primary>q")]
    assert app.get_accels_for_action("win.file.save") == []  # the page handles Ctrl+S itself
    app.shutdown_for_test()
