"""The layout file of the window (D27) agrees with the manifest. No GTK needed: the XML is read as data."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from importlib import resources

from claudia_shell_gtk import manifest


def window_ui() -> ET.Element:
    return ET.fromstring(resources.files("claudia_shell_gtk").joinpath("data/window.ui").read_text(encoding="utf-8"))


def test_there_is_a_menu_button_for_every_menu_of_the_manifest() -> None:
    wanted = {menu.id: menu.label for menu in manifest.composes().menus}
    buttons = {
        button.findtext("property[@name='menu-model']"): button.findtext("property[@name='label']")
        for button in window_ui().iter("object")
        if button.get("class") == "GtkMenuButton"
    }
    assert buttons == wanted


def test_the_header_toggle_of_the_manifest_is_wired_to_its_action() -> None:
    toggle = manifest.composes().header_toggles[0]
    actions = [node.text for node in window_ui().iter("property") if node.get("name") == "action-name"]
    assert actions == [f"win.{toggle.id}"]


def test_the_visible_texts_of_the_layout_can_be_translated() -> None:
    for node in window_ui().iter("property"):
        if node.get("name") in {"label", "title", "tooltip-text", "description"}:
            assert node.get("translatable") == "yes", f"{node.get('name')}={node.text!r} cannot be translated"


def test_the_menus_are_generated_from_the_manifest_and_not_written_by_hand_in_the_layout() -> None:
    assert not list(window_ui().iter("menu"))
    assert "<!-- menus -->" in resources.files("claudia_shell_gtk").joinpath("data/window.ui").read_text(
        encoding="utf-8"
    )


def test_the_menu_elements_can_be_merged_into_a_layout() -> None:
    fragment = manifest.menu_elements(manifest.composes())
    assert fragment.lstrip().startswith("<menu ")
    assert "<interface" not in fragment
    assert fragment in manifest.menu_xml(manifest.composes())
