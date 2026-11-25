"""The menus of the manifest as GtkBuilder XML (E5.1, D27): the only part of the menu definition that is GTK's.

The definition itself is ``claudia_menus.manifest`` in ``clients/contract`` (D1643); this module turns it into the
``<menu>`` elements that ``data/window.ui`` merges in. It still imports no GTK, so it is tested anywhere.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from claudia_menus.manifest import Action, Manifest, Submenu, Translate

__all__ = ["menu_button_id", "menu_elements", "menu_xml"]


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
