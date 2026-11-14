"""The page and the language of an odt: written into ``styles.xml``, read back, and changed in a file that has them
(D454).

The page of a text is a ``style:page-layout`` (the paper, how it lies, the margins) that the first
``style:master-page`` names; whether pages carry their number is a ``text:page-number`` in that master page's footer.
The language is what the default paragraph style says in ``fo:language``, ``fo:script`` and ``fo:country``; a text with
no language is one with ``zxx``, which is what LibreOffice writes for it.
"""

from __future__ import annotations

from dataclasses import dataclass

from lxml import etree

from claudia_core import PageSetup
from claudia_odf_io import NS, XmlPart

from ._layout import language_from_parts, length_to_mpt, mpt_to_points, page_from_sizes, parts_of_language, sides_of
from .docx import UnsupportedEdit


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


_LAYOUT_NAME = "pm1"
_MASTER_NAME = "Standard"
FOOTER_STYLE = "Footer"
FOOTER_STYLE_XML = (
    f'<style:style style:name="{FOOTER_STYLE}" style:family="paragraph" style:class="extra">'
    '<style:paragraph-properties fo:text-align="center"/></style:style>'
)
_FOOTER = (
    f'<style:footer><text:p text:style-name="{FOOTER_STYLE}"><text:page-number text:select-page="current">1'
    "</text:page-number></text:p></style:footer>"
)
_FOOTER_LOOK = (
    '<style:footer-style><style:header-footer-properties fo:min-height="0.6cm" fo:margin-top="0.3cm"/>'
    "</style:footer-style>"
)
_MARGINS = ("top", "right", "bottom", "left")


# -- writing a new file ----------------------------------------------------------------------------------------------
def layout_attributes(page: PageSetup) -> dict[str, str]:
    """What the ``style:page-layout-properties`` of ``page`` say, by attribute name."""
    width, height = sides_of(page)
    found = {
        "fo:page-width": mpt_to_points(width),
        "fo:page-height": mpt_to_points(height),
        "style:print-orientation": page.orientation,
    }
    for side, value in zip(
        _MARGINS, (page.margin_top, page.margin_right, page.margin_bottom, page.margin_left), strict=True
    ):
        found[f"fo:margin-{side}"] = mpt_to_points(value)
    return found


def page_layout_xml(page: PageSetup) -> str:
    """The ``style:page-layout`` of ``page``, for the automatic styles of ``styles.xml``."""
    said = " ".join(f'{name}="{value}"' for name, value in layout_attributes(page).items())
    footer = _FOOTER_LOOK if page.page_numbers else ""
    return (
        f'<style:page-layout style:name="{_LAYOUT_NAME}"><style:page-layout-properties {said}/>{footer}'
        "</style:page-layout>"
    )


def master_page_xml(page: PageSetup) -> str:
    """The master page that names the layout, with a footer that has the page number when ``page`` says so."""
    footer = _FOOTER if page.page_numbers else ""
    return (
        f'<style:master-page style:name="{_MASTER_NAME}" style:page-layout-name="{_LAYOUT_NAME}">{footer}'
        "</style:master-page>"
    )


def default_style_xml(language: str | None) -> str:
    """The default paragraph style that says ``language``; nothing for a text that has none."""
    if language is None:
        return ""
    name, script, country = parts_of_language(language)
    said = (
        f'fo:language="{name}"'
        + (f' fo:script="{script}"' if script else "")
        + (f' fo:country="{country}"' if country else "")
    )
    return f'<style:default-style style:family="paragraph"><style:text-properties {said}/></style:default-style>'


# -- reading ---------------------------------------------------------------------------------------------------------
@dataclass
class Setup:
    """What ``styles.xml`` says of the page and the language; ``None`` for what it does not say (or says in a way the
    model cannot hold)."""

    page: PageSetup | None = None
    language: str | None = None
    #: A page the model cannot hold (a side that is no length, margins that leave no room).
    odd_page: bool = False


def _master(styles: etree._Element) -> etree._Element | None:
    return styles.find("office:master-styles/style:master-page", NS)


def _layout_of(styles: etree._Element, master: etree._Element) -> etree._Element | None:
    name = master.get(_q("style", "page-layout-name"))
    for layout in styles.iterfind("office:automatic-styles/style:page-layout", NS):
        if layout.get(_q("style", "name")) == name:
            return layout.find("style:page-layout-properties", NS)
    return None


def _length(properties: etree._Element, name: str) -> int | None:
    return length_to_mpt(properties.get(_q("fo", name)))


def _default_text_properties(styles: etree._Element) -> etree._Element | None:
    for style in styles.iterfind("office:styles/style:default-style", NS):
        if style.get(_q("style", "family")) == "paragraph":
            return style.find("style:text-properties", NS)
    return None


def read_setup(styles: etree._Element | None) -> Setup:
    """The page and the language of the file whose ``styles.xml`` is ``styles``."""
    found = Setup()
    if styles is None:
        return found
    if (properties := _default_text_properties(styles)) is not None:
        found.language = language_from_parts(
            properties.get(_q("fo", "language")),
            properties.get(_q("fo", "script")),
            properties.get(_q("fo", "country")),
        )
    master = _master(styles)
    layout = _layout_of(styles, master) if master is not None else None
    if master is None or layout is None:
        return found
    shorthand = _length(layout, "margin")
    sides = tuple(_length(layout, f"margin-{side}") for side in _MARGINS)
    margins = tuple(shorthand if side is None else side for side in sides)
    numbers = any(True for _ in master.iter(_q("text", "page-number")))
    page = page_from_sizes(
        _length(layout, "page-width"),
        _length(layout, "page-height"),
        margins,  # type: ignore[arg-type]
        landscape=layout.get(_q("style", "print-orientation")) == "landscape",
        page_numbers=numbers,
    )
    found.page, found.odd_page = page, page is None
    return found


# -- changing a file that has them -----------------------------------------------------------------------------------
def patch_page(part: XmlPart, before: PageSetup, after: PageSetup) -> bool:
    """Make the page of the file ``after`` where it differs from ``before``; did it change anything?"""
    if before == after:
        return False
    master = _master(part.root)
    layout = _layout_of(part.root, master) if master is not None else None
    if master is None or layout is None:
        raise UnsupportedEdit("this file has no page layout to change")
    if (before.paper, before.width, before.height, before.orientation) != (
        after.paper,
        after.width,
        after.height,
        after.orientation,
    ) or (before.margin_top, before.margin_right, before.margin_bottom, before.margin_left) != (
        after.margin_top,
        after.margin_right,
        after.margin_bottom,
        after.margin_left,
    ):
        part.set_attributes(layout, layout_attributes(after))
    if before.page_numbers != after.page_numbers:
        _patch_page_numbers(part, master, after.page_numbers)
    return True


def _patch_page_numbers(part: XmlPart, master: etree._Element, wanted: bool) -> None:
    fields = list(master.iter(_q("text", "page-number")))
    if not wanted:
        for field in fields:
            part.remove(field)
        return
    footer = master.find("style:footer", NS)
    if footer is None:
        part.insert_into(master, _FOOTER.encode())
    else:
        paragraph = footer.find("text:p", NS)
        number = b'<text:page-number text:select-page="current">1</text:page-number>'
        if paragraph is None:
            part.insert_into(footer, f'<text:p text:style-name="{FOOTER_STYLE}">'.encode() + number + b"</text:p>")
        else:
            part.insert_into(paragraph, number)


def patch_language(part: XmlPart, before: str | None, after: str | None) -> bool:
    """Make the language of the file ``after``; did it change anything?"""
    if before == after:
        return False
    styles = part.root.find("office:styles", NS)
    if styles is None:
        raise UnsupportedEdit("this file has no default style to give a language")
    default = next(
        (s for s in styles.iterfind("style:default-style", NS) if s.get(_q("style", "family")) == "paragraph"), None
    )
    if default is None:
        if after is not None:
            part.insert_into(styles, default_style_xml(after).encode(), at_start=True)
        return after is not None
    properties = default.find("style:text-properties", NS)
    if properties is None:
        if after is not None:
            part.insert_into(
                default, default_style_xml(after).split(">", 1)[1].rsplit("</style:default-style>", 1)[0].encode()
            )
        return after is not None
    name, script, country = parts_of_language(after)
    values = {"fo:language": name}
    for attribute, value in (("fo:script", script), ("fo:country", country)):
        if value is not None:
            values[attribute] = value
        elif properties.get(_q("fo", attribute.split(":")[1])) is not None:
            values[attribute] = "none"
    part.set_attributes(properties, values)
    return True
