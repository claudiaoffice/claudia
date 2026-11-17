"""Defined names and tables in an xlsx file (D457).

A range is a ``definedName`` in ``workbook.xml`` (``localSheetId`` for the names of one sheet); a table is a part of
its own (``xl/tables/tableN.xml``) that its sheet points at with ``tableParts``. Excel keeps a table's column names
equal to the text of its header cells, so a table is only written when the header cells are text, each different from
the others; a table whose header is not (a number, a formula, an empty cell, two columns of one name) is written as
the range it covers, and the loss says so (``name``, ``table-header``).

A kept file is patched in place (:class:`XlsxNamesPatch`): a name that was taken out goes, a name that points somewhere
else is written again where it stood, a table that has more rows or columns is resized in its own part (its style, its
formulas of calculated columns and every other thing of Excel's stay), and a header cell that was edited renames its
column. What the file names that the model does not (a constant, a formula, a name of several areas) stays."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import openpyxl
from lxml import etree
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.table import Table, TableColumn

from claudia_computes import NamedRange, RangeRef, SheetId, WorkbookModel
from claudia_computes.refs import column_name, quote_sheet_name
from claudia_odf_io import LossLog

from ._named import is_table, writable
from .xlsx_patch import PackagePatch, serialized
from .xlsx_read import NS, NameEntry, Package, WorksheetPart, name_entries, q, relationships, rels_part

TABLE_HEADER = "table-header"
_TABLE_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.table+xml"
_AFTER_DEFINED_NAMES = (
    "calcPr",
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


# ------------------------------------------------------------------------------------------------ references
def _a1(rng: RangeRef, *, absolute: bool) -> str:
    mark = "$" if absolute else ""

    def corner(row: int, col: int) -> str:
        return f"{mark}{column_name(col)}{mark}{row + 1}"

    first = corner(rng.first.row, rng.first.col)
    return first if rng.first == rng.last else f"{first}:{corner(rng.last.row, rng.last.col)}"


def reference_of(rng: RangeRef, sheets: Mapping[SheetId, str]) -> str:
    """``rng`` as a defined name holds it: ``Data!$A$1:$C$5``, the sheet quoted when its name needs it."""
    assert rng.sheet is not None  # (a name's range is always on a sheet)
    return f"{quote_sheet_name(sheets[rng.sheet])}!{_a1(rng, absolute=True)}"


def header_texts(model: WorkbookModel, named: NamedRange) -> list[str] | None:
    """The text of the header cells of the table ``named``, or ``None`` when Excel could not take them as its column
    names: a cell that is not text (a number, a formula, nothing), or two with the same name."""
    assert named.range is not None  # (only ranges are written)
    sheet = model.sheets[named.range.sheet]  # type: ignore[index]
    texts: list[str] = []
    for col in range(named.range.first.col, named.range.last.col + 1):
        content = sheet.cells.get((named.range.first.row, col))
        if content is None or content["t"] != "text" or not content["v"]:
            return None
        texts.append(content["v"])
    if len({text.casefold() for text in texts}) != len(texts):
        return None
    return texts


def _as_table(model: WorkbookModel, named: NamedRange) -> bool:
    return is_table(named) and header_texts(model, named) is not None


def header_losses(model: WorkbookModel, baseline: WorkbookModel | None) -> LossLog:
    """The tables of ``model`` that are written as plain ranges because their header is no text, that are new or have
    other header cells than in ``baseline`` (``None``: the start of a fresh file)."""
    losses = LossLog()
    for named in writable(model):
        if not is_table(named) or header_texts(model, named) is not None:
            continue
        before = None if baseline is None else baseline.names.get(named.key)
        if before is None or before != named or _headers_of(baseline, before) != _headers_of(model, named):
            losses.add("name", TABLE_HEADER)
    return losses


def _headers_of(model: WorkbookModel | None, named: NamedRange) -> object:
    if model is None or named.range is None or named.range.sheet not in model.sheets:
        return None
    sheet = model.sheets[named.range.sheet]
    return [
        sheet.cells.get((named.range.first.row, col)) for col in range(named.range.first.col, named.range.last.col + 1)
    ]


# ------------------------------------------------------------------------------------------------ a fresh file
def write_names(workbook: openpyxl.Workbook, model: WorkbookModel) -> None:
    """The names of ``model`` into the openpyxl workbook ``workbook``, whose sheets are those of the model."""
    sheets = {sheet_id: sheet.name for sheet_id, sheet in model.sheets.items()}
    for named in writable(model):
        assert named.range is not None
        if _as_table(model, named):
            workbook[sheets[named.range.sheet]].add_table(_table(model, named))  # type: ignore[index]
            continue
        found = DefinedName(named.name, attr_text=reference_of(named.range, sheets))
        holder = workbook if named.scope is None else workbook[sheets[named.scope]]
        holder.defined_names[named.name] = found


def _table(model: WorkbookModel, named: NamedRange) -> Table:
    assert named.range is not None
    texts = header_texts(model, named) or []
    columns = [TableColumn(id=number, name=text) for number, text in enumerate(texts, start=1)]
    return Table(displayName=named.name, name=named.name, ref=_a1(named.range, absolute=False), tableColumns=columns)


# ------------------------------------------------------------------------------------------------ a kept file
@dataclass
class _Plan:
    """What is to happen to the names of the file: the entries that go, the ones written again in place, and the
    names that are new (a name that changes form -- a range that became a table, or the other way round -- goes and
    comes again)."""

    gone: list[NameEntry]
    again: list[tuple[NamedRange, NameEntry]]
    added: list[NamedRange]


class XlsxNamesPatch:
    """The names of a kept file brought to what ``current`` has. Run it after the cells of the sheets are patched: it
    reads the sheet parts from ``patch`` as they are then."""

    def __init__(self, patch: PackagePatch, package: Package, baseline: WorkbookModel, current: WorkbookModel) -> None:
        self.patch, self.package, self.baseline, self.current = patch, package, baseline, current
        self.sheets = {sheet.sheet_id: sheet for sheet in package.sheets}
        self.names = {sheet_id: sheet.name for sheet_id, sheet in current.sheets.items()}
        self.entries = {entry.named.key: entry for entry in name_entries(package) if entry.named is not None}
        self.workbook_changed = False
        self._next_table_id = 1 + max(
            (int(entry.element.get("id", "0")) for entry in self.entries.values() if entry.part), default=0
        )

    # -- what to do ----------------------------------------------------------------------------------------
    def plan(self) -> _Plan:
        before = {named.key: named for named in self.baseline.names if not named.is_result}
        after = {named.key: named for named in writable(self.current)}
        gone: list[NameEntry] = []
        again: list[tuple[NamedRange, NameEntry]] = []
        added: list[NamedRange] = []
        for key, named in after.items():
            entry = self.entries.get(key)
            if entry is None and before.get(key) == named:
                continue  # (a name the import made, for the source of a pivot, D628: written once it differs)
            if entry is None or key not in before:
                added.append(named)
                continue
            if (entry.part is not None) != _as_table(self.current, named):
                gone.append(entry)  # (a range that became a table, or the other way round)
                added.append(named)
            else:
                again.append((named, entry))
        gone += [self.entries[key] for key in before if key not in after and key in self.entries]
        return _Plan(gone, again, added)

    def run(self) -> bool:
        """Make the changes in ``patch``; whether the file changed."""
        plan = self.plan()
        changed = False
        for entry in plan.gone:
            self._remove(entry)
            changed = True
        for named, entry in plan.again:
            changed |= self._rewrite(named, entry)
        for named in plan.added:
            self._add(named)
            changed = True
        if self.workbook_changed:
            self.patch.parts["xl/workbook.xml"] = serialized(self.package.workbook)
        return changed

    # -- defined names --------------------------------------------------------------------------------------
    def _defined_names(self) -> etree._Element:
        found = self.package.workbook.find("x:definedNames", NS)
        if found is not None:
            return found
        found = etree.Element(q("x", "definedNames"))
        later = next((e for e in self.package.workbook if etree.QName(e).localname in _AFTER_DEFINED_NAMES), None)
        if later is None:
            self.package.workbook.append(found)
        else:
            later.addprevious(found)
        return found

    def _position(self, sheet: SheetId) -> int:
        """Where ``sheet`` is among all the sheets of the workbook, which is what ``localSheetId`` counts."""
        return self.package.places.index(sheet)

    def _add_defined(self, named: NamedRange) -> None:
        assert named.range is not None
        element = etree.SubElement(self._defined_names(), q("x", "definedName"), name=named.name)
        if named.scope is not None:
            element.set("localSheetId", str(self._position(named.scope)))
        element.text = reference_of(named.range, self.names)
        self.workbook_changed = True

    def _remove_defined(self, element: etree._Element) -> None:
        holder = element.getparent()
        assert holder is not None
        holder.remove(element)
        if not len(holder):
            self.package.workbook.remove(holder)
        self.workbook_changed = True

    # -- tables ---------------------------------------------------------------------------------------------
    def _sheet_of(self, named: NamedRange) -> WorksheetPart:
        assert named.range is not None
        return self.sheets[named.range.sheet]  # type: ignore[index]

    def _add_table(self, named: NamedRange) -> None:
        sheet = self._sheet_of(named)
        part = self.patch.free_name("xl/tables/table{}.xml")
        root = etree.fromstring(f'<table xmlns="{NS["x"]}"/>')
        root.set("id", str(self._next_table_id))
        self._next_table_id += 1
        root.set("name", named.name)
        root.set("displayName", named.name)
        assert named.range is not None
        root.set("ref", _a1(named.range, absolute=False))
        columns = etree.SubElement(root, q("x", "tableColumns"))
        for number, text in enumerate(header_texts(self.current, named) or [], start=1):
            etree.SubElement(columns, q("x", "tableColumn"), id=str(number), name=text)
        columns.set("count", str(len(columns)))
        self.patch.parts[part] = serialized(root)
        self.patch.declare(part, _TABLE_TYPE)
        rid = self.patch.add_relationship(sheet.part, "table", part)
        worksheet = etree.fromstring(self.patch.parts[sheet.part])
        holder = worksheet.find("x:tableParts", NS)
        if holder is None:
            holder = etree.Element(q("x", "tableParts"))
            tail = worksheet.find("x:extLst", NS)
            if tail is None:
                worksheet.append(holder)
            else:
                tail.addprevious(holder)
        etree.SubElement(holder, q("x", "tablePart")).set(q("r", "id"), rid)
        holder.set("count", str(len(holder)))
        self.patch.parts[sheet.part] = serialized(worksheet)

    def _remove_table(self, entry: NameEntry) -> None:
        assert entry.part is not None and entry.sheet is not None
        sheet_part = entry.sheet.part
        rid = next(
            (rid for rid, _, target in relationships(self.patch.parts, sheet_part) if target == entry.part),
            None,
        )
        worksheet = etree.fromstring(self.patch.parts[sheet_part])
        holder = worksheet.find("x:tableParts", NS)
        if holder is not None and rid is not None:
            for each in [e for e in holder if e.get(q("r", "id")) == rid]:
                holder.remove(each)
            if len(holder):
                holder.set("count", str(len(holder)))
            else:
                worksheet.remove(holder)
            self.patch.parts[sheet_part] = serialized(worksheet)
        if rid is not None:
            self.patch.remove_relationship(sheet_part, rid)
        self.patch.forget(entry.part)
        self.patch.parts.pop(rels_part(entry.part), None)

    def _resync_table(self, named: NamedRange, entry: NameEntry) -> bool:
        """Bring the table part to the range and the header cells of ``named``; whether it changed."""
        assert named.range is not None and entry.part is not None
        table = entry.element
        texts = header_texts(self.current, named) or []
        ref = _a1(named.range, absolute=False)
        columns = table.find("x:tableColumns", NS)
        assert columns is not None  # (a table has columns; the import read it)
        existing = list(columns)
        if table.get("ref") == ref and [c.get("name") for c in existing] == texts:
            return False
        table.set("ref", ref)
        filtering = table.find("x:autoFilter", NS)
        if filtering is not None:
            filtering.set("ref", ref)
        used = [int(c.get("id", "0")) for c in existing]
        for number, text in enumerate(texts):
            if number < len(existing):
                existing[number].set("name", text)
            else:
                used.append(max(used, default=0) + 1)
                etree.SubElement(columns, q("x", "tableColumn"), id=str(used[-1]), name=text)
        for extra in existing[len(texts) :]:
            columns.remove(extra)
        columns.set("count", str(len(columns)))
        self.patch.parts[entry.part] = serialized(table)
        return True

    # -- the changes ----------------------------------------------------------------------------------------
    def _remove(self, entry: NameEntry) -> None:
        if entry.part is not None:
            self._remove_table(entry)
        else:
            self._remove_defined(entry.element)

    def _rewrite(self, named: NamedRange, entry: NameEntry) -> bool:
        if entry.part is not None:
            return self._resync_table(named, entry)
        before = self.baseline.names.get(named.key)
        if before == named:
            return False
        assert named.range is not None
        entry.element.text = reference_of(named.range, self.names)
        self.workbook_changed = True
        return True

    def _add(self, named: NamedRange) -> None:
        if _as_table(self.current, named):
            self._add_table(named)
        else:
            self._add_defined(named)
