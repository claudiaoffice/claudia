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
        self.editing: list[str] = []
        self.widget = None
        self.closed = False

    def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))

    def load(self, url: str) -> None:
        self.loaded.append(url)

    def run_editing_command(self, command: str) -> None:
        self.editing.append(command)

    def close(self) -> None:
        self.closed = True

    # what the page would do:
    def says(self, message: dict) -> None:
        self.callbacks["on_message"](json.dumps(message))


@pytest.fixture
def window():
    from claudia_shell_gtk._gi import Adw, Gtk
    from claudia_shell_gtk.window import ComposesWindow

    Adw.init()
    pages: list[FakePage] = []

    def factory(**callbacks):
        page = FakePage(**callbacks)
        page.widget = Gtk.Label(label="page")
        pages.append(page)
        return page

    win = ComposesWindow(identity.get("composes"), manifest.composes(), page_factory=factory)
    win.fake_pages = pages
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
        "edit.paste-as": "PasteAsPlainText",
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


def test_about_names_the_app_the_licence_and_the_version(window) -> None:
    window.lookup_action("help.about").activate(None)
    about = window.about_dialog
    assert about is not None
    assert about.get_application_name() == "Claudia Composes"
    assert about.get_application_icon() == "de.claudiaoffice.composes"
    assert about.get_website() == "https://claudia-office.de"
    from claudia_shell_gtk._gi import Gtk

    assert about.get_license_type() == Gtk.License.GPL_3_0


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
