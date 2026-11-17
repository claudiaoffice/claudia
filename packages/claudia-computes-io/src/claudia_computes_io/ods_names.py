"""Named ranges and tables in an ods file (D457).

A range is ``table:named-range`` in ``table:named-expressions`` (the workbook's, after the sheets, or a sheet's own,
at the end of the ``table:table``); a table is ``table:database-range`` with ``table:contains-header``. They are
written the way LibreOffice writes them (``$Data.$A$1:.$C$5`` for a range, ``Data.A1:.C5`` for a table) and read in
every form the programs use. What a file names that the model cannot -- a constant or a formula
(``table:named-expression``), a range of several sheets or of one that does not exist, a table with a filter or
without a header -- is left alone in a kept file and counted by the import (``named-range``, ``filter``)."""

from __future__ import annotations

import re
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass

from lxml import etree

from claudia_computes import NamedRange, RangeRef, SheetId, WorkbookModel
from claudia_computes.limits import MAX_COLS, MAX_ROWS
from claudia_computes.names import name_problem
from claudia_computes.refs import CellRef, column_index, column_name
from claudia_odf_io import NS, XmlPart, qname
from claudia_odf_io import local_name as local_of

from ._named import is_table, writable

_SHEET = r"(?:'(?:[^']|'')+'|[^.:'\s$]+)"
_CELL = r"\$?(?P<{c}>[A-Za-z]{{1,3}})\$?(?P<{r}>\d+)"
_ADDRESS = re.compile(
    rf"^\$?(?P<sheet>{_SHEET})\.{_CELL.format(c='c1', r='r1')}"
    rf"(?::\$?(?P<other>{_SHEET})?\.{_CELL.format(c='c2', r='r2')})?$"
)
_ANONYMOUS = "__Anonymous"

SheetIds = Callable[[str], SheetId | None]


_DECLARED = {prefix: uri for prefix, uri in NS.items() if prefix != "xml"}


def _q(prefix: str, local: str) -> str:
    return qname(f"{prefix}:{local}")


# ------------------------------------------------------------------------------------------------ addresses
def _sheet_text(name: str) -> str:
    return name if re.fullmatch(r"\w+", name) else "'" + name.replace("'", "''") + "'"


def address_of(rng: RangeRef, sheets: Mapping[SheetId, str], *, absolute: bool = True) -> str:
    """``rng`` as ods writes the address of a range: ``$Data.$A$1:.$C$5``, a single cell once (``$Data.$A$1``); the
    ``$`` signs are left out for ``absolute=False`` (the address of a table, ``Data.A1:.C5``)."""
    mark = "$" if absolute else ""

    def corner(cell: CellRef) -> str:
        return f"{mark}{column_name(cell.col)}{mark}{cell.row + 1}"

    assert rng.sheet is not None  # (a name's range is always on a sheet)
    head = f"{mark}{_sheet_text(sheets[rng.sheet])}.{corner(rng.first)}"
    return head if rng.first == rng.last else f"{head}:.{corner(rng.last)}"


def _unquoted(name: str) -> str:
    return name[1:-1].replace("''", "'") if name.startswith("'") else name


def range_of(text: str, sheet_ids: SheetIds) -> RangeRef | None:
    """The range an ods address names, or ``None`` when it is none the model can name: not one range, on a sheet the
    file does not have, over several sheets, or outside the grid."""
    found = _ADDRESS.match(text.strip())
    if found is None:
        return None
    sheet = sheet_ids(_unquoted(found["sheet"]))
    other = found["other"]
    if sheet is None or (other is not None and sheet_ids(_unquoted(other)) != sheet):
        return None
    first = _cell(found["c1"], found["r1"], sheet)
    last = first if found["c2"] is None else _cell(found["c2"], found["r2"], sheet)
    if first is None or last is None:
        return None
    return RangeRef.between(first, last)


def _cell(letters: str, number: str, sheet: SheetId) -> CellRef | None:
    column, row = column_index(letters), int(number) - 1
    return CellRef(row, column, sheet) if 0 <= column < MAX_COLS and 0 <= row < MAX_ROWS else None


# ------------------------------------------------------------------------------------------------ reading
@dataclass(frozen=True)
class Entry:
    """One name or database range of the file. ``named`` is what the model makes of it (``None`` when it cannot);
    ``scope`` the sheet whose own it is."""

    element: etree._Element
    named: NamedRange | None
    scope: SheetId | None


@dataclass(frozen=True)
class SheetPlace:
    """A sheet of the file: its id, its name and its ``table:table``."""

    id: SheetId
    name: str
    element: etree._Element


def _in(element: etree._Element, tag: str) -> list[etree._Element]:
    return element.findall(f"table:{tag}/table:*", NS)


def scan(spreadsheet: etree._Element, sheets: Sequence[SheetPlace]) -> list[Entry]:
    """Every ``table:named-range``, ``table:named-expression`` and ``table:database-range`` of the file, in document
    order, with the name the model makes of it. A name that repeats one of the same scope is the file's and no name of
    the model's."""
    ids = {place.name: place.id for place in sheets}.get
    entries: list[Entry] = []
    taken: set[tuple[SheetId | None, str]] = set()

    def add(element: etree._Element, scope: SheetId | None, named: NamedRange | None) -> None:
        if named is not None and named.key in taken:
            named = None
        if named is not None:
            taken.add(named.key)
        entries.append(Entry(element, named, scope))

    for place in sheets:
        for element in _in(place.element, "named-expressions"):
            add(element, place.id, _range(element, place.id, ids))
    for element in _in(spreadsheet, "named-expressions"):
        add(element, None, _range(element, None, ids))
    for element in _in(spreadsheet, "database-ranges"):
        add(element, None, _table(element, ids))
    return entries


def _range(element: etree._Element, scope: SheetId | None, ids: SheetIds) -> NamedRange | None:
    if local_of(element.tag) != "named-range":
        return None
    name = element.get(_q("table", "name"), "")
    rng = range_of(element.get(_q("table", "cell-range-address"), ""), ids)
    if rng is None or name_problem(name) is not None or (scope is not None and rng.sheet != scope):
        return None
    return NamedRange(name, scope, rng)


def _table(element: etree._Element, ids: SheetIds) -> NamedRange | None:
    name = element.get(_q("table", "name"), "")
    rng = range_of(element.get(_q("table", "target-range-address"), ""), ids)
    header = element.get(_q("table", "contains-header"), "true") == "true"
    if name.startswith(_ANONYMOUS) or rng is None or not header or len(element) or name_problem(name) is not None:
        return None
    return NamedRange(name, None, rng, header=True)


@dataclass(frozen=True)
class NamesRead:
    """What a file names: the names the model has, and how many entries it has not (ranges and expressions it cannot
    read, database ranges that are no table)."""

    names: list[NamedRange]
    unread_ranges: int
    unread_databases: int


def read_names(spreadsheet: etree._Element, sheets: Sequence[SheetPlace]) -> NamesRead:
    """The names of the file as :class:`~claudia_computes.NamedRange`, and what it names that they are not."""
    names: list[NamedRange] = []
    ranges = databases = 0
    for entry in scan(spreadsheet, sheets):
        if entry.named is not None:
            names.append(entry.named)
        elif local_of(entry.element.tag) == "database-range":
            databases += 1
        else:
            ranges += 1
    return NamesRead(names, ranges, databases)


# ------------------------------------------------------------------------------------------------ writing
def _range_element(named: NamedRange, sheets: Mapping[SheetId, str]) -> tuple[str, dict[str, str]]:
    assert named.range is not None  # (only ranges are written)
    first = RangeRef(named.range.first, named.range.first)
    if is_table(named):
        return "database-range", {
            "table:name": named.name,
            "table:target-range-address": address_of(named.range, sheets, absolute=False),
            "table:contains-header": "true",
        }
    return "named-range", {
        "table:name": named.name,
        "table:base-cell-address": address_of(first, sheets),
        "table:cell-range-address": address_of(named.range, sheets),
    }


def _element(named: NamedRange, sheets: Mapping[SheetId, str]) -> etree._Element:
    tag, attributes = _range_element(named, sheets)
    element = etree.Element(_q("table", tag), nsmap=_DECLARED)
    for key, value in attributes.items():
        prefix, _, local = key.partition(":")
        element.set(_q(prefix, local), value)
    return element


def _holder(tag: str, children: Iterable[etree._Element]) -> etree._Element | None:
    items = list(children)
    if not items:
        return None
    holder = etree.Element(_q("table", tag), nsmap=_DECLARED)
    holder.extend(items)
    return holder


def sheet_names(model: WorkbookModel) -> dict[SheetId, str]:
    """The name of every sheet of ``model``, which is how an address names it."""
    return {sheet_id: sheet.name for sheet_id, sheet in model.sheets.items()}


def local_expressions(model: WorkbookModel, scope: SheetId) -> etree._Element | None:
    """The ``table:named-expressions`` that goes at the end of the sheet ``scope``: its own names."""
    sheets = sheet_names(model)
    return _holder("named-expressions", (_element(named, sheets) for named in writable(model) if named.scope == scope))


def global_elements(model: WorkbookModel) -> list[etree._Element]:
    """The ``table:named-expressions`` and ``table:database-ranges`` that go after the sheets of a new file: the names
    of the workbook, ranges first and tables after."""
    sheets = sheet_names(model)
    shared = [named for named in writable(model) if named.scope is None]
    found = (
        _holder("named-expressions", (_element(named, sheets) for named in shared if not is_table(named))),
        _holder("database-ranges", (_element(named, sheets) for named in shared if is_table(named))),
    )
    return [holder for holder in found if holder is not None]


# ------------------------------------------------------------------------------------------------ patching
class NamesPatch:
    """The names of a kept file brought to what ``current`` has, by the edits to ``baseline`` (D457): a name that was
    taken out goes from the file, a name that points somewhere else is written again where it stood, a new name goes
    into the file's own ``table:named-expressions`` (or ``table:database-ranges``) or into one made for it. What the
    file names that the model does not stays."""

    def __init__(
        self,
        part: XmlPart,
        spreadsheet: etree._Element,
        sheets: Sequence[SheetPlace],
        baseline: WorkbookModel,
        current: WorkbookModel,
    ) -> None:
        self.part, self.spreadsheet, self.sheets = part, spreadsheet, sheets
        self.baseline, self.current = baseline, current
        self.entries = {entry.named.key: entry for entry in scan(spreadsheet, sheets) if entry.named is not None}
        self.names = sheet_names(current)

    def changes(self) -> tuple[list[NamedRange], list[NamedRange], list[NamedRange]]:
        """The names to add, to write again and to take out."""
        before = {named.key: named for named in self.baseline.names if not named.is_result}
        after = {named.key: named for named in self.current.names if not named.is_result}
        # (a name the baseline has and the file has not is one the import made for a pivot's source, D628: it is
        # written only once it differs from the baseline)
        added = [
            after[key] for key in after if key not in before or (key not in self.entries and before[key] != after[key])
        ]
        again: list[NamedRange] = []
        gone = [before[key] for key in before if key not in after and key in self.entries]
        for key, named in after.items():
            if key not in before or key not in self.entries:
                continue
            if self._is_database(self.entries[key]) != is_table(named):
                gone.append(before[key])  # (a range that became a table, or the other way round)
                added.append(named)
            elif before[key] != named or self._renamed(named):
                again.append(named)
        return added, again, gone

    @staticmethod
    def _is_database(entry: Entry) -> bool:
        return local_of(entry.element.tag) == "database-range"

    def _renamed(self, named: NamedRange) -> bool:
        """Whether the sheet a name points into has another name than when the file was read: the file names it by the
        old one."""
        sheet = None if named.range is None else named.range.sheet
        return (
            sheet in self.baseline.sheets
            and sheet in self.current.sheets
            and (self.baseline.sheets[sheet].name != self.current.sheets[sheet].name)
        )

    def run(self, known: Collection[SheetId]) -> bool:
        """Make the edits; whether the file changed. ``known`` are the sheets the file has already (the names of a sheet
        that is new are written with the sheet)."""
        added, again, gone = self.changes()
        usable = {named.key for named in writable(self.current)}
        gone = [named for named in gone if self._survives(named)]
        again = [named for named in again if self._survives(named)]
        for named in gone:
            self.part.remove(self.entries[named.key].element)
        for named in again:
            if named.key in usable:
                self.part.replace(self.entries[named.key].element, _element(named, self.names))
            else:
                self.part.remove(self.entries[named.key].element)
        fresh = [named for named in added if named.key in usable and named.scope in (None, *known)]
        self._add(fresh)
        return bool(gone or again or fresh)

    def _survives(self, named: NamedRange) -> bool:
        """Whether the file's entry for ``named`` is still in the file: not inside a sheet that is removed."""
        scope = self.entries[named.key].scope
        return scope is None or scope in self.current.sheets

    def _add(self, names: list[NamedRange]) -> None:
        by_place: dict[str | None, list[NamedRange]] = {}
        for named in names:
            by_place.setdefault(None if named.scope is None else str(named.scope), []).append(named)
        shared = by_place.pop(None, [])
        for scope, group in by_place.items():
            place = next(place for place in self.sheets if str(place.id) == scope)
            self._put(place.element, "named-expressions", group, at=place.element)
        self._put(self.spreadsheet, "named-expressions", [n for n in shared if not is_table(n)], at=None)
        self._put(self.spreadsheet, "database-ranges", [n for n in shared if is_table(n)], at=None)

    def _put(self, parent: etree._Element, tag: str, names: list[NamedRange], *, at: etree._Element | None) -> None:
        if not names:
            return
        items = [_element(named, self.names) for named in names]
        holder = parent.find(f"table:{tag}", NS)
        if holder is not None:
            self.part.insert_into(holder, *items)
            return
        new = _holder(tag, items)
        assert new is not None
        if at is not None:  # a sheet's own: the last thing in it
            self.part.insert_into(at, new)
        else:
            self._place_shared(parent, tag, new)

    def _place_shared(self, spreadsheet: etree._Element, tag: str, new: etree._Element) -> None:
        """A workbook's ``table:named-expressions`` goes before its database ranges, which go before its pivot tables;
        else after the last sheet (or after what has to come first)."""
        later = {
            "named-expressions": ("database-ranges", "data-pilot-tables"),
            "database-ranges": ("data-pilot-tables",),
        }
        for name in later[tag]:
            follower = spreadsheet.find(f"table:{name}", NS)
            if follower is not None:
                self.part.insert_before(follower, new)
                return
        earlier = spreadsheet.find("table:named-expressions", NS) if tag == "database-ranges" else None
        tables = spreadsheet.findall("table:table", NS)
        anchor = earlier if earlier is not None else (tables[-1] if tables else None)
        if anchor is not None:
            self.part.insert_after(anchor, new)
        else:
            self.part.insert_into(spreadsheet, new)
