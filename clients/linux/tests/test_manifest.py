"""The menu definition (``clients/contract``, D1643) as the clients build on it: its kinds of action, keys and roles,
the GTK menus made from it, the short menu of the front page, and the web app's ids.

What the menus hold, in which order, with which words, keys and rules, is the workbook's and is tested against it in
``tests/test_menu_workbook.py`` (D1605); nothing here repeats it.

The drift guard against the web app compares *ids*, the one thing both sides are required to agree on
(``web/app/lib/menu-dispatch.ts``), where a label never was (D121).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

from claudia_menus import manifest
from claudia_menus.manifest import Action, KeyOwner, Kind, Submenu
from claudia_shell_gtk import contract
from claudia_shell_gtk.menu_xml import menu_xml

REPO = Path(__file__).resolve().parents[3]
WEB_SOURCES = {
    "composes": REPO / "web" / "app" / "components" / "TextWorkspace.vue",
    "computes": REPO / "web" / "app" / "components" / "Workspace.vue",
    "creates": REPO / "web" / "app" / "components" / "SlideWorkspace.vue",
}
# The items every app's window shares (File, the Edit and View blocks, Preferences, Help) are built once, here; each
# workspace above assembles them with its own.
WEB_SHARED_MENUS = REPO / "web" / "app" / "lib" / "document-menus.ts"
# The Format menu's four entries are built in one place for all three apps (D300).
WEB_FORMAT_MENU = REPO / "web" / "app" / "lib" / "format-menu.ts"
# Composes' table entries (E9.32), Edit ▸ Row ▸ … Table Options… and Insert ▸ Table…, are built in one place.
WEB_TABLE_MENU = REPO / "web" / "app" / "lib" / "table-menu.ts"
WEB_ROTATE_MENU = REPO / "web" / "app" / "lib" / "rotate-menu.ts"
# Preferences ▸ App Language's ids are built from this list (`config.language.${tag}`), not written out one by one.
WEB_LANGUAGES = REPO / "web" / "app" / "lib" / "i18n.ts"
BUILDERS = {"composes": manifest.composes, "computes": manifest.computes, "creates": manifest.creates}
APPS = tuple(BUILDERS)


#: Until the web assembles its menus from the definition (slice 4 of the menu work, D1644), its hand-built menus
#: still have entries the workbook dropped or moved, and lack the new ones. Emptied by slice 4, then removed.
WEB_CATCHES_UP: dict[str, set[str]] = {
    # in the definition, not yet on the web
    "composes": {"insert.shape.circle", "insert.shape.rectangle", "insert.shape.triangle"},
    "creates": {"insert.shape.circle", "insert.shape.rectangle", "insert.shape.triangle"},
    # on the web, dropped by the workbook (the owner, 2026-11-25; D1608)
    "all": {
        "file.save",
        "file.manage.assign-owner",
        "file.manage.accept-owner",
        "file.manage.leave",
        "file.manage.delete",
        "format.rotate-right",
        "format.rotate-left",
        "help.ask",
    },
    "computes": {"insert.contents", "insert.cross-reference"},
}


def catching_up(app_name: str) -> set[str]:
    return WEB_CATCHES_UP["all"] | WEB_CATCHES_UP.get(app_name, set())


@pytest.fixture(scope="module", params=APPS)
def app(request: pytest.FixtureRequest) -> manifest.Manifest:
    return BUILDERS[request.param]()


@pytest.fixture(scope="module")
def composes() -> manifest.Manifest:
    return manifest.composes()


@pytest.fixture(scope="module")
def computes() -> manifest.Manifest:
    return manifest.computes()


def places(app: manifest.Manifest) -> list[Action]:
    """Every action where it stands: menus, context menus and the keys without an entry, an action shown twice twice."""
    return [
        *(a for menu in app.menus for a in menu.all_actions()),
        *(a for context in app.context_menus for a in context.all_actions()),
        *app.keys_only,
    ]


def menu_actions(app: manifest.Manifest) -> list[Action]:
    return [a for menu in app.menus for a in menu.all_actions()]


# ------------------------------------------------------------------------------------------------- the menus


def test_every_app_has_the_same_eight_menus_in_the_same_order(app: manifest.Manifest) -> None:
    """D120, D1603: the titles are the same in every app and never change."""
    assert [m.label for m in app.menus] == ["File", "Edit", "Insert", "Format", "View", "Tools", "Preferences", "Help"]


def test_every_place_has_a_rule(app: manifest.Manifest) -> None:
    """D1601, D1605: whether an entry fits is a rule, and every entry has one, in its place."""
    assert [a.id for a in places(app) if not a.fits] == []


def test_an_action_in_more_than_one_place_is_the_same_action(app: manifest.Manifest) -> None:
    """Its words and rule are the place's; what it does and its key are the action's (D1614)."""
    first: dict[str, Action] = {}
    for action in places(app):
        seen = first.setdefault(action.id, action)
        same = ("kind", "keys", "key_owner", "checkable", "role", "editing")
        assert all(getattr(seen, f) == getattr(action, f) for f in same), action.id


def test_a_context_menu_holds_actions_and_submenus_only(app: manifest.Manifest) -> None:
    """D1602: every thing's menu has an id and a name for Preferences ▸ Shortcuts (D1604), and no empty group."""
    ids = [c.id for c in app.context_menus]
    assert len(ids) == len(set(ids))
    for context in app.context_menus:
        assert context.label and all(context.sections), context.id


def test_macos_roles_are_set_on_the_shared_undo_redo_and_clipboard_actions(app: manifest.Manifest) -> None:
    """D158: a macOS shell needs a Cocoa role next to each shared Edit item's key, or the key equivalent is swallowed
    by the menu and the web view never sees it. Paste As ▸ Plain Text has no standard selector, so none."""
    pairs = {
        "edit.undo": "undo:",
        "edit.redo": "redo:",
        "edit.copy": "copy:",
        "edit.cut": "cut:",
        "edit.paste": "paste:",
    }
    for action_id, role in pairs.items():
        assert app.action(action_id).role == role
    assert app.action("edit.paste-as-plain").role is None
    assert [a.id for a in app.actions if a.role and a.id not in pairs] == []


# ------------------------------------------------------------------------------------------------- ids and actions


def test_every_action_id_is_a_valid_contract_action(app: manifest.Manifest) -> None:
    for action in app.actions:
        contract.action(action.id)  # raises on a bad id


def test_the_actions_are_listed_once(app: manifest.Manifest) -> None:
    ids = [action.id for action in app.actions]
    assert len(ids) == len(set(ids))


def test_a_submenu_itself_has_no_id_or_kind_only_its_items_do(app: manifest.Manifest) -> None:
    menus: list[manifest.Menu | manifest.ContextMenu] = [*app.menus, *app.context_menus]
    for menu in menus:
        for section in menu.sections:
            for entry in section:
                if isinstance(entry, Submenu):
                    assert not hasattr(entry, "id") and not hasattr(entry, "kind")
                    assert entry.items, f"{menu.label} ▸ {entry.label} has no items"


def _chord(accel: str) -> tuple[frozenset[str], str]:
    """The keys an accelerator stands for: its modifiers in any order (``<Primary><Alt><Shift>f`` is
    ``<Primary><Shift><Alt>f``) and its key, a letter in either case."""
    *modifiers, key = re.findall(r"<(\w+)>|(\w+)$", accel)
    return frozenset(m for m, _ in modifiers), key[1].lower()


def test_keys_are_well_formed_and_not_shared(app: manifest.Manifest) -> None:
    """A key the page or the shell listens for does one thing in an app. A key of the view (Delete, Enter, Tab, the
    clipboard) is the view's where it is pressed: Delete clears cells in the grid and removes a selected object."""
    seen: dict[tuple[frozenset[str], str], str] = {}
    for action in app.actions:
        for accel in filter(None, (action.keys.default, action.keys.macos)):
            assert re.fullmatch(r"(<(Primary|Control|Shift|Alt)>)*[A-Za-z0-9_]+", accel), accel
        if action.keys.default and action.key_owner is not KeyOwner.VIEW:
            chord = _chord(action.keys.default)
            assert chord not in seen, f"{action.keys.default} is on {seen[chord]} and {action.id}"
            seen[chord] = action.id


def test_the_same_chord_written_in_another_order_is_the_same_key() -> None:
    assert _chord("<Primary><Alt><Shift>f") == _chord("<Primary><Shift><Alt>F")
    assert _chord("<Primary><Alt>f") != _chord("<Primary><Shift><Alt>f")


def test_every_menu_entry_has_a_key_but_the_language_names(app: manifest.Manifest) -> None:
    """The project rule (UX-35): every menu entry has a key. The language picker's entries are each a language's own
    name, as many as there are catalogs; they are the one exception. A context menu's own entries need none (D1614)."""
    missing = [a.id for a in menu_actions(app) if not a.keys.default and not a.id.startswith("config.language.")]
    assert not missing, missing


def test_one_action_has_one_key_in_every_app():
    """UX-35: the same entry has the same key in composes, computes and creates."""
    keys: dict[str, manifest.Keys] = {}
    for build in BUILDERS.values():
        for action in build().actions:
            assert keys.setdefault(action.id, action.keys) == action.keys, action.id


def test_only_the_shells_own_keys_are_bound_natively(app: manifest.Manifest) -> None:
    """The page listens for every other key in every client, by the same table (`web/app/lib/keys.generated.ts`). A
    key the shell bound too would never reach the page (GTK takes application keys before the web view), so it would
    lose the page's rules: no shortcut while typing in a field, the right thing in the right place."""
    native = {a.id for a in app.actions if a.key_owner is KeyOwner.SHELL}
    assert native == {"file.quit", "help.about"}
    for action in app.actions:
        if action.kind is Kind.SHELL:
            assert action.key_owner is KeyOwner.SHELL, action.id


def test_no_key_is_one_a_browser_keeps_or_alt_gr_types(app: manifest.Manifest) -> None:
    """The web app is a client too: Chrome and Firefox never hand Ctrl+N, Ctrl+W, Ctrl+T (with or without Shift) to a
    page, and on Windows Ctrl+Alt is AltGr, which types @ € µ and the brackets on a German keyboard. Ctrl+Q only for
    the shells' own Quit. Ubuntu keeps Ctrl+Alt+T (terminal) and Ctrl+Alt+L (lock)."""
    for action in app.actions:
        accel = action.keys.default
        if not accel:
            continue
        lowered = accel.lower()
        assert lowered not in {"<primary>n", "<primary>w", "<primary>t", "<primary><shift>n", "<primary><shift>w"}
        assert lowered not in {"<primary><shift>t", "<primary><alt>t", "<primary><alt>l"}, accel
        if "<primary><alt>" in lowered and "<shift>" not in lowered:
            assert not re.fullmatch(r".*>([qem0-9])", lowered), f"{action.id}: {accel} is AltGr+{lowered[-1]}"
        if lowered == "<primary>q":
            assert action.id == "file.quit"


def test_each_action_is_carried_out_by_exactly_one_party(app: manifest.Manifest) -> None:
    for action in app.actions:
        assert isinstance(action.kind, Kind)
        if action.kind is Kind.EDITING:
            assert action.editing, f"{action.id} needs a WebKit editing command"
        else:
            assert action.editing is None


def test_checkable_actions_are_the_view_toggles_the_lists_and_the_language_picker(app: manifest.Manifest) -> None:
    checkable = {a.id for a in app.actions if a.checkable}
    language_ids = {f"config.language.{tag}" for tag, _label in manifest.LANGUAGES}
    # ticked when the paragraphs are that kind of list, and while the headings are numbered (E9.22)
    shared = {"view.authors", "view.panel", "view.dark", "format.bulleted-list", "format.numbered-list"}
    shared |= {"format.number-headings"} | language_ids
    own = {
        "composes": {"view.page"},
        "computes": {"tools.follow"},  # on while a computation is followed (E6.23)
        "creates": {"view.grid", "view.speaker-notes"},
    }
    assert checkable == shared | own[app.app]


def test_composes_clipboard_actions_are_native_webkit_editing_commands(composes: manifest.Manifest) -> None:
    """D121's scope note: composes' text is WebKit's own, so its clipboard is WebKit's editing commands."""
    pairs = (
        ("edit.copy", "Copy"),
        ("edit.cut", "Cut"),
        ("edit.paste", "Paste"),
        ("edit.paste-as-plain", "PasteAsPlainText"),
    )
    for action_id, command in pairs:
        action = composes.action(action_id)
        assert action.kind is Kind.EDITING and action.editing == command


@pytest.mark.parametrize("app_name", ["computes", "creates"])
def test_computes_and_creates_clipboard_actions_go_through_the_page_instead(app_name: str) -> None:
    """A cell grid or a slide canvas needs its own paste logic, not WebKit's generic one (D121)."""
    built = BUILDERS[app_name]()
    for action_id in ("edit.copy", "edit.cut", "edit.paste", "edit.paste-as-plain"):
        assert built.action(action_id).kind is Kind.PAGE


# ------------------------------------------------------------------------------------------- the web app, by id


@pytest.mark.parametrize("app_name", APPS)
def test_every_page_and_editing_action_id_is_in_the_matching_web_source(app_name: str) -> None:
    """The guard against drift (see this module's docstring): if the web app renames or drops an id of a menu, this
    fails and says which. ``Kind.SHELL`` actions (Quit, About) have no web equivalent by design. The context menus'
    ids are the web's when it assembles them from the definition (D1644)."""
    sources = (WEB_SOURCES[app_name], WEB_SHARED_MENUS, WEB_FORMAT_MENU, WEB_LANGUAGES, WEB_TABLE_MENU, WEB_ROTATE_MENU)
    if not all(path.exists() for path in sources):
        pytest.skip("the web sources are not next to the client")
    app_source, shared_menus, format_menu, languages_source, table_menu, rotate_menu = (
        path.read_text(encoding="utf-8") for path in sources
    )
    shared_source = shared_menus + format_menu + rotate_menu
    table_source = table_menu if app_name == "composes" else ""

    def in_web(action_id: str) -> bool:
        if f"id: '{action_id}'" in app_source or f"id: '{action_id}'" in shared_source:
            return True
        if f"'{action_id}'" in table_source:
            return True
        tag = action_id.removeprefix("config.language.")
        return (
            tag != action_id and "id: `config.language.${tag}`" in shared_source and f"['{tag}', " in languages_source
        )

    built = BUILDERS[app_name]()
    missing = [a.id for a in menu_actions(built) if a.kind is not Kind.SHELL and not in_web(a.id)]
    assert sorted(set(missing) - catching_up(app_name)) == [], f"{app_name}: the web app no longer has " + ", ".join(
        missing
    )


# ------------------------------------------------------------------------------------------------- GMenu XML


def test_the_gmenu_xml_has_one_menu_per_manifest_menu_in_order(app: manifest.Manifest) -> None:
    root = ET.fromstring(menu_xml(app))
    assert root.tag == "interface"
    assert [m.get("id") for m in root.findall("menu")] == [menu.id for menu in app.menus]


def test_menu_items_call_window_actions_and_are_translatable(app: manifest.Manifest) -> None:
    root = ET.fromstring(menu_xml(app))
    items = root.findall(".//item")
    assert len(items) == len(menu_actions(app))
    for item in items:
        attributes = {a.get("name"): a for a in item.findall("attribute")}
        assert (attributes["action"].text or "").startswith("win.")
        assert attributes["label"].get("translatable") == "yes"


def test_a_submenu_renders_as_a_nested_gmenu_submenu_with_its_own_section(computes: manifest.Manifest) -> None:
    """D130: ``<submenu>`` nested in a ``<section>``, GTK's own flyout shape — the same thing ``MenuBar.vue``'s
    ``items`` property draws on the web side."""
    root = ET.fromstring(menu_xml(computes))
    edit_menu = root.find("menu[@id='menu-edit']")
    assert edit_menu is not None
    submenus = edit_menu.findall(".//submenu")
    assert {s.findtext("attribute[@name='label']") for s in submenus} == {"Paste As", "Remove"}
    remove = next(s for s in submenus if s.findtext("attribute[@name='label']") == "Remove")
    targets = [i.findtext("attribute[@name='action']") for i in remove.findall("section/item")]
    assert targets == ["win.edit.row-delete", "win.edit.column-delete"]


def test_sections_become_gmenu_sections_so_that_separators_are_drawn(app: manifest.Manifest) -> None:
    root = ET.fromstring(menu_xml(app))
    file_menu = root.find("menu[@id='menu-file']")
    assert file_menu is not None
    assert len(file_menu.findall("section")) == len(app.menu("File").sections) > 1


def test_menu_xml_defaults_to_no_translation_at_all() -> None:
    """Every other test in this module calls ``menu_xml``/``menu_elements`` with no ``translate`` and still gets
    plain English back — the default is the identity function, so none of this module needs a locale installed."""
    root = ET.fromstring(menu_xml(manifest.composes()))
    label = root.find(".//menu[@id='menu-file']//item/attribute[@name='label']")
    assert label is not None and label.text == "New"


def test_a_translate_function_is_applied_to_item_and_submenu_labels() -> None:
    loud = {"New": "NEW", "Open": "OPEN"}.get
    root = ET.fromstring(menu_xml(manifest.composes(), translate=lambda s: loud(s) or s))
    new_item = root.find(".//menu[@id='menu-file']//item/attribute[@name='label']")
    assert new_item is not None and new_item.text == "NEW"
    open_submenu = root.find(".//menu[@id='menu-file']//submenu/attribute[@name='label']")
    assert open_submenu is not None and open_submenu.text == "OPEN"


def test_a_translate_function_never_touches_the_language_pickers_own_autonyms() -> None:
    """``config.language.en``/``config.language.de``'s labels are ``LANGUAGES``' own autonyms, not English UI text —
    translating them would be exactly the mistake this module's docstring calls out."""
    shout_everything = str.upper
    root = ET.fromstring(menu_xml(manifest.composes(), translate=shout_everything))
    preferences_menu = root.find(".//menu[@id='menu-preferences']")
    assert preferences_menu is not None
    language_labels = {
        item.findtext("attribute[@name='label']")
        for item in preferences_menu.findall(".//submenu/section/item")
        if (item.findtext("attribute[@name='action']") or "").startswith("win.config.language.")
    }
    assert language_labels == {"English", "Deutsch"}


def test_special_characters_in_a_label_are_escaped() -> None:
    odd = manifest.Manifest(
        app="composes",
        menus=(manifest.Menu("Tools", ((manifest.Action("tools.odd", "Fish & <Chips>", Kind.SHELL),),)),),
    )
    root = ET.fromstring(menu_xml(odd))
    label = root.find(".//item/attribute[@name='label']")
    assert label is not None and label.text == "Fish & <Chips>"


def test_the_manifest_can_be_listed_for_the_page_and_the_docs(app: manifest.Manifest) -> None:
    listing = app.describe()
    assert listing["app"] == app.app
    assert listing["menus"][0]["label"] == "File"
    json.dumps(listing)  # plain data, including any submenu's nested "items"
    paste_as = next(e for e in listing["menus"][1]["sections"][1] if e.get("label") == "Paste As")
    assert paste_as["items"][0]["id"] == "edit.paste-as-plain"
    assert paste_as["items"][0]["fits"] == "role: editor or owner"
    assert [c["id"] for c in listing["context_menus"]] == [c.id for c in app.context_menus]


def test_role_is_in_the_listing_so_the_macos_client_can_read_it_without_importing_this_module(
    app: manifest.Manifest,
) -> None:
    """The macOS client (``clients/neutralino``) has no PyGObject and no reason to import this GTK-adjacent package
    at run time; it reads ``describe()``'s JSON instead (``clients/neutralino/tools/generate_menu.py``). ``role`` has to
    survive that trip or D158's Cocoa mapping cannot be built on the other side."""
    listing = app.describe()
    by_id = {a["id"]: a for menu in listing["menus"] for a in _flatten(menu)}
    assert by_id["edit.copy"]["role"] == "copy:"
    assert by_id["file.new"]["role"] is None


def _flatten(menu: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for section in menu["sections"]:
        for entry in section:
            out.extend(entry.get("items", [entry]))
    return out


# ------------------------------------------------------------------------- the short menu of the front page (sheet 11)
@pytest.mark.parametrize("app_name", ["composes", "computes", "creates"])
def test_the_front_page_menu_has_only_what_works_without_a_document(app_name: str) -> None:
    short = manifest.for_start(manifest.for_app(app_name))
    assert [menu.label for menu in short.menus] == ["File", "View", "Preferences", "Help"]
    ids = [action.id for action in short.actions]
    assert ids == [
        "file.new",
        "file.open",
        "file.open-file",
        "file.quit",
        "view.dark",
        "config.language.en",
        "config.language.de",
        "help.about",
    ]


def test_the_front_page_menu_keeps_the_language_flyout_and_drops_empty_sections(composes: manifest.Manifest) -> None:
    short = manifest.for_start(composes)
    config = short.menu("Preferences")
    assert len(config.sections) == 1
    (flyout,) = config.sections[0]
    assert isinstance(flyout, manifest.Submenu) and flyout.label == "App Language"
    assert all(section for menu in short.menus for section in menu.sections)
    assert short.context_menus == () and short.keys_only == ()


def test_the_listing_says_which_actions_belong_on_the_front_page(composes: manifest.Manifest) -> None:
    listed = {
        a["id"]: a["start"]
        for m in composes.describe()["menus"]
        for s in m["sections"]
        for e in s
        for a in e.get("items", [e])
    }
    assert listed["file.open-file"] is True and listed["config.language.de"] is True
    assert listed["edit.cut"] is False and listed["help.how-to"] is False


def test_about_links_are_website_then_report_an_issue_then_legal() -> None:
    """D28's shared About dialog (``window.py``'s ``_show_about``, ``AboutDialog.vue``'s own ``LINKS``): this is the
    one side of that agreement GTK can test without a display — the three links, their order and their targets."""
    labels = [label for label, _url in manifest.about_links()]
    assert labels == ["Website", "Report an Issue", "Legal"]
    urls = dict(manifest.about_links())
    assert urls["Website"] == "https://www.claudia-office.de"
    assert urls["Report an Issue"] == "https://github.com/claudiaoffice/claudia/issues"
    # linked, not reproduced in full — claudiaoffice-log/notes/README.md's reason for not duplicating generated
    # content applies here too: a second copy of the licence text cannot be kept true.
    assert urls["Legal"] == "https://github.com/claudiaoffice/claudia/blob/main/LICENSE"


# ----------------------------------------------------------------------------------- the registry (one shell, any app)


@pytest.mark.parametrize("app", APPS)
def test_for_app_gives_the_manifest_of_that_app(app: str) -> None:
    assert manifest.for_app(app).app == app
    assert manifest.for_app(app).describe() == BUILDERS[app]().describe()


def test_the_registry_knows_exactly_the_apps_that_have_an_identity() -> None:
    from claudia_shell_gtk import identity

    assert set(identity.names()) == set(APPS)


def test_the_definition_needs_nothing_but_its_own_folder() -> None:
    """D1643: the definition is pure data that every client reads, so it imports with no Linux client, no GTK and
    nothing installed: a fresh interpreter with only ``clients/contract/src`` on its path builds every app's menus."""
    script = (
        "import sys; from claudia_menus import manifest; "
        "[manifest.for_app(app).describe() for app in ('composes', 'computes', 'creates')]; "
        "print(sorted(name for name in sys.modules if name.split('.')[0] in ('gi', 'claudia_shell_gtk')))"
    )
    env = {"PYTHONPATH": str(REPO / "clients" / "contract" / "src")}
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, env=env, check=True)
    assert done.stdout.strip() == "[]"


def test_an_app_without_a_manifest_is_a_clear_error_naming_the_available_ones() -> None:
    with pytest.raises(manifest.UnknownApp) as problem:
        manifest.for_app("drawbook")
    assert "composes" in str(problem.value)


# UX-36: the other direction. Entries that are only a flyout's parent (they have an id for the web's own drawing, not
# an action) are named, with the reason, so that nothing else can be web-only without someone saying so here.
WEB_ONLY_PARENTS = {
    "file.manage": "File ▸ Manage ▸ is a Submenu here (no id, no action)",
    "edit.paste-as": "Edit ▸ Paste As ▸ is a Submenu here",
    "edit.row": "Edit ▸ Row ▸ is a Submenu here",
    "edit.column": "Edit ▸ Column ▸ is a Submenu here",
    "edit.sort": "composes' Edit ▸ Sort ▸ is a Submenu here",
    "tools.row": "composes' Tools ▸ Row ▸ is a Submenu here (D1229)",
    "tools.column": "composes' Tools ▸ Column ▸ is a Submenu here (D1229)",
    "tools.sort": "composes' Tools ▸ Sort ▸ is a Submenu here (D1229)",
}


@pytest.mark.parametrize("app_name", APPS)
def test_every_web_menu_entry_is_in_the_desktop_menus_too(app_name: str) -> None:
    """At cfa2d91 File ▸ Print…, Image…, Chart…, Names…, SQL Query…, Show Grid and the List flyout were on the web
    only, and the desktop shells hide the web menu bar: on the desktop they could not be found. A menu item on the web
    is `{ id: '…', label: … }`; a keyboard shortcut (`get label()`) is not a menu item."""
    sources = (WEB_SOURCES[app_name], WEB_SHARED_MENUS, WEB_FORMAT_MENU, WEB_TABLE_MENU, WEB_ROTATE_MENU)
    if not all(path.exists() for path in sources):
        pytest.skip("the web sources are not next to the client")
    app_source, shared_menus, format_menu, table_menu, rotate_menu = (
        path.read_text(encoding="utf-8") for path in sources
    )
    item = re.compile(r"\{\s*id: '([a-z.-]+)',\s*label:")
    ids = set(item.findall(app_source)) | set(item.findall(format_menu)) | set(item.findall(shared_menus))
    if "rotateItem(" in app_source:  # the apps that turn objects hand the Format menu the shared Rotate submenu
        ids |= set(item.findall(rotate_menu))
    if app_name == "composes":
        ids |= set(item.findall(table_menu))
    ids |= {"file.manage", "edit.paste-as"} & set(re.findall(r"id: '([a-z.-]+)',\n", shared_menus))
    if "print: " not in app_source:  # File ▸ Print… is only in the apps that hand the shared File menu a `print`
        ids.discard("file.print")
    native = {a.id for a in BUILDERS[app_name]().actions}
    missing = sorted(ids - native - set(WEB_ONLY_PARENTS) - catching_up(app_name))
    assert not missing, f"{app_name}: on the web menus but not on the desktop's: {missing}"


def test_the_gmenu_xml_shows_every_key_whoever_listens_for_it(app: manifest.Manifest) -> None:
    """GTK draws an item's ``accel`` attribute beside its label without binding it: the menu shows the page's keys too
    (UX-35), which before only the web menu did."""
    root = ET.fromstring(menu_xml(app))
    shown = {}
    for item in root.iter("item"):
        attributes = {a.get("name"): a.text for a in item.findall("attribute")}
        shown[str(attributes["action"]).removeprefix("win.")] = attributes.get("accel")
    assert shown["file.print"] is not None
    for action in menu_actions(app):
        assert shown[action.id] == action.keys.default, action.id
