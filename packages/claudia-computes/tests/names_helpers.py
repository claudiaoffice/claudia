"""Helpers the tests of names, tables and SQL() share: typing into cells by address, reading what they show."""

from __future__ import annotations

from conftest import S1

from claudia_computes import DefineName, NamedRange, SetCells, parse_input
from claudia_computes.refs import SheetId, parse_cell_ref, parse_range_ref
from claudia_computes.values import ErrorValue

S2 = "s2"


def at(address):
    ref = parse_cell_ref(address)
    return ref.row, ref.col


def fill(doc, cells: dict, *, sheet=S1):
    items = tuple((*at(address), parse_input(str(text))) for address, text in cells.items())
    return doc.execute(SetCells(sheet, items), author="ana")


def shown(doc, address, sheet=S1):
    row, col = at(address)
    return doc.model.value(sheet, row, col)


def code(doc, address, sheet=S1):
    value = shown(doc, address, sheet)
    assert isinstance(value, ErrorValue), f"{address} shows {value!r}"
    return value.code


def name(text, area, *, sheet=S1, scope=None, **fields) -> NamedRange:
    return NamedRange(text, scope, parse_range_ref(area).resolved(SheetId(sheet)), **fields)


def define(doc, text, area, *, sheet=S1, scope=None, **fields):
    return doc.execute(DefineName(name(text, area, sheet=sheet, scope=scope, **fields)), author="ana")


def region_of(doc, text, scope=None):
    named = doc.model.names.get((scope, text.casefold()))
    assert named is not None, f"no name {text}"
    assert named.range is not None
    return named.range.to_a1(lambda sheet_id: doc.model.sheet_name_of(sheet_id))


SALES = {
    "A1": "Region",
    "B1": "Units",
    "C1": "Unit price",
    "D1": "Amount",
    "A2": "North",
    "B2": 10,
    "C2": 2.5,
    "D2": "=B2*C2",
    "A3": "South",
    "B3": 4,
    "C3": 10,
    "D3": "=B3*C3",
    "A4": "East",
    "B4": 6,
    "C4": 5,
    "D4": "=B4*C4",
}
