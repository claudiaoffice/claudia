"""The looks of a workbook's cells in a new ods file (E6.14, D349).

Body text is the file's *Default* cell style. A style with a name a person gave it becomes a named cell style
(``office:styles`` in ``styles.xml``) with that name; every look a cell has is an automatic style (``ce1``,
``ce2``... in ``content.xml``) based on its named style, as LibreOffice writes direct formats. Number formats become
number styles (:mod:`.odf_numbers`). Row and column style ranges become the rows' and columns' default cell styles.
"""

from __future__ import annotations

from collections.abc import Mapping

from lxml import etree

from claudia_computes import WorkbookModel
from claudia_computes.cellstyles import DEFAULT_CELL_STYLE
from claudia_odf_io import NS

from .cell_looks import GENERAL, CellLook, LookExport, first_family, points, solid
from .odf_numbers import number_style

_ALIGN = {"left": "start", "start": "start", "center": "center", "right": "end", "end": "end", "justify": "justify"}
_DEFAULT = "Default"


_DECLARED = {prefix: uri for prefix, uri in NS.items() if prefix != "xml"}


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def _length(pt: float) -> str:
    return f"{round(pt, 2):g}pt"


def _border(value: str) -> str:
    if value == "none":
        return "none"
    width, line, colour = value.split(" ", 2)
    rgb = solid(colour) or "000000"
    return f"{_length(points(width) or 0.75)} {line} #{rgb.lower()}"


def _text_properties(css: Mapping[str, str]) -> dict[str, str]:
    props: dict[str, str] = {}
    if "font-family" in css:
        family = first_family(css["font-family"])
        props["fo:font-family"] = f"'{family}'" if " " in family else family
    size = points(css.get("font-size", ""))
    if size:
        props["fo:font-size"] = _length(size)
    weight = css.get("font-weight", "normal")
    bold = weight in ("bold", "bolder") or (weight.isdigit() and int(weight) >= 600)  # noqa: PLR2004
    props["fo:font-weight"] = "bold" if bold else "normal"
    props["fo:font-style"] = "italic" if css.get("font-style") in ("italic", "oblique") else "normal"
    decoration = css.get("text-decoration", "")
    if "underline" in decoration:
        props.update({"style:text-underline-style": "solid", "style:text-underline-width": "auto",
                      "style:text-underline-color": "font-color"})  # fmt: skip
    if "line-through" in decoration:
        props["style:text-line-through-style"] = "solid"
    colour = solid(css.get("color", ""))
    if colour:
        props["fo:color"] = f"#{colour.lower()}"
    return props


def _cell_properties(css: Mapping[str, str]) -> dict[str, str]:
    colour = solid(css.get("background-color", "transparent"))
    props = {"fo:background-color": f"#{colour.lower()}" if colour else "transparent"}
    for side in ("top", "right", "bottom", "left"):
        props[f"fo:border-{side}"] = _border(css.get(f"border-{side}", "none"))
    props["style:vertical-align"] = {"top": "top", "middle": "middle"}.get(css.get("vertical-align", ""), "bottom")
    if css.get("white-space") in ("normal", "pre-wrap"):
        props["fo:wrap-option"] = "wrap"
    props["style:text-align-source"] = "fix" if "text-align" in css else "value-type"
    return props


def _paragraph_properties(css: Mapping[str, str]) -> dict[str, str]:
    props = {}
    if "text-align" in css:
        props["fo:text-align"] = _ALIGN.get(css["text-align"], "start")
    indent = points(css.get("padding-left", ""))
    if indent:
        props["fo:margin-left"] = _length(indent)
    return props


def _with(element: etree._Element, local: str, props: Mapping[str, str]) -> None:
    if not props:
        return
    child = etree.SubElement(element, _q("style", local))
    for name, value in props.items():
        prefix, _, attribute = name.partition(":")
        child.set(_q(prefix, attribute), value)


class OdsLookWriter:
    """Collects the styles a new ods file needs while its cells are written, then hands out its two style lists."""

    def __init__(self, model: WorkbookModel, prefix: str = "") -> None:
        self.model = model
        self.prefix = prefix
        self.looks = LookExport(model)
        self._automatic: dict[CellLook, str] = {}
        self._named: dict[str, str] = {}
        self._numbers: dict[tuple[str, bool], str] = {}
        self._number_elements: dict[bool, list[etree._Element]] = {True: [], False: []}
        self._style_elements: list[etree._Element] = []

    def cell_style(self, box: str, words: str) -> str:
        """The name of the automatic style for a cell with these two styles, made the first time."""
        return self.name_for(self.looks.look(box, words))

    def name_for(self, look: CellLook) -> str:
        """The name of the automatic style for ``look``, made the first time."""
        if look not in self._automatic:
            name = f"{self.prefix}ce{len(self._automatic) + 1}"
            parent = self._named_style(look.parent)
            self._automatic[look] = name
            self._style_elements.append(self._style(name, look, parent, named=False))
        return self._automatic[look]

    def _named_style(self, style_id: str) -> str:
        if style_id == DEFAULT_CELL_STYLE:
            return _DEFAULT
        if style_id not in self._named:
            self._named[style_id] = style_id
        return self._named[style_id]

    def _number(self, code: str, *, named: bool) -> str | None:
        if code == GENERAL:
            return None
        key = (code, named)
        if key not in self._numbers:
            name = f"{self.prefix}{'NS' if named else 'N'}{len(self._numbers) + 1}"
            self._number_elements[named].extend(number_style(code, name))
            self._numbers[key] = name
        return self._numbers[key]

    def _style(self, name: str, look: CellLook, parent: str | None, *, named: bool) -> etree._Element:
        element = etree.Element(_q("style", "style"), nsmap=_DECLARED)  # (it may go into a file on its own)
        element.set(_q("style", "name"), name)
        element.set(_q("style", "family"), "table-cell")
        if parent is not None:
            element.set(_q("style", "parent-style-name"), parent)
        if named and name != _DEFAULT:
            element.set(_q("style", "display-name"), self.model.styles.get(name).name)
        data = self._number(look.code, named=named)
        if data is not None:
            element.set(_q("style", "data-style-name"), data)
        css = look.style
        _with(element, "table-cell-properties", _cell_properties(css))
        _with(element, "paragraph-properties", _paragraph_properties(css))
        _with(element, "text-properties", _text_properties(css))
        return element

    def automatic_styles(self) -> list[etree._Element]:
        """The number styles and cell styles that go into ``content.xml``'s automatic styles."""
        return [*self._number_elements[False], *self._style_elements]

    def office_styles(self) -> list[etree._Element]:
        """The named cell styles (Default first) and their number styles, for ``styles.xml``."""
        named = [self._style(_DEFAULT, self.looks.named_look(DEFAULT_CELL_STYLE), None, named=True)]
        named.extend(self._style(i, self.looks.named_look(i), _DEFAULT, named=True) for i in self._named)
        return [*self._number_elements[True], *named]


class OdsRestyler(OdsLookWriter):
    """The styles an *edited* ods file needs for the looks that changed: automatic styles with names of their own
    (``claudia-ce1``...), based on the file's named style of the same name -- ``Default`` for Body text -- and the
    named styles the file does not have yet, for its ``styles.xml``."""

    def __init__(self, model: WorkbookModel, styles: etree._Element | None) -> None:
        super().__init__(model, prefix="claudia-")
        self._file: dict[str, str] = {}
        if styles is not None:
            for element in styles.iterfind("office:styles/style:style", NS):
                if element.get(_q("style", "family")) != "table-cell":
                    continue
                name = element.get(_q("style", "name"), "")
                shown = element.get(_q("style", "display-name")) or name
                self._file.setdefault(shown.casefold(), name)
        self.has_default = _DEFAULT.casefold() in self._file

    def _named_style(self, style_id: str) -> str:
        if style_id == DEFAULT_CELL_STYLE:
            return _DEFAULT
        known = self._file.get(self.model.styles.get(style_id).name.casefold())
        return known if known is not None else super()._named_style(style_id)

    def default_name(self) -> str:
        """What a cell, row or column without a look of its own is given: the file's Default style."""
        return _DEFAULT

    def new_named_styles(self) -> list[etree._Element]:
        """The named styles (and their number styles) the file does not have yet, for ``office:styles``."""
        made = [
            self._style(style_id, self.looks.named_look(style_id), _DEFAULT if self.has_default else None, named=True)
            for style_id in self._named
        ]
        return [*self._number_elements[True], *made]
