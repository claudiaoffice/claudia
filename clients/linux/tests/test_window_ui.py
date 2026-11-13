"""The layout file of the window (D27) agrees with the manifest. No GTK needed: the XML is read as data."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from importlib import resources

import pytest

from claudia_shell_gtk import identity, manifest


def window_ui() -> ET.Element:
    return ET.fromstring(resources.files("claudia_shell_gtk").joinpath("data/window.ui").read_text(encoding="utf-8"))


@pytest.mark.parametrize("app", identity.names())
def test_there_is_a_menu_button_for_every_menu_of_every_app(app: str) -> None:
    """One layout serves all apps: their menus have the same ids and labels, only their items differ."""
    wanted = {manifest.menu_button_id(menu.id): menu.label for menu in manifest.for_app(app).menus}
    buttons = {
        button.get("id"): button.findtext("property[@name='label']")
        for button in window_ui().iter("object")
        if button.get("class") == "GtkMenuButton"
    }
    assert buttons == wanted


def test_the_window_class_has_a_child_for_every_menu_button() -> None:
    """``window.py`` declares one ``Gtk.Template.Child`` per button; a button without one could not get its menu."""
    from importlib import resources

    source = resources.files("claudia_shell_gtk").joinpath("window.py").read_text(encoding="utf-8")
    for app in identity.names():
        for menu in manifest.for_app(app).menus:
            assert f"{manifest.menu_button_id(menu.id)} = Gtk.Template.Child()" in source


def test_the_header_bars_own_panel_toggle_is_wired_to_the_view_panel_action() -> None:
    """The quick-access `GtkToggleButton` in the header bar (independent of the View menu's own "History and
    chat" item) is not generated from the manifest at all — it is hand-written in `window.ui` — but still has to
    name a real action. D120 moved `view.panel` out of `Manifest.header_toggles` (now always empty: nothing else
    uses it) into the View menu proper, so this checks the id directly rather than through that field."""
    assert "view.panel" in {a.id for a in manifest.composes().menu("View").all_actions()}
    actions = [node.text for node in window_ui().iter("property") if node.get("name") == "action-name"]
    assert actions == ["win.view.panel"]


def test_the_visible_texts_of_the_layout_can_be_translated() -> None:
    for node in window_ui().iter("property"):
        if node.get("name") in {"label", "title", "tooltip-text", "description"}:
            assert node.get("translatable") == "yes", f"{node.get('name')}={node.text!r} cannot be translated"


def test_the_menus_are_generated_from_the_manifest_and_not_written_by_hand_in_the_layout() -> None:
    assert not list(window_ui().iter("menu"))
    assert not [p for p in window_ui().iter("property") if p.get("name") == "menu-model"]


def test_the_waiting_page_has_no_app_name_in_it() -> None:
    """Its title is set by the window from the identity ("Starting Claudia Computes…")."""
    text = resources.files("claudia_shell_gtk").joinpath("data/window.ui").read_text(encoding="utf-8")
    assert "Composes" not in text
    assert 'id="starting_page"' in text


def test_the_menu_elements_can_be_merged_into_a_layout() -> None:
    fragment = manifest.menu_elements(manifest.composes())
    assert fragment.lstrip().startswith("<menu ")
    assert "<interface" not in fragment
    assert fragment in manifest.menu_xml(manifest.composes())
