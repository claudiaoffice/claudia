"""Pivot tables in an xlsx file (E6.30, D625, D628): the cache, the pivot table and the :class:`FilePivot` they say.

A pivot table of Excel is three parts that belong together: a *cache definition* (the source and its fields, with the
distinct values of each) and its *records* (the source rows, as numbers that point at those values), and the
``pivotTableDefinition`` (where the pivot is, which field goes where, how a value is added up). The workbook names each
cache (``pivotCaches``), the sheet names each table, and the table names its cache. The cells a pivot fills are
ordinary cells of the sheet.

*Writing* (:func:`add_pivots`): one cache for each pivot, ``refreshOnLoad`` so that Excel makes the table again when it
opens the file; the cells are written beside it, so a program that does not make pivots shows the numbers too. The
tabular layout is used, since that is the grid of the engine (a field's name above its members, not "Row Labels").
Excel puts the buttons of the filters in the rows above a pivot; a pivot with filters and no free rows there is written
as its values (:func:`written_pivots_of`, the loss detail ``room``).

*Reading* (:func:`read_pivots`): the cache gives the source (a range of a sheet, or a table or name), the table the
fields. What the engine has no word for is *unreadable*: the cells then stay the cells they are, and the loss says
why, by its detail: ``external-source`` and ``data-model`` (the cache is not a range of this file),
``calculated-field``, ``grouping``, ``slicer``, ``pivot-chart``, ``show-as``, ``aggregation`` (a function the engine
lacks), ``hidden-items``, ``top-n`` and ``sort``.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass, field
from typing import cast

from lxml import etree

from claudia_computes import (
    Aggregation,
    CellRef,
    PivotFilter,
    PivotLabels,
    PivotRole,
    RangeRef,
    SheetId,
    ValueField,
    WorkbookModel,
)
from claudia_computes.names import key_of
from claudia_computes.refs import column_name
from claudia_computes.values import ErrorValue, Value
from claudia_odf_io import LossLog, xml_safe
from claudia_opc_io import write_parts

from .pivot_exchange import PIVOT_LOSS, FilePivot, WrittenPivots, source_table, written_pivots
from .xlsx_patch import PackagePatch, serialized
from .xlsx_read import NS, Package, area, open_package, parse_xml, q, relationships

_MAIN = NS["x"]
_R = NS["r"]
_TYPES = "application/vnd.openxmlformats-officedocument.spreadsheetml."
#: What ``workbook.xml`` may hold after ``pivotCaches`` (ECMA-376 18.2.27): the element goes before the first of them.
_AFTER_CACHES = ("smartTagPr", "smartTagTypes", "webPublishing", "fileRecoveryPr", "webPublishObjects", "extLst")

_FUNCTIONS = {
    Aggregation.SUM: "sum",
    Aggregation.COUNT: "count",
    Aggregation.AVERAGE: "average",
    Aggregation.MIN: "min",
    Aggregation.MAX: "max",
}
_AGGREGATIONS = {name: aggregation for aggregation, name in _FUNCTIONS.items()}
_SORTED_DOWN = "descending"
#: The types of a pivot filter that keep the first items of a field by their values (the others hide by their labels).
_TOP_N = ("count", "percent", "sum")


# The default namespace has the key None, which the lxml stubs do not allow.
_NSMAP = cast("dict[str, str]", {None: _MAIN})


def _el(tag: str, **attributes: object) -> etree._Element:
    return etree.Element(f"{{{_MAIN}}}{tag}", {key: str(value) for key, value in attributes.items()}, nsmap=_NSMAP)


def _sub(parent: etree._Element, tag: str, **attributes: object) -> etree._Element:
    return etree.SubElement(parent, f"{{{_MAIN}}}{tag}", {key: str(value) for key, value in attributes.items()})


def _flag(value: bool) -> str:  # noqa: FBT001
    return "1" if value else "0"


def _reference(rng: RangeRef) -> str:
    first, last = rng.first, rng.last
    return f"{column_name(first.col)}{first.row + 1}:{column_name(last.col)}{last.row + 1}"


def _number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else repr(float(value))


# ------------------------------------------------------------------------------------------------ what can be written
def has_room(model: WorkbookModel, pivot: FilePivot) -> bool:
    """Whether the filters of ``pivot`` have the rows Excel puts them in: one for each and an empty one above its
    cells, with nothing in the cells they will fill."""
    if not pivot.filters:
        return True
    needed = len(pivot.filters) + 1
    target = pivot.target
    if target.first.row < needed:
        return False
    sheet = model.sheet(cast("SheetId", target.sheet))
    return not any(
        (row, col) in sheet.cells
        for row in range(target.first.row - needed, target.first.row)
        for col in (target.first.col, target.first.col + 1)
    )


def written_pivots_of(model: WorkbookModel, among: Collection[str] | None = None) -> WrittenPivots:
    """The pivots of ``model`` (with ``among``: of those names) an xlsx file holds as pivots, and the losses of the
    others: those the exchange cannot make a pivot of (:func:`~claudia_computes_io.pivot_exchange.written_pivots`) and
    those with filters and no room."""
    found = written_pivots(model, among)
    fitting = tuple(pivot for pivot in found.pivots if has_room(model, pivot))
    losses = LossLog()
    for pivot in found.pivots:
        if pivot not in fitting:
            losses.add(PIVOT_LOSS, "room")
    return WrittenPivots(fitting, (*found.losses, *losses.result()))


# ------------------------------------------------------------------------------------------------ writing
def add_pivots(data: bytes, model: WorkbookModel, pivots: tuple[FilePivot, ...]) -> bytes:
    """``data`` (an xlsx file made of ``model``'s sheets) with a pivot table for each of ``pivots``
    (:func:`put_pivots`)."""
    if not pivots:
        return data
    package = open_package(data)
    patch = PackagePatch(package.parts)
    put_pivots(patch, package, model, pivots)
    return write_parts(patch.finish())


def put_pivots(patch: PackagePatch, package: Package, model: WorkbookModel, pivots: tuple[FilePivot, ...]) -> None:
    """A pivot table for each of ``pivots`` in ``package`` (changed in ``patch``), a new file or a kept one (CODE-70):
    its cache and records, the table, and the relationships and content types that join them to the workbook and the
    sheet. The caches are numbered on from those the workbook has, in its ``pivotCaches``."""
    workbook = parse_xml(patch.parts["xl/workbook.xml"])
    caches = _caches_of(workbook)
    first = max((int(each.get("cacheId") or 0) for each in caches), default=0) + 1
    parts = {sheet.name.casefold(): sheet.part for sheet in package.sheets}
    for number, pivot in enumerate(pivots, start=first):
        cache = _Cache(model, pivot)
        definition = patch.free_name("xl/pivotCache/pivotCacheDefinition{}.xml")
        records = patch.free_name("xl/pivotCache/pivotCacheRecords{}.xml")
        patch.parts[records] = serialized(cache.records())
        patch.declare(records, _TYPES + "pivotCacheRecords+xml")
        records_rid = patch.add_relationship(definition, "pivotCacheRecords", records)
        sheet = model.sheet(cast("SheetId", pivot.source.sheet)).name
        patch.parts[definition] = serialized(cache.definition(sheet, records_rid))
        patch.declare(definition, _TYPES + "pivotCacheDefinition+xml")
        workbook_rid = patch.add_relationship("xl/workbook.xml", "pivotCacheDefinition", definition)
        _sub(caches, "pivotCache", cacheId=number).set(f"{{{_R}}}id", workbook_rid)
        table = patch.free_name("xl/pivotTables/pivotTable{}.xml")
        patch.parts[table] = serialized(_table(pivot, cache, number))
        patch.declare(table, _TYPES + "pivotTable+xml")
        patch.add_relationship(table, "pivotCacheDefinition", definition)
        patch.add_relationship(
            parts[model.sheet(cast("SheetId", pivot.target.sheet)).name.casefold()], "pivotTable", table
        )
    patch.parts["xl/workbook.xml"] = serialized(workbook)


def _caches_of(workbook: etree._Element) -> etree._Element:
    """The ``pivotCaches`` of ``workbook``, made where the standard has it when there is none."""
    caches = workbook.find("x:pivotCaches", NS)
    if caches is not None:
        return caches
    caches = etree.Element(f"{{{_MAIN}}}pivotCaches", nsmap={**_NSMAP, "r": _R})
    later = next((e for e in workbook if isinstance(e.tag, str) and etree.QName(e).localname in _AFTER_CACHES), None)
    if later is None:
        workbook.append(caches)
    else:
        later.addprevious(caches)
    return caches


def _kind(value: Value) -> str:
    """How a cache stores ``value``: ``m`` nothing, ``b`` a boolean, ``n`` a number, ``e`` an error, ``s`` text."""
    if value is None:
        return "m"
    if isinstance(value, bool):
        return "b"
    if isinstance(value, (int, float)):
        return "n"
    return "e" if isinstance(value, ErrorValue) else "s"


def _item(value: Value) -> etree._Element:
    """One value as the cache writes it: ``s`` text, ``n`` number, ``b`` boolean, ``e`` error, ``m`` nothing."""
    kind = _kind(value)
    if kind == "m":
        return _el("m")
    if isinstance(value, ErrorValue):
        return _el("e", v=xml_safe(value.code))
    if isinstance(value, bool):
        return _el("b", v=_flag(value))
    if isinstance(value, (int, float)):
        return _el("n", v=_number(value))
    return _el("s", v=xml_safe(str(value)))


def _key(value: Value) -> tuple[str, object]:
    """What makes two values one item of a field: the same kind, the same value (``1`` is ``1.0``, not ``True``)."""
    kind = _kind(value)
    if kind == "n":
        return kind, float(cast("float", value))
    return kind, value.code if isinstance(value, ErrorValue) else value


@dataclass
class _Field:
    """One column of the source in the cache: its name, its values, and the *shared* items a record points at. A field
    on an axis is always shared, and so is one that has text, a boolean or an error in it; numbers of a field that is
    only added up are written in the records."""

    name: str
    values: list[Value]
    axis: bool
    members: list[Value]  # the values in the order the pivot shows them
    shared: bool = field(init=False)
    items: list[Value] = field(init=False, default_factory=list)
    index: dict[tuple[str, object], int] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        self.kinds = {_kind(value) for value in self.values}
        self.shared = self.axis or bool(self.kinds & {"s", "b", "e"})
        if self.shared:
            seen: dict[tuple[str, object], Value] = {}
            for value in (*self.members, *self.values):
                seen.setdefault(_key(value), value)
            self.items = list(seen.values())
            self.index = {key: position for position, key in enumerate(seen)}

    def shared_items(self) -> etree._Element:
        numbers = [float(cast("float", v)) for v in self.values if _kind(v) == "n"]
        attributes: dict[str, str] = {}
        if self.kinds == {"n"}:
            attributes.update(containsSemiMixedTypes="0", containsString="0", containsNumber="1")
        elif "n" in self.kinds and "s" in self.kinds:
            attributes.update(containsMixedTypes="1", containsNumber="1")
        elif "n" in self.kinds:
            attributes.update(containsString="0", containsNumber="1")
        if "m" in self.kinds:
            attributes["containsBlank"] = "1"
        if numbers:
            if all(number.is_integer() for number in numbers):
                attributes["containsInteger"] = "1"
            attributes.update(minValue=_number(min(numbers)), maxValue=_number(max(numbers)))
        element = _el("sharedItems", **attributes)
        if self.shared:
            element.set("count", str(len(self.items)))
            element.extend(_item(value) for value in self.items)
        return element


class _Cache:
    """The cache of one pivot: the fields of its source, built from the source's cells in the model."""

    def __init__(self, model: WorkbookModel, pivot: FilePivot) -> None:
        self.pivot = pivot
        self.names, self.rows = source_table(model, pivot.source)
        axes = {name.casefold() for name in (*pivot.rows, *pivot.columns, *(each.field for each in pivot.filters))}
        shown = shown_members(pivot)
        self.fields = [
            _Field(name, [row[column] for row in self.rows], name.casefold() in axes, shown.get(name.casefold(), []))
            for column, name in enumerate(self.names)
        ]

    def number(self, name: str) -> int:
        """The place of the field called ``name`` (without regard to case) among the source's columns."""
        return [each.casefold() for each in self.names].index(name.casefold())

    def definition(self, sheet: str, records_rid: str) -> etree._Element:
        root = _el(
            "pivotCacheDefinition",
            refreshOnLoad="1",
            refreshedBy="claudia",
            createdVersion="6",
            refreshedVersion="6",
            minRefreshableVersion="3",
            recordCount=len(self.rows),
        )
        root.set(f"{{{_R}}}id", records_rid)
        source = _sub(root, "cacheSource", type="worksheet")
        _sub(source, "worksheetSource", ref=_reference(self.pivot.source), sheet=sheet)
        fields = _sub(root, "cacheFields", count=len(self.fields))
        for each in self.fields:
            _sub(fields, "cacheField", name=xml_safe(each.name), numFmtId="0").append(each.shared_items())
        return root

    def records(self) -> etree._Element:
        root = _el("pivotCacheRecords", count=len(self.rows))
        for row in self.rows:
            record = _sub(root, "r")
            for each, value in zip(self.fields, row, strict=True):
                record.append(_el("x", v=each.index[_key(value)]) if each.shared else _item(value))
        return root


def shown_members(pivot: FilePivot) -> dict[str, list[Value]]:
    """The members of each axis field in the order the pivot shows them, so that the table lists its items in that
    order (Excel keeps the order of a table's items, and so shows the cells that were written)."""
    result = pivot.result
    if result is None or not result.rows:
        return {}
    found: dict[str, list[Value]] = {}
    blank = pivot.labels.blank
    if pivot.rows:
        found[pivot.rows[0].casefold()] = [
            None if result.rows[r][0] == blank else result.rows[r][0]
            for r in range(result.header_rows, result.height)
            if result.roles[r][0] is PivotRole.LABEL
        ]
    if pivot.columns:
        total = len(pivot.values) if pivot.total_column else 0
        cells = result.rows[1][1 : result.width - total]
        found[pivot.columns[0].casefold()] = [None if cell == blank else cell for cell in cells if cell is not None]
    return found


def _table(pivot: FilePivot, cache: _Cache, number: int) -> etree._Element:
    """The ``pivotTableDefinition`` of ``pivot`` over ``cache``."""
    several = len(pivot.values) > 1
    root = _el(
        "pivotTableDefinition",
        name=xml_safe(pivot.name),
        cacheId=number,
        applyNumberFormats="0",
        applyBorderFormats="0",
        applyFontFormats="0",
        applyPatternFormats="0",
        applyAlignmentFormats="0",
        applyWidthHeightFormats="1",
        dataCaption="Values",
        grandTotalCaption=xml_safe(pivot.labels.total),
        updatedVersion="6",
        minRefreshableVersion="3",
        useAutoFormatting="1",
        itemPrintTitles="1",
        createdVersion="6",
        indent="0",
        compact="0",
        compactData="0",
        outline="0",
        outlineData="0",
        multipleFieldFilters="0",
        rowGrandTotals=_flag(pivot.total_column),
        colGrandTotals=_flag(pivot.total_row),
    )
    location = _sub(
        root,
        "location",
        ref=_reference(pivot.target),
        firstHeaderRow=0 if several and not pivot.columns else 1,
        firstDataRow=3 if several and pivot.columns else 2 if pivot.columns else 1,
        firstDataCol=1,
    )
    if pivot.filters:
        location.set("rowPageCount", str(len(pivot.filters)))
        location.set("colPageCount", "1")
    _pivot_fields(root, pivot, cache)
    _fields(root, "rowFields", [cache.number(name) for name in pivot.rows])
    _items(root, "rowItems", _lines(pivot, cache, pivot.rows, total=pivot.total_row))
    _fields(root, "colFields", [*(cache.number(name) for name in pivot.columns), *([-2] if several else [])])
    if not several:
        _items(root, "colItems", _lines(pivot, cache, pivot.columns, total=pivot.total_column))
    if pivot.filters:
        pages = _sub(root, "pageFields", count=len(pivot.filters))
        for each in pivot.filters:
            attributes = {"item": _page_item(each, cache)} if each.keep is not None and len(each.keep) == 1 else {}
            _sub(pages, "pageField", fld=cache.number(each.field), hier="-1", **attributes)
    values = _sub(root, "dataFields", count=len(pivot.values))
    for value in pivot.values:
        title = xml_safe(value.name or pivot.labels.title(value.aggregation, value.field))
        element = _sub(values, "dataField", name=title, fld=cache.number(value.field), baseField="0", baseItem="0")
        if value.aggregation is not Aggregation.SUM:
            element.set("subtotal", _FUNCTIONS[value.aggregation])
    _sub(
        root,
        "pivotTableStyleInfo",
        name="PivotStyleLight16",
        showRowHeaders="1",
        showColHeaders="1",
        showRowStripes="0",
        showColStripes="0",
        showLastColumn="1",
    )
    return root


def _pivot_fields(root: etree._Element, pivot: FilePivot, cache: _Cache) -> None:
    axis = {name.casefold(): "axisRow" for name in pivot.rows}
    axis.update({name.casefold(): "axisCol" for name in pivot.columns})
    axis.update({each.field.casefold(): "axisPage" for each in pivot.filters})
    kept = {each.field.casefold(): each.keep for each in pivot.filters}
    data = {value.field.casefold() for value in pivot.values}
    fields = _sub(root, "pivotFields", count=len(cache.fields))
    for each in cache.fields:
        key = each.name.casefold()
        element = _sub(fields, "pivotField", showAll="0")
        if key in axis:
            element.set("axis", axis[key])
            element.set("compact", "0")
            element.set("outline", "0")
            element.set("defaultSubtotal", "0")
            wanted = None if kept.get(key) is None else {_key(member) for member in kept[key] or ()}
            if wanted is not None and len(wanted) > 1:
                element.set("multipleItemSelectionAllowed", "1")
            items = _sub(element, "items", count=len(each.items))
            for position, value in enumerate(each.items):
                hidden = wanted is not None and len(wanted) > 1 and _key(value) not in wanted
                _sub(items, "item", **({"h": "1"} if hidden else {}), x=position)
        if key in data:
            element.set("dataField", "1")


def _page_item(each: PivotFilter, cache: _Cache) -> int:
    """The place of the one member a filter shows, among its field's items."""
    keep = cast("tuple[Value, ...]", each.keep)
    return cache.fields[cache.number(each.field)].index[_key(keep[0])]


def _fields(root: etree._Element, tag: str, numbers: list[int]) -> None:
    if numbers:
        holder = _sub(root, tag, count=len(numbers))
        for number in numbers:
            _sub(holder, "field", x=number)


def _lines(pivot: FilePivot, cache: _Cache, fields: tuple[str, ...], *, total: bool) -> list[tuple[str, int | None]]:
    """The lines of the table along one axis as ``rowItems`` and ``colItems`` list them: ``("", n)`` the nth item,
    ``("grand", 0)`` the line of totals; an axis with no field is one line with no item."""
    if not fields:
        return [("", None)]
    members = shown_members(pivot).get(fields[0].casefold(), [])
    count = len([value for value in members if _key(value) in cache.fields[cache.number(fields[0])].index])
    return [*(("", position) for position in range(count)), *([("grand", 0)] if total else [])]


def _items(root: etree._Element, tag: str, lines: list[tuple[str, int | None]]) -> None:
    holder = _sub(root, tag, count=len(lines))
    for kind, position in lines:
        line = _sub(holder, "i", **({"t": kind} if kind else {}))
        if position is not None:
            _sub(line, "x", **({"v": position} if position else {}))


def ask_refresh(patch: PackagePatch, package: Package) -> None:
    """Every pivot cache of the file asks to be read again when the file is opened: cells a pivot fills were edited,
    and the cache (and the table Excel keeps) must not show what they were."""
    for part in _cache_parts(package).values():
        if part in patch.parts:
            definition = parse_xml(patch.parts[part])
            definition.set("refreshOnLoad", "1")
            patch.parts[part] = serialized(definition)


# ------------------------------------------------------------------------------------------------ reading
@dataclass
class PivotsRead:
    """The pivots of a file the model can try to hold, and the loss of each it cannot."""

    found: list[FilePivot] = field(default_factory=list)
    losses: LossLog = field(default_factory=LossLog)


def read_pivots(package: Package, model: WorkbookModel) -> PivotsRead:
    """The pivot tables of ``package`` as :class:`FilePivot` (``model`` has its sheets and names, which the source of a
    cache may be); the ones the model cannot have are in ``losses`` under the detail that says why."""
    read = PivotsRead()
    caches = _cache_parts(package)
    slicers = _slicer_pivots(package)
    for sheet in package.sheets:
        for _, kind, part in relationships(package.parts, sheet.part):
            if not kind.endswith("/pivotTable") or part not in package.parts:
                continue
            table = parse_xml(package.parts[part])
            cache = next(
                (target for _, k, target in relationships(package.parts, part) if k.endswith("/pivotCacheDefinition")),
                None,
            )
            cache = cache or caches.get(table.get("cacheId", ""))
            reason = _refusal(package, table, cache, slicers)
            found = None if reason else _pivot(package, model, table, cast("str", cache), sheet.sheet_id)
            if reason or found is None:
                read.losses.add(PIVOT_LOSS, reason or "source")
            else:
                read.found.append(found)
    return read


def _cache_parts(package: Package) -> dict[str, str]:
    """The cache definition part of each ``cacheId`` the workbook names."""
    rids = {rid: target for rid, _, target in relationships(package.parts, "xl/workbook.xml")}
    return {
        cache.get("cacheId", ""): rids[cache.get(q("r", "id"), "")]
        for cache in package.workbook.iterfind("x:pivotCaches/x:pivotCache", NS)
        if cache.get(q("r", "id"), "") in rids
    }


def _slicer_pivots(package: Package) -> set[str]:
    """The names of the pivot tables a slicer of the file reads."""
    found: set[str] = set()
    for name, data in package.parts.items():
        if name.startswith("xl/slicerCaches/") and name.endswith(".xml"):
            found |= {
                each.get("name", "")
                for each in parse_xml(data).iter()
                if isinstance(each.tag, str) and etree.QName(each).localname == "pivotTable"
            }
    return found


def _refusal(package: Package, table: etree._Element, cache_part: str | None, slicers: set[str]) -> str | None:
    """Why the model cannot hold the pivot table ``table`` (a detail), or ``None``."""
    if cache_part is None or cache_part not in package.parts:
        return "source"
    cache = parse_xml(package.parts[cache_part])
    if table.get("name", "") in slicers:
        return "slicer"
    return _cache_refusal(cache) or _table_refusal(table) or _field_refusal(table)


def _cache_refusal(cache: etree._Element) -> str | None:
    """Why a cache is no range of this file, or has what the engine has no word for."""
    source = cache.find("x:cacheSource", NS)
    if source is None:
        return "source"
    if source.get("type") != "worksheet":
        return "data-model" if source.get("type") == "external" and source.get("connectionId") else "external-source"
    sheet_source = source.find("x:worksheetSource", NS)
    if sheet_source is None:
        return "source"
    if sheet_source.get(q("r", "id")):
        return "external-source"
    if any(isinstance(e.tag, str) and etree.QName(e).localname == "fieldGroup" for e in cache.iter()):
        return "grouping"
    if any(e.get("formula") for e in cache.iterfind("x:cacheFields/x:cacheField", NS)):
        return "calculated-field"
    return None


def _table_refusal(table: etree._Element) -> str | None:
    """What a table asks for that the engine cannot do: items made by formula, a chart, a value shown another way."""
    if table.find("x:calculatedItems", NS) is not None:
        return "calculated-field"
    if table.get("chartFormat", "0") not in ("", "0"):
        return "pivot-chart"
    for each in table.iterfind("x:dataFields/x:dataField", NS):
        if each.get("showDataAs", "normal") != "normal":
            return "show-as"
        if each.get("subtotal", "sum") not in _AGGREGATIONS:
            return "aggregation"
    return None


def _field_refusal(table: etree._Element) -> str | None:
    for each in table.iterfind("x:filters/x:filter", NS):
        return "top-n" if each.get("type") in _TOP_N else "hidden-items"
    for each in table.iterfind("x:pivotFields/x:pivotField", NS):
        if each.get("axis") in ("axisRow", "axisCol"):
            if any(item.get("h") == "1" for item in each.iterfind("x:items/x:item", NS)):
                return "hidden-items"
            if each.get("sortType", "manual") == _SORTED_DOWN:
                return "sort"
    return None


def _shared(cache: etree._Element) -> list[list[Value]]:
    """The listed values of each field of a cache."""
    out: list[list[Value]] = []
    for each in cache.iterfind("x:cacheFields/x:cacheField", NS):
        items: list[Value] = []
        for item in each.iterfind("x:sharedItems/*", NS):
            kind = etree.QName(item).localname
            value = item.get("v", "")
            if kind == "m":
                items.append(None)
            elif kind == "b":
                items.append(value in ("1", "true"))
            elif kind == "n":
                items.append(_as_number(value))
            elif kind == "e":
                items.append(ErrorValue(value))
            else:
                items.append(value)
        out.append(items)
    return out


def _as_number(text: str) -> int | float:
    value = float(text)
    return int(value) if value.is_integer() and not any(mark in text.lower() for mark in ".e") else value


def _pivot(
    package: Package, model: WorkbookModel, table: etree._Element, cache_part: str, home: SheetId
) -> FilePivot | None:
    cache = parse_xml(package.parts[cache_part])
    names = [each.get("name", "") for each in cache.iterfind("x:cacheFields/x:cacheField", NS)]
    shared = _shared(cache)
    source = _source_range(package, model, cache)
    location = table.find("x:location", NS)
    if source is None or location is None or not location.get("ref"):
        return None
    first_row, first_col, last_row, last_col = area(location.get("ref", ""))
    target = RangeRef.between(CellRef(first_row, first_col, home), CellRef(last_row, last_col, home))
    fields = table.findall("x:pivotFields/x:pivotField", NS)

    def listed(tag: str) -> list[int]:
        found = (int(each.get("x", "0")) for each in table.iterfind(f"x:{tag}/x:field", NS))
        return [index for index in found if 0 <= index < len(names)]

    filters = []
    for page in table.iterfind("x:pageFields/x:pageField", NS):
        index = int(page.get("fld", "0"))
        if index < len(names):
            filters.append(PivotFilter(names[index], _kept(fields[index], shared[index], page)))
    values = []
    for each in table.iterfind("x:dataFields/x:dataField", NS):
        index = int(each.get("fld", "0"))
        if index < len(names):
            aggregation = _AGGREGATIONS[each.get("subtotal", "sum")]
            title = each.get("name", "")
            values.append(
                ValueField(
                    names[index], aggregation, "" if title == PivotLabels().title(aggregation, names[index]) else title
                )
            )
    return FilePivot(
        table.get("name", ""),
        source,
        target,
        tuple(names[index] for index in listed("rowFields")),
        tuple(names[index] for index in listed("colFields")),
        tuple(values),
        tuple(filters),
        table.get("colGrandTotals", "1") != "0",
        table.get("rowGrandTotals", "1") != "0",
    )


def _kept(each: etree._Element, values: list[Value], page: etree._Element) -> tuple[Value, ...] | None:
    """The members a page field keeps: the one it is set to, or all but the hidden ones; ``None`` for all."""
    items = each.findall("x:items/x:item", NS)

    def value_of(item: etree._Element) -> Value:
        index = item.get("x")
        return values[int(index)] if index is not None and int(index) < len(values) else None

    chosen = page.get("item")
    if chosen is not None and int(chosen) < len(items):
        return (value_of(items[int(chosen)]),)
    shown = [item for item in items if item.get("t") is None and item.get("x") is not None]
    if not any(item.get("h") == "1" for item in shown):
        return None
    return tuple(value_of(item) for item in shown if item.get("h") != "1") or None


def _source_range(package: Package, model: WorkbookModel, cache: etree._Element) -> RangeRef | None:
    source = cache.find("x:cacheSource/x:worksheetSource", NS)
    assert source is not None
    if source.get("name"):
        named = model.names.get(key_of(None, source.get("name", "")))
        return None if named is None else named.range
    sheet = package.sheet_id(source.get("sheet", ""))
    if sheet is None or not source.get("ref"):
        return None
    first_row, first_col, last_row, last_col = area(source.get("ref", ""))
    return RangeRef.between(CellRef(first_row, first_col, sheet), CellRef(last_row, last_col, sheet))


__all__ = ["PivotsRead", "add_pivots", "ask_refresh", "has_room", "read_pivots", "shown_members", "written_pivots_of"]
