"""The tables of a docx (E9.32): which of the file's ``w:tbl`` are regular tables the model holds, and how the model's
tables are written as ``w:tbl``. What a regular table is, is decided by :mod:`._tables`; this module only knows the
elements.

A table that is not regular -- a nested table, a cell with several paragraphs or a picture, a row that starts or ends
short, a table before the first paragraph -- stays in the file as it was; the import counts it as a ``"table"``.

Written, a table has one ``w:tc`` for every cell that starts a rectangle (``w:gridSpan`` for the columns it reaches
over, ``w:vMerge`` for the rows: ``restart`` in the first and an empty one in every row below), each holding one
paragraph in the style of its role; the borders and the shading of the look are the cell's own properties, since a
docx paragraph style has no box."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from claudia_composes import TextModel
from claudia_core import TableDef

from ._docx_contents import body_order
from ._tables import CellLook, FileCell, FileTable, WriteCell, cell_look, column_shares, read_table, write_grid

#: A page is this many twips wide for a table with no text width to measure: the text of an A4 page with 2.5 cm margins.
_TEXT_TWIPS = 9071
#: What a cell must not hold: a drawing, a note, a field or a content control is more than the words of a box.
_NOT_WORDS = ("w:drawing", "w:pict", "w:object", "w:footnoteReference", "w:endnoteReference", "w:commentReference")
_FIELDS = ("w:fldChar", "w:fldSimple", "w:instrText", "w:sdt")
#: Eighths of a point to a point, for the width of a border (``w:sz``).
_EIGHTHS = 8
_EMU_PER_POINT = 12700


@dataclass(frozen=True)
class DocxTable:
    """A ``w:tbl`` of the body: ``paragraph`` is the index (into ``document.paragraphs``) of the paragraph it follows,
    and ``grid`` what the file says of it, ``None`` when it is not a regular table."""

    element: Any
    paragraph: int | None
    grid: FileTable | None


def file_tables(document: Any) -> list[DocxTable]:  # noqa: ANN401
    """The tables of the body of ``document`` in order, each with what it is."""
    numbers = {p._p: n for n, p in enumerate(document.paragraphs)}  # noqa: SLF001
    in_flow = {n for n, toc in body_order(document) if n is not None and toc is None}
    found = []
    last: int | None = None
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            at = numbers.get(child)
            last = at if at in in_flow else None
        elif child.tag == qn("w:sdt"):
            last = None
        elif child.tag == qn("w:tbl"):
            found.append(DocxTable(child, last, _read(child) if last is not None else None))
    return found


# --------------------------------------------------------------------------------------------------- reading
def _read(table: Any) -> FileTable | None:  # noqa: ANN401
    """``table`` as a :class:`~._tables.FileTable`, or ``None`` when something in it is more than the model holds."""
    if table.find(qn("w:tblPr") + "/" + qn("w:tblCellSpacing")) is not None:
        return None
    rows = []
    for row in table.iterchildren(qn("w:tr")):
        line = _row(row)
        if line is None:
            return None
        rows.append(line)
    if not rows:
        return None
    width = sum(span for _, span, _ in rows[0])
    if any(sum(span for _, span, _ in line) != width for line in rows):
        return None
    grid = _grid(rows, width)
    if grid is None:
        return None
    header = 0
    for row in table.iterchildren(qn("w:tr")):
        if row.find(qn("w:trPr") + "/" + qn("w:tblHeader")) is None:
            break
        header += 1
    return FileTable(grid, header, _widths(table, width), _table_width(table))


def _row(row: Any) -> list[tuple[Any, int, str]] | None:  # noqa: ANN401
    """The cells of a row as ``(w:tc, columns it spans, vMerge: "" for none, "restart" or "continue")``; ``None`` for a
    row that does not start at the first column or leave out some at its end."""
    properties = row.find(qn("w:trPr"))
    if properties is not None and any(properties.find(qn(tag)) is not None for tag in ("w:gridBefore", "w:gridAfter")):
        return None
    cells = []
    for cell in row.iterchildren(qn("w:tc")):
        marks = cell.find(qn("w:tcPr"))
        span = marks.find(qn("w:gridSpan")) if marks is not None else None
        merge = marks.find(qn("w:vMerge")) if marks is not None else None
        try:
            columns = int(span.get(qn("w:val"), "1")) if span is not None else 1
        except ValueError:
            return None
        kind = "" if merge is None else ("restart" if merge.get(qn("w:val")) == "restart" else "continue")
        cells.append((cell, columns, kind))
    return cells


def _grid(rows: list[list[tuple[Any, int, str]]], columns: int) -> tuple[tuple[FileCell, ...], ...] | None:
    """The grid of the cells: where a cell reaches over columns or (``vMerge``) rows, and which positions it covers."""
    texts: dict[tuple[int, int], str] = {}
    spans: dict[tuple[int, int], tuple[int, int]] = {}
    covered: set[tuple[int, int]] = set()
    starts: dict[int, tuple[int, int]] = {}  # the row of the cell a vertical merge started in, by column
    for r, line in enumerate(rows):
        c = 0
        for cell, wide, merge in line:
            if merge == "continue":
                begun = starts.get(c)
                if begun is None or spans[(begun[0], c)][1] != wide:
                    return None  # a continuation of nothing, or of a cell of another width
                spans[(begun[0], c)] = (r - begun[0] + 1, wide)
                covered |= {(r, c + j) for j in range(wide)}
            else:
                words = _words(cell)
                if words is None:
                    return None
                texts[(r, c)] = words
                spans[(r, c)] = (1, wide)
                covered |= {(r, c + j) for j in range(1, wide)}
                if merge == "restart":
                    starts[c] = (r, c)
                else:
                    starts.pop(c, None)
            c += wide
    return tuple(
        tuple(
            FileCell("", covered=True)
            if (r, c) in covered
            else FileCell(texts.get((r, c), ""), spans[(r, c)][1], spans[(r, c)][0])
            for c in range(columns)
        )
        for r in range(len(rows))
    )


def _words(cell: Any) -> str | None:  # noqa: ANN401
    """The words of a cell, or ``None`` when it holds more than words: several paragraphs with words in them, a table, a
    picture, a note, a field or a content control."""
    paragraphs = []
    for child in cell.iterchildren():
        if child.tag == qn("w:tcPr"):
            continue
        if child.tag != qn("w:p"):
            return None
        if any(child.find(f".//{qn(tag)}") is not None for tag in (*_NOT_WORDS, *_FIELDS)):
            return None
        paragraphs.append(_text(child))
    filled = [text for text in paragraphs if text.strip()]
    return None if len(filled) > 1 else (filled[0] if filled else "")


def _text(paragraph: Any) -> str:  # noqa: ANN401
    """The words of a paragraph as python-docx reads them: the runs that are its own or a link's, not those of a
    tracked change."""
    words: list[str] = []
    for run in [*paragraph.iterchildren(qn("w:r")), *paragraph.iterfind(qn("w:hyperlink") + "/" + qn("w:r"))]:
        for part in run:
            if part.tag == qn("w:t"):
                words.append(part.text or "")
            elif part.tag in (qn("w:tab"), qn("w:br"), qn("w:cr")):
                words.append(" ")
    return "".join(words)


def _widths(table: Any, columns: int) -> tuple[int, ...] | None:  # noqa: ANN401
    """The widths of the columns the file's grid gives (in twips), when it gives one for every column."""
    grid = table.find(qn("w:tblGrid"))
    if grid is None:
        return None
    found = []
    for column in grid.iterchildren(qn("w:gridCol")):
        try:
            found.append(int(column.get(qn("w:w"), "0")))
        except ValueError:
            return None
    return tuple(found) if len(found) == columns else None


def _table_width(table: Any) -> int | None:  # noqa: ANN401
    """How much of the line the table takes in hundredths of a percent, when the file says so as a percentage (``pct``
    is in fiftieths of a percent) or in twips (compared with the text of an A4 page)."""
    size = table.find(qn("w:tblPr") + "/" + qn("w:tblW"))
    if size is None:
        return None
    try:
        value = int(size.get(qn("w:w"), "0"))
    except ValueError:
        return None
    kind = size.get(qn("w:type"), "dxa")
    if kind == "pct":
        return value * 2
    return round(value * 10_000 / _TEXT_TWIPS) if kind == "dxa" and value > 0 else None


# --------------------------------------------------------------------------------------------------- writing
def write_table(
    document: Any,  # noqa: ANN401
    model: TextModel,
    definition: TableDef,
    style_id: Callable[[str], str | None],
    after: Any | None = None,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    """Add the table ``definition`` to ``document`` as a ``w:tbl`` and return it: right after the element ``after``, or
    at the end of the body. ``style_id`` gives the Word id of a style of the text (``None``: the default)."""
    grid = write_grid(definition, model.language)
    shares = column_shares(definition)
    table = document.add_table(rows=len(grid), cols=len(definition.columns))
    element = table._tbl  # noqa: SLF001
    _properties(element, definition, shares)
    for index, line in enumerate(grid):
        row = table.rows[index]._tr  # noqa: SLF001
        is_header = index < definition.header_rows
        if is_header:
            _header_flag(row)
        _fill_row(model, row, line, shares, style_id)
    if after is not None:
        after.addnext(element)
    return element


def _properties(element: Any, definition: TableDef, shares: list[int]) -> None:  # noqa: ANN401
    """The table's own properties: how wide it is, that it follows the grid, and the grid's columns."""
    old = element.find(qn("w:tblPr"))
    if old is not None:
        element.remove(old)
    marks = OxmlElement("w:tblPr")
    width = OxmlElement("w:tblW")
    share = definition.width if definition.width is not None else 10_000
    width.set(qn("w:w"), str(round(share / 2)))  # fiftieths of a percent
    width.set(qn("w:type"), "pct")
    marks.append(width)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    marks.append(layout)
    element.insert(0, marks)
    grid = element.find(qn("w:tblGrid"))
    for column, each in zip(grid.iterchildren(qn("w:gridCol")), shares, strict=True):
        column.set(qn("w:w"), str(round(each * _TEXT_TWIPS * (share / 10_000) / 10_000)))


def _header_flag(row: Any) -> None:  # noqa: ANN401
    """Mark ``row`` (a ``w:tr``) as a header row, which Word repeats on every page."""
    marks = row.find(qn("w:trPr"))
    if marks is None:
        marks = OxmlElement("w:trPr")
        row.insert(0, marks)
    marks.append(OxmlElement("w:tblHeader"))


def _fill_row(
    model: TextModel,
    row: Any,  # noqa: ANN401
    line: list[Any],
    shares: list[int],
    style_id: Callable[[str], str | None],
) -> None:
    """Put the words and the look of a row's cells in: ``row`` has a ``w:tc`` for every column, and those a merge covers
    sideways are taken out."""
    cells = list(row.iterchildren(qn("w:tc")))
    skip = 0
    for column, (cell, spec) in enumerate(zip(cells, line, strict=True)):
        if skip:
            row.remove(cell)
            skip -= 1
            continue
        _cell(model, cell, spec, style_id, sum(shares[column : column + spec.cols]))
        if spec.cols > 1:
            skip = spec.cols - 1


def _cell(
    model: TextModel,
    cell: Any,  # noqa: ANN401
    spec: WriteCell,
    style_id: Callable[[str], str | None],
    share: int,
) -> None:
    """One ``w:tc``: its width, the columns it reaches over, its look, and one paragraph with the words."""
    for child in list(cell):
        cell.remove(child)
    marks = OxmlElement("w:tcPr")
    width = OxmlElement("w:tcW")
    width.set(qn("w:w"), str(round(share * _TEXT_TWIPS / 10_000)))
    width.set(qn("w:type"), "dxa")
    marks.append(width)
    if spec.cols > 1:
        span = OxmlElement("w:gridSpan")
        span.set(qn("w:val"), str(spec.cols))
        marks.append(span)
    if spec.rows > 1:
        merge = OxmlElement("w:vMerge")
        merge.set(qn("w:val"), "restart")
        marks.append(merge)
    elif spec.covered:
        marks.append(OxmlElement("w:vMerge"))
    _look(marks, cell_look(model, spec.style))
    cell.append(marks)
    paragraph = OxmlElement("w:p")
    properties = OxmlElement("w:pPr")
    named = style_id(spec.style)
    if named is not None:
        style = OxmlElement("w:pStyle")
        style.set(qn("w:val"), named)
        properties.append(style)
    if spec.number:
        align = OxmlElement("w:jc")
        align.set(qn("w:val"), "right")
        properties.append(align)
    paragraph.append(properties)
    if spec.text and not spec.covered:
        run = OxmlElement("w:r")
        text = OxmlElement("w:t")
        text.text = spec.text
        text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        run.append(text)
        paragraph.append(run)
    cell.append(paragraph)


def _look(marks: Any, look: CellLook) -> None:  # noqa: ANN401
    """The borders and the shading a role style gives its cell, as the cell's own properties."""
    if any(side is not None for side in look.sides):
        borders = OxmlElement("w:tcBorders")
        for name, side in zip(
            ("top", "left", "bottom", "right"),
            (look.sides[0], look.sides[3], look.sides[2], look.sides[1]),
            strict=True,
        ):
            line = OxmlElement(f"w:{name}")
            if side is None:
                line.set(qn("w:val"), "nil")
            else:
                (red, green, blue), width = side
                line.set(qn("w:val"), "single")
                line.set(qn("w:sz"), str(max(2, round(width / _EMU_PER_POINT * _EIGHTHS))))
                line.set(qn("w:color"), f"{red:02X}{green:02X}{blue:02X}")
            borders.append(line)
        marks.append(borders)
    if look.fill is not None:
        shade = OxmlElement("w:shd")
        shade.set(qn("w:val"), "clear")
        shade.set(qn("w:color"), "auto")
        shade.set(qn("w:fill"), "{:02X}{:02X}{:02X}".format(*look.fill))
        marks.append(shade)


def read_tables(document: Any, language: str | None) -> list[tuple[DocxTable, TableDef | None]]:  # noqa: ANN401
    """The tables of ``document`` with the definition the text holds for each, ``None`` for one that is not regular. The
    regular ones are called ``t1``, ``t2``... in the order of the file, which is what both the import and the patch of
    a kept file go by."""
    out: list[tuple[DocxTable, TableDef | None]] = []
    taken = 0
    for each in file_tables(document):
        definition = None if each.grid is None else read_table(each.grid, f"t{taken + 1}", language)
        taken += definition is not None
        out.append((each, definition))
    return out
