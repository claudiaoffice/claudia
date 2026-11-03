"""The menu and action manifest of the Linux client (E5.1): one list from which the native menus are built.

D4 gives every app four menus, File, Edit, Tools and Help (Undo and Redo are in Edit, D54; Cut, Copy and Paste too,
D74). An action has an id that names *what it does* (``file.save``, ``view.page``) and not where it sits, so a menu can
be rearranged without touching the shell contract. Each action is carried out by one party (:class:`Kind`).

Nothing here imports GTK: the menus are described as data and turned into GtkBuilder XML by :func:`menu_xml`, so the
layout stays in XML (D27) and the manifest can be tested anywhere.
"""

from __future__ import annotations

import enum
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

__all__ = ["Action", "Kind", "Manifest", "Menu", "composes", "menu_elements", "menu_xml"]


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
class Menu:
    """A menu button of the header bar. ``sections`` are groups drawn with a separator between them."""

    label: str
    sections: tuple[tuple[Action, ...], ...]

    @property
    def id(self) -> str:
        """The id of the menu in the generated XML (``menu-file``)."""
        return f"menu-{self.label.lower()}"

    def all_actions(self) -> Iterator[Action]:
        """Every action of the menu, in order."""
        for section in self.sections:
            yield from section


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

        return {
            "app": self.app,
            "menus": [
                {"label": menu.label, "sections": [[one(a) for a in section] for section in menu.sections]}
                for menu in self.menus
            ],
            "header_toggles": [one(a) for a in self.header_toggles],
        }


def _page(action_id: str, label: str, tooltip: str, *, accelerators: tuple[str, ...] = (), checkable: bool = False):
    return Action(action_id, label, Kind.PAGE, tooltip, accelerators, checkable)


def composes() -> Manifest:
    """The menus of claudia composes in the Linux client.

    The web app still has two more menus (Format, View); what they offer is reachable from Tools and the header bar
    here, so D4 holds natively without touching the web app.
    """
    file_menu = Menu(
        "File",
        (
            (
                _page(
                    "file.open", "Open…", "Create a document or open one from the server", accelerators=("<Primary>o",)
                ),
                _page("file.save", "Save", "Make a checkpoint of the document"),
                _page("file.save-named", "Save with a Name…", "Make a checkpoint and give it a name"),
                _page(
                    "file.save-as",
                    "Save As…",
                    "Download the document to this computer",
                    accelerators=("<Primary><Shift>s",),
                ),
            ),
            (_page("file.share", "Share…", "Let other people into the document"),),
            (Action("file.quit", "Quit", Kind.SHELL, "Close Claudia Composes", ("<Primary>q",)),),
        ),
    )
    edit_menu = Menu(
        "Edit",
        (
            (
                _page("edit.undo", "Undo", "Take back your last step"),
                _page("edit.redo", "Redo", "Do your last undone step again"),
            ),
            (
                Action("edit.cut", "Cut", Kind.EDITING, "Move the selection to the clipboard", editing="Cut"),
                Action("edit.copy", "Copy", Kind.EDITING, "Copy the selection to the clipboard", editing="Copy"),
                Action("edit.paste", "Paste", Kind.EDITING, "Insert the clipboard", editing="Paste"),
                Action(
                    "edit.paste-as",
                    "Paste As Plain Text",
                    Kind.EDITING,
                    "Insert the clipboard without formatting",
                    editing="PasteAsPlainText",
                ),
            ),
        ),
    )
    tools_menu = Menu(
        "Tools",
        (
            (
                _page("style.look", "Look of this Style…", "Change how this kind of paragraph looks"),
                _page("style.all", "All Styles…", "List, rename and tidy the styles of this document"),
            ),
            (
                _page("view.page", "Page View", "Show the text as pages instead of a flowing text", checkable=True),
                _page(
                    "view.authors", "Show Who Wrote What", "Colour the text by the person who wrote it", checkable=True
                ),
            ),
            (
                _page("assistant.ask", "Ask the Assistant…", "Write to the assistant in the chat"),
                _page("assistant.review-text", "Review This Text", "Ask the assistant to suggest improvements"),
                _page(
                    "assistant.review-paragraph",
                    "Review This Paragraph",
                    "Ask the assistant about the current paragraph",
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
    help_menu = Menu(
        "Help",
        (
            (
                _page("help.help", "Help", "Keyboard shortcuts and how to work in a document", accelerators=("F1",)),
                Action("help.about", "About Claudia Composes", Kind.SHELL, "Version, authors and licence"),
            ),
        ),
    )
    panel = _page("view.panel", "History and Chat", "Show or hide the history and the chat", checkable=True)
    return Manifest("composes", (file_menu, edit_menu, tools_menu, help_menu), (panel,))


def _menu_tree(manifest: Manifest) -> ET.Element:
    interface = ET.Element("interface")
    for menu in manifest.menus:
        menu_element = ET.SubElement(interface, "menu", id=menu.id)
        for section in menu.sections:
            section_element = ET.SubElement(menu_element, "section")
            for action in section:
                item = ET.SubElement(section_element, "item")
                label = ET.SubElement(item, "attribute", name="label", translatable="yes")
                label.text = action.label
                target = ET.SubElement(item, "attribute", name="action")
                target.text = f"win.{action.id}"
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
