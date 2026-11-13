"""The menu and action manifest of the Linux client (E5.1 / E5.10, D120–D130) and the menus built from it.

D120 gives every app the same seven menus. composes, computes and creates share Edit's Undo/Redo/Copy/Cut/Paste/
Paste-as block and View's Show-who-wrote-what/History-and-chat/Dark-mode block verbatim; the tests below check that
directly (one set of ids, compared across the three manifests) rather than retyping the block three times.

The drift guard against the web app changed shape with this round (D121): it used to grep ``webroutes.json``'s
*labels* against ``shim.js``'s hidden-DOM-click targets, which is retired along with ``shim.js`` itself. Now that the
page speaks the shell contract directly, the guard compares *ids* — a stronger guarantee, since an id is the one
thing both sides are required to agree on (`web/app/lib/menu-dispatch.ts`), where a label never was.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

from claudia_shell_gtk import contract, manifest
from claudia_shell_gtk.manifest import Action, KeyOwner, Kind, Submenu

REPO = Path(__file__).resolve().parents[3]
WEB_SOURCES = {
    "composes": REPO / "web" / "app" / "components" / "TextWorkspace.vue",
    "computes": REPO / "web" / "app" / "components" / "Workspace.vue",
    "creates": REPO / "web" / "app" / "components" / "SlideWorkspace.vue",
}
# The items every app's window shares (File, the Edit and View blocks, Config, Help) are built once, here; each
# workspace above assembles them with its own.
WEB_SHARED_MENUS = REPO / "web" / "app" / "lib" / "document-menus.ts"
# The Format menu's four entries are built in one place for all three apps (D300).
WEB_FORMAT_MENU = REPO / "web" / "app" / "lib" / "format-menu.ts"
# Config ▸ App Language's ids are built from this list (`config.language.${tag}`), not written out one by one.
WEB_LANGUAGES = REPO / "web" / "app" / "lib" / "i18n.ts"
BUILDERS = {"composes": manifest.composes, "computes": manifest.computes, "creates": manifest.creates}
APPS = tuple(BUILDERS)


@pytest.fixture(scope="module", params=APPS)
def app(request: pytest.FixtureRequest) -> manifest.Manifest:
    """Each of the three manifests in turn — most tests below hold for all three identically."""
    return BUILDERS[request.param]()


@pytest.fixture(scope="module")
def composes() -> manifest.Manifest:
    return manifest.composes()


@pytest.fixture(scope="module")
def computes() -> manifest.Manifest:
    return manifest.computes()


@pytest.fixture(scope="module")
def creates() -> manifest.Manifest:
    return manifest.creates()


def entries(menu: manifest.Menu) -> list[manifest.MenuEntry]:
    return [entry for section in menu.sections for entry in section]


def labels(menu: manifest.Menu) -> list[str]:
    return [entry.label for entry in entries(menu)]


def action_ids(menu: manifest.Menu) -> list[str]:
    return [a.id for a in menu.all_actions()]


# ------------------------------------------------------------------------------------------------------ the schema


def test_every_app_has_the_same_seven_menus_in_the_same_order(app: manifest.Manifest) -> None:
    assert [menu.label for menu in app.menus] == ["File", "Edit", "Format", "View", "Tools", "Config", "Help"]


def test_file_is_grouped_new_open_save_group_manage_close_quit(app: manifest.Manifest) -> None:
    """D123/D124: separators kept, grouped as New/Open · Save-group · Manage · Close/Quit. D141: the Manage
    item replaces the plain "Share…" item it grew out of, and is itself a submenu. The apps that lay out pages print
    (D906): File ▸ Print… was on the web only (UX-36)."""
    file_menu = app.menu("File")
    keep = ["Save", "Save New Checkpoint…", "Download"] + (["Print…"] if app.app in ("composes", "creates") else [])
    assert [[e.label for e in section] for section in file_menu.sections] == [
        ["New", "Open…"],
        keep,
        ["Manage"],
        ["Close Document", "Quit"],
    ]


def test_file_manage_offers_share_assign_owner_leave_export_and_delete(app: manifest.Manifest) -> None:
    """D141: the "Manage" submenu Claude built from the design the owner accepted (assigning a new owner, leaving,
    exporting and deleting a document from the server), with Share… kept as its first item so adding people to a
    document is still possible."""
    file_menu = app.menu("File")
    manage = file_menu.sections[2][0]
    assert isinstance(manage, Submenu) and manage.label == "Manage"
    assert [a.id for a in manage.items] == [
        "file.manage.share",
        "file.manage.assign-owner",
        "file.manage.accept-owner",
        "file.manage.leave",
        "file.manage.export",
        "file.manage.delete",
    ]
    assert [a.label for a in manage.items] == [
        "Share…",
        "Assign New Owner…",
        "Accept Ownership…",
        "Leave Document…",
        "Export…",
        "Delete From Server…",
    ]


def test_edits_shared_block_is_identical_in_every_app(app: manifest.Manifest) -> None:
    """Undo, Redo, Copy, Cut, Paste, Paste as ▸ Plain text — D120's shared block, verbatim in every app."""
    shared_ids = [e.id if isinstance(e, Action) else [i.id for i in e.items] for e in entries(app.menu("Edit"))[:6]]
    assert shared_ids == [
        "edit.undo",
        "edit.redo",
        "edit.copy",
        "edit.cut",
        "edit.paste",
        ["edit.paste-as-plain"],
    ]


def test_macos_roles_are_set_on_the_shared_undo_redo_and_clipboard_actions(app: manifest.Manifest) -> None:
    """D158: a macOS shell needs a Cocoa role (``undo:``, ``redo:``, ``cut:``, ``copy:``, ``paste:``) next to each
    shared Edit item's accelerator, or the key equivalent is swallowed by the menu and the web view never sees it
    (confirmed on the owner's Mac, ``notes/e0-3-neutralino-windows-macos.md``). This holds whether the action's
    ``kind`` is ``EDITING`` (composes, native WebKit commands) or ``PAGE`` (computes/creates, D121): either way the
    key has to reach the item before anything downstream can run. ``edit.paste-as-plain`` has no standard Cocoa
    editing selector, so it is not given one."""
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


def test_only_the_shared_edit_block_carries_a_macos_role(app: manifest.Manifest) -> None:
    """Everything else (``file.*``, ``view.*``, ``tools.*``, app-specific Edit items such as creates'
    ``edit.new-slide``) has no Cocoa editing counterpart, so :attr:`manifest.Action.role` stays unset there."""
    roled = {"edit.undo", "edit.redo", "edit.copy", "edit.cut", "edit.paste"}
    for action in app.actions:
        if action.id not in roled:
            assert action.role is None, f"{action.id} should not carry a macOS role"


def test_views_shared_block_is_identical_in_every_app(app: manifest.Manifest) -> None:
    """Show who wrote what, History and chat, Dark mode — D120's shared block, verbatim in every app (even where,
    per D125, "Show who wrote what" starts permanently disabled: computes and creates track no authorship yet)."""
    section = app.menu("View").sections[0]
    assert all(isinstance(e, Action) for e in section), f"expected only plain actions, got {section!r}"
    assert [e.id for e in section if isinstance(e, Action)] == ["view.authors", "view.panel", "view.dark"]


def test_configs_items_are_shortcuts_then_app_language(app: manifest.Manifest) -> None:
    """The owner's second i18n round: Shortcuts, then App Language ▸ one item per ``manifest.LANGUAGES`` entry."""
    assert action_ids(app.menu("Config")) == ["config.shortcuts", "config.language.en", "config.language.de"]


def test_app_language_items_are_checkable_page_actions_named_after_their_tag(app: manifest.Manifest) -> None:
    config = app.menu("Config")
    app_language = next(
        e for section in config.sections for e in section if getattr(e, "label", None) == "App Language"
    )
    assert isinstance(app_language, manifest.Submenu)
    assert [(a.id, a.label) for a in app_language.items] == [
        (f"config.language.{tag}", label) for tag, label in manifest.LANGUAGES
    ]
    for action in app_language.items:
        assert action.kind is manifest.Kind.PAGE
        assert action.checkable is True


def test_each_language_item_labels_itself_with_its_own_autonym(app: manifest.Manifest) -> None:
    """``LANGUAGES`` itself is the source: "English"/"Deutsch", never translated versions of each other's name."""
    assert dict(manifest.LANGUAGES) == {"en": "English", "de": "Deutsch"}


def test_helps_shared_shape_is_identical_in_every_app(app: manifest.Manifest) -> None:
    """Ask ai, then the two D125 stubs, then About — only the About dialog's own title differs per app."""
    help_menu = app.menu("Help")
    assert action_ids(help_menu) == ["help.ask", "help.how-to", "help.docs", "help.about"]
    about = next(a for a in help_menu.all_actions() if a.id == "help.about")
    assert about.label.startswith("About Claudia ")


def test_composes_format_offers_the_style_actions_the_lists_and_the_document_colours(
    composes: manifest.Manifest,
) -> None:
    assert labels(composes.menu("Format")) == ["Apply Style…", "Edit This Style…", "All Styles…", "List", "Colours…"]


def test_every_app_has_the_list_flyout_of_the_web(app: manifest.Manifest) -> None:
    """UX-36: Format ▸ List ▸ was on the web only. It is in every app, as on the web; outside a text the page reports
    its entries disabled."""
    (flyout,) = [e for e in entries(app.menu("Format")) if isinstance(e, Submenu) and e.label == "List"]
    assert [a.id for a in flyout.items] == [
        "format.bulleted-list",
        "format.numbered-list",
        "format.list-continue",
        "format.list-start",
        "format.list-indent",
        "format.list-outdent",
    ]


def test_composes_view_has_page_after_the_shared_block(composes: manifest.Manifest) -> None:
    section = composes.menu("View").sections[1]
    assert all(isinstance(e, Action) for e in section), f"expected only plain actions, got {section!r}"
    assert [e.id for e in section if isinstance(e, Action)] == ["view.page"]


@pytest.mark.parametrize("app_name", ["computes", "creates"])
def test_every_app_offers_the_same_three_format_actions(app_name: str, request: pytest.FixtureRequest) -> None:
    """Was a single inert stub while only composes had styles (D125). All three have them now (D203), and the
    colours a document is painted from are the same dialog everywhere (D200), so the menu is the same everywhere
    too — what differs is what a style is *of*: a paragraph in composes, a floating object in the other two.
    The two that have floating objects also say what an object shows to someone who cannot see it (BITV 1.1.1)."""
    m = request.getfixturevalue(app_name)
    styles = ["format.apply-style"] + (["format.clear-cell-style"] if app_name == "computes" else [])
    assert [
        a.id for a in m.menu("Format").all_actions() if not a.id.startswith(("format.list", "format.bul", "format.num"))
    ] == [
        *styles,
        "format.look",
        "format.all-styles",
        "format.colours",
        "format.describe",
    ]


@pytest.mark.parametrize("app_name", ["computes", "creates"])
def test_describe_object_is_a_page_action_with_its_own_key(app_name: str, request: pytest.FixtureRequest) -> None:
    """Every menu entry has a key (project rule): Ctrl+Alt+D, the chord the page binds to the same action."""
    m = request.getfixturevalue(app_name)
    describe = m.action("format.describe")
    assert describe.kind is Kind.PAGE and describe.label == "Describe Object…"
    assert describe.accelerators == ("<Primary><Alt>d",)
    assert "format.describe" not in action_ids(request.getfixturevalue("composes").menu("Format"))


@pytest.mark.parametrize("app_name", ["composes", "computes", "creates"])
def test_apply_style_is_one_page_action_that_opens_the_pages_popover(
    app_name: str, request: pytest.FixtureRequest
) -> None:
    """D301: no native list of styles and no new contract message — one page action, as All Styles… is."""
    m = request.getfixturevalue(app_name)
    (apply,) = [a for a in m.menu("Format").all_actions() if a.id == "format.apply-style"]
    assert apply.kind is Kind.PAGE and apply.label == "Apply Style…"
    first = [e.id for e in m.menu("Format").sections[0] if isinstance(e, Action)]
    clear = ["format.clear-cell-style"] if app_name == "computes" else []
    assert first == ["format.apply-style", *clear, "format.look", "format.all-styles"]


def test_computes_edit_has_search_then_new_sheet_then_row_and_column_submenus_then_clear(
    computes: manifest.Manifest,
) -> None:
    """D123 (where new items land) and D130 (confirmed by the owner 2026-11-10 — grouped
    into two submenus of three items each, not six flat items); E5.15 put Search & Replace… ahead of them."""
    edit = computes.menu("Edit")
    tail = entries(edit)[6:]  # past the shared Undo…Paste-as block
    assert [e.label for e in tail] == [
        "Search & Replace…",
        "New Sheet…",
        "Image…",  # UX-36: Image… and Chart… were on the web only
        "Chart…",
        "Row",
        "Column",
        "Clear Cells",
    ]
    row, column = tail[4], tail[5]
    assert isinstance(row, Submenu)
    assert [a.id for a in row.items] == ["edit.row-insert-above", "edit.row-insert-below", "edit.row-delete"]
    assert isinstance(column, Submenu) and [a.id for a in column.items] == [
        "edit.column-insert-left",
        "edit.column-insert-right",
        "edit.column-delete",
    ]


def test_computes_search_and_replace_is_a_page_action_with_ctrl_f(computes: manifest.Manifest) -> None:
    """E5.15, D281: the web page owns the panel, so the entry is a page action with the shortcut the menu shows."""
    (search,) = [a for a in computes.menu("Edit").all_actions() if a.id == "edit.search-replace"]
    assert search.kind is Kind.PAGE
    assert search.accelerators == ("<Primary>f",)


def test_creates_edit_has_new_slide_edit_text_text_box_then_delete(creates: manifest.Manifest) -> None:
    """D123. The shape library itself is dynamic (one entry per document) and, like composes' style names, is
    deliberately not a static manifest entry — see this module's own docstring and ``manifest.py``'s."""
    edit = creates.menu("Edit")
    tail = [e.label for e in entries(edit)[6:]]
    assert tail == ["New Slide", "Edit Text", "Text Box", "Image…", "Delete"]  # Image… was on the web only (UX-36)


# ------------------------------------------------------------------------------------------------- ids and actions


def test_every_action_id_is_a_valid_contract_action(app: manifest.Manifest) -> None:
    for action in app.actions:
        contract.action(action.id)  # raises on a bad id


def test_action_ids_are_unique(app: manifest.Manifest) -> None:
    ids = [action.id for action in app.actions]
    assert len(ids) == len(set(ids))


def test_a_submenu_itself_has_no_id_or_kind_only_its_items_do(app: manifest.Manifest) -> None:
    for menu in app.menus:
        for section in menu.sections:
            for entry in section:
                if isinstance(entry, Submenu):
                    assert not hasattr(entry, "id") and not hasattr(entry, "kind")
                    assert entry.items, f"{menu.label} ▸ {entry.label} has no items"


def test_ids_do_not_depend_on_the_menu_an_action_sits_in(composes: manifest.Manifest) -> None:
    """Moving an item to another menu must not change the contract: Format holds 'format.look', not 'style.look'."""
    assert {"format.look", "format.all-styles"} <= {a.id for a in composes.menu("Format").all_actions()}


def test_accelerators_are_well_formed_and_not_shared(app: manifest.Manifest) -> None:
    seen: dict[str, str] = {}
    for action in app.actions:
        for accel in action.accelerators:
            assert re.fullmatch(r"(<(Primary|Shift|Alt)>)*[A-Za-z0-9_]+", accel), accel
            assert accel not in seen, f"{accel} is on {seen[accel]} and {action.id}"
            seen[accel] = action.id


def test_every_menu_entry_has_a_key_but_the_language_names(app: manifest.Manifest) -> None:
    """The project rule (UX-35): every menu entry has a key shortcut. The language picker's entries are each a
    language's own name, as many as there are catalogs; they are the one exception."""
    missing = [a.id for a in app.actions if not a.accelerators and not a.id.startswith("config.language.")]
    assert not missing, missing


def test_one_action_has_one_key_in_every_app():
    """UX-35: the same entry has the same key in composes, computes and creates."""
    keys: dict[str, tuple[str, ...]] = {}
    for build in BUILDERS.values():
        for action in build().actions:
            assert keys.setdefault(action.id, action.accelerators) == action.accelerators, action.id


def test_only_the_shells_own_keys_are_bound_natively(app: manifest.Manifest) -> None:
    """The page listens for every other key in every client, by the same table (`web/app/lib/keys.generated.ts`). A
    key the shell bound too would never reach the page (GTK takes application keys before the web view), so it would
    lose the page's rules: no shortcut while typing in a field, the right thing in the right place."""
    native = {a.id for a in app.actions if a.key_owner is KeyOwner.SHELL}
    assert native == {"file.quit", "help.about", "format.look"}
    for action in app.actions:
        if action.kind is Kind.SHELL:
            assert action.key_owner is KeyOwner.SHELL, action.id


def test_no_key_is_one_a_browser_keeps_or_alt_gr_types(app: manifest.Manifest) -> None:
    """The web app is a client too: Chrome and Firefox never hand Ctrl+N, Ctrl+W, Ctrl+T (with or without Shift) to a
    page, and on Windows Ctrl+Alt is AltGr, which types @ € µ and the brackets on a German keyboard. Ctrl+Q only for
    the shells' own Quit. Ubuntu keeps Ctrl+Alt+T (terminal) and Ctrl+Alt+L (lock)."""
    for action in app.actions:
        for accel in action.accelerators:
            lowered = accel.lower()
            assert lowered not in {"<primary>n", "<primary>w", "<primary>t", "<primary><shift>n", "<primary><shift>w"}
            assert lowered not in {"<primary><shift>t", "<primary><alt>t", "<primary><alt>l"}, accel
            if "<primary><alt>" in lowered:
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


def test_checkable_actions_are_the_view_toggles_and_the_language_picker(app: manifest.Manifest) -> None:
    checkable = {a.id for a in app.actions if a.checkable}
    language_ids = {f"config.language.{tag}" for tag, _label in manifest.LANGUAGES}
    lists = {"format.bulleted-list", "format.numbered-list"}  # ticked when the paragraphs are that kind of list
    if app.app == "composes":
        assert checkable == {"view.authors", "view.panel", "view.dark", "view.page"} | lists | language_ids
    elif app.app == "computes":
        # ... and Tools ▸ Follow Computation (E6.23), which is on while a computation is followed.
        assert checkable == {"view.authors", "view.panel", "view.dark", "tools.follow"} | lists | language_ids
    else:
        assert checkable == {"view.authors", "view.panel", "view.dark", "view.grid"} | lists | language_ids


def test_composes_clipboard_actions_are_native_webkit_editing_commands(composes: manifest.Manifest) -> None:
    """Carried over unchanged from before this round (D121's scope note in ``manifest.py``)."""
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
def test_computes_and_creates_clipboard_actions_go_through_the_page_instead(
    app_name: str, request: pytest.FixtureRequest
) -> None:
    """New to the GTK shell (D121): a cell grid or a slide canvas needs its own paste logic, not WebKit's generic
    one, so these dispatch through the page like any other ``file.*``/``edit.*`` action, not natively."""
    m = request.getfixturevalue(app_name)
    for action_id in ("edit.copy", "edit.cut", "edit.paste", "edit.paste-as-plain"):
        assert m.action(action_id).kind is Kind.PAGE


# ------------------------------------------------------------------------------------------- the web app, by id


@pytest.mark.parametrize("app_name", APPS)
def test_every_page_and_editing_action_id_is_in_the_matching_web_source(app_name: str) -> None:
    """The guard against drift (see this module's docstring): if the web app renames or drops an id this shell
    still dispatches, this fails and says which. ``Kind.SHELL`` actions (Quit, About) have no web equivalent by
    design — the shell intercepts them before they would ever reach the page — so they are not checked here."""
    sources = (WEB_SOURCES[app_name], WEB_SHARED_MENUS, WEB_FORMAT_MENU, WEB_LANGUAGES)
    if not all(path.exists() for path in sources):
        pytest.skip("the web sources are not next to the client")
    app_source, shared_menus, format_menu, languages_source = (path.read_text(encoding="utf-8") for path in sources)
    assert "formatItems(" in app_source, "every app builds its Format menu with lib/format-menu.ts"
    shared_source = shared_menus + format_menu

    def in_web(action_id: str) -> bool:
        if f"id: '{action_id}'" in app_source or f"id: '{action_id}'" in shared_source:
            return True
        tag = action_id.removeprefix("config.language.")
        return (
            tag != action_id and "id: `config.language.${tag}`" in shared_source and f"['{tag}', " in languages_source
        )

    missing = [a.id for a in BUILDERS[app_name]().actions if a.kind is not Kind.SHELL and not in_web(a.id)]
    assert not missing, f"{app_name}: the web app no longer has " + ", ".join(missing)


# ------------------------------------------------------------------------------------------------- GMenu XML


def test_the_gmenu_xml_has_one_menu_per_manifest_menu_in_order(app: manifest.Manifest) -> None:
    root = ET.fromstring(manifest.menu_xml(app))
    assert root.tag == "interface"
    assert [m.get("id") for m in root.findall("menu")] == [menu.id for menu in app.menus]


def test_menu_items_call_window_actions_and_are_translatable(app: manifest.Manifest) -> None:
    root = ET.fromstring(manifest.menu_xml(app))
    items = root.findall(".//item")
    assert len(items) == sum(1 for menu in app.menus for _ in menu.all_actions())
    for item in items:
        attributes = {a.get("name"): a for a in item.findall("attribute")}
        assert (attributes["action"].text or "").startswith("win.")
        assert attributes["label"].get("translatable") == "yes"


def test_a_submenu_renders_as_a_nested_gmenu_submenu_with_its_own_section(computes: manifest.Manifest) -> None:
    """D130/the schema's one new capability: ``<submenu>`` nested in a ``<section>``, GTK's own flyout shape — the
    same thing ``MenuBar.vue``'s ``items`` property draws on the web side."""
    root = ET.fromstring(manifest.menu_xml(computes))
    edit_menu = root.find("menu[@id='menu-edit']")
    assert edit_menu is not None
    submenus = edit_menu.findall(".//submenu")
    labels_found = {s.findtext("attribute[@name='label']") for s in submenus}
    assert {"Paste As", "Row", "Column"} <= labels_found
    row = next(s for s in submenus if s.findtext("attribute[@name='label']") == "Row")
    row_items = row.findall("section/item")
    assert len(row_items) == 3
    assert all((i.findtext("attribute[@name='action']") or "").startswith("win.edit.row-") for i in row_items)


def test_sections_become_gmenu_sections_so_that_separators_are_drawn(app: manifest.Manifest) -> None:
    root = ET.fromstring(manifest.menu_xml(app))
    file_menu = root.find("menu[@id='menu-file']")
    assert file_menu is not None
    assert len(file_menu.findall("section")) == len(app.menu("File").sections) > 1


def test_menu_xml_defaults_to_no_translation_at_all() -> None:
    """Every other test in this module calls ``menu_xml``/``menu_elements`` with no ``translate`` and still gets
    plain English back — the default is the identity function, so none of this module needs a locale installed."""
    root = ET.fromstring(manifest.menu_xml(manifest.composes()))
    label = root.find(".//menu[@id='menu-file']//item/attribute[@name='label']")
    assert label is not None and label.text == "New"


def test_a_translate_function_is_applied_to_item_and_submenu_labels() -> None:
    loud = {"New": "NEW", "Manage": "MANAGE"}.get
    root = ET.fromstring(manifest.menu_xml(manifest.composes(), translate=lambda s: loud(s) or s))
    new_item = root.find(".//menu[@id='menu-file']//item/attribute[@name='label']")
    assert new_item is not None and new_item.text == "NEW"
    manage_submenu = root.find(".//menu[@id='menu-file']//submenu/attribute[@name='label']")
    assert manage_submenu is not None and manage_submenu.text == "MANAGE"


def test_a_translate_function_never_touches_the_language_pickers_own_autonyms() -> None:
    """``config.language.en``/``config.language.de``'s labels are ``LANGUAGES``' own autonyms, not English UI text —
    translating them would be exactly the mistake this module's docstring calls out."""
    shout_everything = str.upper
    root = ET.fromstring(manifest.menu_xml(manifest.composes(), translate=shout_everything))
    config_menu = root.find(".//menu[@id='menu-config']")
    assert config_menu is not None
    language_labels = {
        item.findtext("attribute[@name='label']")
        for item in config_menu.findall(".//submenu/section/item")
        if (item.findtext("attribute[@name='action']") or "").startswith("win.config.language.")
    }
    assert language_labels == {"English", "Deutsch"}


def test_special_characters_in_a_label_are_escaped() -> None:
    odd = manifest.Manifest(
        app="composes",
        menus=(manifest.Menu("Tools", ((manifest.Action("tools.odd", "Fish & <Chips>", Kind.SHELL),),)),),
    )
    root = ET.fromstring(manifest.menu_xml(odd))
    label = root.find(".//item/attribute[@name='label']")
    assert label is not None and label.text == "Fish & <Chips>"


def test_the_manifest_can_be_listed_for_the_page_and_the_docs(app: manifest.Manifest) -> None:
    listing = app.describe()
    assert listing["app"] == app.app
    assert listing["menus"][0]["label"] == "File"
    json.dumps(listing)  # plain data, including any submenu's nested "items"
    paste_as = next(e for e in listing["menus"][1]["sections"][1] if e.get("label") == "Paste As")
    assert paste_as["items"][0]["id"] == "edit.paste-as-plain"


def test_role_is_in_the_listing_so_the_macos_client_can_read_it_without_importing_this_module(
    app: manifest.Manifest,
) -> None:
    """The macOS client (``clients/macos``) has no PyGObject and no reason to import this GTK-adjacent package at
    run time; it reads ``describe()``'s JSON instead (``clients/macos/tools/generate_menu.py``). ``role`` has to
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


def test_an_app_without_a_manifest_is_a_clear_error_naming_the_available_ones() -> None:
    from claudia_shell_gtk import identity

    with pytest.raises(identity.UnknownApp) as problem:
        manifest.for_app("drawbook")
    assert "composes" in str(problem.value)


def test_computes_tools_menu_has_random_outcomes_and_follow_entries_each_with_a_key(
    computes: manifest.Manifest,
) -> None:
    """E6.21–E6.23: every menu entry has a shortcut (project rule); F9 keeps Excel's meaning of "draw again"."""
    keys = {
        "tools.random": ("<Primary><Alt>r",),
        "tools.resample": ("F9",),
        "tools.outcomes": ("<Primary><Alt>o",),
        "tools.follow": ("<Primary><Alt>f",),
    }
    for action_id, accelerators in keys.items():
        assert computes.action(action_id).accelerators == accelerators, action_id
        assert computes.action(action_id).kind is Kind.PAGE, action_id


# UX-36: the other direction. Entries that are only a flyout's parent (they have an id for the web's own drawing, not
# an action) are named, with the reason, so that nothing else can be web-only without someone saying so here.
WEB_ONLY_PARENTS = {
    "file.manage": "File ▸ Manage ▸ is a Submenu here (no id, no action)",
    "edit.paste-as": "Edit ▸ Paste As ▸ is a Submenu here",
    "edit.row": "computes' Edit ▸ Row ▸ is a Submenu here",
    "edit.column": "computes' Edit ▸ Column ▸ is a Submenu here",
}


@pytest.mark.parametrize("app_name", APPS)
def test_every_web_menu_entry_is_in_the_desktop_menus_too(app_name: str) -> None:
    """At cfa2d91 File ▸ Print…, Image…, Chart…, Names…, SQL Query…, Show Grid and the List flyout were on the web
    only, and the desktop shells hide the web menu bar: on the desktop they could not be found. A menu item on the web
    is `{ id: '…', label: … }`; a keyboard shortcut (`get label()`) is not a menu item."""
    sources = (WEB_SOURCES[app_name], WEB_SHARED_MENUS, WEB_FORMAT_MENU)
    if not all(path.exists() for path in sources):
        pytest.skip("the web sources are not next to the client")
    app_source, shared_menus, format_menu = (path.read_text(encoding="utf-8") for path in sources)
    item = re.compile(r"\{\s*id: '([a-z.-]+)',\s*label:")
    ids = set(item.findall(app_source)) | set(item.findall(format_menu)) | set(item.findall(shared_menus))
    ids |= {"file.manage", "edit.paste-as"} & set(re.findall(r"id: '([a-z.-]+)',\n", shared_menus))
    if "print: " not in app_source:  # File ▸ Print… is only in the apps that hand the shared File menu a `print`
        ids.discard("file.print")
    if "searchItem(" not in app_source:  # Edit ▸ Search & Replace… is shared, and only computes searches so far
        ids.discard("edit.search-replace")
    native = {a.id for a in BUILDERS[app_name]().actions}
    missing = sorted(ids - native - set(WEB_ONLY_PARENTS))
    assert not missing, f"{app_name}: on the web menus but not on the desktop's: {missing}"


def test_the_gmenu_xml_shows_every_key_whoever_listens_for_it(app: manifest.Manifest) -> None:
    """GTK draws an item's ``accel`` attribute beside its label without binding it: the menu shows the page's keys too
    (UX-35), which before only the web menu did."""
    root = ET.fromstring(manifest.menu_xml(app))
    shown = {}
    for item in root.iter("item"):
        attributes = {a.get("name"): a.text for a in item.findall("attribute")}
        shown[str(attributes["action"]).removeprefix("win.")] = attributes.get("accel")
    assert shown["file.print" if app.app != "computes" else "edit.new-sheet"] is not None
    for action in app.actions:
        assert shown[action.id] == (action.accelerators[0] if action.accelerators else None), action.id
