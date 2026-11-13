"""Writing an edit back into an xlsx file cell by cell, so everything else in the file stays as Excel wrote it (D341).

The first way back (D220) let openpyxl load the whole workbook, change the cells and save, and then put back every
part claudia had not touched. The parts it had touched -- the worksheets with an edited cell -- came back as openpyxl
writes them, and openpyxl leaves out what it does not know: a list in a cell that takes its choices from another sheet,
an icon set, the mark that makes a formula spill, a picture placed in a cell. One edit on such a sheet took them away.

Now the edited sheet is changed in its own XML: an edited cell gets its new formula and value (and keeps its look); a
new cell or row goes where it belongs; nothing else in the sheet is rewritten. The only other parts that change are the
ones an edit needs: the comments and their drawing for a note that holds alternatives, the calculation chain (dropped
when a formula changed, since Excel refuses a chain that names a cell without a formula, and rebuilds it), and the
workbook's request to calculate everything when it is opened, because a value claudia changed can change what
formulas on other sheets show.

A cell inside an array formula or a spilled range cannot be changed in the file: the model holds it as a value, and
Excel would treat the range as broken (:class:`~claudia_computes_io.UnsupportedEdit`, as for ods).
"""

from __future__ import annotations

import copy
import posixpath
import re
from dataclasses import dataclass

from lxml import etree

from claudia_computes import Content
from claudia_computes.refs import column_name
from claudia_computes.values import ErrorValue, Value

from .excel_names import with_marks
from .extensions import NOTE_MARKER, to_excel, with_note
from .openformula import Untranslatable
from .xlsx_read import NS, area, child, moved, parse_xml, position, q, related, relationships, rels_part

_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_PR = NS["pr"]
#: What may follow ``legacyDrawing`` in a worksheet (ECMA-376 part 1, 18.3.1.99): a new one goes before the first.
_AFTER_LEGACY_DRAWING = (
    "legacyDrawingHF",
    "drawingHF",
    "picture",
    "oleObjects",
    "controls",
    "webPublishItems",
    "tableParts",
    "extLst",
)
#: What may follow ``calcPr`` in a workbook (18.2.27): a new one goes before the first.
_AFTER_CALC_PR = (
    "oleSize",
    "customWorkbookViews",
    "pivotCaches",
    "smartTagPr",
    "smartTagTypes",
    "webPublishing",
    "fileRecoveryPr",
    "webPublishObjects",
    "extLst",
)
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


class UnsupportedEdit(Exception):
    """An edit that cannot be written into the original file: adding, removing, renaming or reordering a sheet, or
    changing a cell inside an array formula or a spilled range. Changing any other cell's content is supported."""


@dataclass(frozen=True, slots=True)
class Written:
    """A cell as the file is to hold it: its formula in Excel's words (or ``None``), the value it shows, and the note
    that carries its alternatives (or ``None``)."""

    formula: str | None
    value: Value
    note: str | None
    lost: Untranslatable | None = None


def written(content: Content, value: Value) -> Written:
    """What a cell with ``content`` (a formula showing ``value``) is in an xlsx file. A formula Excel cannot say is
    written as its value; ``lost`` says why."""
    with_alternatives = with_note(content)
    shown = with_alternatives.content
    if shown is None:
        return Written(None, None, with_alternatives.note)
    if shown["t"] != "formula":
        return Written(None, shown["v"], with_alternatives.note)
    try:
        text = with_marks(to_excel(shown["v"]))
    except Untranslatable as why:
        return Written(None, value, with_alternatives.note, why)
    return Written(text[1:], value, with_alternatives.note)


def _serialized(element: etree._Element) -> bytes:
    """A part's XML as bytes, with the declaration Excel writes."""
    return etree.tostring(element, xml_declaration=True, encoding="UTF-8", standalone=True)


def _remove(element: etree._Element) -> None:
    parent = element.getparent()
    if parent is not None:
        parent.remove(element)


def _unset(element: etree._Element, *attributes: str) -> None:
    for attribute in attributes:
        if attribute in element.attrib:
            del element.attrib[attribute]


def _escaped(text: str) -> str:
    """Characters XML cannot hold, written as Excel's ``_xHHHH_`` escapes."""
    return _CONTROL.sub(lambda m: f"_x{ord(m[0]):04X}_", text)


def _el(tag: str, text: str | None = None, **attributes: str) -> etree._Element:
    element = etree.Element(q("x", tag), attributes)
    element.text = text
    return element


# ------------------------------------------------------------------------------------------------ one sheet
class SheetPatch:
    """The XML of one worksheet, with its rows and cells found by reference, ready to take edited cells."""

    def __init__(self, data: bytes):
        self.root = parse_xml(data)
        data_element = self.root.find("x:sheetData", NS)
        if data_element is None:
            data_element = _el("sheetData")
            self.root.append(data_element)
        self.data = data_element
        self.rows: dict[int, etree._Element] = {}
        self.cells: dict[str, etree._Element] = {}
        self.arrays: list[tuple[int, int, int, int]] = []
        self.groups: dict[str, list[etree._Element]] = {}
        self._index()

    def _index(self) -> None:
        for place, row in enumerate(self.data.iterfind("x:row", NS), start=1):
            number = int(row.get("r") or place)
            row.set("r", str(number))  # (a file may leave the number out; a row that gets a cell needs it)
            self.rows[number] = row
            column = 0
            for cell in row.iterfind("x:c", NS):
                ref = cell.get("r")
                if ref is None:
                    ref = f"{column_name(column)}{number}"
                    cell.set("r", ref)
                column = position(ref)[1] + 1
                self.cells[ref] = cell
                self._note_formula(cell)

    def _note_formula(self, cell: etree._Element) -> None:
        f = cell.find("x:f", NS)
        if f is None:
            return
        if f.get("t") == "array" and f.get("ref"):
            self.arrays.append(area(f.get("ref", "")))
        elif f.get("t") == "shared":
            self.groups.setdefault(f.get("si", ""), []).append(cell)

    def put(self, row: int, col: int, cell: Written | None) -> bool:
        """Give the cell at ``(row, col)`` its new content (``None``: empty). Returns whether a formula was there or
        is there now, which is what the calculation chain depends on."""
        if any(r0 <= row <= r1 and c0 <= col <= c1 for r0, c0, r1, c1 in self.arrays):
            raise UnsupportedEdit("a cell of an array formula or a spilled range cannot be changed in the file")
        ref = f"{column_name(col)}{row + 1}"
        old = self.cells.get(ref)
        had_formula = old is not None and old.find("x:f", NS) is not None
        if old is not None and had_formula:
            self._free_group(old)
        if cell is None or (cell.formula is None and cell.value is None):
            self._clear(ref, old)
            return had_formula
        element = old if old is not None else self._new_cell(row, col, ref)
        _fill(element, cell)
        return had_formula or cell.formula is not None

    def _free_group(self, cell: etree._Element) -> None:
        """Before the first cell of a shared formula changes, each other cell of its group gets its own formula."""
        f = cell.find("x:f", NS)
        if f is None or f.get("t") != "shared" or not f.text:
            return
        origin = cell.get("r", "")
        for member in self.groups.pop(f.get("si", ""), []):
            member_f = member.find("x:f", NS)
            if member is cell or member_f is None:
                continue
            member_f.text = moved(f.text, origin, member.get("r", ""))
            _unset(member_f, "t", "si", "ref")

    def _clear(self, ref: str, old: etree._Element | None) -> None:
        """An emptied cell keeps its look (Excel shows an empty formatted cell); one without a look goes."""
        if old is None:
            return
        if old.get("s") not in (None, "0"):
            _strip(old)
            return
        _remove(old)
        del self.cells[ref]

    def _new_cell(self, row: int, col: int, ref: str) -> etree._Element:
        row_element = self.rows.get(row + 1)
        if row_element is None:
            row_element = self._new_row(row + 1)
        cell = _el("c", r=ref)
        later = next((c for c in row_element.iterfind("x:c", NS) if position(c.get("r", ""))[1] > col), None)
        if later is None:
            row_element.append(cell)
        else:
            later.addprevious(cell)
        _widen_spans(row_element, col + 1)
        self._widen_dimension(row, col)
        self.cells[ref] = cell
        return cell

    def _new_row(self, number: int) -> etree._Element:
        row = _el("row", r=str(number))
        later = next((n for n in sorted(self.rows) if n > number), None)
        if later is None:
            self.data.append(row)
        else:
            self.rows[later].addprevious(row)
        self.rows[number] = row
        return row

    def _widen_dimension(self, row: int, col: int) -> None:
        dimension = self.root.find("x:dimension", NS)
        if dimension is None or not dimension.get("ref"):
            return
        r0, c0, r1, c1 = area(dimension.get("ref", ""))
        r0, c0, r1, c1 = min(r0, row), min(c0, col), max(r1, row), max(c1, col)
        dimension.set("ref", f"{column_name(c0)}{r0 + 1}:{column_name(c1)}{r1 + 1}")

    def restyle(self, row: int, col: int, look: int) -> None:
        """Point the cell at ``(row, col)`` at the look ``look`` (a place in ``cellXfs``); an empty cell that gets a
        look is written, empty, so that it shows it."""
        ref = f"{column_name(col)}{row + 1}"
        cell = self.cells.get(ref)
        if cell is None:
            if look == 0 and (row + 1) not in self.rows and not self._styled_columns():
                return  # (nothing to say: the cell looks as every cell does)
            cell = self._new_cell(row, col, ref)
        if look:
            cell.set("s", str(look))
        else:
            _unset(cell, "s")

    def restyle_row(self, row: int, look: int | None) -> None:
        """Give row ``row`` the look ``look`` for its cells that have none of their own (``None``: no look)."""
        element = self.rows.get(row + 1)
        if element is None:
            if look is None:
                return
            element = self._new_row(row + 1)
        if look is None:
            _unset(element, "s", "customFormat")
        else:
            element.set("s", str(look))
            element.set("customFormat", "1")

    def restyle_columns(self, first: int, last: int, look: int | None) -> None:
        """Give the columns ``first`` to ``last`` the look ``look`` (``None``: no look); a ``col`` element that
        reaches beyond them is cut, so its other columns keep their width and look."""
        cols = self.root.find("x:cols", NS)
        if cols is None:
            if look is None:
                return
            cols = _el("cols")
            before = self.root.find("x:sheetData", NS)
            assert before is not None  # (__init__ made sure)
            before.addprevious(cols)
        lo, hi = first + 1, last + 1
        _cut_columns(cols, lo, hi)
        _fill_columns(cols, lo, hi)
        for col in cols.iterfind("x:col", NS):
            if lo <= int(col.get("min", "1")) <= hi:
                if look:
                    col.set("style", str(look))
                else:
                    _unset(col, "style")
        _sort_columns(cols)

    def _styled_columns(self) -> bool:
        return any(col.get("style") not in (None, "0") for col in self.root.iterfind("x:cols/x:col", NS))

    def to_bytes(self) -> bytes:
        """The sheet's XML as the file is to hold it."""
        return _serialized(self.root)


def _cut_columns(cols: etree._Element, lo: int, hi: int) -> None:
    """Cut every ``col`` element that reaches over the columns ``lo`` to ``hi`` (counted from 1) at their edges."""
    for col in list(cols.iterfind("x:col", NS)):
        c0, c1 = int(col.get("min", "1")), int(col.get("max", "1"))
        if c1 < lo or c0 > hi:
            continue
        for a, b in ((c0, lo - 1), (max(c0, lo), min(c1, hi)), (hi + 1, c1)):
            if a <= b:
                piece = copy.deepcopy(col)
                piece.set("min", str(a))
                piece.set("max", str(b))
                col.addprevious(piece)
        _remove(col)


def _fill_columns(cols: etree._Element, lo: int, hi: int) -> None:
    """Give the columns ``lo`` to ``hi`` that no ``col`` element covers one of their own (at Excel's own width)."""
    covered = sorted(
        (int(c.get("min", "1")), c) for c in cols.iterfind("x:col", NS) if lo <= int(c.get("min", "1")) <= hi
    )
    cursor = lo
    for start, col in covered:
        if start > cursor:
            col.addprevious(_el("col", min=str(cursor), max=str(start - 1), width="9.140625"))
        cursor = int(col.get("max", "1")) + 1
    if cursor <= hi:
        cols.append(_el("col", min=str(cursor), max=str(hi), width="9.140625"))


def _sort_columns(cols: etree._Element) -> None:
    ordered = sorted(cols.iterfind("x:col", NS), key=lambda col: int(col.get("min", "1")))
    for col in ordered:
        cols.append(col)  # (lxml moves an element it appends)


def _widen_spans(row: etree._Element, column: int) -> None:
    """A row's ``spans`` (a hint of the columns it uses) taking in ``column`` (counted from 1)."""
    spans = row.get("spans")
    if not spans or ":" not in spans:
        return
    first, last = (int(n) for n in spans.split(":", 1))
    row.set("spans", f"{min(first, column)}:{max(last, column)}")


def _strip(cell: etree._Element) -> None:
    """A cell without its content: its reference and its look stay."""
    for inside in list(cell):
        cell.remove(inside)
    _unset(cell, "t", "cm", "vm", "ph")


def _fill(cell: etree._Element, content: Written) -> None:
    _strip(cell)
    value = content.value
    if content.formula is not None:
        cell.append(_el("f", _escaped(content.formula)))
        _cached_value(cell, value)
        return
    if isinstance(value, str):
        cell.set("t", "inlineStr")
        inline = _el("is")
        text = _el("t", _escaped(value))
        if value != value.strip():
            text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        inline.append(text)
        cell.append(inline)
        return
    _cached_value(cell, value)


def _cached_value(cell: etree._Element, value: Value) -> None:
    """The value a cell shows, in the ``v`` element and the ``t`` that says what kind it is."""
    if value is None:
        return
    if isinstance(value, bool):
        cell.set("t", "b")
        cell.append(_el("v", "1" if value else "0"))
    elif isinstance(value, ErrorValue):
        cell.set("t", "e")
        cell.append(_el("v", value.code))
    elif isinstance(value, int | float):
        cell.append(_el("v", repr(value)))
    else:
        cell.set("t", "str")
        cell.append(_el("v", _escaped(str(value))))


# ------------------------------------------------------------------------------------------------ the package
class PackagePatch:
    """The parts of an xlsx file, changed only where an edit needs it."""

    def __init__(self, parts: dict[str, bytes]):
        self.parts = dict(parts)
        self._types: etree._Element | None = None

    @property
    def types(self) -> etree._Element:
        """``[Content_Types].xml``, read once and written back by :meth:`finish`."""
        if self._types is None:
            self._types = parse_xml(self.parts["[Content_Types].xml"])
        return self._types

    def free_name(self, pattern: str) -> str:
        """The first part name ``pattern.format(n)`` (n from 1) the package does not have yet."""
        n = 1
        while pattern.format(n) in self.parts:
            n += 1
        return pattern.format(n)

    def add_relationship(self, source: str, kind: str, target_part: str) -> str:
        """A new relationship from ``source`` to ``target_part``; returns its id."""
        name = rels_part(source)
        root = parse_xml(self.parts.get(name) or f'<Relationships xmlns="{_PR}"/>'.encode())
        used = {rel.get("Id") for rel in root}
        rid = next(f"rId{n}" for n in range(1, len(used) + 2) if f"rId{n}" not in used)
        etree.SubElement(
            root, f"{{{_PR}}}Relationship", Id=rid, Type=_REL + kind, Target=_relative(source, target_part)
        )
        self.parts[name] = _serialized(root)
        return rid

    def remove_relationships(self, source: str, kind: str) -> None:
        name = rels_part(source)
        if name not in self.parts:
            return
        root = parse_xml(self.parts[name])
        for rel in [r for r in root if r.get("Type") == _REL + kind]:
            root.remove(rel)
        self.parts[name] = _serialized(root)

    def declare(self, part: str, content_type: str) -> None:
        """``part`` in ``[Content_Types].xml`` with ``content_type``."""
        etree.SubElement(self.types, f"{{{_CT}}}Override", PartName="/" + part, ContentType=content_type)

    def declare_extension(self, extension: str, content_type: str) -> None:
        if not any(d.get("Extension", "").lower() == extension for d in self.types.iterfind(f"{{{_CT}}}Default")):
            default = etree.Element(f"{{{_CT}}}Default", Extension=extension, ContentType=content_type)
            self.types.insert(0, default)

    def forget(self, part: str) -> None:
        """Take ``part`` out of the package and out of ``[Content_Types].xml``."""
        self.parts.pop(part, None)
        for override in list(self.types.iterfind(f"{{{_CT}}}Override")):
            if override.get("PartName") == "/" + part:
                self.types.remove(override)

    def drop_calculation_chain(self) -> None:
        """Excel's calculation chain names the cells with formulas; after one changed it is dropped, and Excel builds
        it again (a chain that names a cell without a formula makes Excel repair the file)."""
        if "xl/calcChain.xml" not in self.parts:
            return
        self.forget("xl/calcChain.xml")
        self.remove_relationships("xl/workbook.xml", "calcChain")

    def ask_for_calculation(self) -> None:
        """The workbook asks Excel and LibreOffice to calculate every formula when the file is opened: an edited value
        can change what a formula on a sheet claudia did not touch shows."""
        workbook = parse_xml(self.parts["xl/workbook.xml"])
        calc = workbook.find("x:calcPr", NS)
        if calc is None:
            calc = _el("calcPr")
            later = next((e for e in workbook if etree.QName(e).localname in _AFTER_CALC_PR), None)
            if later is None:
                workbook.append(calc)
            else:
                later.addprevious(calc)
        calc.set("fullCalcOnLoad", "1")
        self.parts["xl/workbook.xml"] = _serialized(workbook)

    def finish(self) -> dict[str, bytes]:
        """The parts as the file is to hold them."""
        if self._types is not None:
            self.parts["[Content_Types].xml"] = _serialized(self._types)
        return self.parts


def _relative(source: str, target: str) -> str:
    """``target`` as a relationship of ``source`` writes it: relative to the folder ``source`` is in."""
    return posixpath.relpath(target, posixpath.dirname(source))


# ------------------------------------------------------------------------------------------------ notes
_VML_NS = (
    'xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" '
    'xmlns:x="urn:schemas-microsoft-com:office:excel"'
)
_SHAPE_TYPE = (
    '<v:shapetype id="_x0000_t202" coordsize="21600,21600" o:spt="202" path="m,l,21600r21600,l21600,xe">'
    '<v:stroke joinstyle="miter"/><v:path gradientshapeok="t" o:connecttype="rect"/></v:shapetype>'
)
_SHAPE = re.compile(rb"<v:shape\b.*?</v:shape>", re.DOTALL)
_SHAPE_ID = re.compile(rb'id="_x0000_s(\d+)"')
_COMMENTS = "application/vnd.openxmlformats-officedocument.spreadsheetml.comments+xml"
_VML = "application/vnd.openxmlformats-officedocument.vmlDrawing"
_AUTHOR = "claudia"


class SheetNotes:
    """The notes of one sheet (its legacy comments and the drawing that shows them), changed for claudia's own notes
    only: a comment somebody else wrote stays as it is."""

    def __init__(self, package: PackagePatch, sheet_part: str, sheet: SheetPatch):
        self.package = package
        self.sheet_part = sheet_part
        self.sheet = sheet
        existing = related(package.parts, sheet_part, "comments")
        self.comments_part = existing[0] if existing else None
        self._comments: etree._Element | None = None
        self._changed = False

    def set(self, row: int, col: int, note: str | None) -> None:
        """Give the cell claudia's note ``note``, or take claudia's note away (``None``)."""
        ref = f"{column_name(col)}{row + 1}"
        found = self._comment(ref)
        if found is not None and not _comment_text(found).startswith(NOTE_MARKER):
            return  # somebody else's comment on this cell: it stays, and the alternatives are not written
        if found is None:
            if note is not None:
                self._changed = True
                self._add(ref, note)
                self._add_shape(row, col)
            return
        self._changed = True
        if note is None:
            _remove(found)
            self._drop_shape(row, col)
        else:
            found.remove(child(found, "x:text"))
            found.append(_note_text(note))

    def finish(self) -> None:
        if self._changed and self._comments is not None and self.comments_part is not None:
            self.package.parts[self.comments_part] = _serialized(self._comments)

    def _comment(self, ref: str) -> etree._Element | None:
        if self.comments_part is None:
            return None
        return self.comments.find(f"x:commentList/x:comment[@ref='{ref}']", NS)

    @property
    def comments(self) -> etree._Element:
        if self._comments is None:
            if self.comments_part is None:
                self.comments_part = self.package.free_name("xl/comments{}.xml")
                self.package.add_relationship(self.sheet_part, "comments", self.comments_part)
                self.package.declare(self.comments_part, _COMMENTS)
                root = _el("comments")
                root.append(_el("authors"))
                root.append(_el("commentList"))
                self._comments = root
            else:
                self._comments = parse_xml(self.package.parts[self.comments_part])
        return self._comments

    def _add(self, ref: str, note: str) -> None:
        authors = child(self.comments, "x:authors")
        names = [a.text for a in authors]
        if _AUTHOR not in names:
            authors.append(_el("author", _AUTHOR))
            names.append(_AUTHOR)
        comment = _el("comment", ref=ref, authorId=str(names.index(_AUTHOR)))
        comment.append(_note_text(note))
        child(self.comments, "x:commentList").append(comment)

    def _vml_part(self) -> str:
        legacy = self.sheet.root.find("x:legacyDrawing", NS)
        if legacy is not None:
            rid = legacy.get(q("r", "id"))
            for rel_id, _, target in relationships(self.package.parts, self.sheet_part):
                if rel_id == rid:
                    return target
        part = self.package.free_name("xl/drawings/vmlDrawing{}.vml")
        block = sum(1 for name in self.package.parts if name.endswith(".vml")) + 1
        self.package.parts[part] = (
            f'<xml {_VML_NS}><o:shapelayout v:ext="edit"><o:idmap v:ext="edit" data="{block}"/></o:shapelayout>'
            f"{_SHAPE_TYPE}</xml>"
        ).encode()
        self.package.declare_extension("vml", _VML)
        rid = self.package.add_relationship(self.sheet_part, "vmlDrawing", part)
        legacy = _el("legacyDrawing")
        legacy.set(q("r", "id"), rid)
        later = next((e for e in self.sheet.root if etree.QName(e).localname in _AFTER_LEGACY_DRAWING), None)
        if later is None:
            self.sheet.root.append(legacy)
        else:
            later.addprevious(legacy)
        return part

    def _add_shape(self, row: int, col: int) -> None:
        part = self._vml_part()
        vml = self.package.parts[part]
        numbers = [int(n) for n in _SHAPE_ID.findall(vml)]
        block = re.search(rb'data="(\d+)', vml)
        first = (int(block[1]) if block else 1) * 1024
        number = max([first, *numbers]) + 1
        if b"_x0000_t202" not in vml:
            vml = vml.replace(b"</xml>", _SHAPE_TYPE.encode() + b"</xml>", 1)
        shape = (
            f'<v:shape id="_x0000_s{number}" type="#_x0000_t202" style="position:absolute;margin-left:59.25pt;'
            'margin-top:1.5pt;width:144pt;height:59.25pt;z-index:1;visibility:hidden" fillcolor="#ffffe1" '
            'o:insetmode="auto"><v:fill color2="#ffffe1"/><v:shadow on="t" color="black" obscured="t"/>'
            '<v:path o:connecttype="none"/><v:textbox style="mso-direction-alt:auto"><div style="text-align:left"/>'
            '</v:textbox><x:ClientData ObjectType="Note"><x:MoveWithCells/><x:SizeWithCells/>'
            f"<x:Anchor>{col + 1}, 15, {row}, 10, {col + 3}, 15, {row + 4}, 4</x:Anchor><x:AutoFill>False</x:AutoFill>"
            f"<x:Row>{row}</x:Row><x:Column>{col}</x:Column></x:ClientData></v:shape>"
        )
        self.package.parts[part] = vml.replace(b"</xml>", shape.encode() + b"</xml>", 1)

    def _drop_shape(self, row: int, col: int) -> None:
        part = self._vml_part()
        vml = self.package.parts[part]
        mark = f"<x:Row>{row}</x:Row>".encode(), f"<x:Column>{col}</x:Column>".encode()

        def keep(match: re.Match[bytes]) -> bytes:
            shape = match[0]
            return b"" if b'ObjectType="Note"' in shape and all(m in shape for m in mark) else shape

        self.package.parts[part] = _SHAPE.sub(keep, vml, count=0)


def _comment_text(comment: etree._Element) -> str:
    return "".join(t.text or "" for t in comment.iter(q("x", "t")))


def _note_text(note: str) -> etree._Element:
    text = _el("text")
    run = _el("r")
    t = _el("t", _escaped(note))
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    run.append(t)
    text.append(run)
    return text
