"""The menu and action manifest of the Linux client (E5.1, D4, D54, D74) and the menus built from it.

The four menus are File, Edit, Tools and Help. The web app that this shell shows still has six (it is being cleaned up
separately), so the manifest says what a *native* menu offers and ``webroutes.json`` says where the unchanged page has
each action. The tests below keep the two from drifting apart.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from claudia_shell_gtk import contract, manifest
from claudia_shell_gtk.manifest import Kind

REPO = Path(__file__).resolve().parents[3]
WEB_SOURCE = REPO / "web" / "app" / "components" / "TextWorkspace.vue"
ROUTES = Path(manifest.__file__).parent / "data" / "webroutes.json"


@pytest.fixture(scope="module")
def composes() -> manifest.Manifest:
    return manifest.composes()


def labels(menu: manifest.Menu) -> list[str]:
    return [action.label for section in menu.sections for action in section]


def test_there_are_four_menus_in_the_order_of_d4(composes: manifest.Manifest) -> None:
    assert [menu.label for menu in composes.menus] == ["File", "Edit", "Tools", "Help"]


def test_file_has_open_save_save_as_and_quit(composes: manifest.Manifest) -> None:
    file_menu = composes.menu("File")
    assert {"Open…", "Save", "Save As…", "Quit"} <= set(labels(file_menu))


def test_edit_is_undo_redo_cut_copy_paste_paste_as(composes: manifest.Manifest) -> None:
    """D54 and D74 (Select All is deliberately not a menu item)."""
    assert labels(composes.menu("Edit")) == ["Undo", "Redo", "Cut", "Copy", "Paste", "Paste As Plain Text"]


def test_help_has_help_and_about(composes: manifest.Manifest) -> None:
    assert labels(composes.menu("Help")) == ["Help", "About Claudia Composes"]


def test_the_page_menus_that_d4_does_not_have_are_folded_into_tools(composes: manifest.Manifest) -> None:
    """Format and View of the web app do not exist natively; they are reachable from Tools or the header bar."""
    tools = set(labels(composes.menu("Tools")))
    assert {"Look of this Style…", "All Styles…", "Page View", "Show Who Wrote What"} <= tools
    assert [toggle.id for toggle in composes.header_toggles] == ["view.panel"]


def test_every_action_id_is_a_valid_contract_action(composes: manifest.Manifest) -> None:
    for action in composes.actions:
        contract.action(action.id)  # raises on a bad id


def test_action_ids_are_unique(composes: manifest.Manifest) -> None:
    ids = [action.id for action in composes.actions]
    assert len(ids) == len(set(ids))


def test_ids_do_not_depend_on_the_menu_an_action_sits_in(composes: manifest.Manifest) -> None:
    """Moving an item to another menu must not change the contract: Tools holds 'view.page' and 'style.look'."""
    ids = {action.id for action in composes.menu("Tools").all_actions()}
    assert {"view.page", "style.look"} <= ids


def test_accelerators_are_well_formed_and_not_shared(composes: manifest.Manifest) -> None:
    seen: dict[str, str] = {}
    for action in composes.actions:
        for accel in action.accelerators:
            assert re.fullmatch(r"(<(Primary|Shift|Alt)>)*[A-Za-z0-9_]+", accel), accel
            assert accel not in seen, f"{accel} is on {seen[accel]} and {action.id}"
            seen[accel] = action.id


def test_keys_the_page_handles_itself_are_not_bound_a_second_time(composes: manifest.Manifest) -> None:
    """If both the page and the shell reacted to Ctrl+Z, one keystroke would undo twice."""
    for action_id in ("file.save", "edit.undo", "edit.redo", "style.look", "edit.cut", "edit.copy", "edit.paste"):
        assert composes.action(action_id).accelerators == (), action_id


def test_each_action_is_carried_out_by_exactly_one_party(composes: manifest.Manifest) -> None:
    for action in composes.actions:
        assert isinstance(action.kind, Kind)
        if action.kind is Kind.EDITING:
            assert action.editing, f"{action.id} needs a WebKit editing command"
        else:
            assert action.editing is None


def test_checkable_actions_are_the_three_toggles(composes: manifest.Manifest) -> None:
    assert {a.id for a in composes.actions if a.checkable} == {"view.page", "view.authors", "view.panel"}


# ------------------------------------------------------------------------------------------- the unchanged page


def routes() -> dict[str, dict]:
    return json.loads(ROUTES.read_text(encoding="utf-8"))


def test_every_page_action_has_a_route_and_no_route_is_orphaned(composes: manifest.Manifest) -> None:
    page_actions = {a.id for a in composes.actions if a.kind is Kind.PAGE}
    assert set(routes()) == page_actions


@pytest.mark.skipif(not WEB_SOURCE.exists(), reason="the web sources are not next to the client")
def test_every_route_points_at_a_menu_item_that_the_web_app_still_has() -> None:
    """The guard against drift: if the web cleanup renames 'Save with a name…', this fails and says where."""
    source = WEB_SOURCE.read_text(encoding="utf-8")

    def exists(menu: str, label: str, prefix: bool) -> bool:
        has_menu = f"label: '{menu}'" in source
        has_item = f"label: '{label}'" in source or (prefix and "label: state.can" in source and f"`{label}" in source)
        return has_menu and has_item

    problems = [
        f"{action_id}: {step['menu']} ▸ {step['label']}"
        for action_id, route in routes().items()
        for step in (route, route.get("off"))
        if step and not exists(step["menu"], step["label"], step.get("prefix", False))
    ]
    assert not problems, "the web app no longer has: " + "; ".join(problems)


# ------------------------------------------------------------------------------------------------- GMenu XML


def test_the_gmenu_xml_has_one_menu_per_manifest_menu(composes: manifest.Manifest) -> None:
    root = ET.fromstring(manifest.menu_xml(composes))
    assert root.tag == "interface"
    assert [m.get("id") for m in root.findall("menu")] == ["menu-file", "menu-edit", "menu-tools", "menu-help"]


def test_menu_items_call_window_actions_and_are_translatable(composes: manifest.Manifest) -> None:
    root = ET.fromstring(manifest.menu_xml(composes))
    items = root.findall(".//item")
    assert len(items) == sum(1 for menu in composes.menus for _ in menu.all_actions())
    for item in items:
        attributes = {a.get("name"): a for a in item.findall("attribute")}
        assert (attributes["action"].text or "").startswith("win.")
        assert attributes["label"].get("translatable") == "yes"


def test_sections_become_gmenu_sections_so_that_separators_are_drawn(composes: manifest.Manifest) -> None:
    root = ET.fromstring(manifest.menu_xml(composes))
    file_menu = root.find("menu[@id='menu-file']")
    assert file_menu is not None
    assert len(file_menu.findall("section")) == len(composes.menu("File").sections) > 1


def test_special_characters_in_a_label_are_escaped() -> None:
    odd = manifest.Manifest(
        app="composes",
        menus=(manifest.Menu("Tools", ((manifest.Action("tools.odd", "Fish & <Chips>", Kind.SHELL),),)),),
    )
    root = ET.fromstring(manifest.menu_xml(odd))
    label = root.find(".//item/attribute[@name='label']")
    assert label is not None and label.text == "Fish & <Chips>"


def test_the_manifest_can_be_listed_for_the_page_and_the_docs(composes: manifest.Manifest) -> None:
    listing = composes.describe()
    assert listing["app"] == "composes"
    assert listing["menus"][0]["label"] == "File"
    json.dumps(listing)  # plain data
