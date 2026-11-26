"""The menus of the manifest as GtkBuilder XML (E5.1, D27): the only part of the menu definition that is GTK's.

The definition itself is ``claudia_menus.manifest`` in ``clients/contract`` (D1643); this module turns it into the
``<menu>`` elements that ``data/window.ui`` merges in. It still imports no GTK, so it is tested anywhere.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Mapping

from claudia_menus.manifest import Action, Manifest, Submenu, Translate

__all__ = ["WHY_ACTION", "menu_button_id", "menu_elements", "menu_xml"]


def _translatable(action: Action) -> bool:
    """Everything except :data:`LANGUAGES`' own autonyms (see this module's docstring)."""
    return not action.id.startswith("config.language.")


def _item_element(parent: ET.Element, action: Action, translate: Translate) -> None:
    item = ET.SubElement(parent, "item")
    label = ET.SubElement(item, "attribute", name="label", translatable="yes")
    label.text = translate(action.label) if _translatable(action) else action.label
    target = ET.SubElement(item, "attribute", name="action")
    target.text = f"win.{action.id}"
    if action.keys.default:
        # Shown, whoever listens for it: GTK draws the ``accel`` attribute next to the label without binding it.
        accel = ET.SubElement(item, "attribute", name="accel")
        accel.text = action.keys.default


def _submenu_element(parent: ET.Element, submenu: Submenu, translate: Translate) -> None:
    """``<submenu>``: GTK's own nested-flyout element, holding one ``<section>`` of items — the GMenu-XML shape for
    exactly what ``MenuBar.vue``'s ``items`` property draws as a flyout on the web side."""
    element = ET.SubElement(parent, "submenu")
    label = ET.SubElement(element, "attribute", name="label", translatable="yes")
    label.text = translate(submenu.label)
    section = ET.SubElement(element, "section")
    for action in submenu.items:
        _item_element(section, action, translate)


#: The window's action for the line that says why a menu has nothing left, never enabled, so GTK greys the line (D1603).
WHY_ACTION = "menu-why"


def _why_element(menu_element: ET.Element, why: str) -> None:
    """The one greyed line of a menu with nothing left: the page's own sentence, already in the person's language."""
    item = ET.SubElement(ET.SubElement(menu_element, "section"), "item")
    ET.SubElement(item, "attribute", name="label").text = why
    ET.SubElement(item, "attribute", name="action").text = f"win.{WHY_ACTION}"


def _menu_tree(manifest: Manifest, translate: Translate, empty: Mapping[str, str]) -> ET.Element:
    interface = ET.Element("interface")
    for menu in manifest.menus:
        menu_element = ET.SubElement(interface, "menu", id=menu.id)
        why = empty.get(menu.word)
        if not menu.sections and why:
            _why_element(menu_element, why)
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


def menu_elements(
    manifest: Manifest, *, translate: Translate = lambda text: text, empty: Mapping[str, str] | None = None
) -> str:
    """Only the ``<menu>`` elements, to be merged into the layout file of a window (see ``window.ui``).

    ``translate`` is applied here, while the XML is built, rather than through GtkBuilder's own translation-domain
    machinery: the shell installs exactly one gettext mechanism (``i18n.install_translation``, bound to Python's own
    ``_()``), and calling ``translate`` directly reuses it instead of also wiring ``Gtk.Builder.set_translation_domain``
    and glibc's ``bindtextdomain`` for a second, parallel one. Left at the default identity function, this (and
    everything it calls) needs no locale installed at all — which is what every test below does.

    ``empty``: the menus with nothing left, by their word in lower case, and the page's sentence that says why
    (slice 6 of the menu work, D1645); such a menu holds that one greyed line.
    """
    tree = _menu_tree(manifest, translate, empty or {})
    return "\n  ".join(ET.tostring(menu, encoding="unicode").strip() for menu in tree)


def menu_xml(
    manifest: Manifest, *, translate: Translate = lambda text: text, empty: Mapping[str, str] | None = None
) -> str:
    """GtkBuilder XML for the menus of ``manifest``: one ``<menu id="menu-file">`` and so on.

    Every item calls the window action ``win.<id>``; ``translatable="yes"`` on its label is a GtkBuilder hint for
    any future tooling (xgettext and the like) that reads this XML directly; translation itself has already
    happened by the time this text is written, under ``menu_elements``'s own ``translate`` parameter above (E5.7).
    """
    elements = menu_elements(manifest, translate=translate, empty=empty)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<interface>\n  {elements}\n</interface>\n'
