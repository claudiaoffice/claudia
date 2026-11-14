"""Reading an xlsx file's cells, names and tables straight from its XML, the way :mod:`.ods` reads an ods (D370).

The file is read part by part with ``lxml`` instead of through openpyxl, for three reasons a real workbook showed:

* **A cell is never wrong, only less live** (D413's rule, now for xlsx too). A formula the model cannot calculate
  the way Excel does -- an array formula, a spilled one, a function the model lacks, a name or table the import
  could not bring along -- comes in as the value Excel last showed for it, and is counted as a loss. openpyxl does
  not give both the formula and that value at once, and it hands an array formula over as an object, not as text
  (the import of a real planning workbook failed on exactly that).
* **What Excel adds stays readable:** ``_xlfn.`` marks on newer functions are taken off (:mod:`.excel_names`),
  shared formulas become each cell's own, and strings keep their ``_xHHHH_`` escapes decoded.
* **Speed and memory:** a sheet is read once, cell by cell, without building openpyxl's object for every cell.

Dates and times are numbers in the model, as in Excel: a cell formatted as a date comes in as its serial number and
shows as a date through its number format. Which look every cell, row and column has is noted by its place in
``cellXfs``; :mod:`.xlsx_looks` reads what those looks are.
"""

from __future__ import annotations

import posixpath
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cache
from zipfile import BadZipFile

from lxml import etree
from openpyxl.formula.translate import Translator

from claudia_computes import Content, function_catalog
from claudia_computes.formula import Call, Name, parse_formula
from claudia_computes.formula.nodes import TableRef, walk
from claudia_computes.limits import MAX_COLS, MAX_ROWS
from claudia_computes.names import NamedRange, name_problem
from claudia_computes.refs import CellRef, RangeRef, RefParseError, SheetId, column_index, column_name, parse_range_ref
from claudia_odf_io import Loss, LossLog
from claudia_opc_io import read_parts

from .excel_names import without_marks
from .extensions import INVERSE_NAMES, NOTE_MARKER, from_excel, restore_alternatives
from .openformula import Untranslatable

NS = {
    "x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
    "x14": "http://schemas.microsoft.com/office/spreadsheetml/2009/9/main",
    "xdr": "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
}
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
_SAFE = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True, remove_blank_text=False)

#: A sheet that holds more cells than this is refused, as in :mod:`.ods`.
MAX_CELLS = 2_000_000
_CELL = re.compile(r"\$?([A-Za-z]{1,3})\$?(\d+)")
_ESCAPE = re.compile(r"_x([0-9A-Fa-f]{4})_")


class XlsxError(ValueError):
    """The bytes are not an xlsx file this module can read, and why."""


def parse_xml(data: bytes) -> etree._Element:
    """A part's XML, read without resolving entities or reaching the network (a file is never trusted)."""
    return etree.fromstring(data, _SAFE)


def q(prefix: str, tag: str) -> str:
    """``tag`` in the namespace ``prefix`` stands for in :data:`NS`."""
    return f"{{{NS[prefix]}}}{tag}"


def resolve(source_part: str, target: str) -> str:
    """A relationship's ``Target`` resolved against the part that holds the relationship."""
    if target.startswith("/"):
        return target[1:]
    return posixpath.normpath(posixpath.join(posixpath.dirname(source_part), target))


def rels_part(part: str) -> str:
    """The name of the part that holds ``part``'s relationships."""
    folder, name = posixpath.split(part)
    return posixpath.join(folder, "_rels", name + ".rels")


def relationships(parts: dict[str, bytes], part: str) -> list[tuple[str, str, str]]:
    """``(id, type, target part)`` of each internal relationship of ``part``; external ones are left out."""
    data = parts.get(rels_part(part))
    if data is None:
        return []
    return [
        (rel.get("Id", ""), rel.get("Type", ""), resolve(part, rel.get("Target", "")))
        for rel in parse_xml(data).iter(q("pr", "Relationship"))
        if rel.get("TargetMode") != "External"
    ]


def related(parts: dict[str, bytes], part: str, kind: str) -> list[str]:
    """The parts ``part`` points at with relationships of ``kind`` (``comments``, ``drawing``...)."""
    return [target for _, rel_type, target in relationships(parts, part) if rel_type == _REL + kind]


def position(ref: str) -> tuple[int, int]:
    """``"B3"`` as the model's ``(row, col)``, ``(2, 1)``."""
    match = _CELL.fullmatch(ref)
    if match is None:
        raise XlsxError(f"{ref!r} is not a cell reference")
    return int(match[2]) - 1, column_index(match[1])


def area(ref: str) -> tuple[int, int, int, int]:
    """``"B3:C9"`` (or one cell) as ``(row0, col0, row1, col1)``."""
    first, _, last = ref.partition(":")
    r0, c0 = position(first)
    r1, c1 = position(last) if last else (r0, c0)
    return r0, c0, r1, c1


def decoded(text: str) -> str:
    """A string as Excel stores it, with its ``_xHHHH_`` escapes turned back into characters."""
    return _ESCAPE.sub(lambda m: chr(int(m[1], 16)), text) if "_x" in text else text


def _text_of(item: etree._Element) -> str:
    """The text of a shared or inline string: its own ``t`` or the ``t`` of each run, never the phonetic guide."""
    phonetic = q("x", "rPh")
    return decoded("".join(t.text or "" for t in item.iter(q("x", "t")) if _parent_tag(t) != phonetic))


def _parent_tag(element: etree._Element) -> str | None:
    parent = element.getparent()
    return None if parent is None else parent.tag


def child(element: etree._Element, path: str) -> etree._Element:
    """The element at ``path`` under ``element``, or ``XlsxError`` when the file leaves it out."""
    found = element.find(path, NS)
    if found is None:
        raise XlsxError(f"a {etree.QName(element).localname} without {path}")
    return found


# ------------------------------------------------------------------------------------------------ the workbook
@dataclass(frozen=True, slots=True)
class WorksheetPart:
    """One worksheet: its name, its place among the sheets (``s1``, ``s2``...) and the part it lives in."""

    name: str
    sheet_id: SheetId
    part: str


@dataclass
class Package:
    """An xlsx file opened for reading: its parts and what the cells of every sheet need to be read."""

    parts: dict[str, bytes]
    sheets: list[WorksheetPart]
    workbook: etree._Element
    shared: list[str]

    def sheet_id(self, name: str) -> SheetId | None:
        """The id of the sheet called ``name``, if there is one."""
        folded = name.casefold()
        return next((sheet.sheet_id for sheet in self.sheets if sheet.name.casefold() == folded), None)


def open_package(data: bytes) -> Package:
    """``data`` opened as an xlsx file, or ``XlsxError`` saying why it is not one."""
    try:
        parts = read_parts(data)
    except BadZipFile as problem:
        raise XlsxError("this is not an xlsx file: it is not a zip file") from problem
    if "xl/workbook.xml" not in parts:
        raise XlsxError("this is not an xlsx file: it has no workbook part")
    workbook = parse_xml(parts["xl/workbook.xml"])
    rels = {rid: target for rid, _, target in relationships(parts, "xl/workbook.xml")}
    sheets: list[WorksheetPart] = []
    for element in workbook.iterfind("x:sheets/x:sheet", NS):
        target = rels.get(element.get(q("r", "id"), ""))
        if target is not None and target in parts:  # a chart sheet or a dialog sheet has no cells to read
            sheets.append(WorksheetPart(element.get("name", ""), SheetId(f"s{len(sheets) + 1}"), target))
    return Package(parts, sheets, workbook, _shared_strings(parts))


def _shared_strings(parts: dict[str, bytes]) -> list[str]:
    data = parts.get("xl/sharedStrings.xml")
    return [] if data is None else [_text_of(item) for item in parse_xml(data).iterfind("x:si", NS)]


# ------------------------------------------------------------------------------------------------ names and tables
@cache
def model_functions() -> frozenset[str]:
    """The functions the model calculates: a formula that calls another comes in as its value."""
    return frozenset(entry.name for entry in function_catalog()) | INVERSE_NAMES


def names_and_tables(package: Package) -> tuple[list[NamedRange], LossLog]:
    """The workbook's defined names that are a range of cells, and its tables, as the model's names; what else the
    file names (a constant, a formula, a name of several areas or of a removed cell) is counted as ``named-range``."""
    found: list[NamedRange] = []
    lost = LossLog()
    for element in package.workbook.iterfind("x:definedNames/x:definedName", NS):
        name = element.get("name", "")
        if name.startswith("_xlnm.") or element.get("hidden") == "1":
            continue  # print areas, filters and Excel's own bookkeeping: no name a person gave
        named = _defined_range(package, element, name)
        if named is None:
            lost.add("named-range")
        else:
            found.append(named)
    for sheet in package.sheets:
        for table_part in related(package.parts, sheet.part, "table"):
            table = parse_xml(package.parts[table_part])
            named = _table(table, sheet.sheet_id)
            if named is None:
                lost.add("table")
            else:
                found.append(named)
    return found, lost


def _defined_range(package: Package, element: etree._Element, name: str) -> NamedRange | None:
    scope = None
    local = element.get("localSheetId")
    if local is not None:
        index = int(local)
        scope = package.sheets[index].sheet_id if 0 <= index < len(package.sheets) else None
        if scope is None:
            return None
    try:
        rng = parse_range_ref((element.text or "").strip().lstrip("="), package.sheet_id)
    except RefParseError:
        return None
    if rng.sheet is None or name_problem(name) is not None:
        return None
    return NamedRange(name, scope, rng)


def _table(table: etree._Element, sheet: SheetId) -> NamedRange | None:
    name = table.get("displayName") or table.get("name") or ""
    ref = table.get("ref")
    if not ref or name_problem(name) is not None or table.get("headerRowCount") == "0":
        return None
    try:
        rng = parse_range_ref(ref, lambda _name: sheet)
    except RefParseError:
        return None
    whole = RangeRef(CellRef(rng.first.row, rng.first.col, sheet), CellRef(rng.last.row, rng.last.col, sheet))
    return NamedRange(name, None, whole, header=True)


# ------------------------------------------------------------------------------------------------ cells
@dataclass
class SheetRead:
    """What one worksheet gives the model, and what it does not show of the sheet."""

    cells: dict[tuple[int, int], dict] = field(default_factory=dict)
    lost: LossLog = field(default_factory=LossLog)
    #: The look (a place in ``cellXfs``) of every cell the file lists, of rows with a look of their own, and of
    #: runs of columns (first, last, look).
    looks: dict[tuple[int, int], int] = field(default_factory=dict)
    row_looks: dict[int, int] = field(default_factory=dict)
    column_looks: list[tuple[int, int, int]] = field(default_factory=list)


def _number(text: str) -> int | float:
    if any(ch in text for ch in ".eEnN"):  # a fraction, an exponent, INF or NaN
        return float(text)
    return int(text)


def _cached(cell: etree._Element, shared: list[str]) -> tuple[Content, str | None]:
    """The constant a cell shows (for a formula, the value Excel wrote beside it) and, for an error, ``error-value``."""
    kind = cell.get("t", "n")
    if kind == "inlineStr":
        inline = cell.find("x:is", NS)
        text = "" if inline is None else _text_of(inline)
        return ({"t": "text", "v": text} if text else None), None
    value = cell.findtext("x:v", namespaces=NS)
    if value is None:
        return None, None
    if kind == "s":
        index = int(value)
        return {"t": "text", "v": shared[index] if 0 <= index < len(shared) else ""}, None
    if kind == "str":
        return ({"t": "text", "v": decoded(value)} if value else None), None
    if kind == "b":
        return {"t": "bool", "v": value.strip() == "1"}, None
    if kind == "e":
        return _error(value), "error-value"
    if kind == "d":
        return {"t": "text", "v": value}, "date"
    try:
        number = _number(value)
    except ValueError:  # a number cell that holds something else: shown as the text it holds
        return {"t": "text", "v": value}, None
    return {"t": "int" if isinstance(number, int) else "float", "v": number}, None


def _error(code: str) -> Content:
    """An error Excel shows as the model holds it: a formula that is the error (``=#N/A``), so that every formula
    using the cell gets the error too, as in Excel; an error the model does not know stays its text."""
    return {"t": "formula", "v": "=" + code} if parse_formula("=" + code).ast is not None else {"t": "text", "v": code}


def model_formula(excel_text: str, names: frozenset[str]) -> str:
    """The model's text of a formula as an xlsx file holds it (without its ``=``), or :class:`Untranslatable` when the
    model cannot calculate it as Excel does: a function it lacks (``function``), a name or a table the import did not
    bring along (``name``), or text it cannot read (``syntax``, e.g. a reference into another file)."""
    text = from_excel(without_marks("=" + excel_text))
    formula = parse_formula(text)
    if formula.ast is None:
        raise Untranslatable("syntax")
    functions = model_functions()
    for node in walk(formula.ast):
        if isinstance(node, Call) and node.name.upper() not in functions:
            raise Untranslatable("function", node.name)
        if isinstance(node, Name) and node.text.casefold() not in names:
            raise Untranslatable("name", node.text)
        if isinstance(node, TableRef) and node.table.casefold() not in names:
            raise Untranslatable("name", node.table)
    return text


@dataclass
class _Shared:
    """The shared formulas of a sheet: the text and the cell of the one that writes each group out, and the cells
    that came before the first cell of their group."""

    masters: dict[str, tuple[str, str]] = field(default_factory=dict)
    waiting: list[tuple[str, etree._Element]] = field(default_factory=list)


def _formula_text(f: etree._Element, ref: str, shared: _Shared) -> str | None:
    """The formula text of a cell (its own, or its group's moved to it), or ``None`` until its group is known."""
    if f.get("t") != "shared":
        return f.text or ""
    group = f.get("si", "")
    if f.text:
        shared.masters[group] = (f.text, ref)
        return f.text
    master = shared.masters.get(group)
    if master is None:
        return None
    return moved(master[0], master[1], ref)


def moved(text: str, origin: str, ref: str) -> str:
    """A shared formula's text as it reads from the cell ``ref`` (written for ``origin``)."""
    return Translator("=" + text, origin=origin).translate_formula(ref)[1:]


def cells_of(sheet_xml: etree._Element) -> Iterator[tuple[str, etree._Element]]:
    """Every cell of a worksheet with its reference -- given, or the next place in its row when the file leaves it
    out (allowed, and written by some programs)."""
    for row_number, row in enumerate(sheet_xml.iterfind("x:sheetData/x:row", NS), start=1):
        number = int(row.get("r", str(row_number)))
        column = 0
        for cell in row.iterfind("x:c", NS):
            ref = cell.get("r")
            if ref is None:
                ref = f"{column_name(column)}{number}"
            else:
                column = position(ref)[1]
            column += 1
            yield ref, cell


def read_sheet(package: Package, sheet: WorksheetPart, names: frozenset[str]) -> SheetRead:
    """The cells of one worksheet as the model's contents, and the losses reading them."""
    root = parse_xml(package.parts[sheet.part])
    reading = _Reading(package, names, notes_of(package, sheet))
    for ref, cell in cells_of(root):
        if len(reading.read.cells) >= MAX_CELLS:
            raise XlsxError(f"the sheet {sheet.name!r} holds more than {MAX_CELLS} cells")
        reading.cell(ref, cell)
    reading.finish()
    _row_and_column_looks(root, reading.read)
    _count_sheet_losses(package, sheet, root, reading.read.lost)
    return reading.read


def _row_and_column_looks(root: etree._Element, read: SheetRead) -> None:
    for column in root.iterfind("x:cols/x:col", NS):
        style = int(column.get("style", "0") or 0)
        first, last = int(column.get("min", "1")) - 1, min(int(column.get("max", "1")), MAX_COLS) - 1
        if style and 0 <= first <= last:
            read.column_looks.append((first, last, style))
    for number, row in enumerate(root.iterfind("x:sheetData/x:row", NS), start=1):
        index = int(row.get("r", str(number))) - 1
        if row.get("customFormat") in ("1", "true") and index < MAX_ROWS:
            read.row_looks[index] = int(row.get("s", "0") or 0)


def notes_of(package: Package, sheet: WorksheetPart) -> dict[str, str]:
    """The text of each comment on a sheet, by the cell it is on."""
    notes: dict[str, str] = {}
    for comments in related(package.parts, sheet.part, "comments"):
        for comment in parse_xml(package.parts[comments]).iterfind("x:commentList/x:comment", NS):
            text = comment.find("x:text", NS)
            notes[comment.get("ref", "")] = "" if text is None else _text_of(text)
    return notes


@dataclass
class _Reading:
    """Reading the cells of one sheet: what the file gives, what the model gets, what it does not show."""

    package: Package
    names: frozenset[str]
    notes: dict[str, str]
    read: SheetRead = field(default_factory=SheetRead)
    shared: _Shared = field(default_factory=_Shared)

    def cell(self, ref: str, cell: etree._Element) -> None:
        """Read one cell, or keep it for later when it continues a shared formula whose first cell is still to come."""
        f = cell.find("x:f", NS)
        if f is not None and not f.text and f.get("t") not in ("shared", "array"):
            f = None  # a cell a spilled formula fills: Excel marks it, but its value is all it holds
        text = None if f is None else _formula_text(f, ref, self.shared)
        if f is not None and text is None:
            self.shared.waiting.append((ref, cell))
            return
        self._place(ref, cell, f, text)

    def finish(self) -> None:
        """Read the cells that waited for the first cell of their shared formula."""
        for ref, cell in self.shared.waiting:
            f = child(cell, "x:f")
            master = self.shared.masters.get(f.get("si", ""))
            self._place(ref, cell, f, None if master is None else moved(master[0], master[1], ref))

    def _place(self, ref: str, cell: etree._Element, f: etree._Element | None, text: str | None) -> None:
        row, col = position(ref)
        lost = self.read.lost
        if row >= MAX_ROWS or col >= MAX_COLS:
            lost.add("outside")
            return
        constant, kind = _cached(cell, self.package.shared)
        self.read.looks[(row, col)] = int(cell.get("s", "0") or 0)
        content = constant
        if text is not None:
            content = self._formula(text, f, constant, kind)
        elif kind and constant is not None:
            lost.add(kind)
        content = restore_alternatives(content, self.notes.get(ref))
        if content is not None:
            self.read.cells[(row, col)] = content

    def _formula(self, text: str, f: etree._Element | None, constant: Content, kind: str | None) -> Content:
        """A formula cell's content: its formula, or the value Excel showed when the model cannot calculate it."""
        try:
            if f is not None and f.get("t") == "array":
                raise Untranslatable("array")
            return {"t": "formula", "v": model_formula(text, self.names)}
        except Untranslatable as why:
            self.read.lost.add("formula", why.reason)
            if kind:
                self.read.lost.add(kind)
            return constant


def _count_sheet_losses(package: Package, sheet: WorksheetPart, root: etree._Element, lost: LossLog) -> None:
    """What the model does not show of a sheet beside its cells, each with how many."""
    counts = {
        "merge": len(root.findall("x:mergeCells/x:mergeCell", NS)),
        "conditional-format": len(root.findall("x:conditionalFormatting", NS))
        + len(root.findall(".//x14:conditionalFormatting", NS)),
        "validation": len(root.findall("x:dataValidations/x:dataValidation", NS))
        + len(root.findall(".//x14:dataValidation", NS)),
        "filter": len(root.findall("x:autoFilter", NS)),
        "protection": len(root.findall("x:sheetProtection", NS)),
        "pivot-table": len(related(package.parts, sheet.part, "pivotTable")),
    }
    counts["comment"] = sum(1 for text in notes_of(package, sheet).values() if not text.startswith(NOTE_MARKER))
    for drawing in related(package.parts, sheet.part, "drawing"):
        pictures, charts, shapes = _drawn(parse_xml(package.parts[drawing]))
        counts["picture"], counts["chart"], counts["shape"] = pictures, charts, shapes
    for kind, count in counts.items():
        if count:
            lost.add(kind, count=count)


def _drawn(drawing: etree._Element) -> tuple[int, int, int]:
    """Pictures, charts and other shapes anchored on a sheet's drawing."""
    pictures = charts = shapes = 0
    for anchor in drawing:
        for item in anchor:
            tag = etree.QName(item).localname
            if tag == "pic":
                pictures += 1
            elif tag == "graphicFrame":
                is_chart = any("chart" in (g.get("uri") or "") for g in item.iter("{*}graphicData"))
                charts += is_chart
                shapes += not is_chart
            elif tag in ("sp", "grpSp", "cxnSp"):
                shapes += 1
    return pictures, charts, shapes


def workbook_losses(package: Package, lost: LossLog) -> None:
    """What the model does not show of the workbook as a whole: sheets without cells (a chart sheet), hidden sheets."""
    hidden = sum(
        1 for s in package.workbook.iterfind("x:sheets/x:sheet", NS) if s.get("state") in ("hidden", "veryHidden")
    )
    if hidden:
        lost.add("hidden-sheet", count=hidden)
    if package.workbook.find("x:workbookProtection", NS) is not None:
        lost.add("protection")


def losses_in_order(found: tuple[Loss, ...], order: tuple[str, ...]) -> tuple[Loss, ...]:
    """``found`` sorted by the place of each kind in ``order`` (kinds not in it last, in the order they came)."""
    return tuple(sorted(found, key=lambda loss: order.index(loss.kind) if loss.kind in order else len(order)))
