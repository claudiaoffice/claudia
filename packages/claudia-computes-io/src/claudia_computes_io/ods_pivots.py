"""Pivot tables in an ods file (E6.30, D625, D628): ``table:data-pilot-table`` and the :class:`FilePivot` it says.

A pivot table is a ``table:data-pilot-table`` in the ``table:data-pilot-tables`` that follows the sheets, the names and
the database ranges of ``office:spreadsheet``. It names its source (``table:source-cell-range``), the cells it fills
(``table:target-range-address``) and its fields: each ``table:data-pilot-field`` is a column of the source with an
``orientation`` -- ``row``, ``column``, ``page`` (a filter) or ``data`` (a value, with its ``function``). The cells it
fills are ordinary cells of the sheet; LibreOffice makes them again when the pivot is refreshed.

What the engine has no word for makes a pivot *unreadable* here (the cells then stay the cells they are, and the loss
is said by its detail): a source that is no range (``external-source``), a function it lacks (``aggregation``), a
member hidden in a row or column (``hidden-items``), and ``show-as``, ``grouping``, ``manual-sort`` and ``top-n``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from lxml import etree

from claudia_computes import Aggregation, PivotFilter, SheetId, ValueField, WorkbookModel
from claudia_computes.values import Value, format_value
from claudia_odf_io import NS, LossLog, qname
from claudia_odf_io import local_name as local_of

from .ods_names import SheetPlace, address_of, range_of
from .pivot_exchange import PIVOT_LOSS, FilePivot, source_table

_DECLARED = {prefix: uri for prefix, uri in NS.items() if prefix != "xml"}

#: The functions of ``table:function`` the engine has, by the aggregation it makes of them.
_FUNCTIONS = {
    "sum": Aggregation.SUM,
    "count": Aggregation.COUNT,
    "average": Aggregation.AVERAGE,
    "min": Aggregation.MIN,
    "max": Aggregation.MAX,
}
#: What a level of a field may hold that the engine cannot do, by the detail it is said under.
_UNSUPPORTED = {
    "data-pilot-field-reference": "show-as",
    "data-pilot-groups": "grouping",
    "data-pilot-display-info": "top-n",
}
_SOURCES = {"database-source-sql", "database-source-table", "database-source-query", "source-service"}


def _q(prefix: str, local: str) -> str:
    return qname(f"{prefix}:{local}")


def _get(element: etree._Element, name: str, default: str = "") -> str:
    return element.get(_q("table", name), default)


# ------------------------------------------------------------------------------------------------ writing
def data_pilot_tables(
    model: WorkbookModel, pivots: Sequence[FilePivot], sheets: Mapping[SheetId, str]
) -> etree._Element | None:
    """The ``table:data-pilot-tables`` that goes after the database ranges of a new file, or ``None`` with no pivot."""
    if not pivots:
        return None
    holder = etree.Element(_q("table", "data-pilot-tables"), nsmap=_DECLARED)
    holder.extend(_pilot(model, pivot, sheets) for pivot in pivots)
    return holder


def _pilot(model: WorkbookModel, pivot: FilePivot, sheets: Mapping[SheetId, str]) -> etree._Element:
    element = etree.Element(_q("table", "data-pilot-table"), nsmap=_DECLARED)
    for name, value in (
        ("name", pivot.name),
        ("application-data", ""),
        ("grand-total", _grand_total(pivot)),
        ("target-range-address", address_of(pivot.target, sheets, absolute=False)),
    ):
        element.set(_q("table", name), value)
    source = etree.SubElement(element, _q("table", "source-cell-range"))
    source.set(_q("table", "cell-range-address"), address_of(pivot.source, sheets, absolute=False))
    for name in pivot.rows:
        element.append(_field(name, "row"))
    for name in pivot.columns:
        element.append(_field(name, "column"))
    if len(pivot.values) > 1:  # (which value a cell of the grid is: a field of its own that sits with the columns)
        element.append(_field("Data", "column", layout=True))
    for each in pivot.filters:
        element.append(_field(each.field, "page", members=_filter_members(model, pivot, each)))
    for summed in pivot.values:
        element.append(_field(summed.field, "data", function=_function_name(summed.aggregation)))
    return element


def _grand_total(pivot: FilePivot) -> str:
    """``row`` is the row of grand totals at the bottom, ``column`` the column of them at the right (as LibreOffice
    shows them, which a file made by it settles)."""
    if pivot.total_row and pivot.total_column:
        return "both"
    if pivot.total_row:
        return "row"
    return "column" if pivot.total_column else "none"


def _function_name(aggregation: Aggregation) -> str:
    return next(name for name, each in _FUNCTIONS.items() if each is aggregation)


def _field(
    name: str,
    orientation: str,
    *,
    function: str = "auto",
    layout: bool = False,
    members: list[tuple[str, bool]] | None = None,
) -> etree._Element:
    element = etree.Element(_q("table", "data-pilot-field"), nsmap=_DECLARED)
    for key, value in (
        ("source-field-name", name),
        ("orientation", orientation),
        ("used-hierarchy", "-1"),
        ("function", function),
    ):
        element.set(_q("table", key), value)
    if layout:
        element.set(_q("table", "is-data-layout-field"), "true")
    level = etree.SubElement(element, _q("table", "data-pilot-level"))
    if members:
        holder = etree.SubElement(level, _q("table", "data-pilot-members"))
        for member, shown in members:
            item = etree.SubElement(holder, _q("table", "data-pilot-member"))
            item.set(_q("table", "name"), member)
            item.set(_q("table", "display"), "true" if shown else "false")
    return element


def _filter_members(model: WorkbookModel, pivot: FilePivot, each: PivotFilter) -> list[tuple[str, bool]] | None:
    """The members of a filter field, each with whether it stays: a pivot that keeps them all lists none."""
    if each.keep is None:
        return None
    header, rows = source_table(model, pivot.source)
    column = [name.casefold() for name in header].index(each.field.casefold())
    kept = {format_value(member) for member in each.keep}
    seen: dict[str, None] = {}
    for line in rows:
        if line[column] is not None:
            seen.setdefault(format_value(line[column]), None)
    return [(member, member in kept) for member in seen]


# ------------------------------------------------------------------------------------------------ reading
@dataclass
class PivotsRead:
    """The pivots of a file the model can try to hold, and the loss of each it cannot (``unread``)."""

    found: list[FilePivot] = field(default_factory=list)
    losses: LossLog = field(default_factory=LossLog)


def read_pivots(spreadsheet: etree._Element, sheets: Sequence[SheetPlace]) -> PivotsRead:
    """The ``table:data-pilot-table`` elements of ``spreadsheet`` as :class:`FilePivot`; the ones the model cannot have
    are in ``losses`` under the detail that says why."""
    ids = {place.name: place.id for place in sheets}.get
    read = PivotsRead()
    for element in spreadsheet.iterfind("table:data-pilot-tables/table:data-pilot-table", NS):
        refusal = _refusal(element)
        found = None if refusal else _pivot(element, ids)
        if refusal or found is None:
            read.losses.add(PIVOT_LOSS, refusal or "source")
        else:
            read.found.append(found)
    return read


def _refusal(element: etree._Element) -> str | None:
    """Why the model cannot hold ``element`` (a detail), or ``None``."""
    if any(local_of(child.tag) in _SOURCES for child in element if isinstance(child.tag, str)):
        return "external-source"
    if element.find("table:source-cell-range", NS) is None:
        return "source"
    for level in element.iterfind("table:data-pilot-field/table:data-pilot-level", NS):
        for child in level.iter():
            name = local_of(child.tag) if isinstance(child.tag, str) else ""
            if name in _UNSUPPORTED:
                return _UNSUPPORTED[name]
            if name == "data-pilot-sort-info" and child.get(_q("table", "sort-mode")) not in (None, "name"):
                return "manual-sort"
    for each in element.iterfind("table:data-pilot-field", NS):
        orientation = _get(each, "orientation")
        if orientation == "data" and _get(each, "function", "auto") not in _FUNCTIONS:
            return "aggregation"
        if orientation in ("row", "column") and _hidden(each):
            return "hidden-items"
    return None


def _listed(each: etree._Element) -> list[tuple[str, bool]]:
    return [
        (_get(member, "name"), _get(member, "display", "true") != "false")
        for member in each.iterfind("table:data-pilot-level/table:data-pilot-members/table:data-pilot-member", NS)
    ]


def _hidden(each: etree._Element) -> bool:
    return any(not shown for _, shown in _listed(each))


def _pivot(element: etree._Element, ids) -> FilePivot | None:  # noqa: ANN001 (the sheet-id lookup of ods_names)
    source = range_of(element.find("table:source-cell-range", NS).get(_q("table", "cell-range-address"), ""), ids)  # type: ignore[union-attr]
    target = range_of(_get(element, "target-range-address"), ids)
    if source is None or target is None:
        return None
    rows, columns, filters, values = [], [], [], []
    for each in element.iterfind("table:data-pilot-field", NS):
        name, orientation = _get(each, "source-field-name"), _get(each, "orientation")
        if _get(each, "is-data-layout-field") == "true":
            continue  # (it says which value a column is; the engine puts the values under the column field)
        if orientation == "row":
            rows.append(name)
        elif orientation == "column":
            columns.append(name)
        elif orientation == "page":
            filters.append(PivotFilter(name, _kept(each)))
        elif orientation == "data":
            values.append(ValueField(name, _FUNCTIONS[_get(each, "function")]))
    both = _get(element, "grand-total", "both")
    return FilePivot(
        _get(element, "name"),
        source,
        target,
        tuple(rows),
        tuple(columns),
        tuple(values),
        tuple(filters),
        both in ("both", "row"),
        both in ("both", "column"),
    )


def _kept(each: etree._Element) -> tuple[Value, ...] | None:
    """The members a filter field keeps: those not hidden (or the one page it is set to), ``None`` for all."""
    selected = _get(each, "selected-page")
    members = _listed(each)
    if selected:
        return (selected,)
    if all(shown for _, shown in members):
        return None
    return tuple(name for name, shown in members if shown) or None


__all__ = ["PivotsRead", "data_pilot_tables", "read_pivots"]
