"""Converting between a :class:`~claudia_computes.WorkbookModel` and OpenDocument spreadsheet (ods) (D413).

The third of the OpenDocument formats (D70: odt, odp, ods), with the promise of the first two (D401, D403): **maximum
preservation from day one**.

* ``workbook_to_ods`` writes a model as a new file, and ``ods_export_losses`` says what the file cannot hold.
* ``ods_to_workbook`` reads a file as a model, and ``ods_import_losses`` says what the model does not show of it.
  Nothing is thrown away by reading.
* ``apply_edits_to_ods`` is the way back for an *edited* import: it patches the cells that changed onto the bytes of
  the original, so a chart, a picture, a comment, a merged cell, the look of every cell, a named range -- everything
  the spreadsheet has no model for -- is still there, and every byte of ``content.xml`` outside the edited cells is
  the original's.

What the model sees of an ods: every ``table:table`` is a sheet (``s1``, ``s2``... by its place) and every cell with
something in it is a constant or a formula. The file writes a run of equal rows or cells once, with a count
(``table:number-rows-repeated``, ``table:number-columns-repeated``); the model has the cell in each place of the run,
and an edit of one of them splits the run so that only that cell changes.

Formulas are translated between the model's language (Excel's, D12) and OpenFormula (:mod:`.openformula`). A cell
is written with its formula **and** the value it shows, so a program that does not calculate still shows the right
numbers; a formula that cannot be translated is written as its value alone and counted as a loss (D408), and one that
is read and cannot be translated comes in as its last value (also a loss): a cell is never wrong, only less live.

Dates and times are numbers in the model, as in Excel: they come in as the serial number (a date and a time of day as
a fraction of a day) and the file keeps its date format for as long as the cell is not edited. That is a loss
(``date``), as is every look of a cell: the model has no per-cell style.
"""

from __future__ import annotations

import copy
import datetime
import math
import re
from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import cache
from zipfile import BadZipFile

from lxml import etree

from claudia_computes import Content, Sheet, SheetId, WorkbookModel, function_catalog
from claudia_computes.limits import MAX_COLS, MAX_ROWS
from claudia_computes.values import INT_LIMIT, ErrorValue, Value
from claudia_odf_io import (
    MIME,
    NS,
    DocumentInfo,
    Loss,
    LossLog,
    OdfError,
    XmlPart,
    local_name,
    new_meta,
    new_package,
    read_text,
    set_text,
    update_package_meta,
    xml_safe,
)
from claudia_opc_io import read_parts, write_parts

from .openformula import Untranslatable, from_openformula, to_openformula
from .xlsx import UnsupportedEdit

_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>\n'
_NS_DECLS = {prefix: uri for prefix, uri in NS.items() if prefix != "xml"}
#: A sheet that holds more cells than this is refused: a run of a million rows with a value in each of
#: sixteen thousand columns is a file made to use up memory, not a spreadsheet.
_MAX_CELLS = 2_000_000
_EPOCH = datetime.date(1899, 12, 30)
_DATE = re.compile(r"(\d{4})-(\d\d)-(\d\d)(?:T(\d\d):(\d\d):(\d\d(?:\.\d+)?))?")
_DURATION = re.compile(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?")
_NUMBER_TYPES = {"float", "percentage", "currency"}
_DRAWN = ("frame", "custom-shape", "g", "line", "rect", "ellipse", "circle", "path", "polygon", "polyline", "connector")
_DRAWN_TAGS = tuple(f"{{{NS['draw']}}}{name}" for name in _DRAWN)
_CELL_TAGS = ("table-cell", "covered-table-cell")
#: What a cell says about its value and formula, all of which is replaced when the cell is given a new content.
_VALUE_ATTRIBUTES = (
    ("office", "value-type"),
    ("office", "value"),
    ("office", "date-value"),
    ("office", "time-value"),
    ("office", "boolean-value"),
    ("office", "string-value"),
    ("office", "currency"),
    ("calcext", "value-type"),
    ("table", "formula"),
)
_MATRIX = (("table", "number-matrix-columns-spanned"), ("table", "number-matrix-rows-spanned"))
_ORDER = ("formula", "date", "error-value", "chart", "picture", "object", "shape", "comment", "merge", "look")


def _q(prefix: str, local: str) -> str:
    return f"{{{NS[prefix]}}}{local}"


def _qualified(name: str) -> str:
    prefix, _, local = name.partition(":")
    return _q(prefix, local)


def _unset(element: etree._Element, name: str) -> None:
    """Take an attribute off an element if it has it."""
    if name in element.attrib:
        del element.attrib[name]


@cache
def _functions() -> frozenset[str]:
    """The names of the functions the model implements: a formula that calls another is not read as a formula."""
    return frozenset(entry.name for entry in function_catalog())


# -- reading a file ------------------------------------------------------------------------------------------------
def _read(data: bytes) -> dict[str, bytes]:
    """The parts of an ods file, or an ``OdfError`` saying why it is not one."""
    try:
        parts = read_parts(data)
    except BadZipFile as problem:
        raise OdfError("this is not an OpenDocument file: it is not a zip file") from problem
    kind = parts.get("mimetype")
    if kind is None or not kind.startswith(b"application/vnd.oasis.opendocument."):
        raise OdfError("this is not an OpenDocument file: it has no mimetype")
    if kind.strip() != MIME["spreadsheet"].encode():
        raise OdfError("this OpenDocument file is not a spreadsheet")
    if "content.xml" not in parts:
        raise OdfError("this is not an OpenDocument file: it has no content.xml")
    return parts


def _spreadsheet(root: etree._Element) -> etree._Element:
    found = root.find("office:body/office:spreadsheet", NS)
    if found is None:
        raise OdfError("this OpenDocument file is not a spreadsheet: its content has no sheets")
    return found


def _repeated(element: etree._Element, name: str) -> int:
    """How many times a row or a cell is repeated: at least one, and ``OdfError`` for a count that is not a number."""
    text = element.get(_q("table", name))
    if text is None:
        return 1
    try:
        return max(1, int(text))
    except ValueError:
        raise OdfError(f"{name} is {text!r}, which is not a number") from None


@dataclass
class _Run:
    """A row or a cell as the file writes it: the element, the place of the first of its repeats, and how many."""

    element: etree._Element
    first: int
    count: int


@dataclass
class _Row(_Run):
    #: The child of the table that holds this row: the row itself or the group of rows around it.
    top: etree._Element
    cells: list[_Run] = field(default_factory=list)


@dataclass
class _Table:
    id: str
    name: str
    element: etree._Element
    rows: list[_Row] = field(default_factory=list)
    columns: int = 0  # how many columns the table declares
    last_column: etree._Element | None = None  # the child of the table that holds the last of them
    cells: dict[tuple[int, int], dict] = field(default_factory=dict)
    #: What is in the sheet and not in the model, as ``(kind, detail, count)``.
    left_out: list[tuple[str, str, int]] = field(default_factory=list)


def _top(element: etree._Element, table: etree._Element) -> etree._Element:
    while element.getparent() is not table:
        parent = element.getparent()
        assert parent is not None  # the element is inside the table
        element = parent
    return element


def _paragraphs_of(cell: etree._Element) -> list[etree._Element]:
    return cell.findall("text:p", NS)


def _words(cell: etree._Element) -> str:
    return "\n".join(read_text(paragraph) for paragraph in _paragraphs_of(cell))


def _number(text: str | None) -> int | float | None:
    """A number of the file as the model holds it: a whole number as an ``int`` (as in an xlsx), else a float."""
    try:
        number = float(text) if text is not None else None
    except ValueError:
        return None
    if number is None or not math.isfinite(number):
        return None
    return int(number) if number.is_integer() and abs(number) <= INT_LIMIT else number


def _serial(text: str | None) -> int | float | None:
    """A date or a date with a time (``2026-11-11``, ``2026-11-11T13:45:00``) as Excel's serial number."""
    match = _DATE.fullmatch((text or "").strip())
    if match is None:
        return None
    try:
        days = (datetime.date(int(match[1]), int(match[2]), int(match[3])) - _EPOCH).days
    except ValueError:
        return None
    if match[4] is None:
        return days
    return days + (int(match[4]) * 3600 + int(match[5]) * 60 + float(match[6])) / 86400


def _fraction(text: str | None) -> float | None:
    """A time (``PT13H45M00S``) as a part of a day."""
    match = _DURATION.fullmatch((text or "").strip())
    if match is None or not any(match.groups()):
        return None
    days, hours, minutes, seconds = (float(part or 0) for part in match.groups())
    return days + (hours * 3600 + minutes * 60 + seconds) / 86400


def _constant(value: int | float) -> dict:
    return {"t": "int" if isinstance(value, int) else "float", "v": value}


def _cached(cell: etree._Element) -> tuple[Content, str | None]:
    """The constant a cell shows -- its content, or for a formula the value written beside it -- and, if it has
    one, what kind of loss reading it is (``"date"``, ``"error-value"``)."""
    kind = cell.get(_q("office", "value-type"))
    if cell.get(_q("calcext", "value-type")) == "error":
        return {"t": "text", "v": _words(cell)}, "error-value"
    if kind in _NUMBER_TYPES:
        value = _number(cell.get(_q("office", "value")))
        return (None if value is None else _constant(value)), None
    if kind in ("date", "time"):
        value = (
            _serial(cell.get(_q("office", "date-value")))
            if kind == "date"
            else _fraction(cell.get(_q("office", "time-value")))
        )
        return (None if value is None else _constant(value)), "date"
    if kind == "boolean":
        return {"t": "bool", "v": cell.get(_q("office", "boolean-value")) == "true"}, None
    if kind == "string":
        text = cell.get(_q("office", "string-value"))
        text = _words(cell) if text is None else text
        return ({"t": "text", "v": text} if text else None), None
    return None, None


def _read_cell(cell: etree._Element) -> tuple[Content, list[tuple[str, str]]]:
    """The content of a cell and what is lost of it (``(kind, detail)`` for each, before the cell is counted)."""
    lost: list[tuple[str, str]] = []
    constant, kind = _cached(cell)
    if kind and constant is not None:
        lost.append((kind, ""))
    attribute = cell.get(_q("table", "formula"))
    if attribute is None:
        return constant, lost
    try:
        if any(cell.get(_q(*name)) is not None for name in _MATRIX):
            raise Untranslatable("array")
        return {"t": "formula", "v": from_openformula(attribute, _functions())}, lost
    except Untranslatable as why:
        lost.append(("formula", why.reason))
        return constant, lost


def _cell_losses(cell: etree._Element, content: Content) -> list[tuple[str, str]]:
    """What a cell has that the model does not show: its look, being merged, a comment, a link or a format."""
    lost: list[tuple[str, str]] = []
    if content is not None and cell.get(_q("table", "style-name")):
        lost.append(("look", ""))
    if any(int(cell.get(_q("table", name)) or 1) > 1 for name in ("number-columns-spanned", "number-rows-spanned")):
        lost.append(("merge", ""))
    if cell.find("office:annotation", NS) is not None:
        lost.append(("comment", ""))
    for paragraph in _paragraphs_of(cell):
        lost.extend(
            ("formatting", "") for span in paragraph.iter(_q("text", "span")) if span.get(_q("text", "style-name"))
        )
        lost.extend(("link", "") for _ in paragraph.iter(_q("text", "a")))
    return lost


def _scan_table(element: etree._Element, number: int, cells_so_far: int) -> _Table:
    """One sheet: where its rows and cells are in the file, what the model has of them, and what it does not."""
    table = _Table(f"s{number}", element.get(_q("table", "name")) or f"Sheet{number}", element)
    losses: dict[tuple[str, str], int] = {}

    def lose(kind: str, detail: str, count: int) -> None:
        losses[(kind, detail)] = losses.get((kind, detail), 0) + count

    for declared in element.iter(_q("table", "table-column")):
        width = _repeated(declared, "number-columns-repeated")
        table.columns += width
        table.last_column = _top(declared, element)
        if declared.get(_q("table", "visibility")) in ("collapse", "filter"):
            lose("hidden-column", "", width)
    position, populated = 0, cells_so_far
    for row in element.iter(_q("table", "table-row")):
        repeat = _repeated(row, "number-rows-repeated")
        run = _Row(row, position, repeat, _top(row, element))
        table.rows.append(run)
        if row.get(_q("table", "visibility")) in ("collapse", "filter"):
            lose("hidden-row", "", repeat)
        column = 0
        for cell in row:
            if not isinstance(cell.tag, str) or local_name(cell.tag) not in _CELL_TAGS:
                continue
            across = _repeated(cell, "number-columns-repeated")
            run.cells.append(_Run(cell, column, across))
            content, lost = _read_cell(cell)
            lost += _cell_losses(cell, content)
            if content is not None or lost:
                populated = _place(table, (position, repeat), (column, across), content, lost, lose, populated)
            column += across
        position += repeat
    _table_losses(table, element, lose)
    table.left_out = [(kind, detail, count) for (kind, detail), count in losses.items()]
    return table


def _place(  # noqa: PLR0913 (one cell run: where it is, what it holds, and how what it loses is counted)
    table: _Table,
    down: tuple[int, int],
    across: tuple[int, int],
    content: Content,
    lost: list[tuple[str, str]],
    lose,  # noqa: ANN001 (the counter of the sheet being scanned)
    populated: int,
) -> int:
    """Put ``content`` in every place of a run of cells (``down`` is the first row and how many, ``across`` the
    first column and how many), and count what the cell loses once for each of them. Returns how many cells the sheet
    holds so far; ``OdfError`` when that is too many."""
    (first_row, rows), (first_col, cols) = down, across
    for kind, detail in lost:
        lose(kind, detail, rows * cols)
    if content is None:
        return populated
    inside_rows, inside_cols = max(0, min(rows, MAX_ROWS - first_row)), max(0, min(cols, MAX_COLS - first_col))
    if inside_rows * inside_cols < rows * cols:
        lose("out-of-range", "", rows * cols - inside_rows * inside_cols)
    populated += inside_rows * inside_cols
    if populated > _MAX_CELLS:
        raise OdfError(f"this spreadsheet has more than {_MAX_CELLS} cells with something in them")
    for r in range(first_row, first_row + inside_rows):
        for c in range(first_col, first_col + inside_cols):
            table.cells[(r, c)] = content
    return populated


def _inside_drawing(element: etree._Element, table: etree._Element) -> bool:
    parent = element.getparent()
    while parent is not None and parent is not table:
        if parent.tag in _DRAWN_TAGS:
            return True
        parent = parent.getparent()
    return False


def _table_losses(table: _Table, element: etree._Element, lose) -> None:  # noqa: ANN001
    """What a sheet has beside its cells: drawings, conditional formats, protection, a layout of its own."""
    for drawn in element.iter(*_DRAWN_TAGS):
        if _inside_drawing(drawn, element):
            continue
        if local_name(drawn.tag) != "frame":
            lose("shape", "", 1)
        elif drawn.find("draw:object", NS) is not None:
            lose("chart", "", 1)
        elif drawn.find("draw:image", NS) is not None:
            lose("picture", "", 1)
        else:
            lose("object", "", 1)
    formats = sum(1 for _ in element.iter(_q("calcext", "conditional-format"), _q("table", "conditional-format")))
    if formats:
        lose("conditional-format", "", formats)
    if element.get(_q("table", "protected")) == "true":
        lose("protection", "", 1)
    if any(row.element.get(_q("table", "style-name")) for row in table.rows) or any(
        column.get(_q("table", "style-name")) for column in element.iter(_q("table", "table-column"))
    ):
        lose("layout", "", 1)


def _document(data: bytes) -> tuple[dict[str, bytes], etree._Element, list[_Table]]:
    parts = _read(data)
    try:
        content = etree.fromstring(parts["content.xml"], etree.XMLParser(resolve_entities=False, no_network=True))
    except etree.XMLSyntaxError as problem:
        raise OdfError(f"this OpenDocument file is not well-formed XML: {problem}") from problem
    return parts, content, _tables(content)


def _tables(content: etree._Element) -> list[_Table]:
    tables: list[_Table] = []
    populated = 0
    for number, element in enumerate(_spreadsheet(content).findall("table:table", NS), start=1):
        table = _scan_table(element, number, populated)
        populated += len(table.cells)
        tables.append(table)
    return tables


def ods_to_workbook(ods_bytes: bytes) -> WorkbookModel:
    """``ods_bytes`` as a :class:`~claudia_computes.WorkbookModel`: a sheet per table, in order, called ``s1``,
    ``s2``..., and a constant or a formula in every cell that holds something -- in each place of a repeated run of
    them. The formulas are translated from OpenFormula; one that cannot be comes in as its last value. What the
    model does not hold is in :func:`ods_import_losses`. Raises :class:`~claudia_odf_io.OdfError` for a file that is
    not an ods."""
    _, _, tables = _document(ods_bytes)
    model = WorkbookModel()
    for table in tables:
        sheet = Sheet(SheetId(table.id), table.name)
        sheet.cells = dict(table.cells)
        model.sheets[sheet.id] = sheet
        model.open_container(str(sheet.id))
    model._calculate_loaded()  # noqa: SLF001 (the restore()-mirroring construction idiom; see xlsx_to_workbook)
    return model


def ods_import_losses(ods_bytes: bytes) -> tuple[Loss, ...]:
    """What :func:`ods_to_workbook` does not show of the file, each as a code (``"formula"`` with the reason it was
    not read as one, ``"date"``, ``"look"``, ``"merge"``, ``"comment"``, ``"chart"``, ``"picture"``, ``"pivot-table"``,
    ``"named-range"``...) with how many there are. None of it is lost from the *file*: an edit exported with
    :func:`apply_edits_to_ods` keeps all of it."""
    _, content, tables = _document(ods_bytes)
    losses = LossLog()
    for table in tables:
        for kind, detail, count in table.left_out:
            losses.add(kind, detail, count)
    ranges = sum(1 for _ in content.iter(_q("table", "named-range"), _q("table", "named-expression")))
    if ranges:
        losses.add("named-range", count=ranges)
    for name, kind in (
        ("content-validation", "validation"),
        ("database-range", "filter"),
        ("data-pilot-table", "pivot-table"),
    ):
        found = sum(1 for _ in content.iter(_q("table", name)))
        if found:
            losses.add(kind, count=found)
    return _in_order(losses.result())


def _in_order(losses: tuple[Loss, ...]) -> tuple[Loss, ...]:
    return tuple(sorted(losses, key=lambda loss: _ORDER.index(loss.kind) if loss.kind in _ORDER else len(_ORDER)))


# -- writing ---------------------------------------------------------------------------------------------------------
def _el(prefix: str, local: str, attributes: Mapping[str, str] | None = None) -> etree._Element:
    element = etree.Element(_q(prefix, local), nsmap=_NS_DECLS)
    for name, value in (attributes or {}).items():
        element.set(_qualified(name), value)
    return element


def _number_text(value: int | float) -> str:
    return str(value) if isinstance(value, int) else repr(value)


def _value_parts(value: Value, *, formula: bool) -> tuple[dict[str, str], list[str]]:
    """The attributes that say what a cell shows, and the lines of text it shows (one ``text:p`` each). The value of a
    formula carries the ``office:string-value`` LibreOffice writes with it."""
    if isinstance(value, bool):
        shown = "true" if value else "false"
        return {"office:value-type": "boolean", "office:boolean-value": shown}, [shown.upper()]
    if isinstance(value, ErrorValue):
        return {"office:value-type": "string", "office:string-value": "", "calcext:value-type": "error"}, [value.code]
    if isinstance(value, int | float):
        return {"office:value-type": "float", "office:value": _number_text(value)}, [_number_text(value)]
    if isinstance(value, str):
        attributes = {"office:value-type": "string"}
        if formula:
            attributes["office:string-value"] = xml_safe(value)
        return attributes, value.split("\n")
    return {}, []


def _fill(cell: etree._Element, attributes: Mapping[str, str], lines: list[str]) -> None:
    for name, value in attributes.items():
        cell.set(_qualified(name), value)
    for line in lines:
        paragraph = etree.SubElement(cell, _q("text", "p"))
        set_text(paragraph, xml_safe(line))


def _formula_attribute(content: dict, lost: LossLog | None) -> str | None:
    """The ``table:formula`` of a formula content, or ``None`` (and a loss) when OpenFormula cannot say it."""
    try:
        return to_openformula(content["v"])
    except Untranslatable as why:
        if lost is not None:
            lost.add("formula", why.reason)
        return None


def _new_cell(content: Content, value: Value, lost: LossLog | None) -> etree._Element:
    """A cell holding ``content``; ``value`` is what a formula shows."""
    cell = _el("table", "table-cell")
    if content is None:
        return cell
    if content["t"] == "formula":
        attribute = _formula_attribute(content, lost)
        if attribute is not None:
            cell.set(_q("table", "formula"), attribute)
        attributes, lines = _value_parts(value, formula=True)
    else:
        attributes, lines = _value_parts(content["v"], formula=False)
    _fill(cell, attributes, lines)
    return cell


def _gap(count: int, *, row: bool = False) -> etree._Element:
    """``count`` empty rows (each with one empty cell) or empty cells, written once."""
    name = "number-rows-repeated" if row else "number-columns-repeated"
    element = _el("table", "table-row" if row else "table-cell", {f"table:{name}": str(count)} if count > 1 else None)
    if row:
        etree.SubElement(element, _q("table", "table-cell"))
    return element


def _cells_of(cells: Mapping[int, tuple[Content, Value]], lost: LossLog | None) -> list[etree._Element]:
    """The cells of one row, with the empty stretches between them written as one each."""
    out: list[etree._Element] = []
    cursor = 0
    for column in sorted(cells):
        if column > cursor:
            out.append(_gap(column - cursor))
        out.append(_new_cell(*cells[column], lost))
        cursor = column + 1
    return out


def _rows_of(sheet: Sheet, lost: LossLog | None) -> list[etree._Element]:
    """The rows of ``sheet``, as the file writes them."""
    by_row: dict[int, dict[int, tuple[Content, Value]]] = {}
    for (row, column), content in sheet.cells.items():
        by_row.setdefault(row, {})[column] = (content, sheet.grid.get((row, column)))
    out: list[etree._Element] = []
    cursor = 0
    for row in sorted(by_row):
        if row > cursor:
            out.append(_gap(row - cursor, row=True))
        element = _el("table", "table-row")
        element.extend(_cells_of(by_row[row], lost))
        out.append(element)
        cursor = row + 1
    return out


def _new_table(sheet: Sheet, lost: LossLog | None) -> etree._Element:
    table = _el("table", "table", {"table:name": xml_safe(sheet.name)})
    width = max((column for _, column in sheet.cells), default=0) + 1
    table.append(_el("table", "table-column", {"table:number-columns-repeated": str(width)} if width > 1 else None))
    table.extend(_rows_of(sheet, lost) or [_gap(1, row=True)])
    return table


def _styles_part() -> bytes:
    declared = " ".join(f'xmlns:{prefix}="{uri}"' for prefix, uri in _NS_DECLS.items())
    return (
        f'{_DECLARATION}<office:document-styles {declared} office:version="1.3"><office:styles/>'
        "</office:document-styles>"
    ).encode()


def workbook_to_ods(model: WorkbookModel, *, info: DocumentInfo | None = None) -> bytes:
    """``model`` as ods bytes: a table per sheet, and in it a row per row that holds something (empty stretches are
    written once, with a count). A formula is written as OpenFormula with the value it shows, a constant as its value.
    ``info`` is the metadata (D411). Anything the file cannot hold is in :func:`ods_export_losses`."""
    root = _el("office", "document-content", {"office:version": "1.3"})
    for name in ("scripts", "font-face-decls", "automatic-styles"):
        etree.SubElement(root, _q("office", name))
    spreadsheet = etree.SubElement(etree.SubElement(root, _q("office", "body")), _q("office", "spreadsheet"))
    for sheet in model.sheets.values():
        spreadsheet.append(_new_table(sheet, None))
    if not model.sheets:
        spreadsheet.append(_new_table(Sheet(SheetId("s1"), "Sheet1"), None))
    content = _DECLARATION + etree.tostring(root, encoding="unicode")
    return new_package("spreadsheet", content.encode(), _styles_part(), meta=new_meta(info or DocumentInfo()))


def ods_export_losses(model: WorkbookModel) -> tuple[Loss, ...]:
    """What :func:`workbook_to_ods` cannot put into the file for ``model``, each as a code with how many:
    ``"formula"`` (with the reason: the cell is written as its value), ``"chart"`` and ``"object"`` (charts and the
    text, shape and image objects floating on a sheet are not written yet) and ``"layout"`` (a sheet with its own column
    widths or row heights)."""
    losses = LossLog()
    for sheet in model.sheets.values():
        for content in sheet.cells.values():
            if content["t"] == "formula":
                _formula_attribute(content, losses)
        if sheet.row_heights or sheet.col_widths:
            losses.add("layout")
    if model.charts:
        losses.add("chart", count=len(model.charts))
    floating = len(model.objects)
    if floating:
        losses.add("object", count=floating)
    return _in_order(losses.result())


# -- edit and re-export ----------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class _Change:
    """What one cell is to become: its content, the value it shows, and whether only that value changed (a formula
    whose own text is as it was and whose result is not)."""

    content: Content
    value: Value
    refresh: bool = False


def _segments(first: int, count: int, edited: list[int]) -> list[tuple[int, int, bool]]:
    """A run of ``count`` places from ``first`` cut at the ``edited`` ones: ``(start, length, edited)`` in order."""
    out: list[tuple[int, int, bool]] = []
    cursor = first
    for place in sorted(edited):
        if place > cursor:
            out.append((cursor, place - cursor, False))
        out.append((place, 1, True))
        cursor = place + 1
    if cursor < first + count:
        out.append((cursor, first + count - cursor, False))
    return out


def _repeats(element: etree._Element, name: str, count: int) -> etree._Element:
    """A copy of a row or a cell written ``count`` times."""
    clone = copy.deepcopy(element)
    if count > 1:
        clone.set(_q("table", name), str(count))
    else:
        _unset(clone, _q("table", name))
    return clone


def _like(element: etree._Element) -> etree._Element:
    """A copy of a cell that knows every namespace the file uses: a copy made the plain way declares only the ones the
    cell itself uses, and the attributes and paragraphs given to it later would get names like ``ns0``."""
    clone = etree.Element(element.tag, nsmap=_NS_DECLS)
    for name, value in element.attrib.items():
        clone.set(name, value)
    clone.extend(copy.deepcopy(child) for child in element)
    return clone


def _shown(value: Value) -> str:
    return repr(value)


class _Patch:
    """One run of :func:`apply_edits_to_ods`: the original's parts, what is to change and the edits recorded so far."""

    def __init__(
        self,
        original: bytes,
        baseline: WorkbookModel,
        current: WorkbookModel,
        *,
        losses: LossLog | None,
        info: DocumentInfo | None,
    ) -> None:
        self.original, self.baseline, self.current = original, baseline, current
        self.losses, self.info = losses, info
        # what a formula shows is the model's own result, not a value left over from before an edit settled
        current.calc.recalculate_all()
        self.parts = _read(original)
        self.part = XmlPart(self.parts["content.xml"])
        self.spreadsheet = _spreadsheet(self.part.root)
        self.tables = _tables(self.part.root)
        self.by_id = {table.id: table for table in self.tables}
        self.changed = False
        self._check_baseline()

    def _check_baseline(self) -> None:
        if [(sheet.id, sheet.name) for sheet in self.baseline.sheets.values()] != [
            (table.id, table.name) for table in self.tables
        ] or any(self.baseline.sheets[SheetId(table.id)].cells != table.cells for table in self.tables):
            raise UnsupportedEdit("the baseline is not the workbook this file holds")
        kept = [sheet_id for sheet_id in self.current.sheets if sheet_id in self.baseline.sheets]
        if kept != [sheet_id for sheet_id in self.baseline.sheets if sheet_id in set(kept)]:
            raise UnsupportedEdit("sheets cannot be moved relative to each other in the file")

    def _lose(self, kind: str, detail: str = "", count: int = 1) -> None:
        if self.losses is not None:
            self.losses.add(kind, detail, count)

    # -- the run ---------------------------------------------------------------------------------------------------
    def run(self) -> bytes:
        for table in self.tables:
            sheet = self.current.sheets.get(SheetId(table.id))
            if sheet is None:
                self._remove(table)
            else:
                self._patch_table(table, sheet)
        self._add_tables()
        if not self.changed:
            return self.original
        self.parts["content.xml"] = self.part.result()
        if self.info is not None:
            update_package_meta(self.parts, self.info)
        return write_parts(self.parts)

    # -- sheets ----------------------------------------------------------------------------------------------------
    def _remove(self, table: _Table) -> None:
        for kind, detail, count in table.left_out:
            self._lose(f"removed-{kind}", detail, count)
        self._stale("removed")
        self.part.remove(table.element)
        self.changed = True

    def _stale(self, what: str) -> None:
        """A sheet that was removed or renamed may still be named by what the model does not hold: a name, a chart,
        a validation, a conditional format."""
        if self.losses is None:
            return
        tags = (
            "named-expression",
            "named-range",
            "content-validation",
            "conditional-format",
            "object",
            "data-pilot-table",
        )
        if any(local_name(element.tag) in tags for element in self.part.root.iter() if isinstance(element.tag, str)):
            self.losses.add("stale-reference", f"{what} sheet")

    def _add_tables(self) -> None:
        """The sheets that are new, each after the sheet before it (several at one place come out in order)."""
        anchor: etree._Element | None = None
        lonely: list[etree._Element] = []  # new sheets in a file that has no sheet at all
        for sheet_id, sheet in self.current.sheets.items():
            existing = self.by_id.get(str(sheet_id))
            if existing is not None:
                anchor = existing.element
                continue
            element = _new_table(sheet, self.losses)
            self.changed = True
            if anchor is not None:
                self.part.insert_after(anchor, element)
            elif self.tables:
                self.part.insert_before(self.tables[0].element, element)
            else:
                lonely.append(element)
        if lonely:
            self.part.insert_into(self.spreadsheet, *lonely)

    def _patch_table(self, table: _Table, sheet: Sheet) -> None:
        if sheet.name != table.name:
            self.part.set_attributes(table.element, {"table:name": xml_safe(sheet.name)})
            self._stale("renamed")
            self.changed = True
        before, after = self.baseline.sheets[SheetId(table.id)], sheet
        changes: dict[int, dict[int, _Change]] = {}
        for position in before.cells.keys() | after.cells.keys():
            old, new = before.cells.get(position), after.cells.get(position)
            if old != new:
                change = _Change(new, after.grid.get(position))
            elif (
                new is not None
                and new["t"] == "formula"
                and _shown(before.grid.get(position)) != _shown(after.grid.get(position))
            ):
                change = _Change(new, after.grid.get(position), refresh=True)
            else:
                continue
            changes.setdefault(position[0], {})[position[1]] = change
        if not changes:
            return
        self.changed = True
        lead = self._columns(table, changes)
        starts = [row.first for row in table.rows]
        by_run: dict[int, dict[int, dict[int, _Change]]] = {}
        beyond: dict[int, dict[int, _Change]] = {}
        for row, cells in changes.items():
            index = bisect_right(starts, row) - 1
            if index >= 0 and row < table.rows[index].first + table.rows[index].count:
                by_run.setdefault(index, {})[row] = cells
            else:
                beyond[row] = cells
        for index, rows in by_run.items():
            self._patch_rows(table.rows[index], rows)
        self._append_rows(table, beyond, lead)

    def _columns(self, table: _Table, changes: dict[int, dict[int, _Change]]) -> list[etree._Element]:
        """Declare the columns a new cell needs, when the table does not. A table with no columns and no rows is
        given them together with its first rows: the column is returned to go in with those."""
        wanted = max(
            (c + 1 for cells in changes.values() for c, change in cells.items() if change.content is not None),
            default=0,
        )
        if wanted <= table.columns:
            return []
        column = _el("table", "table-column", {"table:number-columns-repeated": str(wanted - table.columns)})
        if table.last_column is not None:
            self.part.insert_after(table.last_column, column)
        elif table.rows:
            self.part.insert_before(table.rows[0].top, column)
        else:
            return [column]
        return []

    # -- rows ------------------------------------------------------------------------------------------------------
    def _patch_rows(self, run: _Row, rows: dict[int, dict[int, _Change]]) -> None:
        """The changed rows inside one row of the file, which may stand for many equal ones."""
        if run.count == 1:
            self._patch_cells(run.element, rows[run.first], tree=False)
            return
        pieces: list[etree._Element] = []
        for start, length, hit in _segments(run.first, run.count, list(rows)):
            piece = _repeats(run.element, "number-rows-repeated", length)
            if hit:
                self._patch_cells(piece, rows[start], tree=True)
            pieces.append(piece)
        self.part.replace(run.element, *pieces)

    def _append_rows(self, table: _Table, rows: dict[int, dict[int, _Change]], lead: list[etree._Element]) -> None:
        """The rows after the last one of the file (``lead`` goes in before them, in a table that has no rows)."""
        cursor = table.rows[-1].first + table.rows[-1].count if table.rows else 0
        pieces: list[etree._Element] = []
        for row in sorted(rows):
            cells = {c: ch for c, ch in rows[row].items() if ch.content is not None}
            if not cells:
                continue
            if row > cursor:
                pieces.append(_gap(row - cursor, row=True))
            element = _el("table", "table-row")
            element.extend(self._new_cells(cells, 0))
            pieces.append(element)
            cursor = row + 1
        if table.rows:
            for piece in pieces:
                self.part.insert_after(table.rows[-1].top, piece)
        elif pieces or lead:
            self.part.insert_into(table.element, *lead, *pieces)

    # -- cells -----------------------------------------------------------------------------------------------------
    def _patch_cells(self, row: etree._Element, cells: dict[int, _Change], *, tree: bool) -> None:
        """Change cells of one row element: in the file's bytes (``tree`` false) or in a copy of the row that is
        going to be written in its place (``tree`` true)."""
        runs: list[_Run] = []
        column = 0
        for cell in row:
            if isinstance(cell.tag, str) and local_name(cell.tag) in _CELL_TAGS:
                across = _repeated(cell, "number-columns-repeated")
                runs.append(_Run(cell, column, across))
                column += across
        for run in runs:
            inside = [c for c in cells if run.first <= c < run.first + run.count]
            if not inside:
                continue
            pieces = [
                self._rewritten(run.element, cells[start])
                if hit
                else _repeats(run.element, "number-columns-repeated", length)
                for start, length, hit in _segments(run.first, run.count, inside)
            ]
            self._swap(run.element, pieces, tree=tree)
        tail = self._new_cells({c: ch for c, ch in cells.items() if c >= column and ch.content is not None}, column)
        if tail:
            if tree:
                row.extend(tail)
            else:
                self.part.insert_into(row, *tail)

    def _swap(self, element: etree._Element, pieces: list[etree._Element], *, tree: bool) -> None:
        if not tree:
            self.part.replace(element, *pieces)
            return
        pieces[-1].tail = element.tail
        for piece in pieces:
            element.addprevious(piece)
        parent = element.getparent()
        assert parent is not None  # a cell is in a row
        parent.remove(element)

    def _new_cells(self, cells: Mapping[int, _Change], start: int) -> list[etree._Element]:
        out: list[etree._Element] = []
        cursor = start
        for column in sorted(cells):
            if column > cursor:
                out.append(_gap(column - cursor))
            out.append(self._rewritten(None, cells[column]))
            cursor = column + 1
        return out

    def _rewritten(self, old: etree._Element | None, change: _Change) -> etree._Element:
        """The cell as it is to be: ``old`` (or a new cell) with another value and, unless only the value changed,
        another formula. Its look, comment, merge and everything else of it stay."""
        cell = _like(old) if old is not None else _el("table", "table-cell")
        if any(cell.get(_q(*name)) is not None for name in _MATRIX):
            raise UnsupportedEdit("a cell of an array formula cannot be changed in the file")
        for paragraph in _paragraphs_of(cell):
            if not change.refresh:
                self._lose_words(paragraph)
            cell.remove(paragraph)
        formula = cell.get(_q("table", "formula"))
        for prefix, local in _VALUE_ATTRIBUTES:
            _unset(cell, _q(prefix, local))
        _unset(cell, _q("table", "number-columns-repeated"))
        content = change.content
        if content is None:
            return cell
        if content["t"] == "formula":
            if change.refresh and formula is not None:
                cell.set(_q("table", "formula"), formula)
            elif (attribute := _formula_attribute(content, self.losses)) is not None:
                cell.set(_q("table", "formula"), attribute)
            attributes, lines = _value_parts(change.value, formula=True)
        else:
            attributes, lines = _value_parts(content["v"], formula=False)
        _fill(cell, attributes, lines)
        return cell

    def _lose_words(self, paragraph: etree._Element) -> None:
        """What a changed cell loses of its old words: the formatting inside them and the links."""
        for span in paragraph.iter(_q("text", "span")):
            if span.get(_q("text", "style-name")):
                self._lose("removed-formatting")
        for _ in paragraph.iter(_q("text", "a")):
            self._lose("removed-link")


def apply_edits_to_ods(
    original_bytes: bytes,
    baseline: WorkbookModel,
    current: WorkbookModel,
    *,
    losses: LossLog | None = None,
    info: DocumentInfo | None = None,
) -> bytes:
    """Re-export ``current`` to ods by patching what changed since ``baseline`` (the model as :func:`ods_to_workbook`
    read it from ``original_bytes``) onto those same bytes -- so a chart, a picture, a comment, a merged cell, the look
    of every cell, anything the app does not model, is still in the file, and every byte of ``content.xml`` outside what
    was edited is the original's. Every other part of the package is exactly as it was. With nothing changed the result
    *is* ``original_bytes``.

    What it patches: a cell whose content changed (a run of equal cells or rows is split so that only that cell
    changes, and the cell keeps its look, its comment and its merge), a formula whose result changed because a cell it
    reads did (the value written beside it), and sheets that were added, removed or renamed (``losses`` gets a
    ``removed-...`` entry for what went with a removed sheet, and a ``stale-reference`` when the file has something that
    may still name a sheet that is gone or has another name). ``info`` brings ``meta.xml`` up to date for a file that
    was changed (D411).

    Raises :class:`~claudia_computes_io.UnsupportedEdit` for what cannot be patched: a baseline that is not the
    workbook the file holds, sheets moved relative to each other, and a cell of an array formula."""
    return _Patch(original_bytes, baseline, current, losses=losses, info=info).run()
