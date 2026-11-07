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
growing one entry per document. The same reasoning drops the "visible but inert" stub items (D125) from the
*accelerator* story but not from the menu itself: ``format.none``, ``help.how-to`` and ``help.docs`` below are
ordinary ``Kind.PAGE`` actions the shell greys out the moment the page connects (``set_action_states``, driven by the
page's own ``collectStates`` — nothing shell-side needs to know they are permanent stubs rather than temporarily
disabled ones).
"""

from __future__ import annotations

import enum
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Action",
    "Kind",
    "Manifest",
    "Menu",
    "Submenu",
    "composes",
    "computes",
    "creates",
    "menu_elements",
    "menu_xml",
    "about_links",
]

WEBSITE = "https://www.claudia-office.de"
ISSUES = "https://github.com/claudiaoffice/claudia/issues"
LEGAL = "https://github.com/claudiaoffice/claudia/blob/main/LICENSE"


def about_links() -> tuple[tuple[str, str], ...]:
    """The three outbound links every About dialog shows, in this order (D28, the owner's 2026-11-06 report that the
    web and Linux About dialogs had drifted apart): data, so both can be tested without GTK (``window.py``'s
    ``_show_about`` is what actually builds the dialog). The licence is linked rather than shown in full here, for
    the same reason ``claudiaoffice-log/notes/README.md`` gives for not duplicating generated content elsewhere: a
    second copy of the licence text cannot be kept true and competes with the one in the repository.

    Web's own copy of this list is ``AboutDialog.vue``'s ``LINKS`` — there is no shared manifest for the two shells
    to read this from, so a change here needs the same change made there by hand.
    """
    return (("Website", WEBSITE), ("Report an Issue", ISSUES), ("Legal", LEGAL))


class Kind(enum.Enum):
    """Who carries an action out."""

    PAGE = "page"
    """The web page does it, when the shell sends it an ``action`` message (shell contract)."""
    SHELL = "shell"
    """The shell does it itself (quit, About)."""
    EDITING = "editing"
    """The web view's own editing machinery does it (WebKit editing commands such as cut, copy, paste)."""


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
    """Only keys that the shell handles. A key the page already handles (Ctrl+Z, Ctrl+S) is never bound twice."""
    checkable: bool = False
    editing: str | None = None
    """For :attr:`Kind.EDITING`: the name of the WebKit editing command (``Cut``, ``Copy``, ``Paste``, ...)."""


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


def _page(action_id: str, label: str, tooltip: str, *, accelerators: tuple[str, ...] = (), checkable: bool = False):
    return Action(action_id, label, Kind.PAGE, tooltip, accelerators, checkable)


# --------------------------------------------------------------------------------------------- shared across apps
# D120's shared blocks, written once so the three manifests below cannot drift from each other by a typo the way the
# three ``onWindowKey`` handlers did on the web side before D122.


def _file_menu(*, title: str) -> Menu:
    """New, Open… · Save, Save new checkpoint…, Download · Manage ▸ (Share…, Assign new owner…, Accept
    ownership…, Leave document…, Export…, Delete from server…) · Close document, Quit (D123, D124's grouping;
    D141's Manage submenu, renamed from the plain "Share…" item it grew out of)."""
    return Menu(
        "File",
        (
            (
                _page("file.new", "New", "Start a new document", accelerators=("<Primary>n",)),
                _page(
                    "file.open",
                    "Open…",
                    "Create a document or open one from the server",
                    accelerators=("<Primary>o",),
                ),
            ),
            (
                _page("file.save", "Save", "Make a checkpoint of the document"),
                _page("file.save-as", "Save New Checkpoint…", "Make a checkpoint and give it a name"),
                _page("file.download", "Download", "Download the document to this computer"),
            ),
            (
                Submenu(
                    "Manage",
                    (
                        _page("file.manage.share", "Share…", "Let other people into the document"),
                        _page(
                            "file.manage.assign-owner",
                            "Assign New Owner…",
                            "Hand this document over to somebody else",
                        ),
                        _page(
                            "file.manage.accept-owner",
                            "Accept Ownership…",
                            "Accept a document that was handed over to you",
                        ),
                        _page("file.manage.leave", "Leave Document…", "Remove yourself from this document"),
                        _page(
                            "file.manage.export",
                            "Export…",
                            "Save the document's content in Claudia's own format",
                        ),
                        _page(
                            "file.manage.delete",
                            "Delete From Server…",
                            "Remove this document from the server for good",
                        ),
                    ),
                ),
            ),
            (
                _page("file.close", "Close Document", "Back to the list of documents"),
                Action("file.quit", "Quit", Kind.SHELL, f"Close {title}", accelerators=("<Primary>q",)),
            ),
        ),
    )


def _shared_edit_block() -> tuple[Action, ...]:
    """Undo, Redo — identical in every app (D120); their accelerators are page-handled (``lib/shortcuts.ts``), not
    shell-handled, so none are bound here, the same as before this round."""
    return (
        _page("edit.undo", "Undo", "Take back your last step"),
        _page("edit.redo", "Redo", "Do your last undone step again"),
    )


def _shared_clipboard_block(*, native: bool) -> tuple[MenuEntry, ...]:
    """Copy, Cut, Paste, Paste as ▸ Plain text — identical in every app (D120).

    ``native=True`` (composes, carried over unchanged from before this round) dispatches straight to WebKit's own
    editing commands. ``native=False`` (computes, creates — both new to the GTK shell, D121) goes through the page
    instead: a cell grid's paste needs to split the clipboard by tabs and newlines onto the current selection, and a
    slide canvas's paste needs to land in whichever text frame is being edited, neither of which WebKit's generic
    "insert this text here" command knows how to do. The page's own ``lib/clipboard.ts`` is what actually does this.
    """
    if native:
        return (
            Action("edit.copy", "Copy", Kind.EDITING, "Copy the selection to the clipboard", editing="Copy"),
            Action("edit.cut", "Cut", Kind.EDITING, "Move the selection to the clipboard", editing="Cut"),
            Action("edit.paste", "Paste", Kind.EDITING, "Insert the clipboard", editing="Paste"),
            Submenu(
                "Paste As",
                (
                    Action(
                        "edit.paste-as-plain",
                        "Plain Text",
                        Kind.EDITING,
                        "Insert the clipboard without formatting",
                        editing="PasteAsPlainText",
                    ),
                ),
            ),
        )
    return (
        _page("edit.copy", "Copy", "Copy the selection to the clipboard"),
        _page("edit.cut", "Cut", "Move the selection to the clipboard"),
        _page("edit.paste", "Paste", "Insert the clipboard"),
        Submenu("Paste As", (_page("edit.paste-as-plain", "Plain Text", "Insert the clipboard without formatting"),)),
    )


def _shared_view_block(*, authors: bool) -> tuple[Action, ...]:
    """Show who wrote what, History and chat, Dark mode (D120). ``authors=False`` for computes/creates, which track
    no per-item authorship yet — the action still exists and starts checkable (D125's visible-but-inert treatment),
    the page itself reports it permanently disabled."""
    return (
        _page(
            "view.authors",
            "Show Who Wrote What",
            "Colour the text by the person who wrote it" if authors else "Not available yet",
            checkable=True,
        ),
        _page("view.panel", "History and Chat", "Show or hide the history and the chat", checkable=True),
        _page("view.dark", "Dark Mode", "Follow or override the system's light/dark setting", checkable=True),
    )


def _config_menu() -> Menu:
    """Shortcuts only, for now (D120, D122): an editable remapping UI is deferred."""
    return Menu(
        "Config",
        ((_page("config.shortcuts", "Shortcuts", "The keyboard shortcuts this app uses", accelerators=("F1",)),),),
    )


def _help_menu(title: str) -> Menu:
    """Ask ai, then the two not-yet-real stubs, then About (D120, D125, D126) — identical shape in every app; only
    the About dialog's own title differs."""
    return Menu(
        "Help",
        (
            (
                _page("help.ask", "Ask ai", "Open the chat with an empty prompt"),
                _page("help.how-to", "How Do I…?", "Not available yet"),
                _page("help.docs", "Documentation", "Not available yet"),
                Action("help.about", f"About {title}", Kind.SHELL, "Version, authors and licence"),
            ),
        ),
    )


# ------------------------------------------------------------------------------------------------------ the three apps


def composes() -> Manifest:
    """The menus of claudia composes in the Linux client."""
    edit_menu = Menu("Edit", (_shared_edit_block(), _shared_clipboard_block(native=True)))
    format_menu = Menu(
        "Format",
        (
            (
                _page(
                    "format.look",
                    "Edit This Style…",
                    "Change how this kind of paragraph looks",
                    accelerators=("<Shift>F10",),
                ),
                _page("format.all-styles", "All Styles…", "List, rename and tidy the styles of this document"),
            ),
        ),
    )
    view_menu = Menu(
        "View",
        (
            _shared_view_block(authors=True),
            (_page("view.page", "Page", "Show the text as pages instead of a flowing text", checkable=True),),
        ),
    )
    tools_menu = Menu(
        "Tools",
        (
            (
                _page("tools.ask", "Ask the Assistant…", "Write to the assistant in the chat"),
                _page("tools.review-text", "Review This Text", "Ask the assistant to suggest improvements"),
                _page(
                    "tools.review-paragraph", "Review This Paragraph", "Ask the assistant about the current paragraph"
                ),
            ),
            (
                _page(
                    "tools.insert-sample",
                    "Insert Sample Text",
                    "Put a sample text into the document to try the assistant",
                ),
            ),
        ),
    )
    return Manifest(
        "composes",
        (
            _file_menu(title="Claudia Composes"),
            edit_menu,
            format_menu,
            view_menu,
            tools_menu,
            _config_menu(),
            _help_menu("Claudia Composes"),
        ),
    )


def computes() -> Manifest:
    """The menus of claudia computes in the Linux client (new, D121 — no window or application class yet)."""
    edit_menu = Menu(
        "Edit",
        (
            _shared_edit_block(),
            _shared_clipboard_block(native=False),
            (_page("edit.new-sheet", "New Sheet…", "Add a new sheet to the document"),),
            (
                # D130 (Claude's recommendation, not yet confirmed — decision-log.md): grouped into Row ▸ /
                # Column ▸ rather than six flat items, reusing the same submenu mechanism Paste as ▸ already needed.
                Submenu(
                    "Row",
                    (
                        _page("edit.row-insert-above", "Insert Above", "Insert a row above the selection"),
                        _page("edit.row-insert-below", "Insert Below", "Insert a row below the selection"),
                        _page("edit.row-delete", "Delete", "Delete the selected rows"),
                    ),
                ),
                Submenu(
                    "Column",
                    (
                        _page("edit.column-insert-left", "Insert Left", "Insert a column to the left of the selection"),
                        _page(
                            "edit.column-insert-right",
                            "Insert Right",
                            "Insert a column to the right of the selection",
                        ),
                        _page("edit.column-delete", "Delete", "Delete the selected columns"),
                    ),
                ),
            ),
            (_page("edit.clear", "Clear Cells", "Clear the selected cells"),),
        ),
    )
    format_menu = Menu("Format", ((_page("format.none", "No Styles Yet", "computes has no style system yet"),),))
    view_menu = Menu("View", (_shared_view_block(authors=False),))
    tools_menu = Menu(
        "Tools",
        (
            (
                _page("tools.ask", "Ask the Assistant…", "Write to the assistant in the chat"),
                _page(
                    "tools.example-budget",
                    "Ask for an Example Budget",
                    "Ask the assistant to build an example budget",
                ),
            ),
        ),
    )
    return Manifest(
        "computes",
        (
            _file_menu(title="Claudia Computes"),
            edit_menu,
            format_menu,
            view_menu,
            tools_menu,
            _config_menu(),
            _help_menu("Claudia Computes"),
        ),
    )


def creates() -> Manifest:
    """The menus of claudia creates in the Linux client (new, D121 — no window or application class yet).

    The shape library (``InsertBar``'s per-document list) is dynamic, like composes' style names — see this module's
    docstring — so it has no entry here; only the fixed actions around it (New slide, Edit text, Text box, Delete) do.
    """
    edit_menu = Menu(
        "Edit",
        (
            _shared_edit_block(),
            _shared_clipboard_block(native=False),
            (_page("edit.new-slide", "New Slide", "Add a new slide to the presentation"),),
            (
                _page("edit.edit-text", "Edit Text", "Write in the selected text box"),
                _page("edit.text-box", "Text Box", "Add a text box to the slide"),
            ),
            (_page("edit.delete", "Delete", "Take the selected object off the slide"),),
        ),
    )
    format_menu = Menu("Format", ((_page("format.none", "No Styles Yet", "creates has no style system yet"),),))
    view_menu = Menu("View", (_shared_view_block(authors=False),))
    tools_menu = Menu("Tools", ((_page("tools.ask", "Ask the Assistant…", "Write to the assistant in the chat"),),))
    return Manifest(
        "creates",
        (
            _file_menu(title="Claudia Creates"),
            edit_menu,
            format_menu,
            view_menu,
            tools_menu,
            _config_menu(),
            _help_menu("Claudia Creates"),
        ),
    )


# ----------------------------------------------------------------------------------------------------- GtkBuilder XML


def _item_element(parent: ET.Element, action: Action) -> None:
    item = ET.SubElement(parent, "item")
    label = ET.SubElement(item, "attribute", name="label", translatable="yes")
    label.text = action.label
    target = ET.SubElement(item, "attribute", name="action")
    target.text = f"win.{action.id}"


def _submenu_element(parent: ET.Element, submenu: Submenu) -> None:
    """``<submenu>``: GTK's own nested-flyout element, holding one ``<section>`` of items — the GMenu-XML shape for
    exactly what ``MenuBar.vue``'s ``items`` property draws as a flyout on the web side."""
    element = ET.SubElement(parent, "submenu")
    label = ET.SubElement(element, "attribute", name="label", translatable="yes")
    label.text = submenu.label
    section = ET.SubElement(element, "section")
    for action in submenu.items:
        _item_element(section, action)


def _menu_tree(manifest: Manifest) -> ET.Element:
    interface = ET.Element("interface")
    for menu in manifest.menus:
        menu_element = ET.SubElement(interface, "menu", id=menu.id)
        for section in menu.sections:
            section_element = ET.SubElement(menu_element, "section")
            for entry in section:
                if isinstance(entry, Submenu):
                    _submenu_element(section_element, entry)
                else:
                    _item_element(section_element, entry)
    ET.indent(interface)
    return interface


def menu_elements(manifest: Manifest) -> str:
    """Only the ``<menu>`` elements, to be merged into the layout file of a window (see ``window.ui``)."""
    return "\n  ".join(ET.tostring(menu, encoding="unicode").strip() for menu in _menu_tree(manifest))


def menu_xml(manifest: Manifest) -> str:
    """GtkBuilder XML for the menus of ``manifest``: one ``<menu id="menu-file">`` and so on.

    Every item calls the window action ``win.<id>`` and its label is marked translatable (E5.7).
    """
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<interface>\n  {menu_elements(manifest)}\n</interface>\n'
