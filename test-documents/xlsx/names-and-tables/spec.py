"""A table with a style, a named cell that a formula uses, a name that is a formula, a print area and a name of one
sheet (written the way Excel lays them out). The model has the cell, the table and the names it can hold, and the
formula that uses them calculates. A name and a row of the table made in Claudia are patched into the file; the table
keeps its style, and the name that is a formula and the print area stay (D457)."""

from __future__ import annotations

from claudia_computes import CellRef, NamedRange, RangeRef, SheetId, WorkbookModel
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case

SALES, PLAN = SheetId("s1"), SheetId("s2")


def import_checks(model: WorkbookModel) -> None:
    assert {named.name for named in model.names} == {"Rate", "Orders", "Local"}
    assert model.names.get((None, "orders")).header
    assert model.names.get((PLAN, "local")).range.sheet == PLAN
    assert model.sheets[SALES].cells[(1, 4)] == {"t": "formula", "v": "=Rate*SUM(Orders[Amount])"}
    assert model.value(SALES, 1, 4) == 86


def modify(model: WorkbookModel) -> WorkbookModel:
    sales = model.sheets[SALES]
    model.store(sales, 4, 0, {"t": "text", "v": "West"})
    model.store(sales, 4, 1, {"t": "int", "v": 70})
    orders = model.names.get((None, "orders"))
    grown = RangeRef(orders.range.first, CellRef(4, 1, SALES))
    model.names.put(NamedRange("Orders", None, grown, header=True))
    model.names.put(NamedRange("Top", None, RangeRef(CellRef(0, 1, SALES), CellRef(0, 1, SALES))))
    return model


def after_checks(model: WorkbookModel) -> None:
    assert model.names.get((None, "orders")).range.last.row == 4
    assert model.names.get((None, "top")) is not None
    assert model.value(SALES, 1, 4) == 100


def names_stay(original: bytes, edited: bytes) -> None:
    before, after = read_parts(original), read_parts(edited)
    workbook = after["xl/workbook.xml"].decode()
    for kept in ('name="Twice"', 'name="_xlnm.Print_Area"', 'name="Rate"', 'name="Local"', 'name="Top"'):
        assert kept in workbook
    table = after["xl/tables/table1.xml"].decode()
    assert 'ref="A1:B5"' in table and "TableStyleMedium2" in table
    assert before["xl/tables/table1.xml"].decode().count("TableStyleMedium2") == 1


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_elements=names_stay,
)
