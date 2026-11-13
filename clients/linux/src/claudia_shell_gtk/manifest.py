"""The menu and action manifest of the Linux client (E5.1 / E5.10): one list from which the native menus are built.

D120 gives every app the same seven header-bar menus — File, Edit, Format, View, Tools, Config, Help — superseding
D4's four. An action has an id that names *what it does* (``file.save``, ``view.page``) and not where it sits, so a
menu can be rearranged without touching the shell contract, and so the *same* id means the same thing on the web
side (``web/app/lib/menu-dispatch.ts``) and here. Each action is carried out by one party (:class:`Kind`).

Nothing here imports GTK: the menus are described as data and turned into GtkBuilder XML by :func:`menu_xml`, so the
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

A second note, added for Config ▸ App Language (E5.7, D31/D148's groundwork, D160): translation itself is
applied by :func:`menu_xml`/:func:`menu_elements`, not here — this module still imports no gettext, stays pure data,
and is tested without any locale installed. The one deliberate exception is :data:`LANGUAGES` itself: each entry's
own name is its autonym ("Deutsch", not "German" from an English catalog) and is never run through ``translate``,
the same universal convention every OS and browser language picker already follows, so ``_item_element`` and
``scripts/extract_i18n.py``'s manifest walk both skip any action whose id starts with ``"config.language."``.
"""

from __future__ import annotations

import enum
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from .identity import UnknownApp

__all__ = [
    "Action",
    "Kind",
    "KeyOwner",
    "LANGUAGES",
    "Manifest",
    "Menu",
    "Submenu",
    "composes",
    "computes",
    "creates",
    "for_app",
    "menu_button_id",
    "menu_elements",
    "menu_xml",
    "about_links",
]

Translate = Callable[[str], str]
"""A label translator, usually ``i18n.translate`` — defaults to the identity everywhere below, so every function
here stays callable (and testable) with no locale installed at all."""

LANGUAGES: tuple[tuple[str, str], ...] = (("en", "English"), ("de", "Deutsch"))
"""The language picker's own short, explicit list for Config ▸ App Language — exactly the catalogs that exist
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
    """Who listens for an action's key (UX-35, D340). The key itself is the same in every client: the web app, and the
    Linux, Windows and macOS shells, which show it in their menus."""

    PAGE = "page"
    """The page listens, in every client (``web/app/lib/keys.generated.ts``, made from this manifest). A shell only
    shows the key: binding it too would take it away from the page's own rules (no shortcut while typing in a
    field)."""
    SHELL = "shell"
    """The shell binds the key itself and sends the action. That is Quit, About, and the one key a web view would
    otherwise keep for its own context menu (Shift+F10)."""
    VIEW = "view"
    """The document view or the browser handles the key where it is pressed (Enter, Delete, Tab, the clipboard). Shown
    in the menus, listened for by nobody else."""


@dataclass(frozen=True, slots=True)
class Action:
    """One menu item."""

    id: str
    """``file.save``: lower case, namespaced, independent of the menu it sits in (see the shell contract)."""
    label: str
    """English label in the capitalisation of the GNOME HIG; it is the key that translations are looked up by (E5.7)."""
    kind: Kind
    tooltip: str = ""
    accelerators: tuple[str, ...] = ()
    """The action's key, in GTK's notation, the same in every app and every client (UX-35, D340); who listens for it
    is :attr:`key_owner`. Empty only for the few actions that have no key on purpose (the language picker's own
    autonyms)."""
    checkable: bool = False
    editing: str | None = None
    """For :attr:`Kind.EDITING`: the name of the WebKit editing command (``Cut``, ``Copy``, ``Paste``, ...)."""
    role: str | None = None
    """The Cocoa selector (``copy:``, ``cut:``, ``paste:``, ``undo:``, ``redo:``) a macOS shell puts on this item
    next to its accelerator (D158). GTK ignores it; it is carried here, rather than kept only in the macOS client, so
    one manifest stays the single source for every shell (the module docstring's reason for existing at all) and
    ``describe()`` can hand it to a shell that never imports this package (``clients/macos``). Unset for everything
    that is not a standard editing command — macOS has no selector for "paste as plain text" or an app's own
    commands, and giving those a Cocoa role would route the key to a native editing action with no page effect."""
    key_owner: KeyOwner = KeyOwner.PAGE
    """Who listens for :attr:`accelerators`: see :class:`KeyOwner`."""


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


@dataclass(frozen=True, slots=True)
class Menu:
    """A menu button of the header bar. ``sections`` are groups drawn with a separator between them."""

    label: str
    sections: tuple[tuple[MenuEntry, ...], ...]

    @property
    def id(self) -> str:
        """The id of the menu in the generated XML (``menu-file``)."""
        return f"menu-{self.label.lower()}"

    def all_actions(self) -> Iterator[Action]:
        """Every actionable item of the menu, in order — a :class:`Submenu`'s own ``items``, not the ``Submenu``
        itself, which has no id and backs no GTK action."""
        for section in self.sections:
            for entry in section:
                if isinstance(entry, Submenu):
                    yield from entry.items
                else:
                    yield entry


@dataclass(frozen=True, slots=True)
class Manifest:
    """All menus of one app, and the toggle buttons that sit in the header bar next to them."""

    app: str
    menus: tuple[Menu, ...]
    header_toggles: tuple[Action, ...] = field(default=())

    @property
    def actions(self) -> tuple[Action, ...]:
        """Every action, menus first, then the header-bar toggles."""
        return (*(a for menu in self.menus for a in menu.all_actions()), *self.header_toggles)

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
                "accelerators": list(action.accelerators),
                "key_owner": action.key_owner.value,
                "role": action.role,
            }

        def entry(e: MenuEntry) -> dict[str, Any]:
            if isinstance(e, Submenu):
                return {"label": e.label, "items": [one(a) for a in e.items]}
            return one(e)

        return {
            "app": self.app,
            "menus": [
                {"label": menu.label, "sections": [[entry(e) for e in section] for section in menu.sections]}
                for menu in self.menus
            ],
            "header_toggles": [one(a) for a in self.header_toggles],
        }


def _page(
    action_id: str,
    label: str,
    tooltip: str,
    *,
    accelerators: tuple[str, ...] = (),
    checkable: bool = False,
    role: str | None = None,
    key_owner: KeyOwner = KeyOwner.PAGE,
):
    return Action(action_id, label, Kind.PAGE, tooltip, accelerators, checkable, role=role, key_owner=key_owner)


def _shell(action_id: str, label: str, tooltip: str, *, accelerators: tuple[str, ...]) -> Action:
    return Action(action_id, label, Kind.SHELL, tooltip, accelerators, key_owner=KeyOwner.SHELL)


# --------------------------------------------------------------------------------------------- shared across apps
# D120's shared blocks, written once so the three manifests below cannot drift from each other by a typo the way the
# three ``onWindowKey`` handlers did on the web side before D122.
#
# The keys (UX-35, D340) are one table for the three apps and every client. They keep out of the way of what a browser
# keeps for itself (Ctrl+N, Ctrl+W, Ctrl+T, Ctrl+Q never reach a page), of what Ctrl+Alt types on a German Windows
# keyboard (AltGr: Q, E, M and the digits), and of the desktop's own (Ctrl+Alt+T, Ctrl+Alt+L on Ubuntu). An app's own
# commands are Ctrl+Alt+letter, the rare and weighty ones of File ▸ Manage are Ctrl+Alt+Shift+letter.


def _file_menu(*, title: str, prints: bool) -> Menu:
    """New, Open… · Save, Save new checkpoint…, Download, Print… (the apps that lay out pages, D906) · Manage ▸
    (Share…, Assign new owner…, Accept ownership…, Leave document…, Export…, Delete from server…) · Close document,
    Quit (D123, D124's grouping; D141's Manage submenu)."""
    keep: tuple[Action, ...] = (
        _page("file.save", "Save", "Make a checkpoint of the document", accelerators=("<Primary>s",)),
        _page(
            "file.save-as",
            "Save New Checkpoint…",
            "Make a checkpoint and give it a name",
            accelerators=("<Primary><Shift>s",),
        ),
        _page("file.download", "Download", "Download the document to this computer", accelerators=("<Primary><Alt>s",)),
    )
    if prints:
        keep = (*keep, _page("file.print", "Print…", "See the pages and print them", accelerators=("<Primary>p",)))
    return Menu(
        "File",
        (
            (
                _page("file.new", "New", "Start a new document", accelerators=("<Primary><Alt>n",)),
                _page(
                    "file.open",
                    "Open…",
                    "Create a document or open one from the server",
                    accelerators=("<Primary>o",),
                ),
            ),
            keep,
            (
                Submenu(
                    "Manage",
                    (
                        _page(
                            "file.manage.share",
                            "Share…",
                            "Let other people into the document",
                            accelerators=("<Primary><Alt><Shift>s",),
                        ),
                        _page(
                            "file.manage.assign-owner",
                            "Assign New Owner…",
                            "Hand this document over to somebody else",
                            accelerators=("<Primary><Alt><Shift>o",),
                        ),
                        _page(
                            "file.manage.accept-owner",
                            "Accept Ownership…",
                            "Accept a document that was handed over to you",
                            accelerators=("<Primary><Alt><Shift>c",),
                        ),
                        _page(
                            "file.manage.leave",
                            "Leave Document…",
                            "Remove yourself from this document",
                            accelerators=("<Primary><Alt><Shift>l",),
                        ),
                        _page(
                            "file.manage.export",
                            "Export…",
                            "Save the document's content in Claudia's own format",
                            accelerators=("<Primary><Alt><Shift>x",),
                        ),
                        _page(
                            "file.manage.delete",
                            "Delete From Server…",
                            "Remove this document from the server for good",
                            accelerators=("<Primary><Alt><Shift>r",),
                        ),
                    ),
                ),
            ),
            (
                _page(
                    "file.close", "Close Document", "Back to the list of documents", accelerators=("<Primary><Alt>w",)
                ),
                _shell("file.quit", "Quit", f"Close {title}", accelerators=("<Primary>q",)),
            ),
        ),
    )


def _shared_edit_block() -> tuple[Action, ...]:
    """Undo, Redo — identical in every app (D120). Each also carries its macOS role (D158): on that shell the key
    equivalent needs one to reach the item at all."""
    return (
        _page("edit.undo", "Undo", "Take back your last step", accelerators=("<Primary>z",), role="undo:"),
        _page("edit.redo", "Redo", "Do your last undone step again", accelerators=("<Primary><Shift>z",), role="redo:"),
    )


def _shared_clipboard_block(*, native: bool) -> tuple[MenuEntry, ...]:
    """Copy, Cut, Paste, Paste as ▸ Plain text — identical in every app (D120). The keys are the browser's own in
    every client (:attr:`KeyOwner.VIEW`): the clipboard events reach the page from there.

    ``native=True`` (composes) dispatches the menu item straight to WebKit's own editing commands. ``native=False``
    (computes, creates) goes through the page instead: a cell grid's paste needs to split the clipboard by tabs and
    newlines onto the current selection, and a slide canvas's paste needs to land in whichever text frame is being
    edited, neither of which WebKit's generic "insert this text here" command knows how to do.
    """
    view = KeyOwner.VIEW
    if native:
        return (
            Action(
                "edit.copy",
                "Copy",
                Kind.EDITING,
                "Copy the selection to the clipboard",
                ("<Primary>c",),
                editing="Copy",
                role="copy:",
                key_owner=view,
            ),
            Action(
                "edit.cut",
                "Cut",
                Kind.EDITING,
                "Move the selection to the clipboard",
                ("<Primary>x",),
                editing="Cut",
                role="cut:",
                key_owner=view,
            ),
            Action(
                "edit.paste",
                "Paste",
                Kind.EDITING,
                "Insert the clipboard",
                ("<Primary>v",),
                editing="Paste",
                role="paste:",
                key_owner=view,
            ),
            Submenu(
                "Paste As",
                (
                    Action(
                        "edit.paste-as-plain",
                        "Plain Text",
                        Kind.EDITING,
                        "Insert the clipboard without formatting",
                        ("<Primary><Shift>v",),
                        editing="PasteAsPlainText",
                        key_owner=view,
                    ),
                ),
            ),
        )
    return (
        _page(
            "edit.copy",
            "Copy",
            "Copy the selection to the clipboard",
            accelerators=("<Primary>c",),
            role="copy:",
            key_owner=view,
        ),
        _page(
            "edit.cut",
            "Cut",
            "Move the selection to the clipboard",
            accelerators=("<Primary>x",),
            role="cut:",
            key_owner=view,
        ),
        _page(
            "edit.paste", "Paste", "Insert the clipboard", accelerators=("<Primary>v",), role="paste:", key_owner=view
        ),
        Submenu(
            "Paste As",
            (
                _page(
                    "edit.paste-as-plain",
                    "Plain Text",
                    "Insert the clipboard without formatting",
                    accelerators=("<Primary><Shift>v",),
                    key_owner=view,
                ),
            ),
        ),
    )


def _search_block() -> tuple[Action, ...]:
    """E5.15: the same entry, label and key in every app that searches (D281). Ctrl+H, which opens the panel with
    Replace showing, is a second way in and has no menu entry of its own."""
    return (
        _page(
            "edit.search-replace",
            "Search & Replace…",
            "Find text, formulas and values, and replace them",
            accelerators=("<Primary>f",),
        ),
    )


def _format_menu(*, look: str, clear_cell_style: bool = False, describe: bool = False) -> Menu:
    """The Format menu, one shape in every app (D300): Apply Style…, Edit This Style…, All Styles…, List ▸ · Colours… ·
    and where there are objects, Describe Object… (BITV 1.1.1). List ▸ is in every app as on the web; outside a text
    the page reports its entries disabled. Computes adds Clear Cell Style, which the web has in Apply Style's flyout."""
    styles: tuple[MenuEntry, ...] = (
        _page(
            "format.apply-style",
            "Apply Style…",
            "Choose a style for the selection, each drawn in its own look",
            accelerators=("<Primary><Alt>a",),
        ),
    )
    if clear_cell_style:
        styles = (
            *styles,
            _page(
                "format.clear-cell-style",
                "Clear Cell Style",
                "Take the selected cells' own style off, back to the table's",
                accelerators=("<Primary><Alt><Shift>k",),
            ),
        )
    styles = (
        *styles,
        _page(
            "format.look",
            "Edit This Style…",
            look,
            accelerators=("<Shift>F10",),
            # A web view keeps Shift+F10 for its own context menu, so the shell takes it first (as before UX-35).
            key_owner=KeyOwner.SHELL,
        ),
        _page(
            "format.all-styles",
            "All Styles…",
            "List, rename and tidy the styles of this document",
            accelerators=("<Primary><Alt><Shift>a",),
        ),
        Submenu(
            "List",
            (
                _page(
                    "format.bulleted-list",
                    "Bulleted List",
                    "Make the paragraphs a list with bullets, or plain again",
                    accelerators=("<Primary><Shift>8",),
                    checkable=True,
                ),
                _page(
                    "format.numbered-list",
                    "Numbered List",
                    "Make the paragraphs a numbered list, or plain again",
                    accelerators=("<Primary><Shift>7",),
                    checkable=True,
                ),
                _page(
                    "format.list-continue",
                    "Continue Previous List",
                    "Go on counting where the list before this one stopped",
                    accelerators=("<Primary><Alt><Shift>p",),
                ),
                _page(
                    "format.list-start",
                    "Start At…",
                    "The number this list starts at",
                    accelerators=("<Primary><Alt><Shift>n",),
                ),
                _page(
                    "format.list-indent",
                    "Indent",
                    "Move the item one level in",
                    accelerators=("Tab",),
                    key_owner=KeyOwner.VIEW,
                ),
                _page(
                    "format.list-outdent",
                    "Outdent",
                    "Move the item one level out",
                    accelerators=("<Shift>Tab",),
                    key_owner=KeyOwner.VIEW,
                ),
            ),
        ),
    )
    sections: tuple[tuple[MenuEntry, ...], ...] = (
        styles,
        (
            _page(
                "format.colours",
                "Colours…",
                "The colours of this document, by what each one means",
                accelerators=("<Primary><Alt>k",),
            ),
        ),
    )
    if describe:
        sections = (
            *sections,
            (
                _page(
                    "format.describe",
                    "Describe Object…",
                    "Say what the object you have selected shows to someone who cannot see it",
                    accelerators=("<Primary><Alt>d",),
                ),
            ),
        )
    return Menu("Format", sections)


def _shared_view_block(*, authors: bool) -> tuple[Action, ...]:
    """Show who wrote what, History and chat, Dark mode (D120). ``authors=False`` for computes/creates, which track
    no per-item authorship yet — the action still exists and starts checkable (D125's visible-but-inert treatment),
    the page itself reports it permanently disabled."""
    return (
        _page(
            "view.authors",
            "Show Who Wrote What",
            "Colour the text by the person who wrote it" if authors else "Not available yet",
            accelerators=("<Primary><Alt>u",),
            checkable=True,
        ),
        _page(
            "view.panel",
            "History and Chat",
            "Show or hide the history and the chat",
            accelerators=("<Primary><Alt>h",),
            checkable=True,
        ),
        _page(
            "view.dark",
            "Dark Mode",
            "Follow or override the system's light/dark setting",
            accelerators=("<Primary><Alt><Shift>d",),
            checkable=True,
        ),
    )


def _tools_ask() -> Action:
    return _page(
        "tools.ask", "Ask the Assistant…", "Write to the assistant in the chat", accelerators=("<Primary><Alt>j",)
    )


def _config_menu() -> Menu:
    """Shortcuts (D120, D122: an editable remapping UI is deferred; Ctrl+? as in GNOME), then App Language (the owner's
    second i18n round): one checkable ``Kind.PAGE`` action per :data:`LANGUAGES` entry, in its own section/flyout.

    The language entries are the one place without a key: each is a language's own name, and there may be many.
    Mutual exclusion (picking one unchecks the rest) is enforced nowhere in this data — it is just ``LANGUAGES``
    many independent checkable actions, the same primitive ``view.dark`` already uses. The page is the one source of
    truth for which is active (it owns the catalog): a click sends the usual ``action`` message, the page's own
    ``menus`` recomputes every item's ``checked`` from its one ``locale`` ref, and ``collectStates`` reports all of
    them back, so ``window.py``'s ``set_action_states`` — already written to apply whatever the page reports, one id
    at a time — needs no special case to keep the native tick marks in step."""
    return Menu(
        "Config",
        (
            (
                _page(
                    "config.shortcuts",
                    "Shortcuts",
                    "The keyboard shortcuts this app uses",
                    accelerators=("<Primary>question",),
                ),
            ),
            (
                Submenu(
                    "App Language",
                    tuple(_page(f"config.language.{tag}", label, "", checkable=True) for tag, label in LANGUAGES),
                ),
            ),
        ),
    )


def _help_menu(title: str) -> Menu:
    """Ask ai, How do I…?, Documentation, About (D120, D125, D126) — identical shape in every app; only the About
    dialog's own title differs. F1 is help, as everywhere."""
    return Menu(
        "Help",
        (
            (
                _page("help.ask", "Ask ai", "Open the chat with an empty prompt", accelerators=("<Primary>F1",)),
                _page("help.how-to", "How Do I…?", "Answers to what people often want to do", accelerators=("F1",)),
                _page(
                    "help.docs", "Documentation", "Every function and feature, to look up", accelerators=("<Shift>F1",)
                ),
                _shell(
                    "help.about", f"About {title}", "Version, authors and licence", accelerators=("<Primary><Shift>F1",)
                ),
            ),
        ),
    )


def _manifest(
    app: str, title: str, *, edit: Menu, format_menu: Menu, view: Menu, tools: Menu, prints: bool
) -> Manifest:
    return Manifest(
        app,
        (
            _file_menu(title=title, prints=prints),
            edit,
            format_menu,
            view,
            tools,
            _config_menu(),
            _help_menu(title),
        ),
    )


# ------------------------------------------------------------------------------------------------------ the three apps


def composes() -> Manifest:
    """The menus of claudia composes."""
    edit_menu = Menu(
        "Edit",
        (
            _shared_edit_block(),
            _shared_clipboard_block(native=True),
            (
                Submenu(
                    "Insert",
                    (
                        _page(
                            "edit.soft-hyphen",
                            "Soft Hyphen",
                            "Where the word may be broken at the end of a line",
                            accelerators=("<Primary>minus",),
                        ),
                        _page(
                            "edit.nonbreaking-hyphen",
                            "Non-breaking Hyphen",
                            "A hyphen the line is never broken at",
                            accelerators=("<Primary>underscore",),
                        ),
                    ),
                ),
            ),
        ),
    )
    view_menu = Menu(
        "View",
        (
            _shared_view_block(authors=True),
            (
                _page(
                    "view.page",
                    "Page",
                    "Show the text as pages instead of a flowing text",
                    accelerators=("<Primary><Alt>p",),
                    checkable=True,
                ),
            ),
        ),
    )
    # Tools has only the generic entry (D126): the canned demo requests and Insert Sample Text went (2026-11-12).
    return _manifest(
        "composes",
        "Claudia Composes",
        edit=edit_menu,
        format_menu=_format_menu(look="Change how this kind of paragraph looks"),
        view=view_menu,
        tools=Menu("Tools", ((_tools_ask(),),)),
        prints=True,
    )


def computes() -> Manifest:
    """The menus of claudia computes."""
    edit_menu = Menu(
        "Edit",
        (
            _shared_edit_block(),
            _shared_clipboard_block(native=False),
            _search_block(),
            (
                _page("edit.new-sheet", "New Sheet…", "Add a new sheet to the document", accelerators=("<Shift>F11",)),
                _page("edit.image", "Image…", "Put a picture on the sheet", accelerators=("<Primary><Alt>i",)),
                _page("edit.chart", "Chart…", "Add a chart of the selected cells", accelerators=("<Primary><Alt>c",)),
            ),
            (
                # D130 (confirmed by the owner 2026-11-10): grouped into Row ▸ / Column ▸ rather than six flat items.
                Submenu(
                    "Row",
                    (
                        _page(
                            "edit.row-insert-above",
                            "Insert Above",
                            "Insert a row above the selection",
                            accelerators=("<Alt><Shift>Up",),
                        ),
                        _page(
                            "edit.row-insert-below",
                            "Insert Below",
                            "Insert a row below the selection",
                            accelerators=("<Alt><Shift>Down",),
                        ),
                        _page(
                            "edit.row-delete",
                            "Delete",
                            "Delete the selected rows",
                            accelerators=("<Primary><Alt>minus",),
                        ),
                    ),
                ),
                Submenu(
                    "Column",
                    (
                        _page(
                            "edit.column-insert-left",
                            "Insert Left",
                            "Insert a column to the left of the selection",
                            accelerators=("<Alt><Shift>Left",),
                        ),
                        _page(
                            "edit.column-insert-right",
                            "Insert Right",
                            "Insert a column to the right of the selection",
                            accelerators=("<Alt><Shift>Right",),
                        ),
                        _page(
                            "edit.column-delete",
                            "Delete",
                            "Delete the selected columns",
                            accelerators=("<Primary><Alt>underscore",),  # Shift+- types "_"
                        ),
                    ),
                ),
            ),
            (
                _page(
                    "edit.clear",
                    "Clear Cells",
                    "Clear the selected cells",
                    accelerators=("Delete",),
                    key_owner=KeyOwner.VIEW,
                ),
            ),
        ),
    )
    tools_menu = Menu(
        "Tools",
        (
            # Only the generic entry (D126): "Ask for an Example Budget" was taken out (2026-11-12).
            (_tools_ask(),),
            # Random numbers, alternatives and following a computation (E6.21–E6.23, D292–D297).
            (
                _page(
                    "tools.random",
                    "Random Generator…",
                    "Pick a distribution and put RANDOM into the cell",
                    accelerators=("<Primary><Alt>r",),
                ),
                _page(
                    "tools.resample",
                    "Resample Random Numbers",
                    "Draw new random numbers for everybody",
                    accelerators=("F9",),
                ),
                _page(
                    "tools.outcomes",
                    "Outcomes of This Cell…",
                    "Every outcome of the alternatives this cell depends on",
                    accelerators=("<Primary><Alt>o",),
                ),
                _page(
                    "tools.follow",
                    "Follow Computation",
                    "Light up the cells that take part in this cell's computation",
                    accelerators=("<Primary><Alt>f",),
                    checkable=True,
                ),
            ),
            # Names, tables and SQL() (E6.5, D600–D609).
            (
                _page(
                    "tools.names",
                    "Names…",
                    "The named ranges and tables of this workbook",
                    accelerators=("<Primary>F3",),
                ),
                _page(
                    "tools.sql",
                    "SQL Query…",
                    "Put the result of a query on the selected cell",
                    accelerators=("<Primary><Alt>y",),
                ),
            ),
        ),
    )
    return _manifest(
        "computes",
        "Claudia Computes",
        edit=edit_menu,
        format_menu=_format_menu(
            look="Change how the object you have selected looks", clear_cell_style=True, describe=True
        ),
        view=Menu("View", (_shared_view_block(authors=False),)),
        tools=tools_menu,
        prints=False,
    )


def creates() -> Manifest:
    """The menus of claudia creates.

    The shape library (``InsertBar``'s per-document list) is dynamic, like composes' style names — see this module's
    docstring — so it has no entry here; only the fixed actions around it do.
    """
    edit_menu = Menu(
        "Edit",
        (
            _shared_edit_block(),
            _shared_clipboard_block(native=False),
            (
                _page(
                    "edit.new-slide", "New Slide", "Add a new slide to the presentation", accelerators=("<Primary>m",)
                ),
            ),
            (
                _page(
                    "edit.edit-text",
                    "Edit Text",
                    "Write in the selected text box",
                    accelerators=("Return",),
                    key_owner=KeyOwner.VIEW,
                ),
                _page("edit.text-box", "Text Box", "Add a text box to the slide", accelerators=("<Primary><Alt>b",)),
                _page("edit.image", "Image…", "Put a picture on the slide", accelerators=("<Primary><Alt>i",)),
            ),
            (
                _page(
                    "edit.delete",
                    "Delete",
                    "Take the selected object off the slide",
                    accelerators=("Delete",),
                    key_owner=KeyOwner.VIEW,
                ),
            ),
        ),
    )
    view_menu = Menu(
        "View",
        (
            _shared_view_block(authors=False),
            (
                _page(
                    "view.grid",
                    "Show Grid",
                    "Show the grid that objects snap to",
                    accelerators=("<Primary><Alt>g",),
                    checkable=True,
                ),
            ),
        ),
    )
    return _manifest(
        "creates",
        "Claudia Creates",
        edit=edit_menu,
        format_menu=_format_menu(look="Change how the object you have selected looks", describe=True),
        view=view_menu,
        tools=Menu("Tools", ((_tools_ask(),),)),
        prints=True,
    )


def for_app(name: str) -> Manifest:
    """The manifest of the app called ``name`` — what a shell started for that app builds its menus from.

    :class:`~claudia_shell_gtk.identity.UnknownApp` (naming the available apps) if there is none.
    """
    builders: dict[str, Callable[[], Manifest]] = {"composes": composes, "computes": computes, "creates": creates}
    try:
        return builders[name]()
    except KeyError:
        raise UnknownApp(
            f"there is no Linux client for '{name}' yet; available: {', '.join(sorted(builders))}"
        ) from None


# ----------------------------------------------------------------------------------------------------- GtkBuilder XML


def _translatable(action: Action) -> bool:
    """Everything except :data:`LANGUAGES`' own autonyms (see this module's docstring)."""
    return not action.id.startswith("config.language.")


def _item_element(parent: ET.Element, action: Action, translate: Translate) -> None:
    item = ET.SubElement(parent, "item")
    label = ET.SubElement(item, "attribute", name="label", translatable="yes")
    label.text = translate(action.label) if _translatable(action) else action.label
    target = ET.SubElement(item, "attribute", name="action")
    target.text = f"win.{action.id}"
    if action.accelerators:
        # Shown, whoever listens for it: GTK draws the ``accel`` attribute next to the label without binding it.
        accel = ET.SubElement(item, "attribute", name="accel")
        accel.text = action.accelerators[0]


def _submenu_element(parent: ET.Element, submenu: Submenu, translate: Translate) -> None:
    """``<submenu>``: GTK's own nested-flyout element, holding one ``<section>`` of items — the GMenu-XML shape for
    exactly what ``MenuBar.vue``'s ``items`` property draws as a flyout on the web side."""
    element = ET.SubElement(parent, "submenu")
    label = ET.SubElement(element, "attribute", name="label", translatable="yes")
    label.text = translate(submenu.label)
    section = ET.SubElement(element, "section")
    for action in submenu.items:
        _item_element(section, action, translate)


def _menu_tree(manifest: Manifest, translate: Translate) -> ET.Element:
    interface = ET.Element("interface")
    for menu in manifest.menus:
        menu_element = ET.SubElement(interface, "menu", id=menu.id)
        for section in menu.sections:
            section_element = ET.SubElement(menu_element, "section")
            for entry in section:
                if isinstance(entry, Submenu):
                    _submenu_element(section_element, entry, translate)
                else:
                    _item_element(section_element, entry, translate)
    ET.indent(interface)
    return interface


def menu_button_id(menu_id: str) -> str:
    """The id that ``data/window.ui`` gives the menu button of the menu ``menu_id`` (``menu-file`` → ``menu_file``)."""
    return menu_id.replace("-", "_")


def menu_elements(manifest: Manifest, *, translate: Translate = lambda text: text) -> str:
    """Only the ``<menu>`` elements, to be merged into the layout file of a window (see ``window.ui``).

    ``translate`` is applied here, while the XML is built, rather than through GtkBuilder's own translation-domain
    machinery: the shell installs exactly one gettext mechanism (``i18n.install_translation``, bound to Python's own
    ``_()``), and calling ``translate`` directly reuses it instead of also wiring ``Gtk.Builder.set_translation_domain``
    and glibc's ``bindtextdomain`` for a second, parallel one. Left at the default identity function, this (and
    everything it calls) needs no locale installed at all — which is what every test below does.
    """
    return "\n  ".join(ET.tostring(menu, encoding="unicode").strip() for menu in _menu_tree(manifest, translate))


def menu_xml(manifest: Manifest, *, translate: Translate = lambda text: text) -> str:
    """GtkBuilder XML for the menus of ``manifest``: one ``<menu id="menu-file">`` and so on.

    Every item calls the window action ``win.<id>``; ``translatable="yes"`` on its label is a GtkBuilder hint for
    any future tooling (xgettext and the like) that reads this XML directly; translation itself has already
    happened by the time this text is written, under ``menu_elements``'s own ``translate`` parameter above (E5.7).
    """
    elements = menu_elements(manifest, translate=translate)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<interface>\n  {elements}\n</interface>\n'
