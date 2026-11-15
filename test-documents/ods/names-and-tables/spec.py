"""A named range of the workbook, a name of one sheet at the end of its table, a database range that is a table, a name
that is an expression and a formula that uses a name, laid out the way LibreOffice does. The model has the names it can
hold and the formula stays a formula; a name made in Claudia is added to the file's own ``table:named-expressions``, and
the name that is an expression stays (D457)."""

from __future__ import annotations

from claudia_computes import CellRef, NamedRange, RangeRef, SheetId, WorkbookModel
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case

SALES = SheetId("s1")


def import_checks(model: WorkbookModel) -> None:
    assert {named.name for named in model.names} == {"Rate", "Mine", "Orders"}
    assert model.names.get((SALES, "mine")).range.first == CellRef(1, 1, SALES)
    assert model.names.get((None, "orders")).header
    assert model.sheets[SALES].cells[(1, 3)] == {"t": "formula", "v": "=D1*B2"}
    assert model.value(SALES, 1, 3) == 20


def modify(model: WorkbookModel) -> WorkbookModel:
    model.store(model.sheets[SALES], 1, 1, {"t": "int", "v": 150})
    model.names.put(NamedRange("Limit", None, RangeRef(CellRef(2, 1, SALES), CellRef(2, 1, SALES))))
    return model


def after_checks(model: WorkbookModel) -> None:
    assert {named.name for named in model.names} == {"Rate", "Mine", "Orders", "Limit"}
    assert model.value(SALES, 1, 3) == 30


def names_stay(original: bytes, edited: bytes) -> None:
    content = read_parts(edited)["content.xml"].decode()
    assert 'table:name="Pi"' in content, "the name that is an expression stays"
    assert 'table:name="Limit"' in content and content.count("<table:named-expressions>") == 2
    assert 'table:target-range-address="Sales.A1:Sales.B3"' in content


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["styles.xml", "META-INF/manifest.xml"],
    preserve_elements=names_stay,
)
