"""The menu and action manifest of every client (E5.1 / E5.10, D1643): one list from which all menus are built.

It lives in ``clients/contract`` beside the shell contract because it belongs to every client: the Linux client turns
it into GtkBuilder XML (``claudia_shell_gtk/menu_xml.py``), ``clients/neutralino/tools/generate_menu.py`` into the
macOS and Windows menus, and ``scripts/generate_menus.py`` into the web app's key table.


D120 gives every app the same seven header-bar menus — File, Edit, Format, View, Tools, Preferences (called Config
until E7.11; its action ids still start with ``config.``), Help — superseding D4's four. An action has an id that
names *what it does* (``file.save``, ``view.page``) and not where it sits, so a menu can be rearranged without
touching the shell contract, and so the *same* id means the same thing on the web side
(``web/app/lib/menu-dispatch.ts``) and here. Each action is carried out by one party (:class:`Kind`).

Nothing here imports GTK: the menus are described as data and turned into GtkBuilder XML by the Linux client, so the
layout stays in XML (D27) and the manifest can be tested anywhere. :func:`composes` already shipped; :func:`computes`
and :func:`creates` are new (D121) — neither has a GTK window or application class yet (E5.1's scope cut, see
``claudiaoffice-log/notes/e5-1-e5-10-menus-and-accessibility.md``), so these two are exercised only as data today.

A note on what is deliberately *not* here, following the one precedent this file already had (composes' Format menu
never listed a style by name): nothing data-driven gets a static entry. Dynamic, per-document content — composes'
and computes' style names, creates' shape library — has no id and no `Action` of its own on the web side either
(``lib/menu-dispatch.ts``'s `collectStates`/`findMenuItem` walk explicitly skip id-less items); a shell reaches that
content through its one real submenu-shaped escape hatch (composes: "All Styles…") rather than the static menu
growing one entry per document. Format ▸ Apply Style… is the same escape hatch for applying a style: one page action
that opens the page's own popover with the styles drawn in their looks (D300, D301), never a native list of them.
The same reasoning drops the "visible but inert" stub items (D125) from the
*accelerator* story but not from the menu itself: ``help.how-to`` and ``help.docs`` below are
ordinary ``Kind.PAGE`` actions the shell greys out the moment the page connects (``set_action_states``, driven by the
page's own ``collectStates`` — nothing shell-side needs to know they are permanent stubs rather than temporarily
disabled ones).

A second note, added for Preferences ▸ App Language (E5.7, D31/D148's groundwork, D160): translation itself is applied
by the Linux client's ``menu_xml``/``menu_elements``, not here — this module still imports no gettext, stays pure data,
and is tested without any locale installed. The one deliberate exception is :data:`LANGUAGES` itself: each entry's own
name is its autonym ("Deutsch", not "German" from an English catalog) and is never run through ``translate``, the same
universal convention every OS and browser language picker already follows, so ``_item_element`` and
``scripts/extract_i18n.py``'s manifest walk both skip any action whose id starts with ``"config.language."``.
"""

from __future__ import annotations

import enum
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from typing import Any

__all__ = [
    "Action",
    "Kind",
    "KeyOwner",
    "LANGUAGES",
    "REFERENCE_SHOWS",
    "Manifest",
    "Menu",
    "Submenu",
    "UnknownApp",
    "composes",
    "computes",
    "creates",
    "for_app",
    "for_start",
    "on_start",
    "about_links",
    "visible_only",
]


class UnknownApp(KeyError):
    """There is no manifest for the app asked for; the message names the ones there are."""


Translate = Callable[[str], str]
"""A label translator, usually ``i18n.translate`` — defaults to the identity everywhere below, so every function
here stays callable (and testable) with no locale installed at all."""

LANGUAGES: tuple[tuple[str, str], ...] = (("en", "English"), ("de", "Deutsch"))
"""The language picker's own short, explicit list for Preferences ▸ App Language — exactly the catalogs that exist
(``po/en`` is the source text itself, ``po/de.po``), extended by adding one more ``(tag, autonym)`` pair here, a new
``po/<tag>.po``, and the matching items in each workspace's own ``menus`` (``web/app/lib/menu-dispatch.ts``'s drift
guard, ``tests/test_manifest.py``). Not a directory scan: two catalogs do not justify one, and an explicit list
can never show a half-finished catalog nobody meant to ship yet."""

WEBSITE = "https://www.claudia-office.de"
ISSUES = "https://github.com/claudiaoffice/claudia/issues"
LEGAL = "https://github.com/claudiaoffice/claudia/blob/main/LICENSE"


def about_links(translate: Translate = lambda text: text) -> tuple[tuple[str, str], ...]:
    """The three outbound links every About dialog shows, in this order (D28, the owner's 2026-11-06 report that the
    web and Linux About dialogs had drifted apart): data, so both can be tested without GTK (``window.py``'s
    ``_show_about`` is what actually builds the dialog). The licence is linked rather than shown in full here, for
    the same reason ``claudiaoffice-log/notes/README.md`` gives for not duplicating generated content elsewhere: a
    second copy of the licence text cannot be kept true and competes with the one in the repository.

    Web's own copy of this list is ``AboutDialog.vue``'s ``LINKS`` — there is no shared manifest for the two shells
    to read this from, so a change here needs the same change made there by hand.
    """
    return ((translate("Website"), WEBSITE), (translate("Report an Issue"), ISSUES), (translate("Legal"), LEGAL))


class Kind(enum.Enum):
    """Who carries an action out."""

    PAGE = "page"
    """The web page does it, when the shell sends it an ``action`` message (shell contract)."""
    SHELL = "shell"
    """The shell does it itself (quit, About)."""
    EDITING = "editing"
    """The web view's own editing machinery does it (WebKit editing commands such as cut, copy, paste)."""


class KeyOwner(enum.Enum):
    """Who listens for an action's key (UX-35, D360). The key itself is the same in every client: the web app, and the
    Linux, Windows and macOS shells, which show it in their menus."""

    PAGE = "page"
    """The page listens, in every client (``web/app/lib/menus.generated.ts``, made from this manifest). A shell only
    shows the key: binding it too would take it away from the page's own rules (no shortcut while typing in a
    field)."""
    SHELL = "shell"
    """The shell binds the key itself and sends the action. That is Quit, About, and the one key a web view would
    otherwise keep for its own context menu (Shift+F10)."""
    VIEW = "view"
    """The document view or the browser handles the key where it is pressed (Enter, Delete, Tab, the clipboard). Shown
    in the menus, listened for by nobody else."""


@dataclass(frozen=True, slots=True)
class Keys:
    """An action's key, in GTK's notation, the same in every app (UX-35, D360): ``default`` on Linux, Windows and the
    web, and ``macos`` where macOS keeps the default's key for itself (D1616, D1648). There ``<Primary>`` is Cmd and
    ``<Control>`` is Ctrl; without it macOS takes the default with Cmd for Ctrl and Option for Alt."""

    default: str | None = None
    macos: str | None = None


@dataclass(frozen=True, slots=True)
class Action:
    """One menu item. The same action may stand in more than one place (Edit ▸ Copy and an object's Copy): its id,
    kind and keys are the same everywhere, its label and its rule (:attr:`fits`) are those of the place."""

    id: str
    """``file.save``: lower case, namespaced, independent of the menu it sits in (see the shell contract)."""
    label: str
    """English label in the capitalisation of the GNOME HIG; it is the key that translations are looked up by (E5.7)."""
    kind: Kind
    tooltip: str = ""
    keys: Keys = Keys()
    """Who listens for the key is :attr:`key_owner`. No key only where an action has none on purpose: the language
    picker's own autonyms, and an entry of a context menu that no menu entry shares (D1614)."""
    checkable: bool = False
    editing: str | None = None
    """For :attr:`Kind.EDITING`: the name of the WebKit editing command (``Cut``, ``Copy``, ``Paste``, ...)."""
    role: str | None = None
    """The Cocoa selector (``copy:``, ``cut:``, ``paste:``, ``undo:``, ``redo:``) a macOS shell puts on this item
    next to its accelerator (D158). GTK ignores it; it is carried here, rather than kept only in the macOS client, so
    one manifest stays the single source for every shell (the module docstring's reason for existing at all) and
    ``describe()`` can hand it to a shell that never imports this package (``clients/neutralino``). Unset for everything
    that is not a standard editing command — macOS has no selector for "paste as plain text" or an app's own
    commands, and giving those a Cocoa role would route the key to a native editing action with no page effect."""
    key_owner: KeyOwner = KeyOwner.PAGE
    """Who listens for :attr:`keys`: see :class:`KeyOwner`."""
    fits: str = ""
    """When the entry fits, in the workbook's words, word for word (D1601, D1605, D1646): ``"role: editor or owner ·
    selection: something"``. The page judges it; ``scripts``' workbook test holds it to the workbook."""


@dataclass(frozen=True, slots=True)
class Submenu:
    """A flyout inside a menu: Edit ▸ Paste as ▸ (every app, D120) and computes' Edit ▸ Row ▸ / Column ▸
    (D130).

    GTK's own menu format nests these natively (a ``<submenu>`` inside a ``<menu>``'s section) — the same one extra
    level of nesting ``MenuBar.vue`` grew for exactly this (``claudiaoffice-log/notes/mockups/menu-bar-states.svg``,
    panel E). A ``Submenu`` carries no id and is never itself a GTK action — only its ``items`` are.
    """

    label: str
    items: tuple[Action, ...]


MenuEntry = Action | Submenu


def _actions_of(sections: tuple[tuple[MenuEntry, ...], ...]) -> Iterator[Action]:
    for section in sections:
        for entry in section:
            if isinstance(entry, Submenu):
                yield from entry.items
            else:
                yield entry


@dataclass(frozen=True, slots=True)
class Menu:
    """A menu button of the header bar. ``sections`` are groups drawn with a separator between them."""

    label: str
    sections: tuple[tuple[MenuEntry, ...], ...]

    @property
    def word(self) -> str:
        """The menu's one word in lower case (``insert``): how the page names it to a shell, as a menu with nothing
        left (the contract's ``action_state.empty``, D1645)."""
        return self.label.lower()

    @property
    def id(self) -> str:
        """The id of the menu in the generated XML (``menu-file``)."""
        return f"menu-{self.word}"

    def all_actions(self) -> Iterator[Action]:
        """Every actionable item of the menu, in order — a :class:`Submenu`'s own ``items``, not the ``Submenu``
        itself, which has no id and backs no GTK action."""
        return _actions_of(self.sections)


@dataclass(frozen=True, slots=True)
class ContextMenu:
    """The menu of a right press on a thing (D1602, D1612, D1619): ``id`` names the thing (``object``, ``cell``,
    ``pivot``), ``label`` is what Preferences ▸ Shortcuts calls it (D1604). The page draws it in every client."""

    id: str
    label: str
    sections: tuple[tuple[MenuEntry, ...], ...]

    def all_actions(self) -> Iterator[Action]:
        """Every actionable item, in order."""
        return _actions_of(self.sections)


@dataclass(frozen=True, slots=True)
class Manifest:
    """All menus of one app, and the toggle buttons that sit in the header bar next to them."""

    app: str
    menus: tuple[Menu, ...]
    header_toggles: tuple[Action, ...] = field(default=())
    context_menus: tuple[ContextMenu, ...] = field(default=())
    keys_only: tuple[Action, ...] = field(default=())
    """Keys whose entry left the menus while the key stayed (the workbook's sheet "Keys without entry")."""

    @property
    def actions(self) -> tuple[Action, ...]:
        """Every action once, where it first stands: the menus, the header-bar toggles, the context menus, then the
        keys without an entry."""
        seen: dict[str, Action] = {}
        everywhere = (
            *(a for menu in self.menus for a in menu.all_actions()),
            *self.header_toggles,
            *(a for context in self.context_menus for a in context.all_actions()),
            *self.keys_only,
        )
        for action in everywhere:
            seen.setdefault(action.id, action)
        return tuple(seen.values())

    def menu(self, label: str) -> Menu:
        """The menu called ``label``."""
        for menu in self.menus:
            if menu.label == label:
                return menu
        raise KeyError(label)

    def action(self, action_id: str) -> Action:
        """The action with this id."""
        for action in self.actions:
            if action.id == action_id:
                return action
        raise KeyError(action_id)

    def describe(self) -> dict[str, Any]:
        """The manifest as plain data (for the documentation and for tools that compare shells)."""

        def one(action: Action) -> dict[str, Any]:
            return {
                "id": action.id,
                "label": action.label,
                "kind": action.kind.value,
                "checkable": action.checkable,
                "accelerators": [action.keys.default] if action.keys.default else [],
                "key_macos": action.keys.macos,
                "key_owner": action.key_owner.value,
                "role": action.role,
                "start": on_start(action.id),
                "fits": action.fits,
            }

        def entry(e: MenuEntry) -> dict[str, Any]:
            if isinstance(e, Submenu):
                return {"label": e.label, "items": [one(a) for a in e.items]}
            return one(e)

        def sections(of: tuple[tuple[MenuEntry, ...], ...]) -> list[list[dict[str, Any]]]:
            return [[entry(e) for e in section] for section in of]

        return {
            "app": self.app,
            "menus": [
                {"word": menu.word, "label": menu.label, "sections": sections(menu.sections)} for menu in self.menus
            ],
            "header_toggles": [one(a) for a in self.header_toggles],
            "context_menus": [
                {"id": c.id, "label": c.label, "sections": sections(c.sections)} for c in self.context_menus
            ],
            "keys_only": [one(a) for a in self.keys_only],
        }


_START_ACTIONS = frozenset({"file.new", "file.open", "file.open-file", "file.quit", "view.dark", "help.about"})


def on_start(action_id: str) -> bool:
    """Does the action belong in the menu of the front page, where no document is open (sheet 11)? New, Open…,
    Open a File… and Quit; Dark Mode; App Language; About. Everything else needs a document."""
    return action_id in _START_ACTIONS or action_id.startswith("config.language.")


def visible_only(manifest: Manifest, keep: Callable[[str], bool]) -> Manifest:
    """The menus of ``manifest`` with only the actions ``keep`` keeps (slice 6 of the menu work, D1645): no empty
    section or flyout, so no separator comes first, last or twice (``clients/contract/fixtures/menu-collapse.json``).
    A menu with nothing left stays, with no sections: its title never goes (D1603), and the shell shows why."""

    def kept(entry: MenuEntry) -> MenuEntry | None:
        if isinstance(entry, Submenu):
            items = tuple(a for a in entry.items if keep(a.id))
            return replace(entry, items=items) if items else None
        return entry if keep(entry.id) else None

    def sections(menu: Menu) -> tuple[tuple[MenuEntry, ...], ...]:
        cut = (tuple(e for e in (kept(entry) for entry in section) if e is not None) for section in menu.sections)
        return tuple(section for section in cut if section)

    return replace(manifest, menus=tuple(replace(menu, sections=sections(menu)) for menu in manifest.menus))


def for_start(manifest: Manifest) -> Manifest:
    """The short menu of the front page (sheet 11): only the actions :func:`on_start` keeps, and no menu with nothing
    in it — Edit, Format and Tools disappear rather than show greyed-out entries. The shells show it while the page
    has said ``hello`` with ``view: "start"``, and the whole manifest for a document."""
    shown = visible_only(manifest, on_start)
    menus = tuple(menu for menu in shown.menus if menu.sections)
    return replace(shown, menus=menus, header_toggles=(), context_menus=(), keys_only=())


def _page(
    action_id: str,
    label: str,
    tooltip: str,
    *,
    fits: str,
    key: str | None = None,
    mac: str | None = None,
    checkable: bool = False,
    role: str | None = None,
    key_owner: KeyOwner = KeyOwner.PAGE,
) -> Action:
    return Action(
        action_id,
        label,
        Kind.PAGE,
        tooltip,
        Keys(key, mac),
        checkable,
        role=role,
        key_owner=key_owner,
        fits=fits,
    )


def _shell(action_id: str, label: str, tooltip: str, *, key: str, fits: str) -> Action:
    return Action(action_id, label, Kind.SHELL, tooltip, Keys(key), key_owner=KeyOwner.SHELL, fits=fits)


def _here(action: Action, label: str | None = None, *, fits: str) -> Action:
    """``action`` in another place, with that place's words and rule (D1605): its id, kind and key stay."""
    return replace(action, label=label or action.label, fits=fits)


# The rules of the workbook's "Fits when" column that many entries share (D1601, D1615).
ANYONE = "role: anyone"
EDITORS = "role: editor or owner"
SELECTED = f"{EDITORS} · selection: something"
CELLS = f"{EDITORS} · selection: a cell or range"
# what is selected, or the paragraph the cursor is in: what a style is for (a caret is not "something", D1601; D1654)
HERE = f"{EDITORS} · selection: something, or the cursor in a text"
LIST_ITEM = f"{EDITORS} · selection: a list item"

# --------------------------------------------------------------------------------------------- shared across apps
# The menus follow the workbook ``claudiaoffice-log/notes/claudia-menus.xlsx`` (D1605): its rows, groups, words,
# keys and rules, which ``tests/test_menu_workbook.py`` compares with this file. The labels are in the GNOME HIG's
# header capitalisation (D1609), with "…" where a dialog opens first (D1618).
#
# The keys (UX-35, D360, D1617) are one table for the three apps and every client. They keep out of the way of what a
# browser keeps for itself (Ctrl+N, Ctrl+W, Ctrl+T, Ctrl+Q never reach a page), of what Ctrl+Alt types on a German
# Windows keyboard (AltGr: Q, E, M and the digits), and of the desktop's own (Ctrl+Alt+T, Ctrl+Alt+L on Ubuntu). An
# app's own commands are Ctrl+Alt+letter, the rare and weighty ones Ctrl+Shift+Alt+letter.

UNDO = _page(
    "edit.undo",
    "Undo",
    "Take back your last step",
    key="<Primary>z",
    role="undo:",
    fits=f"{EDITORS} · document: something to undo",
)
REDO = _page(
    "edit.redo",
    "Redo",
    "Do your last undone step again",
    key="<Primary><Shift>z",
    role="redo:",
    fits=f"{EDITORS} · document: something to redo",
)
DESCRIBE = _page(
    "format.describe",
    "Name & Describe…",
    "Give the thing you have selected a name, and say what it shows to someone who cannot see it",
    key="<Primary><Alt>d",
    mac="<Primary><Control>n",  # Cmd+Option+D hides the Dock (D1616)
    fits=SELECTED,
)
REFERENCE = _page(
    "edit.reference",
    "Reference in Chat",
    "Write a tag for this thing into the chat, so that everybody can go to it",
    key="<Primary><Alt>x",
    fits=EDITORS,
)
STYLE = _page(
    "format.apply-style",
    "Apply…",
    "Choose a style for the selection, each drawn in its own look",
    key="<Primary><Alt>a",
    fits=HERE,
)
ROTATE_BY = _page(
    "format.rotate-by",
    "Rotate By…",
    "Turn the object you have selected to an angle, in whole degrees",
    key="<Primary><Alt><Shift>z",  # Ctrl+Alt+Z is Replay's
    fits=f"{EDITORS} · selection: an object that can turn",
)
DELETE = _page(
    "edit.delete",
    "Delete",
    "Take away what you have selected",
    key="Delete",
    key_owner=KeyOwner.VIEW,
    fits=EDITORS,
)
ASK = _page(
    "tools.ask",
    "Ask ai…",
    "Ask the ai in the chat",
    key="<Primary>F1",
    fits=f"{ANYONE} · ai: the ai can really answer",
)


def _clipboard(*, native: bool) -> tuple[Action, Action, Action, Action]:
    """Copy, Cut, Paste and Paste As ▸ Plain Text, the same in every app (D120). The keys are the browser's own in every
    client (:attr:`KeyOwner.VIEW`): the clipboard events reach the page from there. A viewer cannot copy (D1640).

    ``native=True`` (composes) dispatches the menu item straight to WebKit's own editing commands. ``native=False``
    (computes, creates) goes through the page instead: a cell grid's paste needs to split the clipboard by tabs and
    newlines onto the current selection, and a slide canvas's paste needs to land in whichever text frame is being
    edited, neither of which WebKit's generic "insert this text here" command knows how to do.
    """
    kind = Kind.EDITING if native else Kind.PAGE

    def one(action_id: str, label: str, tooltip: str, key: str, editing: str, role: str | None, fits: str) -> Action:
        return Action(
            action_id,
            label,
            kind,
            tooltip,
            Keys(key),
            editing=editing if native else None,
            role=role,
            key_owner=KeyOwner.VIEW,
            fits=fits,
        )

    return (
        one("edit.copy", "Copy", "Copy the selection to the clipboard", "<Primary>c", "Copy", "copy:", SELECTED),
        one("edit.cut", "Cut", "Move the selection to the clipboard", "<Primary>x", "Cut", "cut:", SELECTED),
        one("edit.paste", "Paste", "Insert the clipboard", "<Primary>v", "Paste", "paste:", EDITORS),
        one(
            "edit.paste-as-plain",
            "Plain Text",
            "Insert the clipboard without formatting; with no text on it, says so",
            "<Primary><Shift>v",
            "PasteAsPlainText",
            None,
            EDITORS,
        ),
    )


def _file_menu(*, title: str) -> Menu:
    """New, Open ▸ · Save Checkpoint…, Download · Print… · Manage ▸ · Close · Quit, the desktop's only (D1616).
    Save left the menu; Assign New Owner…, Accept Ownership… and Leave Document… became Manage ▸ My Role…, one dialog
    (the owner, 2026-11-25, UX-98); Delete From Server… went to the front page's list (D1608)."""
    return Menu(
        "File",
        (
            (
                _page("file.new", "New", "Start a new document", key="<Primary><Alt>n", fits=ANYONE),
                Submenu(
                    "Open",
                    (
                        _page(
                            "file.open",
                            "Document…",
                            "Open a document from one of your places, a collection or Mine",
                            key="<Primary>o",
                            fits=ANYONE,
                        ),
                        _page(
                            "file.open-file",
                            "Import from Disk…",
                            "Open a Word, Excel, PowerPoint, OpenDocument or Claudia file from this computer",
                            key="<Primary><Shift>o",
                            fits=ANYONE,
                        ),
                    ),
                ),
            ),
            (
                _page(
                    "file.save-as",
                    "Save Checkpoint…",
                    "Make a checkpoint of the document and give it a name",
                    key="<Primary>s",
                    fits=EDITORS,
                ),
                _page(
                    "file.download",
                    "Download",
                    "Download the document to this computer",
                    key="<Primary><Alt>s",
                    fits=ANYONE,
                ),
            ),
            (_page("file.print", "Print…", "See the pages and print them", key="<Primary>p", fits=ANYONE),),
            (
                Submenu(
                    "Manage",
                    (
                        _page(
                            "file.manage.share",
                            "Share…",
                            "Let other people into the document",
                            key="<Primary><Alt><Shift>s",
                            fits="role: owner",
                        ),
                        _page(
                            "file.manage.change-password",
                            "Password…",
                            "Choose a new password of your own for this document",
                            key="<Primary><Alt><Shift>w",
                            fits=ANYONE,
                        ),
                        _page(
                            "file.manage.export",
                            "Export…",
                            "Save the document in another format, or in Claudia's own",
                            key="<Primary><Alt><Shift>x",
                            fits=ANYONE,
                        ),
                        _page(
                            "file.manage.redact",
                            "Redact History…",
                            "Take content out of the document's history and chat for good",
                            key="<Primary><Shift>F8",
                            fits=EDITORS,
                        ),
                        _page(
                            "file.manage.my-role",
                            "My Role…",
                            "Hand the document over, accept it from its owner, or leave it",
                            key="<Primary><Alt><Shift>l",
                            fits=ANYONE,
                        ),
                    ),
                ),
            ),
            (_page("file.close", "Close", "Back to the list of documents", key="<Primary><Alt>w", fits=ANYONE),),
            (_shell("file.quit", "Quit", f"Close {title}", key="<Primary>q", fits="client: desktop only"),),
        ),
    )


def _edit_menu(*, native: bool, own: tuple[MenuEntry, ...] = ()) -> Menu:
    """Undo, Redo · Copy, Cut, Paste, Paste As ▸ · Name & Describe… and the app's own (``own``). What adds something
    went to Insert; Search and Replace… to Tools; Reference in Chat and Go to Target to the context menus (D1607)."""
    copy, cut, paste, plain = _clipboard(native=native)
    return Menu(
        "Edit",
        (
            (UNDO, REDO),
            (copy, cut, paste, Submenu("Paste As", (plain,))),
            (DESCRIBE, *own),
        ),
    )


def _image(where: str) -> Action:
    return _page("edit.image", "Image…", f"Put a picture {where}", key="<Primary><Alt>i", fits=EDITORS)


def _text_box(where: str) -> Action:
    return _page("edit.text-box", "Text Box", f"Add a text box {where}", key="<Primary><Alt>b", fits=EDITORS)


def _shapes() -> Submenu:
    """Insert ▸ Shape ▸, the three of the shape library that the workbook names (D1617's keys)."""
    return Submenu(
        "Shape",
        tuple(
            _page(f"insert.shape.{name.lower()}", name, f"Put a {name.lower()} here", key=key, fits=EDITORS)
            for name, key in (
                ("Circle", "<Primary><Alt><Shift>c"),
                ("Rectangle", "<Primary><Alt><Shift>r"),
                ("Triangle", "<Primary><Alt><Shift>1"),
            )
        ),
    )


def _containers() -> Submenu:
    """A container: the person writes the text and the server draws its picture (D390, D560), with the server's tool
    for it (D1601). In alphabetical order (D1618)."""

    def one(name: str, what: str, key: str) -> Action:
        return _page(
            f"insert.container.{name.lower()}",
            name,
            f"Put {what} written in {name} here",
            key=key,
            fits=f"{EDITORS} · server: has the tool for {name}",
        )

    return Submenu(
        "Container",
        (
            one("LaTeX", "a formula or text", "<Primary><Alt><Shift>f"),
            one("Mermaid", "a diagram", "<Primary><Alt><Shift>g"),
            one("Typst", "a page of text", "<Primary><Alt><Shift>y"),
        ),
    )


def _cross_reference() -> Action:
    return _page(
        "insert.cross-reference",
        "Cross Reference…",
        "Put a reference to a heading, an item or a named thing at the caret; it follows what it points at",
        key="<Primary>F2",
        fits=f"{EDITORS} · document: has something to refer to",
    )


def _contents(label: str, tooltip: str) -> Action:
    """Table of Contents in composes, Agenda in creates (E9.31)."""
    return _page("insert.contents", label, tooltip, key="<Primary><Alt><Shift>i", fits=EDITORS)


def _format_menu(*, look: str, clear_cell_style: bool = False, headings: tuple[str, str, str]) -> Menu:
    """Style ▸, List ▸ and Palette…, one shape in every app (D300). Computes adds Style ▸ Clear. ``headings`` is what
    Number Headings is called, says and needs in this app (creates: Number All Slide Titles, E9.22). Name & Describe…
    went to Edit, Rotate and Wrap Text to the object's context menu (D1602)."""
    clear = (
        (
            _page(
                "format.clear-cell-style",
                "Clear",
                "Take the selected cells' own style off, back to the table's",
                key="<Primary><Alt><Shift>k",
                fits=CELLS,
            ),
        )
        if clear_cell_style
        else ()
    )
    label, tooltip, fits = headings
    style = Submenu(
        "Style",
        (
            STYLE,
            _page("format.look", "Edit…", look, key="<Primary><Alt><Shift>h", fits=HERE),
            *clear,
            _page(
                "format.all-styles",
                "All Styles…",
                "List, rename, delete and hide the styles of this document",
                key="<Primary><Alt><Shift>a",
                fits=EDITORS,
            ),
        ),
    )
    lists = Submenu(
        "List",
        (
            _page(
                "format.bulleted-list",
                "Bulleted List",
                "Make the paragraphs a list with bullets, or plain again",
                key="<Primary><Shift>8",
                checkable=True,
                fits=f"{EDITORS} · selection: text",
            ),
            _page(
                "format.numbered-list",
                "Numbered List",
                "Make the paragraphs a numbered list, or plain again",
                key="<Primary><Shift>7",
                checkable=True,
                fits=f"{EDITORS} · selection: text",
            ),
            _page(
                "format.list-continue",
                "Continue Previous List",
                "Go on counting where the list before this one stopped",
                key="<Primary><Alt><Shift>p",
                fits=LIST_ITEM,
            ),
            _page(
                "format.list-start",
                "Start At…",
                "The number this list starts at",
                key="<Primary><Alt><Shift>n",
                fits=LIST_ITEM,
            ),
            _page(
                "format.list-indent",
                "Indent",
                "Move the item one level in",
                key="Tab",
                key_owner=KeyOwner.VIEW,
                fits=LIST_ITEM,
            ),
            _page(
                "format.list-outdent",
                "Outdent",
                "Move the item one level out",
                key="<Shift>Tab",
                key_owner=KeyOwner.VIEW,
                fits=LIST_ITEM,
            ),
            _page("format.number-headings", label, tooltip, key="<Primary><Alt><Shift>b", checkable=True, fits=fits),
            _page(
                "format.all-numbering",
                "All Numbering…",
                "The numbering schemes of this document: how each level of a list is drawn",
                key="<Primary><Alt><Shift>j",
                fits=EDITORS,
            ),
        ),
    )
    palette = _page(
        "format.colours",
        "Palette…",
        "The colours of this document, by what each one means",
        key="<Primary><Alt>k",
        fits=EDITORS,
    )
    return Menu("Format", ((style, lists, palette),))


HEADINGS = ("Number Headings", "Number every heading style: 1, 1.1, 1.2, 2 …", EDITORS)
SLIDE_TITLES = (
    "Number All Slide Titles",
    "Number the title of every slide: 1, 2, 3 …",
    f"{EDITORS} · document: has more than one slide",
)


def _view_menu(*, authors: bool, own: tuple[Action, ...] = ()) -> Menu:
    """Who Wrote What, History & Chat, Replay…, Back Where I Was, Dark Mode and the app's own views, one group.
    ``authors=False`` for computes and creates, which track no authorship yet: the page reports it disabled (D125)."""
    return Menu(
        "View",
        (
            (
                _page(
                    "view.authors",
                    "Who Wrote What",
                    "Colour the text by the person who wrote it" if authors else "Not available yet",
                    key="<Primary><Alt>u",
                    checkable=True,
                    fits=EDITORS,
                ),
                _page(
                    "view.panel",
                    "History & Chat",
                    "Show or hide the history and the chat",
                    key="<Primary><Alt>h",
                    mac="<Primary><Control>h",  # Cmd+Option+H hides the other apps (D1616)
                    checkable=True,
                    fits=ANYONE,
                ),
                _page(
                    "view.replay",
                    "Replay…",
                    "Look at the document as it was, step by step (the mouse wheel over the history does the same)",
                    key="<Primary><Alt>z",
                    fits=EDITORS,
                ),
                _page(
                    "view.back",
                    "Back Where I Was",
                    "Go back to where you were before a tag in the chat took you somewhere else",
                    key="<Primary><Shift>b",
                    fits=f"{ANYONE} · document: a place to go back to",
                ),
                _page(
                    "view.dark",
                    "Dark Mode",
                    "Follow or override the system's light/dark setting",
                    key="<Primary><Alt><Shift>d",
                    checkable=True,
                    fits=ANYONE,
                ),
                *own,
            ),
        ),
    )


def _search(describe: str) -> Action:
    """E5.15, E9.28, E10.19: the same entry and key in every app (D281); only the tooltip says what the app can look
    in. Ctrl+H opens it with Replace showing and has no entry of its own."""
    return _page("edit.search-replace", "Search and Replace…", describe, key="<Primary>f", fits=ANYONE)


def _names(tooltip: str) -> Action:
    return _page("tools.names", "Names…", tooltip, key="<Primary>F3", fits=ANYONE)


def _preferences_menu() -> Menu:
    """Shortcuts (Ctrl+? as in GNOME), AI… (E7.11, the owners' consent for Claude in this document) and App Language ▸,
    one checkable ``Kind.PAGE`` action per :data:`LANGUAGES` entry (E5.7).

    The language entries are the one place without a key: each is a language's own name, and there may be many.
    Mutual exclusion (picking one unchecks the rest) is enforced nowhere in this data — it is just ``LANGUAGES``
    many independent checkable actions, the same primitive ``view.dark`` already uses. The page is the one source of
    truth for which is active (it owns the catalog): a click sends the usual ``action`` message, the page's own
    ``menus`` recomputes every item's ``checked`` from its one ``locale`` ref, and ``collectStates`` reports all of
    them back, so ``window.py``'s ``set_action_states`` — already written to apply whatever the page reports, one id
    at a time — needs no special case to keep the native tick marks in step."""
    return Menu(
        "Preferences",
        (
            (
                _page(
                    "config.shortcuts",
                    "Shortcuts",
                    "The keyboard shortcuts of this app, and when each fits",
                    key="<Primary>question",
                    fits=ANYONE,
                ),
                _page(
                    "config.ai",
                    "AI…",
                    "Who may answer @ai in this document, and what is sent to Anthropic if Claude does (E7.11)",
                    key="<Primary><Shift><Alt>e",
                    fits=ANYONE,
                ),
                Submenu(
                    "App Language",
                    tuple(
                        _page(f"config.language.{tag}", label, "", checkable=True, fits=ANYONE)
                        for tag, label in LANGUAGES
                    ),
                ),
            ),
        ),
    )


def _help_menu() -> Menu:
    """Ask ai…, How Do I…?, Documentation, About (D120, D125, D126) — identical in every app. Ask ai… is the same
    action as in Tools, with Help's own rule. F1 is help, as everywhere."""
    return Menu(
        "Help",
        (
            (
                _here(ASK, fits="ai: the ai can really answer"),
                _page("help.how-to", "How Do I…?", "Answers to what people often want to do", key="F1", fits=ANYONE),
                _page(
                    "help.docs",
                    "Documentation",
                    "Every function and feature, to look up",
                    key="<Shift>F1",
                    fits=ANYONE,
                ),
                _shell("help.about", "About", "Version, authors and licence", key="<Primary><Shift>F1", fits=ANYONE),
            ),
        ),
    )


def _manifest(
    app: str,
    title: str,
    *,
    menus: tuple[Menu, Menu, Menu, Menu, Menu],
    context_menus: tuple[ContextMenu, ...],
    keys_only: tuple[Action, ...] = (),
) -> Manifest:
    """File, then the app's Edit, Insert, Format, View and Tools, then Preferences and Help."""
    return Manifest(
        app,
        (_file_menu(title=title), *menus, _preferences_menu(), _help_menu()),
        context_menus=context_menus,
        keys_only=keys_only,
    )


# ----------------------------------------------------------------------------------------------------- context menus
# A right press on a thing opens its menu (D1602, D1612, D1619); the first entries name and style it. The page draws
# them in every client. An entry that is also in a menu is the same action, with the place's words and rule.


def _thing(context: str, label: str, *more: tuple[MenuEntry, ...], style: bool = False) -> ContextMenu:
    """A thing's menu: Name & Describe… (Style… where it has one) and Reference in Chat, then ``more``."""
    first = (
        _here(DESCRIBE, fits=EDITORS),
        *((_here(STYLE, "Style…", fits=EDITORS),) if style else ()),
        _here(REFERENCE, fits=EDITORS),
    )
    return ContextMenu(context, label, (first, *more))


def _object_menu(*, native: bool, edit_text: bool, wrap: bool, grid: bool) -> ContextMenu:
    """A picture, text box, shape, container or chart (D1229, D1024, D1064). Its Cut and Copy are Edit's: in composes
    WebKit's, whose clipboard events the page's object clipboard hears (``object-clipboard.ts``)."""
    copy, cut, _, _ = _clipboard(native=native)
    first: tuple[MenuEntry, ...] = (
        _here(DESCRIBE, fits=EDITORS),
        _here(REFERENCE, fits=EDITORS),
        *(
            (
                _page(
                    "edit.edit-text",
                    "Edit Text",
                    "Write in the object you have selected",
                    key="Return",
                    key_owner=KeyOwner.VIEW,
                    fits=f"{EDITORS} · selection: an object that holds text",
                ),
            )
            if edit_text
            else ()
        ),
        _here(STYLE, "Style…", fits=EDITORS),
        ROTATE_BY,
        *(
            (
                _page(
                    "format.wrap-text",
                    "Wrap Text…",
                    "How the text flows round the object you have selected",
                    key="<Primary><Alt>r",
                    fits=EDITORS,
                ),
            )
            if wrap
            else ()
        ),
    )
    release = (
        _page(
            "edit.release-from-grid",
            "Release from Grid",
            "Stop this object following the layout grid",
            fits=f"{EDITORS} · selection: an object on the grid",
        ),
    )
    last = (*(release if grid else ()), DELETE)
    return ContextMenu("object", "Object", (first, (_here(cut, fits=EDITORS), _here(copy, fits=EDITORS)), last))


def _paragraph_menus() -> tuple[ContextMenu, ...]:
    """A paragraph and a list, in a text and in a text box (D1619)."""
    return (_thing("paragraph", "Paragraph", style=True), _thing("list", "List"))


#: The ways a reference can show (E9.31 step H, ``references.ts``): id, words in its Show As submenu.
REFERENCE_SHOWS = (
    ("number", "Number"),
    ("text", "Text"),
    ("number-text", "Number and Text"),
    ("page", "Page"),
    ("name", "Name"),
)


def _reference_menu() -> ContextMenu:
    """A reference, in the text or in a text box: how it shows, Go to Target (D1607) and Remove Reference (UX-99)."""
    show_as = Submenu(
        "Show As",
        tuple(
            _page(
                f"format.show-as-{show}", label, f"Show the reference as: {label.lower()}", checkable=True, fits=EDITORS
            )
            for show, label in REFERENCE_SHOWS
        ),
    )
    go = _page(
        "edit.go-to-target",
        "Go to Target",
        "Go to what the reference points at (Ctrl+click on a reference does the same)",
        key="<Primary><Alt>Return",
        fits=ANYONE,
    )
    remove = _page("edit.remove-reference", "Remove Reference", "Take the reference out of the text", fits=EDITORS)
    return ContextMenu("reference", "Reference", ((show_as,), (go, remove)))


ROW_ABOVE = _page(
    "edit.row-insert-above", "Row Above", "Insert a row above the selection", key="<Alt><Shift>Up", fits=CELLS
)
ROW_BELOW = _page(
    "edit.row-insert-below", "Row Below", "Insert a row below the selection", key="<Alt><Shift>Down", fits=CELLS
)
COLUMN_LEFT = _page(
    "edit.column-insert-left",
    "Column Left",
    "Insert a column to the left of the selection",
    key="<Alt><Shift>Left",
    fits=CELLS,
)
COLUMN_RIGHT = _page(
    "edit.column-insert-right",
    "Column Right",
    "Insert a column to the right of the selection",
    key="<Alt><Shift>Right",
    fits=CELLS,
)
REMOVE_ROW = _page("edit.row-delete", "Row", "Remove the selected rows", key="<Primary><Alt>minus", fits=CELLS)
REMOVE_COLUMN = _page(
    "edit.column-delete",
    "Column",
    "Remove the selected columns",
    key="<Primary><Alt>underscore",  # Shift+- types "_"
    fits=CELLS,
)


def _header_menus() -> tuple[ContextMenu, ...]:
    """The row and column headers, of a sheet and of a table in a text (D1612)."""
    row = (
        _here(ROW_ABOVE, fits=EDITORS),
        _here(ROW_BELOW, fits=EDITORS),
        _here(REMOVE_ROW, "Remove Row", fits=EDITORS),
        _page("edit.row-height", "Row Height…", "The height of the row whose header you pressed", fits=EDITORS),
    )
    column = (
        _here(COLUMN_LEFT, fits=EDITORS),
        _here(COLUMN_RIGHT, fits=EDITORS),
        _here(REMOVE_COLUMN, "Remove Column", fits=EDITORS),
        _page("edit.column-width", "Column Width…", "The width of the column whose header you pressed", fits=EDITORS),
    )
    return (ContextMenu("row-header", "Row Header", (row,)), ContextMenu("column-header", "Column Header", (column,)))


# ------------------------------------------------------------------------------------------------------ the three apps


def composes() -> Manifest:
    """The menus of claudia composes."""
    insert = Menu(
        "Insert",
        (
            (
                _contents(
                    "Table of Contents", "A list of the headings, each a link to its place; it follows them by itself"
                ),
                _cross_reference(),
            ),
            (
                _page(
                    "insert.table",
                    "Table…",
                    "Put a table into the text at the caret",
                    key="<Primary><Alt><Shift>t",
                    fits=EDITORS,
                ),
            ),
            (_image("in the text"), _text_box("to the text"), _shapes(), _containers()),
        ),
    )
    view = _view_menu(
        authors=True,
        own=(
            _page(
                "view.page",
                "Page View",
                "Show the text as pages instead of a flowing text",
                key="<Primary><Alt>p",
                checkable=True,
                fits=ANYONE,
            ),
        ),
    )
    tools = Menu(
        "Tools", ((ASK, _search("Find words, headings, remarks and what is said in objects, and replace them")),)
    )
    table = ContextMenu(
        "table",
        "Table",
        (
            (
                _here(DESCRIBE, fits=EDITORS),
                _here(REFERENCE, fits=EDITORS),
                _page(
                    "tools.table-options",
                    "Table Options…",
                    "Header rows, banding, look, width and the columns of this table",
                    key="<Primary><Shift>l",
                    fits=EDITORS,
                ),
            ),
            (
                _page(
                    "tools.merge-cells",
                    "Merge Cells",
                    "Make this cell and the one next to it one cell",
                    key="<Primary><Shift>g",
                    fits=f"{EDITORS} · selection: more than one cell of the table",
                ),
                _page(
                    "tools.split-cell",
                    "Split Cell",
                    "Make a merged cell into single cells again",
                    key="<Primary><Shift>h",
                    fits=f"{EDITORS} · selection: a merged cell",
                ),
                Submenu(
                    "Sort",
                    (
                        _page(
                            "tools.sort-ascending",
                            "Ascending",
                            "Order the rows of the table by the column the caret is in, smallest first",
                            key="<Primary><Shift>x",
                            fits=EDITORS,
                        ),
                        _page(
                            "tools.sort-descending",
                            "Descending",
                            "Order the rows of the table by the column the caret is in, largest first",
                            key="<Primary><Shift>y",
                            fits=EDITORS,
                        ),
                    ),
                ),
            ),
            (_here(DELETE, "Delete Table", fits=EDITORS),),
        ),
    )
    return _manifest(
        "composes",
        "Claudia Composes",
        menus=(
            _edit_menu(native=True),
            insert,
            _format_menu(look="Change how this kind of paragraph looks", headings=HEADINGS),
            view,
            tools,
        ),
        context_menus=(
            _object_menu(native=True, edit_text=True, wrap=True, grid=False),
            *_paragraph_menus(),
            table,
            _thing("heading", "Heading"),
            *_header_menus(),
            _reference_menu(),
        ),
        keys_only=(
            _page(
                "edit.nonbreaking-hyphen",
                "Non-breaking Hyphen",
                "A hyphen the line is never broken at",
                key="<Primary>underscore",
                fits=EDITORS,
            ),
        ),
    )


def computes() -> Manifest:
    """The menus of claudia computes."""
    edit = _edit_menu(
        native=False,
        own=(
            _page(
                "edit.rename-sheet",
                "Rename Sheet…",
                "Give the sheet you are on another name; the formulas that read it follow",
                key="<Primary><Shift>F11",
                fits=EDITORS,
            ),
            Submenu("Remove", (REMOVE_ROW, REMOVE_COLUMN)),
        ),
    )
    insert = Menu(
        "Insert",
        (
            (
                _image("on the sheet"),
                _containers(),
                _page("edit.chart", "Chart…", "Add a chart of the selected cells", key="<Primary><Alt>c", fits=EDITORS),
            ),
            (
                _page(
                    "edit.new-sheet", "New Sheet…", "Add a new sheet to the document", key="<Shift>F11", fits=EDITORS
                ),
                Submenu("Row or Column", (ROW_ABOVE, ROW_BELOW, COLUMN_LEFT, COLUMN_RIGHT)),
            ),
        ),
    )
    resample = _page(
        "tools.resample",
        "Re-sample",
        "Draw new random numbers for everybody",
        key="F9",
        fits=f"{EDITORS} · document: has random numbers",
    )
    outcomes = _page(
        "tools.outcomes",
        "Outcomes of This Cell…",
        "Every outcome of the alternatives this cell depends on",
        key="<Primary><Alt>o",
        fits=f"{ANYONE} · selection: a cell or range · document: has random numbers",
    )
    follow = _page(
        "tools.follow",
        "Follow Computation",
        "Light up the cells that take part in this cell's computation",
        key="<Primary><Alt>f",
        checkable=True,
        fits=f"{ANYONE} · selection: a cell or range",
    )
    tools = Menu(
        "Tools",
        (
            (ASK, _search("Find text, formulas and values, and replace them")),
            # Random numbers, alternatives and following a computation (E6.21–E6.23, D292–D297).
            (
                Submenu(
                    "Random Generator",
                    (
                        _page(
                            "tools.random",
                            "Generate…",
                            "Pick a distribution and put RANDOM into the cell",
                            key="<Primary><Alt>r",
                            fits=CELLS,
                        ),
                        resample,
                    ),
                ),
            ),
            (Submenu("Tracking", (outcomes, follow)),),
            (_names("The named ranges and tables of this workbook"),),
            # Pivot tables (E6.30, D624); what works on one pivot table is in its context menu (D1612).
            (
                _page(
                    "tools.pivot",
                    "Pivot Table…",
                    "Make a pivot table from a table",
                    key="<Primary><Alt>v",
                    fits=CELLS,
                ),
            ),
            (
                _page(
                    "tools.sql",
                    "SQL…",
                    "Put the result of a query on the selected cell",
                    key="<Primary><Alt>y",
                    fits=EDITORS,
                ),
            ),
        ),
    )
    copy, cut, paste, plain = _clipboard(native=False)
    cell = ContextMenu(
        "cell",
        "Cell",
        (
            (_here(DESCRIBE, fits=EDITORS), _here(STYLE, "Style…", fits=EDITORS), _here(REFERENCE, fits=EDITORS)),
            (
                _here(copy, fits=EDITORS),
                _here(cut, fits=EDITORS),
                _here(paste, fits=EDITORS),
                Submenu("Paste As", (_here(plain, fits=EDITORS),)),
            ),
            (
                _here(outcomes, fits=f"{ANYONE} · document: has random numbers"),
                _here(follow, fits=ANYONE),
                _here(resample, fits=f"{EDITORS} · document: has random numbers"),
            ),
        ),
    )
    pivot = ContextMenu(
        "pivot",
        "Pivot Table",
        (
            (
                _page(
                    "tools.pivot-value",
                    "Value Field Settings…",
                    "How the values of a pivot table field are put together",
                    key="<Primary><Shift><Alt>u",
                    fits=EDITORS,
                ),
                _page(
                    "tools.pivot-fields",
                    "Pivot Fields",
                    "Show or hide the panel with the fields of the pivot table",
                    key="<Primary><Shift><Alt>m",
                    fits=EDITORS,
                ),
                _page(
                    "tools.pivot-sql",
                    "Show Pivot as SQL…",
                    "The query the pivot table asks of its source",
                    key="<Primary><Shift><Alt>q",
                    fits=ANYONE,
                ),
                _page(
                    "tools.pivot-delete",
                    "Delete Pivot Table…",
                    "Take the pivot table away; its source stays",
                    key="<Primary><Shift><Alt>v",
                    fits=EDITORS,
                ),
            ),
        ),
    )
    chart = ContextMenu(
        "chart",
        "Chart on a Sheet",
        (
            (
                _page(
                    "edit.move-to-slide",
                    "Move to Slide",
                    "Make a slide right after the sheet and move the chart onto it",
                    fits=EDITORS,
                ),
            ),
        ),
    )
    return _manifest(
        "computes",
        "Claudia Computes",
        menus=(
            edit,
            insert,
            _format_menu(
                look="Change how the object you have selected looks", clear_cell_style=True, headings=HEADINGS
            ),
            _view_menu(authors=False),
            tools,
        ),
        context_menus=(
            _object_menu(native=False, edit_text=True, wrap=False, grid=False),
            cell,
            _thing("paragraph", "Paragraph", style=True),
            _thing("list", "List"),
            _thing("table", "Table"),
            _thing("tab", "Sheet Tab"),
            *_header_menus(),
            chart,
            pivot,
            _reference_menu(),
        ),
        keys_only=(
            _page(
                "edit.clear",
                "Clear Cells",
                "Clear the selected cells",
                key="Delete",
                key_owner=KeyOwner.VIEW,
                fits=CELLS,
            ),
        ),
    )


def creates() -> Manifest:
    """The menus of claudia creates. The shape library has fixed entries for the three shapes the workbook names; the
    rest of it stays in the slide's tool bar."""
    edit = _edit_menu(
        native=False,
        own=(
            _page(
                "edit.rename-slide",
                "Rename Slide…",
                "Give the slide you are on another name; a tag in the chat keeps pointing at it",
                key="<Primary><Shift>F11",
                fits=EDITORS,
            ),
        ),
    )
    insert = Menu(
        "Insert",
        (
            (
                _cross_reference(),
                _contents(
                    "Agenda", "A text box listing the slide titles with their numbers; it follows them by itself"
                ),
            ),
            (_image("on the slide"), _text_box("to the slide"), _shapes(), _containers()),
            (
                _page(
                    "edit.new-slide", "New Slide", "Add a new slide to the presentation", key="<Primary>m", fits=EDITORS
                ),
            ),
        ),
    )
    view = _view_menu(
        authors=False,
        own=(
            _page(
                "view.grid",
                "Grid",
                "Show the grid that objects snap to",
                key="<Primary><Alt>g",
                checkable=True,
                fits=ANYONE,
            ),
            _page(
                "view.speaker-notes",
                "Speaker Notes",
                "Show or hide the notes under the slide",
                key="<Primary><Alt>v",
                checkable=True,
                fits=ANYONE,
            ),
        ),
    )
    # The show (E10.2, D344): F5 and Shift+F5, as in every presentation program; on a Mac, where they are the
    # system's, a letter (D1651), which the page also listens for (``lib/present-keys.ts``).
    tools = Menu(
        "Tools",
        (
            (ASK, _search("Find words, labels, speaker notes and descriptions, and replace them")),
            (
                Submenu(
                    "Present",
                    (
                        _page(
                            "view.present-here",
                            "From Slide",
                            "Show the presentation full screen, beginning with the slide you are on",
                            key="<Shift>F5",
                            mac="<Control><Alt><Shift>h",
                            fits=ANYONE,
                        ),
                        _page(
                            "view.present-start",
                            "From Beginning",
                            "Show the presentation full screen, beginning with the first slide",
                            key="F5",
                            mac="<Control><Alt>p",
                            fits=ANYONE,
                        ),
                    ),
                ),
                _page(
                    "edit.slide-time",
                    "Plan Time for Slide…",
                    "How long you want to spend on this slide; the bar below the slides adds the times up",
                    key="<Primary><Alt><Shift>t",
                    fits=EDITORS,
                ),
            ),
        ),
    )
    return _manifest(
        "creates",
        "Claudia Creates",
        menus=(
            edit,
            insert,
            _format_menu(look="Change how the object you have selected looks", headings=SLIDE_TITLES),
            view,
            tools,
        ),
        context_menus=(
            _object_menu(native=False, edit_text=True, wrap=False, grid=True),
            *_paragraph_menus(),
            _thing("tab", "Slide Tab"),
            _thing("slide", "Slide"),
            _reference_menu(),
        ),
    )


def for_app(name: str) -> Manifest:
    """The manifest of the app called ``name`` — what a shell started for that app builds its menus from.

    :class:`UnknownApp` (naming the available apps) if there is none.
    """
    builders: dict[str, Callable[[], Manifest]] = {"composes": composes, "computes": computes, "creates": creates}
    try:
        return builders[name]()
    except KeyError:
        raise UnknownApp(f"there is no manifest for '{name}'; available: {', '.join(sorted(builders))}") from None
