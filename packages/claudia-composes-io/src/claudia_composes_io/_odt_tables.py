"""The tables of an odt (E9.32): which of the file's ``table:table`` are regular tables the model holds, and how the
model's tables are written as ``table:table``. What a regular table is, is decided by :mod:`._tables`; this module only
knows the elements.

A table that is not regular -- a nested table, a cell with several paragraphs, a picture or a formula, row groups, a
table before the first paragraph or after a table of contents -- stays in the file as it was; the import counts it as a
``"table"``.

Written, a table is a ``table:table`` with a ``table:table-column`` for every column, its header rows in a
``table:table-header-rows`` (which a program repeats on every page), and a ``table:table-cell`` for every cell that
starts a rectangle (``table:number-columns-spanned`` and ``table:number-rows-spanned``) with a
``table:covered-table-cell`` for every position it reaches over. A cell holds one paragraph in the style of its role.
The borders and the fill of the look are the cell's own automatic style, since an odt paragraph style has no box that a
table cell takes over; the width of the table and of its columns are automatic styles too.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from lxml import etree

from claudia_composes import TextModel
from claudia_core import PageSetup, TableDef
from claudia_odf_io import NS, hidden_content, inches
from claudia_opc_io import EMU_PER_POINT

from ._layout import sides_of
from ._odt_references import read_words
from ._tables import CellLook, FileCell, FileTable, WriteCell, cell_look, column_shares, read_table, write_grid


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


TABLE = _q("table", "table")
_COLUMN = _q("table", "table-column")
_HEADER_ROWS = _q("table", "table-header-rows")
_ROW = _q("table", "table-row")
_CELL = _q("table", "table-cell")
_COVERED = _q("table", "covered-table-cell")
_P = _q("text", "p")
_STYLE_NAME = _q("table", "style-name")
_REPEATED_ROWS = _q("table", "number-rows-repeated")
_REPEATED_COLUMNS = _q("table", "number-columns-repeated")
_SPANNED_ROWS = _q("table", "number-rows-spanned")
_SPANNED_COLUMNS = _q("table", "number-columns-spanned")
#: What a table may hold between its columns and rows without being more than a table of words (a program writes them
#: for its own use).
_IGNORED = {_q("office", "forms"), _q("table", "table-source"), _q("table", "shapes")}
#: How many rows or columns a repeat may stand for, so that a file cannot ask for a table of millions of cells.
_MOST = 1_000
_EMU_PER_CM = 360_000
_POINTS_PER_INCH = 72
_CM_PER_INCH = 2.54


def text_width_in(page: PageSetup | None) -> float | None:
    """The width of the text of ``page`` in inches (``None`` for no page)."""
    if page is None:
        return None
    across = sides_of(page)[0] - page.margin_left - page.margin_right
    return across / 1000 / _POINTS_PER_INCH


# --------------------------------------------------------------------------------------------------- reading
@dataclass(frozen=True)
class OdtTable:
    """A ``table:table`` of the flow: ``paragraph`` is the index (among the paragraphs of the flow) of the paragraph it
    follows, and ``grid`` what the file says of it, ``None`` when it is not a regular table."""

    element: etree._Element
    paragraph: int | None
    grid: FileTable | None


def styles_of(*roots: etree._Element | None) -> dict[str, etree._Element]:
    """The ``style:style`` of the families table and table-column in ``roots`` (the automatic styles first), by name."""
    found: dict[str, etree._Element] = {}
    for root in roots:
        if root is None:
            continue
        for style in root.iter(_q("style", "style")):
            if style.get(_q("style", "family")) in ("table", "table-column"):
                found.setdefault(style.get(_q("style", "name"), ""), style)
    return found


def file_table(
    element: etree._Element, paragraph: int | None, styles: dict[str, etree._Element], text_inches: float | None
) -> OdtTable:
    """What ``element`` is: its grid when it is a regular table."""
    return OdtTable(element, paragraph, _read(element, styles, text_inches))


def _read(element: etree._Element, styles: dict[str, etree._Element], text_inches: float | None) -> FileTable | None:
    columns: list[etree._Element] = []
    grid: list[tuple[FileCell, ...]] = []
    header = 0
    seen_body = False
    for child in element:
        tag = child.tag
        if not isinstance(tag, str) or tag in _IGNORED:
            continue
        if tag == _COLUMN:
            columns += [child] * _repeat(child, _REPEATED_COLUMNS)
        elif tag == _HEADER_ROWS and not seen_body:
            rows = _rows(child, len(columns))
            if rows is None or not rows:
                return None
            grid += rows
            header += len(rows)
        elif tag == _ROW:
            seen_body = True
            rows = _rows([child], len(columns))
            if rows is None:
                return None
            grid += rows
        else:
            return None
    if not columns or not grid or len(columns) > _MOST:
        return None
    return FileTable(tuple(grid), header, _widths(columns, styles), _table_width(element, styles, text_inches))


def _repeat(element: etree._Element, attribute: str) -> int:
    try:
        return min(_MOST + 1, max(1, int(element.get(attribute, "1"))))
    except ValueError:
        return 1


def _rows(parent: Iterable[etree._Element], columns: int) -> list[tuple[FileCell, ...]] | None:
    out: list[tuple[FileCell, ...]] = []
    for row in parent:
        if row.tag != _ROW:
            return None
        cells = _cells(row)
        if cells is None or len(cells) != columns:
            return None
        out += [cells] * _repeat(row, _REPEATED_ROWS)
        if len(out) > _MOST:
            return None
    return out


def _cells(row: etree._Element) -> tuple[FileCell, ...] | None:
    out: list[FileCell] = []
    for cell in row:
        if cell.tag not in (_CELL, _COVERED):
            return None
        if cell.get(_q("table", "formula")) is not None:
            return None
        words = _words(cell)
        if words is None:
            return None
        if cell.tag == _COVERED:
            found = FileCell("", 1, 1, True)
        else:
            found = FileCell(words, _span(cell, _SPANNED_COLUMNS), _span(cell, _SPANNED_ROWS))
        out += [found] * _repeat(cell, _REPEATED_COLUMNS)
        if len(out) > _MOST:
            return None
    return tuple(out)


def _span(cell: etree._Element, attribute: str) -> int:
    try:
        return max(1, int(cell.get(attribute, "1")))
    except ValueError:
        return 1


def _words(cell: etree._Element) -> str | None:
    """The words of a cell, or ``None`` when it holds more than words: several paragraphs with words in them, a
    heading, a list, a table, a picture, a note, a field or a comment."""
    filled = []
    for child in cell:
        if not isinstance(child.tag, str):
            continue
        if child.tag != _P:
            return None
        if hidden_content(child):
            return None
        text, references = read_words(child)
        if references:
            return None
        if text.strip():
            filled.append(text)
    return filled[0] if len(filled) == 1 else ("" if not filled else None)


def _widths(columns: list[etree._Element], styles: dict[str, etree._Element]) -> tuple[int, ...] | None:
    """The proportions of the columns when the file gives one for every column: as relative widths (``2*``) or as
    lengths."""
    relative, absolute = [], []
    for column in columns:
        properties = _properties(styles.get(column.get(_STYLE_NAME, "")), "table-column-properties")
        rel = properties.get(_q("style", "rel-column-width"), "")
        relative.append(int(rel[:-1]) if rel.endswith("*") and rel[:-1].isdigit() else 0)
        length = inches(properties.get(_q("style", "column-width")))
        absolute.append(round(length * 10_000) if length else 0)
    for found in (absolute, relative):
        if all(each > 0 for each in found):
            return tuple(found)
    return None


def _table_width(element: etree._Element, styles: dict[str, etree._Element], text_inches: float | None) -> int | None:
    """How much of the line the table takes in hundredths of a percent: ``style:rel-width`` or, of the text's width,
    ``style:width``."""
    properties = _properties(styles.get(element.get(_STYLE_NAME, "")), "table-properties")
    relative = properties.get(_q("style", "rel-width"), "")
    if relative.endswith("%"):
        try:
            return round(float(relative[:-1]) * 100)
        except ValueError:
            return None
    length = inches(properties.get(_q("style", "width")))
    if length and text_inches:
        return round(length * 10_000 / text_inches)
    return None


def _properties(style: etree._Element | None, kind: str) -> dict[str, str]:
    """The attributes of ``style:<kind>`` of a style, by clark name."""
    if style is None:
        return {}
    found = style.find(f"style:{kind}", NS)
    return {str(key): str(value) for key, value in found.attrib.items()} if found is not None else {}


def read_tables(tables: Iterable[OdtTable], language: str | None) -> list[tuple[OdtTable, TableDef | None]]:
    """The tables of a file with the definition the text holds for each, ``None`` for one that is not regular. The
    regular ones are called ``t1``, ``t2``... in the order of the file, which is what both the import and the patch of
    a kept file go by."""
    out: list[tuple[OdtTable, TableDef | None]] = []
    taken = 0
    for each in tables:
        definition = (
            None if each.grid is None or each.paragraph is None else read_table(each.grid, f"t{taken + 1}", language)
        )
        taken += definition is not None
        out.append((each, definition))
    return out


# --------------------------------------------------------------------------------------------------- writing
class TableStyles:
    """The automatic styles the tables written need: for the table, each column, each look of a cell and each paragraph
    that aligns its numbers right. ``taken`` has the names a file already uses, so that a table put into a kept file
    does not take them; ``new`` collects the XML of the styles to add."""

    def __init__(self, taken: Iterable[str] = ()) -> None:
        self.taken = set(taken)
        self.new: list[str] = []
        self._cells: dict[tuple[object, ...], str] = {}
        self._right: dict[str, str] = {}
        self._numbers = 0

    def _name(self, stem: str) -> str:
        while True:
            self._numbers += 1
            name = f"{stem}{self._numbers}"
            if name not in self.taken:
                self.taken.add(name)
                return name

    def table(self, share: int, centimetres: float) -> str:
        """A table that takes ``share`` hundredths of a percent of the line, ``centimetres`` wide."""
        name = self._name("ClaudiaTable")
        self.new.append(
            f'<style:style xmlns:style="{NS["style"]}" xmlns:table="{NS["table"]}" style:name="{name}" '
            f'style:family="table"><style:table-properties style:width="{_cm(centimetres)}cm" '
            f'style:rel-width="{share / 100:g}%" table:align="margins"/></style:style>'
        )
        return name

    def column(self, share: int, centimetres: float) -> str:
        """A column of ``share`` hundredths of the table's width."""
        name = self._name("ClaudiaColumn")
        self.new.append(
            f'<style:style xmlns:style="{NS["style"]}" style:name="{name}" style:family="table-column">'
            f'<style:table-column-properties style:column-width="{_cm(centimetres)}cm" '
            f'style:rel-column-width="{share}*"/></style:style>'
        )
        return name

    def cell(self, look: CellLook) -> str:
        """A cell with the borders and the fill ``look`` says."""
        key = (look.fill, look.sides)
        if key not in self._cells:
            name = self._name("ClaudiaCell")
            borders = "".join(
                f' fo:border-{side}="{_border(found)}"'
                for side, found in zip(("top", "right", "bottom", "left"), look.sides, strict=True)
            )
            fill = (
                f' fo:background-color="#{look.fill[0]:02x}{look.fill[1]:02x}{look.fill[2]:02x}"' if look.fill else ""
            )
            self.new.append(
                f'<style:style xmlns:style="{NS["style"]}" xmlns:fo="{NS["fo"]}" style:name="{name}" '
                f'style:family="table-cell"><style:table-cell-properties fo:padding="0.1cm"{borders}{fill}/>'
                "</style:style>"
            )
            self._cells[key] = name
        return self._cells[key]

    def right(self, parent: str) -> str:
        """The paragraph style that is ``parent`` with its words aligned right."""
        if parent not in self._right:
            name = self._name("ClaudiaRight")
            self.new.append(
                f'<style:style xmlns:style="{NS["style"]}" xmlns:fo="{NS["fo"]}" style:name="{name}" '
                f'style:family="paragraph" style:parent-style-name="{parent}">'
                '<style:paragraph-properties fo:text-align="end"/></style:style>'
            )
            self._right[parent] = name
        return self._right[parent]


def _cm(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".") or "0"


def _border(side: tuple[tuple[int, int, int], int] | None) -> str:
    if side is None:
        return "none"
    (red, green, blue), width = side
    return f"{max(0.25, width / EMU_PER_POINT):g}pt solid #{red:02x}{green:02x}{blue:02x}"


def write_table(
    model: TextModel,
    definition: TableDef,
    styles: TableStyles,
    paragraph: Callable[[str, str], etree._Element],
    paragraph_style: Callable[[str], str],
    name: str,
) -> etree._Element:
    """``definition`` as a ``table:table`` called ``name``. ``paragraph(style, words)`` makes the paragraph of a cell,
    ``paragraph_style(style)`` says the odt name of a paragraph style of the model."""
    grid = write_grid(definition, model.language)
    shares = column_shares(definition)
    share = definition.width if definition.width is not None else 10_000
    width = (text_width_in(model.page) or 6.0) * _CM_PER_INCH * share / 10_000
    table = etree.Element(TABLE, nsmap={"table": NS["table"], "text": NS["text"]})
    table.set(_q("table", "name"), name)
    table.set(_STYLE_NAME, styles.table(share, width))
    for each in shares:
        etree.SubElement(table, _COLUMN).set(_STYLE_NAME, styles.column(each, width * each / 10_000))
    header = etree.SubElement(table, _HEADER_ROWS) if definition.header_rows else None
    for index, line in enumerate(grid):
        parent = header if header is not None and index < definition.header_rows else table
        row = etree.SubElement(parent, _ROW)
        for spec in line:
            row.append(_cell(model, spec, styles, paragraph, paragraph_style))
    return table


def _cell(
    model: TextModel,
    spec: WriteCell,
    styles: TableStyles,
    paragraph: Callable[[str, str], etree._Element],
    paragraph_style: Callable[[str], str],
) -> etree._Element:
    """One position of the grid: a cell, or the cover of one that starts elsewhere (an odt has an element for every
    position a cell reaches over)."""
    cell = etree.Element(_COVERED if spec.covered else _CELL)
    cell.set(_STYLE_NAME, styles.cell(cell_look(model, spec.style)))
    if not spec.covered:
        if spec.cols > 1:
            cell.set(_SPANNED_COLUMNS, str(spec.cols))
        if spec.rows > 1:
            cell.set(_SPANNED_ROWS, str(spec.rows))
    words = paragraph(spec.style, "" if spec.covered else spec.text)
    if spec.number:
        words.set(_q("text", "style-name"), styles.right(paragraph_style(spec.style)))
    cell.append(words)
    return cell
