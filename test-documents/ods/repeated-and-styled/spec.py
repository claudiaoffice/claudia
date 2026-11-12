"""The worst case for an ods edit, hand-built (``_build_fixtures.py``): a repeated run of identical rows
(``table:number-rows-repeated``), a merged title, a styled header, a cell with a comment, a date, a formula with
a union that has no Excel counterpart, an error cell, a thousand trailing empty rows, a named range and data
validations. The edit changes a value inside the repeated run (the run is split), another value that two
formulas depend on (their cached values refresh) and adds a cell on the second sheet. Everything it did not
touch is byte for byte what it was (D413)."""

from __future__ import annotations

from claudia_computes import SheetId, WorkbookModel
from claudia_opc_io import read_parts
from claudia_test_documents.case import Case

BUDGET = SheetId("s1")
NOTES = SheetId("s2")


def import_checks(model: WorkbookModel) -> None:
    assert [sheet.name for sheet in model.sheets.values()] == ["Budget", "Notes"]
    cells = model.sheets[BUDGET].cells
    assert cells[(2, 3)] == {"t": "formula", "v": "=SUM(B3:C3)"}
    assert [cells[(row, 0)]["v"] for row in (3, 4, 5)] == ["Reserve"] * 3  # the repeated run, one cell per row
    assert cells[(7, 1)] == {"t": "int", "v": 46387}  # the date, as an Excel serial
    assert cells[(8, 1)] == {
        "t": "int",
        "v": 1150,
    }  # the union formula arrives as its cached value; no edit touches the cells it adds up
    assert model.value(BUDGET, 6, 3) == 2300
    assert model.sheets[NOTES].cells[(0, 0)] == {"t": "text", "v": "Amounts in euros."}


def modify(model: WorkbookModel) -> WorkbookModel:
    budget = model.sheets[BUDGET]
    model.store(budget, 2, 1, {"t": "int", "v": 1200})  # Rent in Q1: D3 = 2200, B7 = 1350 ...
    model.store(budget, 4, 1, {"t": "int", "v": 75})  # the middle row of the repeated run
    model.store(model.sheets[NOTES], 1, 0, {"t": "text", "v": "Added by Claudia"})
    return model


def after_checks(model: WorkbookModel) -> None:
    budget = model.sheets[BUDGET]
    assert budget.cells[(2, 1)] == {"t": "int", "v": 1200}
    assert [budget.cells[(row, 1)]["v"] for row in (3, 4, 5)] == [50, 75, 50]
    assert model.value(BUDGET, 2, 3) == 2200
    assert model.value(BUDGET, 6, 1) == 1375
    assert model.value(BUDGET, 6, 3) == 2525
    assert model.sheets[NOTES].cells[(1, 0)] == {"t": "text", "v": "Added by Claudia"}


def everything_else_is_untouched(original: bytes, edited: bytes) -> None:
    before = read_parts(original)["content.xml"].decode()
    after = read_parts(edited)["content.xml"].decode()
    for kept in (
        "<table:named-expressions>",
        "<table:content-validations>",
        'number-rows-repeated="1000"',
        "table:number-columns-spanned=",
        "<office:annotation",
        "of:=1/0",
        "<office:automatic-styles>",
    ):
        assert (kept in before) == (kept in after), kept
    assert "Added by Claudia" in after


CASE = Case(
    import_checks=import_checks,
    modify=modify,
    after_checks=after_checks,
    preserve_parts=["styles.xml", "META-INF/manifest.xml"],
    preserve_elements=everything_else_is_untouched,
)
