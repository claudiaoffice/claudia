"""The GTK window: what it does with the manifest, the bridge and a page. A fake page stands in for WebKit."""

from __future__ import annotations

import json

import pytest

from claudia_shell_gtk import identity, manifest

pytestmark = pytest.mark.gtk


class FakePage:
    """What the window needs from a web page; remembers what the window asked of it."""

    def __init__(self, **callbacks):
        self.callbacks = callbacks
        self.sent: list[dict] = []
        self.loaded: list[str] = []
        self.navigated: list[str] = []
        self.editing: list[str] = []
        self.widget = None
        self.closed = False

    def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))

    def load(self, url: str) -> None:
        self.loaded.append(url)

    def navigate(self, origin: str) -> None:
        self.navigated.append(origin)

    def run_editing_command(self, command: str) -> None:
        self.editing.append(command)

    def close(self) -> None:
        self.closed = True

    # what the page would do:
    def says(self, message: dict) -> None:
        self.callbacks["on_message"](json.dumps(message))


@pytest.fixture
def window(tmp_path):
    from claudia_shell_gtk._gi import Adw, Gtk
    from claudia_shell_gtk.connector import ServerBook
    from claudia_shell_gtk.trust import TrustStore
    from claudia_shell_gtk.window import ClaudiaWindow

    Adw.init()
    pages: list[FakePage] = []
    checked: list[tuple[str, str]] = []
    answers: list = []

    def check(address, app, *, trusted):
        checked.append((address.origin, app))
        return answers.pop(0)

    def factory(**callbacks):
        page = FakePage(**callbacks)
        page.widget = Gtk.Label(label="page")
        pages.append(page)
        return page

    path = tmp_path / "shell.json"
    win = ClaudiaWindow(
        identity.get("composes"),
        manifest.composes(),
        page_factory=factory,
        book=ServerBook("composes", local_origin="http://127.0.0.1:1", local_label="This computer", path=path),
        trust=TrustStore(path),
        work=lambda job, done: done(job()),  # no thread: the test is the main loop
        check=check,
    )
    win.fake_pages = pages
    win.checked = checked
    win.answers = answers
    yield win
    win.destroy()


def hello():
    return {"type": "hello", "contract": 1, "app": "composes"}


def test_every_action_of_the_manifest_is_a_window_action(window) -> None:
    for action in manifest.composes().actions:
        assert window.lookup_action(action.id) is not None, action.id


def test_page_actions_are_disabled_until_the_page_has_said_hello(window) -> None:
    window.show_page("http://127.0.0.1:1")
    assert not window.lookup_action("file.save").get_enabled()
    window.fake_pages[0].says(hello())
    assert window.lookup_action("file.save").get_enabled()
    assert window.fake_pages[0].sent[0]["type"] == "welcome"


def test_the_shell_actions_work_without_a_page(window) -> None:
    assert window.lookup_action("file.quit").get_enabled()
    assert window.lookup_action("help.about").get_enabled()


def test_activating_a_menu_action_sends_it_to_the_page(window) -> None:
    window.show_page("http://127.0.0.1:1")
    page = window.fake_pages[0]
    page.says(hello())
    window.lookup_action("file.save").activate(None)
    assert page.sent[-1] == {"type": "action", "action": "file.save"}


def test_ticking_a_checkable_action_asks_the_page_for_the_new_state_and_waits_for_its_answer(window) -> None:
    window.show_page("http://127.0.0.1:1")
    page = window.fake_pages[0]
    page.says(hello())
    action = window.lookup_action("view.page")
    assert action.get_state().get_boolean() is False
    window.lookup_action("view.page").activate(None)
    assert page.sent[-1] == {"type": "action", "action": "view.page", "target": "on"}
    assert action.get_state().get_boolean() is False  # the page has not confirmed yet
    page.says({"type": "action_state", "states": {"view.page": {"enabled": True, "checked": True}}})
    assert action.get_state().get_boolean() is True
    window.lookup_action("view.page").activate(None)
    assert page.sent[-1]["target"] == "off"


def test_states_from_the_page_enable_and_disable_actions(window) -> None:
    window.show_page("http://127.0.0.1:1")
    page = window.fake_pages[0]
    page.says(hello())
    page.says({"type": "action_state", "states": {"edit.undo": {"enabled": False}}})
    assert not window.lookup_action("edit.undo").get_enabled()
    page.says({"type": "action_state", "states": {"edit.undo": {"enabled": True}}})
    assert window.lookup_action("edit.undo").get_enabled()


def test_the_pages_dark_mode_choice_is_applied_to_the_native_chrome_too(window) -> None:
    """D28/2026-11-06: the About dialog stayed whatever colour GTK's own theme was, regardless of the document's own
    Dark Mode setting — nothing synced the two. `view.dark`'s resolved `checked` state now drives libadwaita's own
    colour scheme, the same way it already drives the GTK menu's own checkmark."""
    from claudia_shell_gtk._gi import Adw

    window.show_page("http://127.0.0.1:1")
    page = window.fake_pages[0]
    page.says(hello())
    page.says({"type": "action_state", "states": {"view.dark": {"checked": True}}})
    assert Adw.StyleManager.get_default().get_color_scheme() == Adw.ColorScheme.FORCE_DARK
    page.says({"type": "action_state", "states": {"view.dark": {"checked": False}}})
    assert Adw.StyleManager.get_default().get_color_scheme() == Adw.ColorScheme.FORCE_LIGHT


def test_the_page_reporting_the_active_language_persists_it_for_the_next_launch(window, monkeypatch) -> None:
    """The owner's second i18n round: the page is the one source of truth for which of `manifest.LANGUAGES` is
    active, so `set_action_states` — already written to apply whatever the page reports — saves it for `__main__.py`
    to read back next launch. This window's own native chrome does not re-translate itself now (`window.py`'s
    `_layout` docstring); only the tick mark (already covered by `test_states_from_the_page_enable_and_disable_
    actions`'s general mechanism) and the save below happen live."""
    from claudia_shell_gtk import window as window_module

    saved: list[str] = []
    monkeypatch.setattr(window_module, "save_shell_locale", saved.append)
    window.show_page("http://127.0.0.1:1")
    page = window.fake_pages[0]
    page.says(hello())
    page.says({"type": "action_state", "states": {"config.language.de": {"checked": True}}})
    assert saved == ["de"]


def test_a_language_reported_as_unchecked_is_not_saved(window, monkeypatch) -> None:
    """Only the one the page says is now *active* is worth persisting — the sibling(s) it just unchecked are not
    "the chosen language," they are simply no longer it."""
    from claudia_shell_gtk import window as window_module

    saved: list[str] = []
    monkeypatch.setattr(window_module, "save_shell_locale", saved.append)
    window.show_page("http://127.0.0.1:1")
    page = window.fake_pages[0]
    page.says(hello())
    page.says({"type": "action_state", "states": {"config.language.en": {"checked": False}}})
    assert saved == []


def test_a_page_that_loads_again_disables_the_page_actions_until_it_says_hello_again(window) -> None:
    window.show_page("http://127.0.0.1:1")
    page = window.fake_pages[0]
    page.says(hello())
    page.callbacks["on_reset"]()
    assert not window.lookup_action("file.save").get_enabled()


def test_editing_actions_go_to_the_web_views_editing_commands(window) -> None:
    window.show_page("http://127.0.0.1:1")
    page = window.fake_pages[0]
    for name, command in {
        "edit.cut": "Cut",
        "edit.copy": "Copy",
        "edit.paste": "Paste",
        "edit.paste-as-plain": "PasteAsPlainText",
    }.items():
        window.lookup_action(name).activate(None)
        assert page.editing[-1] == command


def test_the_window_shows_the_page_only_when_asked_and_loads_it_once(window) -> None:
    assert window.visible_page == "starting"
    window.show_page("http://127.0.0.1:1")
    assert window.visible_page == "web"
    assert window.fake_pages[0].loaded == ["http://127.0.0.1:1"]
    window.show_page("http://127.0.0.1:1")
    assert len(window.fake_pages) == 1


def test_a_problem_is_shown_in_the_window_with_its_details(window) -> None:
    window.show_error("The server did not start", "line one\nline two")
    assert window.visible_page == "error"
    assert window.error_title == "The server did not start"
    assert "line two" in window.error_details


def test_a_page_that_cannot_be_loaded_is_reported_in_the_window(window) -> None:
    window.show_page("http://127.0.0.1:1")
    window.fake_pages[0].callbacks["on_problem"]("The page could not be loaded", "connection refused")
    assert window.visible_page == "error"
    assert "connection refused" in window.error_details


def _labels(box) -> list[str]:
    """The text of every `Gtk.Label`/`Gtk.Button` found by walking a box's children (depth 1, not recursive) —
    enough to read what `_show_about` put there without reaching into Adwaita's own widget internals."""
    found = []
    child = box.get_first_child()
    while child is not None:
        if hasattr(child, "get_label") and child.get_label() is not None:
            found.append(child.get_label())
        child = child.get_next_sibling()
    return found


def test_about_shows_the_apps_own_icon_name_title_and_version(window) -> None:
    from claudia_shell_gtk._version import __version__

    window.lookup_action("help.about").activate(None)
    about = window.about_dialog
    assert about is not None
    body = about.get_child().get_content()  # Adw.ToolbarView's content: the Gtk.Box built in _show_about
    assert body.get_first_child().get_icon_name() == "de.claudiaoffice.composes"
    texts = _labels(body)
    assert "Claudia Composes" in texts
    assert f"v{__version__}" in texts


def test_about_offers_the_same_three_links_as_the_web_dialog(window) -> None:
    from claudia_shell_gtk.manifest import about_links

    window.lookup_action("help.about").activate(None)
    body = window.about_dialog.get_child().get_content()
    links = body.get_last_child()  # the Gtk.Box of link buttons, appended last
    assert _labels(links) == [label for label, _url in about_links()]


def test_quit_closes_the_window(window) -> None:
    window.show_page("http://127.0.0.1:1")
    window.present()  # a window that was never shown has nothing to close
    closed: list[bool] = []

    def on_close_request(*_args: object) -> bool:
        closed.append(True)
        return False  # let it close

    window.connect("close-request", on_close_request)
    window.lookup_action("file.quit").activate(None)
    assert closed


def test_a_toast_can_be_shown_for_a_saved_download(window) -> None:
    window.toast("Saved notes.md to Downloads")
    assert window.last_toast == "Saved notes.md to Downloads"


def test_the_page_is_released_when_the_window_is_closed(window) -> None:
    """A page holds on to a session that all web views share; it must let go when its window is gone."""
    window.show_page("http://127.0.0.1:1")
    window.present()
    page = window.fake_pages[0]
    assert not page.closed
    window.close()
    assert page.closed


def test_releasing_the_page_twice_is_harmless(window) -> None:
    window.show_page("http://127.0.0.1:1")
    window.release_page()
    window.release_page()
    assert window.fake_pages[0].closed


# --------------------------------------------------------------------------------------- one window class, any app


@pytest.mark.parametrize("app", identity.names())
def test_every_app_gets_its_own_title_menus_and_actions(app: str, tmp_path) -> None:
    from claudia_shell_gtk._gi import Adw
    from claudia_shell_gtk.connector import ServerBook
    from claudia_shell_gtk.window import ClaudiaWindow

    Adw.init()
    spec = manifest.for_app(app)
    win = ClaudiaWindow(
        identity.get(app),
        spec,
        page_factory=lambda **_: FakePage(),
        book=ServerBook(app, local_origin=None, local_label="x", path=tmp_path / "s.json"),
    )
    try:
        assert win.get_title() == identity.get(app).title
        for action in spec.actions:
            assert win.lookup_action(action.id) is not None, action.id
        for menu in spec.menus:
            button = getattr(win, manifest.menu_button_id(menu.id))
            assert button.get_menu_model() is not None, menu.id
            assert button.get_menu_model().get_n_items() > 0, menu.id
    finally:
        win.destroy()


@pytest.mark.parametrize("app", identity.names())
def test_the_waiting_page_names_the_app(app: str, tmp_path) -> None:
    from claudia_shell_gtk._gi import Adw
    from claudia_shell_gtk.window import ClaudiaWindow

    Adw.init()
    win = ClaudiaWindow(identity.get(app), manifest.for_app(app), page_factory=lambda **_: FakePage())
    try:
        assert win.starting_page.get_title() == f"Starting {identity.get(app).title}…"
    finally:
        win.destroy()


# ------------------------------------------------------------------------------------- connecting to another server


def test_the_page_is_told_which_servers_there_are_when_it_says_hello(window) -> None:
    window.show_page("http://127.0.0.1:1")
    page = window.fake_pages[0]
    page.says({"type": "hello", "contract": 1, "app": "composes", "capabilities": ["connect", "servers"]})
    sent = [m for m in page.sent if m["type"] == "servers"]
    assert [e["origin"] for e in sent[0]["servers"]] == ["http://127.0.0.1:1"]
    assert sent[0]["servers"][0]["local"] is True


def test_a_server_the_page_asks_for_is_checked_for_this_app_and_shown_in_the_same_window(window) -> None:
    from claudia_shell_gtk.connection import Reached

    window.show_page("http://127.0.0.1:1")
    page = window.fake_pages[0]
    page.says({"type": "hello", "contract": 1, "app": "composes", "capabilities": ["connect"]})
    window.answers.append(Reached("https://demo.example.org:8420", "composes"))
    page.says({"type": "connect", "address": "demo.example.org:8420"})
    assert window.checked == [("https://demo.example.org:8420", "composes")]
    assert page.navigated == ["https://demo.example.org:8420"]
    assert len(window.fake_pages) == 1  # the same page, the same window
    assert window.visible_page == "web"


def test_a_server_that_is_refused_is_reported_to_the_page_and_nothing_is_switched(window) -> None:
    from claudia_shell_gtk.connection import Refused

    window.show_page("http://127.0.0.1:1")
    page = window.fake_pages[0]
    page.says({"type": "hello", "contract": 1, "app": "composes", "capabilities": ["connect"]})
    window.answers.append(Refused("wrong_app", "That server runs Claudia Computes."))
    page.says({"type": "connect", "address": "demo.example.org"})
    assert page.sent[-1] == {
        "type": "connect_failed",
        "code": "wrong_app",
        "message": "That server runs Claudia Computes.",
    }
    assert page.navigated == []


def test_plain_http_to_another_computer_is_refused_before_the_network_is_asked(window) -> None:
    window.show_page("http://127.0.0.1:1")
    page = window.fake_pages[0]
    page.says({"type": "hello", "contract": 1, "app": "composes", "capabilities": ["connect"]})
    page.says({"type": "connect", "address": "http://192.0.2.7:8420"})
    assert window.checked == []
    assert page.sent[-1]["code"] == "insecure"


def test_the_command_line_server_is_checked_like_a_typed_one_and_shown_without_a_page_before(window) -> None:
    from claudia_shell_gtk.connection import Reached

    window.answers.append(Reached("https://demo.example.org", "composes"))
    window.connect_to("https://demo.example.org")
    assert window.checked == [("https://demo.example.org", "composes")]
    assert window.fake_pages[0].loaded == ["https://demo.example.org"]
    assert window.visible_page == "web"


def test_a_command_line_server_that_is_refused_is_shown_as_the_windows_error(window) -> None:
    from claudia_shell_gtk.connection import Refused

    window.answers.append(Refused("unreachable", "Could not reach demo.example.org."))
    window.connect_to("https://demo.example.org")
    assert window.visible_page == "error"
    assert "Could not reach demo.example.org." in window.error_details


def test_the_page_is_made_with_a_way_to_ask_for_the_trusted_certificates(window) -> None:
    window.show_page("http://127.0.0.1:1")
    pinned = window.fake_pages[0].callbacks["pinned"]
    assert pinned("https://demo.example.org") is None
