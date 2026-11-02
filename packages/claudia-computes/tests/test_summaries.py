"""The history panel's sentences and the cell contents that travel with change events."""

from claudia_computes import AddSheet, RemoveSheet, SetCells, Structure
from claudia_computes.model import content_of
from claudia_computes.refs import DeleteCols, InsertRows

S1 = "s1"


def cells(*items):
    return SetCells(S1, tuple((r, c, content_of(v)) for r, c, v in items))


def test_one_cell_reads_like_a_formula_bar():
    assert cells((2, 1, 40)).summary == "B3 = 40"
    assert cells((0, 0, "Revenue")).summary == "A1 = Revenue"
    assert cells((0, 0, 3.5)).summary == "A1 = 3.5"
    assert cells((0, 0, True)).summary == "A1 = TRUE"
    assert cells((4, 27, None)).summary == "AB5 cleared"


def test_long_text_is_cut_short():
    text = "x" * 80
    assert cells((0, 0, text)).summary == f"A1 = {'x' * 29}…"


def test_a_few_cells_are_listed():
    assert cells((0, 0, "Item"), (0, 1, "Amount")).summary == "A1 = Item, B1 = Amount"
    assert cells((0, 0, 5), (0, 1, None), (0, 2, 7)).summary == "A1 = 5, B1 cleared, C1 = 7"


def test_many_cells_are_named_by_their_area():
    assert cells((0, 0, 1), (0, 1, 2), (1, 0, 3), (1, 1, 4)).summary == "4 cells in A1:B2"
    assert cells((0, 0, "x" * 30), (0, 1, "y" * 30), (0, 2, "z" * 30)).summary == "3 cells in A1:C1"
    assert cells((0, 0, None), (0, 1, None)).summary == "cleared 2 cells in A1:B1"


def test_structure_and_sheets():
    assert Structure(InsertRows(S1, 4, 2)).summary == "insert 2 rows before row 5"
    assert Structure(InsertRows(S1, 0, 1)).summary == "insert 1 row before row 1"
    assert Structure(DeleteCols(S1, 1, 1)).summary == "delete column B"
    assert Structure(DeleteCols(S1, 1, 3)).summary == "delete columns B:D"
    assert AddSheet(S1, "Budget").summary == "add sheet Budget"
    assert RemoveSheet(S1).summary == "remove a sheet"


def test_the_change_event_carries_the_new_contents(doc):
    seen = []
    doc.subscribe(lambda event: seen.append(event.to_data()) if event.to_data()["type"] == "cells" else None)
    doc.execute(cells((1, 2, 5), (3, 0, "hi")), author="ana")
    (data,) = seen
    assert data["sheet"] == S1
    assert data["cells"] == [[1, 2, {"t": "int", "v": 5}], [3, 0, {"t": "text", "v": "hi"}]]


def test_cleared_cells_arrive_as_empty(doc):
    doc.execute(cells((0, 0, 1)), author="ana")
    seen = []
    doc.subscribe(lambda event: seen.append(event.to_data()) if event.to_data()["type"] == "cells" else None)
    doc.execute(cells((0, 0, None)), author="ana")
    assert seen[0]["cells"] == [[0, 0, None]]
